import tempfile
import unittest
from pathlib import Path

import yaml

from fundos.agent_harness import evaluate_agent
from fundos.agent_outputs import make_structured_agent_output
from fundos.context import make_context_pack
from fundos.evidence import make_evidence_pack
from fundos.io import REPO_ROOT, read_yaml


class MemoryPolicyTests(unittest.TestCase):
    def test_each_default_agent_has_source_controlled_memory_policy(self):
        roster = read_yaml(REPO_ROOT / "specs" / "agents" / "default-roster.yaml")
        required_keys = [
            "version",
            "agent_id",
            "role",
            "memory_policy_id",
            "read_namespaces",
            "write_namespaces",
            "retrieval_contract",
            "writeback_rules",
            "forbidden_memory_writes",
            "staleness_policy",
            "context_compression",
            "personality_stability_guards",
            "harness_checks",
            "real_trade_allowed",
            "broker_integration",
        ]
        for agent in roster["agents"]:
            aid = agent["id"]
            with self.subTest(agent_id=aid):
                path = REPO_ROOT / "specs" / "agents" / "memory-policies" / f"{aid}.yaml"
                self.assertTrue(path.exists(), path)
                policy = read_yaml(path)
                for key in required_keys:
                    self.assertIn(key, policy)
                self.assertEqual(policy["agent_id"], aid)
                self.assertEqual(policy["role"], agent["role"])
                self.assertIn(f"memory/agents/{aid}", policy["read_namespaces"])
                self.assertIn(f"memory/agents/{aid}", policy["write_namespaces"])
                self.assertTrue(policy["retrieval_contract"]["max_memory_items"] >= 1)
                self.assertTrue(policy["writeback_rules"]["requires_evolution_gate"])
                self.assertIn("core_profile", policy["forbidden_memory_writes"])
                self.assertIn("tool_permissions", policy["forbidden_memory_writes"])
                self.assertIn("memory_policy_loaded", policy["harness_checks"])
                self.assertFalse(policy["real_trade_allowed"])
                self.assertFalse(policy["broker_integration"])

    def test_context_pack_embeds_memory_policy_and_retrieval_contract(self):
        roster = read_yaml(REPO_ROOT / "specs" / "agents" / "default-roster.yaml")
        agent = next(item for item in roster["agents"] if item["id"] == "risk_manager")
        pack = make_evidence_pack("memory-policy-run", "topic", "机器人产业链投资机会")

        context = make_context_pack("memory-policy-run", agent, pack)

        self.assertIn("memory_policy", context)
        self.assertEqual(context["memory_policy"]["source_path"], "specs/agents/memory-policies/risk_manager.yaml")
        self.assertIn("memory/agents/risk_manager", context["memory_policy"]["read_namespaces"])
        self.assertIn("retrieval_contract", context["memory_policy"])
        self.assertIn("memory_policy_loaded", context["memory_quality_controls"])
        self.assertEqual(context["memory_retrieval_contract"]["max_memory_items"], context["memory_policy"]["retrieval_contract"]["max_memory_items"])
        self.assertFalse(context["memory_policy"]["real_trade_allowed"])
        self.assertFalse(context["memory_policy"]["broker_integration"])

    def test_agent_output_reports_memory_policy_checks(self):
        roster = read_yaml(REPO_ROOT / "specs" / "agents" / "default-roster.yaml")
        agent = next(item for item in roster["agents"] if item["id"] == "tech_growth_analyst")
        pack = make_evidence_pack("memory-output-run", "topic", "机器人产业链投资机会")
        context = make_context_pack("memory-output-run", agent, pack)

        output = make_structured_agent_output(agent, context, pack, "机器人产业链投资机会")

        for key in [
            "memory_policy",
            "memory_namespaces",
            "memory_retrieval_contract",
            "memory_writeback_rules",
            "memory_permission_checks",
            "forbidden_memory_writes",
        ]:
            self.assertIn(key, output)
        self.assertEqual(output["memory_policy"]["source_path"], "specs/agents/memory-policies/tech_growth_analyst.yaml")
        self.assertIn("memory/agents/tech_growth_analyst", output["memory_namespaces"]["read"])
        self.assertTrue(output["memory_permission_checks"]["evolution_gate_required"])
        self.assertTrue(output["memory_permission_checks"]["forbidden_memory_writes_declared"])
        self.assertFalse(output["memory_permission_checks"]["real_trade_allowed"])
        self.assertFalse(output["memory_permission_checks"]["broker_integration"])

    def test_agent_harness_scores_memory_policy_alignment(self):
        context = {
            "role": "TechGrowthAnalyst",
            "memory_policy": {
                "available": True,
                "source_path": "specs/agents/memory-policies/tech_growth_analyst.yaml",
                "read_namespaces": ["memory/agents/tech_growth_analyst", "memory/organization"],
                "write_namespaces": ["memory/agents/tech_growth_analyst"],
                "retrieval_contract": {"max_memory_items": 6, "max_age_days": 180, "require_source_basis": True},
                "writeback_rules": {"requires_evolution_gate": True, "requires_reversible_ledger": True, "allow_direct_profile_mutation": False},
                "forbidden_memory_writes": ["core_profile", "tool_permissions", "risk_limits"],
                "harness_checks": ["memory_policy_loaded", "retrieval_contract_declared", "evolution_gate_required", "forbidden_memory_writes_respected", "no_real_trade_action"],
                "real_trade_allowed": False,
                "broker_integration": False,
            },
            "included_evidence": [{"evidence_id": "E001", "allowed_claims": ["C001"], "policy_matched_tags": ["industry"]}],
            "missing_evidence": ["公告"],
            "contradiction_table": [{"issue": "stub"}],
            "excluded_evidence_summary": [{"category": "irrelevant"}],
            "agent_card": {"available": True, "source_path": "specs/agents/agent-cards/tech_growth_analyst/agent.md", "declared_skills": ["supply_chain_chokepoint"]},
            "skill_contract": {"available": True, "source_path": "specs/skills/tech_growth_analyst/SKILL.md", "sections": ["Evidence Rules", "Context Management", "Role-Specific Checklist", "Forbidden Outputs"]},
        }
        output = {
            "agent_id": "tech_growth_analyst",
            "role": "TechGrowthAnalyst",
            "key_claims": [{"evidence_id": "E001", "claim_id": "C001"}],
            "agent_runtime": {"agent_card_path": "specs/agents/agent-cards/tech_growth_analyst/agent.md", "skill_path": "specs/skills/tech_growth_analyst/SKILL.md", "skill_sections": ["Evidence Rules", "Context Management", "Role-Specific Checklist", "Forbidden Outputs"]},
            "role_checklist_applied": ["产业链"],
            "skill_evidence_rules": ["No source, no confidence."],
            "agent_declared_skills": ["supply_chain_chokepoint"],
            "forbidden_actions_checked": ["no_real_trade_action"],
            "memory_policy": {"source_path": "specs/agents/memory-policies/tech_growth_analyst.yaml"},
            "memory_namespaces": {"read": ["memory/agents/tech_growth_analyst", "memory/organization"], "write": ["memory/agents/tech_growth_analyst"]},
            "memory_retrieval_contract": {"max_memory_items": 6, "max_age_days": 180, "require_source_basis": True},
            "memory_writeback_rules": {"requires_evolution_gate": True, "requires_reversible_ledger": True, "allow_direct_profile_mutation": False},
            "forbidden_memory_writes": ["core_profile", "tool_permissions", "risk_limits"],
            "memory_permission_checks": {"memory_policy_available": True, "retrieval_contract_declared": True, "evolution_gate_required": True, "forbidden_memory_writes_declared": True, "real_trade_allowed": False, "broker_integration": False},
            "disclaimer": "研究分析，不构成投资建议；不接真实交易，不自动下单。",
        }

        result = evaluate_agent("tech_growth_analyst", context, output)

        self.assertIn("memory_policy_quality", result)
        self.assertGreaterEqual(result["memory_policy_quality"]["score"], 80)
        self.assertTrue(result["memory_policy_quality"]["memory_policy_available"])
        self.assertTrue(result["memory_policy_quality"]["retrieval_contract_declared"])
        self.assertTrue(result["memory_policy_quality"]["evolution_gate_required"])
        self.assertTrue(result["memory_policy_quality"]["forbidden_memory_writes_respected"])


if __name__ == "__main__":
    unittest.main()
