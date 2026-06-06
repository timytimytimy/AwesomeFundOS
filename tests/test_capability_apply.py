import json
import tempfile
import unittest
from pathlib import Path

import yaml

from fundos.capability_apply import apply_approved_capability, list_pending_capabilities
from fundos.capabilities import append_jsonl


class CapabilityApplyTests(unittest.TestCase):
    def test_list_pending_capabilities_reads_agent_capability_registry(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            registry = root / "memory" / "agents" / "fund_manager" / "capabilities" / "workflow.jsonl"
            append_jsonl(registry, [
                {
                    "candidate_id": "cand_apply_001",
                    "target_agent": "fund_manager",
                    "capability_kind": "workflow",
                    "application_status": "pending_human_apply",
                    "proposal": "最终结论前检查 Tool Harness。",
                    "required_tests": ["agent_harness", "tool_harness"],
                    "controls": ["no_direct_profile_mutation", "no_real_trade_action"],
                },
                {
                    "candidate_id": "cand_already_applied",
                    "target_agent": "fund_manager",
                    "capability_kind": "workflow",
                    "application_status": "applied",
                    "proposal": "已经应用。",
                },
            ])

            pending = list_pending_capabilities(root)

            self.assertEqual([row["candidate_id"] for row in pending], ["cand_apply_001"])
            self.assertEqual(pending[0]["registry_path"], "memory/agents/fund_manager/capabilities/workflow.jsonl")

    def test_apply_approved_skill_candidate_appends_managed_section_without_mutating_agent_card(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            skill_path = root / "skills" / "swing_trader" / "SKILL.md"
            agent_card = root / "agents" / "swing_trader" / "agent.md"
            skill_path.parent.mkdir(parents=True)
            agent_card.parent.mkdir(parents=True)
            original_skill = "# Swing Trader Skill\n\n## Existing Rules\n\n- Keep old rule.\n"
            original_card = "# Swing Trader Agent\n\nCore profile.\n"
            skill_path.write_text(original_skill, encoding="utf-8")
            agent_card.write_text(original_card, encoding="utf-8")
            registry = root / "memory" / "agents" / "swing_trader" / "capabilities" / "skill.jsonl"
            append_jsonl(registry, [
                {
                    "candidate_id": "cand_skill_apply",
                    "run_id": "run-apply",
                    "source_agent": "learning_curator",
                    "target_agent": "swing_trader",
                    "capability_kind": "skill",
                    "candidate_type": "skill_update",
                    "target_scope": "skill",
                    "application_status": "pending_human_apply",
                    "regression_status": "passed",
                    "proposal": "事件催化后必须等待量价确认，并回链一手公告。",
                    "required_tests": ["historical_case_replay", "role_drift_check"],
                    "controls": ["no_direct_profile_mutation", "no_real_trade_action"],
                }
            ])

            result = apply_approved_capability(root, "cand_skill_apply", approver="human-test")

            updated_skill = skill_path.read_text(encoding="utf-8")
            self.assertEqual(result["application_status"], "applied")
            self.assertEqual(result["target_path"], "skills/swing_trader/SKILL.md")
            self.assertIn("<!-- FUNDOS_CAPABILITY:cand_skill_apply START -->", updated_skill)
            self.assertIn("事件催化后必须等待量价确认", updated_skill)
            self.assertEqual(agent_card.read_text(encoding="utf-8"), original_card)
            rows = [json.loads(line) for line in registry.read_text().splitlines() if line.strip()]
            self.assertEqual(rows[0]["application_status"], "applied")
            self.assertTrue(rows[0]["applied_ref"]["reversible"])
            ledger = root / "memory" / "organization" / "capability-apply-ledger.jsonl"
            self.assertTrue(ledger.exists())
            ledger_row = json.loads(ledger.read_text().splitlines()[0])
            self.assertFalse(ledger_row["mutated_agent_card"])
            self.assertFalse(ledger_row["real_trade_allowed"])

    def test_apply_approved_principle_candidate_writes_managed_runtime_policy(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            policy = root / "agents" / "fund_manager" / "applied-capabilities.yaml"
            registry = root / "memory" / "agents" / "fund_manager" / "capabilities" / "principle.jsonl"
            append_jsonl(registry, [
                {
                    "candidate_id": "cand_principle_apply",
                    "run_id": "run-apply",
                    "source_agent": "learning_curator",
                    "target_agent": "fund_manager",
                    "capability_kind": "principle",
                    "candidate_type": "principle_update",
                    "target_scope": "principle",
                    "application_status": "pending_human_apply",
                    "regression_status": "passed",
                    "proposal": "方法论源只能生成研究问题，不能替代一手事实。",
                    "required_tests": ["evidence_quality_check"],
                    "controls": ["no_direct_profile_mutation", "no_real_trade_action"],
                }
            ])

            result = apply_approved_capability(root, "cand_principle_apply", approver="human-test")

            self.assertEqual(result["target_path"], "agents/fund_manager/applied-capabilities.yaml")
            doc = yaml.safe_load(policy.read_text(encoding="utf-8"))
            self.assertEqual(doc["agent_id"], "fund_manager")
            self.assertEqual(doc["applied_capabilities"][0]["candidate_id"], "cand_principle_apply")
            self.assertEqual(doc["applied_capabilities"][0]["capability_kind"], "principle")
            self.assertFalse(doc["applied_capabilities"][0]["mutated_core_profile"])

    def test_apply_rejects_candidates_without_human_approval_flag(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            registry = root / "memory" / "agents" / "fund_manager" / "capabilities" / "workflow.jsonl"
            append_jsonl(registry, [{"candidate_id": "cand_needs_approval", "target_agent": "fund_manager", "capability_kind": "workflow", "application_status": "pending_human_apply", "proposal": "test"}])

            with self.assertRaises(PermissionError):
                apply_approved_capability(root, "cand_needs_approval", approver="")

    def test_apply_rejects_candidate_blocked_by_regression_harness(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            registry = root / "memory" / "agents" / "fund_manager" / "capabilities" / "workflow.jsonl"
            append_jsonl(registry, [{"candidate_id": "cand_blocked_regression", "target_agent": "fund_manager", "capability_kind": "workflow", "application_status": "blocked_regression", "proposal": "test"}])

            with self.assertRaises(ValueError):
                apply_approved_capability(root, "cand_blocked_regression", approver="human-test")


if __name__ == "__main__":
    unittest.main()

class CapabilityApprovalWorkflowTests(unittest.TestCase):
    def test_list_pending_capabilities_exposes_approval_route_regression_and_risk_flags(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            registry = root / "memory" / "agents" / "position_trend_trader" / "capabilities" / "workflow.jsonl"
            append_jsonl(registry, [
                {
                    "candidate_id": "cand_route_pending",
                    "target_agent": "position_trend_trader",
                    "capability_kind": "workflow",
                    "candidate_type": "workflow_update",
                    "target_scope": "workflow",
                    "application_status": "pending_human_apply",
                    "regression_status": "passed",
                    "adoption_route": "managed_capability_pending_human_apply",
                    "memory_write_policy": "no_direct_memory_write",
                    "human_approval_required": True,
                    "protected_mutation_allowed": False,
                    "proposal": "missing tools require confidence cap",
                    "required_tests": ["historical_case_replay"],
                    "controls": ["no_direct_profile_mutation", "no_real_trade_action"],
                    "real_trade_allowed": False,
                    "broker_integration": "disabled",
                }
            ])

            pending = list_pending_capabilities(root)

            self.assertEqual(len(pending), 1)
            row = pending[0]
            self.assertEqual(row["candidate_id"], "cand_route_pending")
            self.assertEqual(row["adoption_route"], "managed_capability_pending_human_apply")
            self.assertEqual(row["regression_status"], "passed")
            self.assertEqual(row["memory_write_policy"], "no_direct_memory_write")
            self.assertTrue(row["human_approval_required"])
            self.assertEqual(row["risk_flags"], [])
            self.assertTrue(row["ready_for_apply"])

    def test_apply_rejects_pending_candidate_without_passed_regression(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            registry = root / "memory" / "agents" / "fund_manager" / "capabilities" / "workflow.jsonl"
            append_jsonl(registry, [
                {
                    "candidate_id": "cand_missing_regression",
                    "target_agent": "fund_manager",
                    "capability_kind": "workflow",
                    "candidate_type": "workflow_update",
                    "target_scope": "workflow",
                    "application_status": "pending_human_apply",
                    "proposal": "test",
                    "controls": ["no_direct_profile_mutation", "no_real_trade_action"],
                    "adoption_route": "managed_capability_pending_human_apply",
                    "real_trade_allowed": False,
                    "broker_integration": "disabled",
                }
            ])

            with self.assertRaises(ValueError) as ctx:
                apply_approved_capability(root, "cand_missing_regression", approver="human-test")

            self.assertIn("regression_status must be passed", str(ctx.exception))

    def test_apply_rejects_forbidden_or_unsafe_route_even_with_human_approver(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            registry = root / "memory" / "agents" / "fund_manager" / "capabilities" / "workflow.jsonl"
            append_jsonl(registry, [
                {
                    "candidate_id": "cand_forbidden_route",
                    "target_agent": "fund_manager",
                    "capability_kind": "workflow",
                    "candidate_type": "tool_permission_update",
                    "target_scope": "tool_permission",
                    "application_status": "pending_human_apply",
                    "regression_status": "passed",
                    "proposal": "grant tool permission",
                    "controls": ["no_direct_profile_mutation", "no_real_trade_action"],
                    "adoption_route": "forbidden_protected_mutation",
                    "protected_mutation_allowed": False,
                    "real_trade_allowed": False,
                    "broker_integration": "disabled",
                }
            ])

            with self.assertRaises(ValueError) as ctx:
                apply_approved_capability(root, "cand_forbidden_route", approver="human-test")

            self.assertIn("adoption route is not applyable", str(ctx.exception))

    def test_apply_ledger_records_approval_snapshot_and_route(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            registry = root / "memory" / "agents" / "swing_trader" / "capabilities" / "skill.jsonl"
            append_jsonl(registry, [
                {
                    "candidate_id": "cand_skill_route_apply",
                    "run_id": "run-approve",
                    "source_agent": "evaluation_harness",
                    "target_agent": "swing_trader",
                    "capability_kind": "skill",
                    "candidate_type": "skill_update",
                    "target_scope": "skill",
                    "application_status": "pending_human_apply",
                    "regression_status": "passed",
                    "proposal": "append only managed skill section",
                    "required_tests": ["role_drift_check"],
                    "controls": ["no_direct_profile_mutation", "no_real_trade_action"],
                    "adoption_route": "skill_patch_pending_human_apply",
                    "memory_write_policy": "no_direct_memory_write",
                    "human_approval_required": True,
                    "protected_mutation_allowed": False,
                    "real_trade_allowed": False,
                    "broker_integration": "disabled",
                }
            ])

            result = apply_approved_capability(root, "cand_skill_route_apply", approver="human-test")

            self.assertEqual(result["approval_snapshot"]["approver"], "human-test")
            self.assertEqual(result["approval_snapshot"]["adoption_route"], "skill_patch_pending_human_apply")
            ledger_row = json.loads((root / "memory/organization/capability-apply-ledger.jsonl").read_text().splitlines()[0])
            self.assertEqual(ledger_row["adoption_route"], "skill_patch_pending_human_apply")
            self.assertEqual(ledger_row["memory_write_policy"], "no_direct_memory_write")
            self.assertTrue(ledger_row["human_approval_required"])
            self.assertFalse(ledger_row["protected_mutation_allowed"])

    def test_apply_ledger_preserves_candidate_audit_fields_and_safety_snapshot(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            registry = root / "memory" / "agents" / "fund_manager" / "capabilities" / "workflow.jsonl"
            append_jsonl(registry, [
                {
                    "candidate_id": "cand_workflow_audit_apply",
                    "run_id": "run-audit-apply",
                    "source_agent": "learning_curator",
                    "target_agent": "fund_manager",
                    "capability_kind": "workflow",
                    "candidate_type": "workflow_update",
                    "target_scope": "workflow",
                    "application_status": "pending_human_apply",
                    "regression_status": "passed",
                    "proposal": "Before committee memo, require explicit policy contract and evidence-quality checks.",
                    "source_basis": [
                        {"evidence_id": "E001", "source_tier": "tier_1_primary_fact"},
                        {"source_id": "serenity_aleabitoreddit", "source_tier": "tier_3_verified_public_practitioner", "usage": "hypothesis_only"},
                    ],
                    "required_tests": ["historical_case_replay", "role_drift_check", "evidence_quality_check"],
                    "scores": {"source_quality": 0.82, "role_fit": 0.91},
                    "controls": ["no_direct_profile_mutation", "no_real_trade_action", "broker_integration_disabled"],
                    "adoption_route": "managed_capability_pending_human_apply",
                    "memory_write_policy": "no_direct_memory_write",
                    "human_approval_required": True,
                    "protected_mutation_allowed": False,
                    "reversible": True,
                    "real_trade_allowed": False,
                    "broker_integration": "disabled",
                }
            ])

            result = apply_approved_capability(root, "cand_workflow_audit_apply", approver="human-test")

            self.assertEqual(result["candidate_type"], "workflow_update")
            self.assertEqual(result["target_scope"], "workflow")
            self.assertEqual(result["source_basis"][0]["evidence_id"], "E001")
            self.assertEqual(result["scores"]["role_fit"], 0.91)
            self.assertTrue(result["reversible"])
            self.assertFalse(result["real_trade_allowed"])
            self.assertEqual(result["broker_integration"], "disabled")
            registry_rows = [json.loads(line) for line in registry.read_text().splitlines() if line.strip()]
            applied_ref = registry_rows[0]["applied_ref"]
            self.assertEqual(applied_ref["candidate_type"], "workflow_update")
            self.assertEqual(applied_ref["target_scope"], "workflow")
            self.assertEqual(applied_ref["source_basis"][1]["usage"], "hypothesis_only")
            self.assertEqual(applied_ref["scores"]["source_quality"], 0.82)
            self.assertFalse(applied_ref["mutated_agent_card"])
            self.assertFalse(applied_ref["real_trade_allowed"])
            ledger_row = json.loads((root / "memory/organization/capability-apply-ledger.jsonl").read_text().splitlines()[0])
            for field in [
                "candidate_type",
                "target_scope",
                "source_basis",
                "scores",
                "capability_kind",
                "reversible",
                "mutated_agent_card",
                "mutated_runtime_skill",
                "real_trade_allowed",
                "broker_integration",
            ]:
                self.assertIn(field, ledger_row)
            self.assertEqual(ledger_row["candidate_type"], "workflow_update")
            self.assertEqual(ledger_row["target_scope"], "workflow")
            self.assertEqual(ledger_row["source_basis"][0]["source_tier"], "tier_1_primary_fact")
            self.assertEqual(ledger_row["scores"], {"source_quality": 0.82, "role_fit": 0.91})
            self.assertTrue(ledger_row["reversible"])
            self.assertFalse(ledger_row["mutated_agent_card"])
            self.assertFalse(ledger_row["mutated_runtime_skill"])
            self.assertFalse(ledger_row["real_trade_allowed"])
            self.assertEqual(ledger_row["broker_integration"], "disabled")
