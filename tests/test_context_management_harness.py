import tempfile
import unittest
from pathlib import Path

import yaml

from fundos.agent_harness import evaluate_agent_harness, write_agent_harness
from fundos.context import make_context_pack
from fundos.evidence import evidence_item, now_iso
from fundos.harness import make_evaluation_for_run
from fundos.io import REPO_ROOT, read_yaml, write_yaml


class ContextManagementHarnessTests(unittest.TestCase):
    def test_context_pack_contains_budget_manifest_and_loss_accounting_for_vertical_agent(self):
        roster = read_yaml(REPO_ROOT / "specs" / "agents" / "default-roster.yaml")
        trader = next(item for item in roster["agents"] if item["id"] == "position_trend_trader")
        pack = dense_evidence_pack("ctx-budget-run")

        context = make_context_pack("ctx-budget-run", trader, pack)

        self.assertIn("context_budget_manifest", context)
        manifest = context["context_budget_manifest"]
        self.assertEqual(manifest["agent_id"], "position_trend_trader")
        self.assertEqual(manifest["compression_style"], trader_context_style("position_trend_trader"))
        self.assertEqual(manifest["max_context_items"], context["context_policy"]["max_context_items"])
        self.assertLessEqual(manifest["included_items"], manifest["max_context_items"])
        self.assertGreater(manifest["candidate_items"], manifest["included_items"])
        self.assertGreater(manifest["excluded_items"], 0)
        self.assertGreater(manifest["estimated_tokens_before"], manifest["estimated_tokens_after"])
        self.assertLessEqual(manifest["estimated_tokens_after"], manifest["token_budget"])
        self.assertIn("role_specific_compression", manifest["controls"])
        self.assertIn("loss_accounting_required", manifest["controls"])

        self.assertIn("context_loss_accounting", context)
        loss = context["context_loss_accounting"]
        self.assertGreaterEqual(len(loss["excluded_evidence"]), 1)
        self.assertTrue(all("reason" in row for row in loss["excluded_evidence"]))
        self.assertIn("low_tier_or_lower_priority", {row["reason"] for row in loss["excluded_evidence"]})
        self.assertIn("retained_claim_ids", loss)
        self.assertIn("dropped_claim_ids", loss)

    def test_agent_harness_scores_context_management_quality(self):
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            roster = read_yaml(REPO_ROOT / "specs" / "agents" / "default-roster.yaml")
            selected = [
                {"agent_id": "position_trend_trader"},
                {"agent_id": "tech_growth_analyst"},
            ]
            pack = dense_evidence_pack("ctx-harness-run")
            for item in selected:
                agent = next(row for row in roster["agents"] if row["id"] == item["agent_id"])
                context = make_context_pack("ctx-harness-run", agent, pack)
                write_yaml(run_path / "context" / f"{agent['id']}.context-pack.yaml", context)
                write_yaml(run_path / "agent_work" / f"{agent['id']}.structured.yaml", minimal_output(agent, context))

            report = write_agent_harness(run_path, selected)

            self.assertIn("context_management_quality", report["aggregate_scores"])
            self.assertGreaterEqual(report["aggregate_scores"]["context_management_quality"], 80)
            self.assertIn("context_management_required", report["controls"])
            result = next(row for row in report["agent_results"] if row["agent_id"] == "position_trend_trader")
            quality = result["context_management_quality"]
            self.assertTrue(quality["budget_manifest_present"])
            self.assertTrue(quality["token_budget_respected"])
            self.assertTrue(quality["loss_accounting_present"])
            self.assertTrue(quality["role_specific_compression_present"])
            self.assertGreater(quality["excluded_items"], 0)

    def test_system_evaluation_exposes_context_management_quality(self):
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            roster = read_yaml(REPO_ROOT / "specs" / "agents" / "default-roster.yaml")
            selected = [{"agent_id": "position_trend_trader"}]
            pack = dense_evidence_pack("ctx-eval-run")
            agent = next(row for row in roster["agents"] if row["id"] == "position_trend_trader")
            context = make_context_pack("ctx-eval-run", agent, pack)
            write_yaml(run_path / "context" / "position_trend_trader.context-pack.yaml", context)
            write_yaml(run_path / "agent_work" / "position_trend_trader.structured.yaml", minimal_output(agent, context))
            write_agent_harness(run_path, selected)

            report = make_evaluation_for_run("ctx-eval-run", selected, pack, run_path)

            self.assertIn("context_management_quality", report)
            self.assertGreaterEqual(report["context_management_quality"]["overall"], 80)
            self.assertGreater(report["context_management_quality"]["excluded_items"], 0)
            self.assertIn("context_management", report["accepted_outputs"])


