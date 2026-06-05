from pathlib import Path
import tempfile
import unittest

import yaml

from fundos.agent_harness import evaluate_agent
from fundos.context import make_context_pack
from fundos.evidence import make_evidence_pack
from fundos.io import REPO_ROOT, read_yaml, write_yaml


class ContextPolicyTests(unittest.TestCase):
    def test_each_default_agent_has_source_controlled_context_policy(self):
        roster = read_yaml(REPO_ROOT / "specs" / "agents" / "default-roster.yaml")
        for agent in roster["agents"]:
            aid = agent["id"]
            with self.subTest(agent_id=aid):
                path = REPO_ROOT / "specs" / "agents" / "context-policies" / f"{aid}.yaml"
                self.assertTrue(path.exists(), path)
                policy = read_yaml(path)
                self.assertEqual(policy["agent_id"], aid)
                self.assertEqual(policy["context_policy_id"], agent["context_policy_id"])
                for key in [
                    "role_family",
                    "preferred_context_tags",
                    "must_preserve",
                    "compression_style",
                    "priority_lenses",
                    "exclusion_rules",
                    "max_context_items",
                    "evidence_selection",
                    "harness_checks",
                ]:
                    self.assertIn(key, policy)
                self.assertIn("evidence_ids", policy["must_preserve"])
                self.assertIn("claim_ids", policy["must_preserve"])
                self.assertIn("contradictions", policy["must_preserve"])
                self.assertIn("missing_evidence", policy["must_preserve"])
                self.assertFalse(policy["broker_integration"])
                self.assertFalse(policy["real_trade_allowed"])

    def test_context_pack_uses_source_controlled_policy_for_vertical_routing(self):
        roster = read_yaml(REPO_ROOT / "specs" / "agents" / "default-roster.yaml")
        trader = next(item for item in roster["agents"] if item["id"] == "position_trend_trader")
        analyst = next(item for item in roster["agents"] if item["id"] == "tech_growth_analyst")
        pack = make_evidence_pack("ctx-policy-run", "topic", "机器人产业链投资机会")

        trader_context = make_context_pack("ctx-policy-run", trader, pack)
        analyst_context = make_context_pack("ctx-policy-run", analyst, pack)

        self.assertEqual(trader_context["context_policy"]["source_path"], "specs/agents/context-policies/position_trend_trader.yaml")
        self.assertEqual(analyst_context["context_policy"]["source_path"], "specs/agents/context-policies/tech_growth_analyst.yaml")
        self.assertIn("trading", trader_context["context_policy"]["preferred_context_tags"])
        self.assertIn("industry", analyst_context["context_policy"]["preferred_context_tags"])
        self.assertNotEqual(trader_context["required_focus"], analyst_context["required_focus"])
        self.assertEqual(trader_context["context_budget_tokens"], trader_context["context_policy"]["token_budget"])
        self.assertLessEqual(len(trader_context["included_evidence"]), trader_context["context_policy"]["max_context_items"])
        self.assertIn("source_policy_match", trader_context["context_quality_controls"])
        self.assertIn("no_real_trade_action", trader_context["context_quality_controls"])

    def test_agent_harness_scores_context_policy_alignment(self):
        context = {
            "role": "PositionTrendTrader",
            "context_policy": {
                "available": True,
                "source_path": "specs/agents/context-policies/position_trend_trader.yaml",
                "preferred_context_tags": ["trading", "risk"],
                "must_preserve": ["evidence_ids", "claim_ids", "contradictions", "missing_evidence"],
                "max_context_items": 4,
                "harness_checks": ["source_policy_match", "context_budget_respected", "must_preserve_satisfied"],
                "real_trade_allowed": False,
                "broker_integration": False,
            },
            "included_evidence": [
                {"evidence_id": "E001", "allowed_claims": ["C001"], "policy_matched_tags": ["trading"]}
            ],
            "missing_evidence": ["实时行情"],
            "contradiction_table": [{"issue": "stub"}],
            "excluded_evidence_summary": [{"category": "irrelevant"}],
            "agent_card": {"available": True, "source_path": "specs/agents/agent-cards/position_trend_trader/agent.md", "declared_skills": ["trend_template"]},
            "skill_contract": {"available": True, "source_path": "specs/skills/position_trend_trader/SKILL.md", "sections": ["Evidence Rules", "Context Management", "Role-Specific Checklist", "Forbidden Outputs"]},
        }
        output = {
            "agent_id": "position_trend_trader",
            "role": "PositionTrendTrader",
            "key_claims": [{"evidence_id": "E001", "claim_id": "C001"}],
            "agent_runtime": {"agent_card_path": "specs/agents/agent-cards/position_trend_trader/agent.md", "skill_path": "specs/skills/position_trend_trader/SKILL.md", "skill_sections": ["Evidence Rules", "Context Management", "Role-Specific Checklist", "Forbidden Outputs"]},
            "role_checklist_applied": ["趋势"],
            "skill_evidence_rules": ["No source, no confidence."],
            "agent_declared_skills": ["trend_template"],
            "forbidden_actions_checked": ["no_real_trade_action"],
            "disclaimer": "研究分析，不构成投资建议；不接真实交易，不自动下单。",
        }

        result = evaluate_agent("position_trend_trader", context, output)

        self.assertIn("context_policy_quality", result)
        self.assertGreaterEqual(result["context_policy_quality"]["score"], 80)
        self.assertTrue(result["context_policy_quality"]["source_policy_match"])
        self.assertTrue(result["context_policy_quality"]["must_preserve_satisfied"])


if __name__ == "__main__":
    unittest.main()