def dense_evidence_pack(run_id: str) -> dict:
    retrieved_at = now_iso()
    items = []
    tags = [
        ("market_data", "tier_1_primary_fact", ["trading", "risk"]),
        ("financial_report", "tier_1_primary_fact", ["company", "risk"]),
        ("policy", "tier_1_primary_fact", ["industry", "risk"]),
        ("practitioner_source", "tier_3_verified_public_practitioner", ["trading", "risk"]),
        ("book_summary", "tier_2_canonical_framework", ["trading", "risk"]),
        ("social", "tier_5_social_signal", ["industry"]),
        ("case", "tier_2_canonical_framework", ["bear_case", "risk"]),
        ("learning_pattern", "tier_3_verified_public_practitioner", ["trading"]),
        ("news", "tier_4_expert_opinion", ["industry", "company"]),
    ]
    for idx, (source_type, tier, relevant_to) in enumerate(tags, start=1):
        items.append(evidence_item(
            f"E{idx:03d}",
            source_type,
            tier,
            f"Evidence {idx}",
            "摘要 " + ("很长" * 80),
            f"claim {idx}",
            "fact" if tier == "tier_1_primary_fact" else "opinion",
            retrieved_at,
            relevant_to,
        ))
    return {
        "run_id": run_id,
        "market": "CN_A_SHARE",
        "query": "context management dense pack",
        "retrieved_at": retrieved_at,
        "evidence_items": items,
        "unresolved_gaps": ["实时行情未接入"],
    }


def minimal_output(agent: dict, context: dict) -> dict:
    first = context["included_evidence"][0]
    return {
        "agent_id": agent["id"],
        "role": agent["role"],
        "key_claims": [{"evidence_id": first["evidence_id"], "claim_id": first["allowed_claims"][0]}],
        "agent_runtime": {
            "agent_card_path": context["agent_card"]["source_path"],
            "skill_path": context["skill_contract"]["source_path"],
            "skill_sections": context["skill_contract"]["sections"],
        },
        "role_checklist_applied": ["按角色压缩上下文"],
        "skill_evidence_rules": ["No source, no confidence."],
        "agent_declared_skills": context["agent_card"].get("declared_skills", []),
        "forbidden_actions_checked": ["no_real_trade_action"],
        "disclaimer": "研究分析，不构成投资建议；不接真实交易，不自动下单。",
        "memory_policy": {"source_path": context["memory_policy"]["source_path"]},
        "memory_namespaces": {"read": context["memory_policy"].get("read_namespaces", []), "write": context["memory_policy"].get("write_namespaces", [])},
        "memory_retrieval_contract": context["memory_policy"].get("retrieval_contract", {}),
        "memory_writeback_rules": context["memory_policy"].get("writeback_rules", {}),
        "forbidden_memory_writes": context["memory_policy"].get("forbidden_memory_writes", []),
        "memory_permission_checks": {"evolution_gate_required": True, "real_trade_allowed": False, "broker_integration": False},
        "allowed_tools": context["tool_policy"].get("allowed_tools", []),
        "required_tools": context["tool_policy"].get("required_tools", []),
        "missing_tool_calls": [{"tool": tool} for tool in context["tool_policy"].get("required_tools", [])],
        "forbidden_tool_actions": [],
        "tool_permission_checks": {"forbidden_tools_respected": True, "real_trade_allowed": False, "broker_integration": False},
    }


def trader_context_style(agent_id: str) -> list[str]:
    return read_yaml(REPO_ROOT / "specs" / "agents" / "context-policies" / f"{agent_id}.yaml")["compression_style"]


if __name__ == "__main__":
    unittest.main()
