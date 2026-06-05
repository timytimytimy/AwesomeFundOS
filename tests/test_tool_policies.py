import unittest

from fundos.agent_harness import evaluate_agent
from fundos.agent_outputs import make_structured_agent_output
from fundos.context import make_context_pack
from fundos.evidence import make_evidence_pack
from fundos.io import REPO_ROOT, read_yaml


class ToolPolicyTests(unittest.TestCase):
    def test_each_default_agent_has_source_controlled_tool_policy(self):
        roster = read_yaml(REPO_ROOT / "specs" / "agents" / "default-roster.yaml")
        forbidden = {"broker_api", "order_placement", "real_trade_execution"}
        required_keys = [
            "version",
            "agent_id",
            "role",
            "tool_policy_id",
            "allowed_tools",
            "required_tools",
            "forbidden_tools",
            "tool_categories",
            "permission_level",
            "tool_use_rules",
            "source_boundary_rules",
            "harness_checks",
            "real_trade_allowed",
            "broker_integration",
        ]
        for agent in roster["agents"]:
            aid = agent["id"]
            with self.subTest(agent_id=aid):
                path = REPO_ROOT / "specs" / "agents" / "tool-policies" / f"{aid}.yaml"
                self.assertTrue(path.exists(), path)
                policy = read_yaml(path)
                for key in required_keys:
                    self.assertIn(key, policy)
                self.assertEqual(policy["agent_id"], aid)
                self.assertEqual(policy["role"], agent["role"])
                self.assertTrue(set(agent.get("tools", [])) <= set(policy["allowed_tools"]))
                self.assertTrue(set(policy["required_tools"]) <= set(policy["allowed_tools"]))
                self.assertTrue(forbidden <= set(policy["forbidden_tools"]))
                self.assertFalse(policy["real_trade_allowed"])
                self.assertFalse(policy["broker_integration"])
                self.assertIn("no_real_trade_action", policy["harness_checks"])
                self.assertIn("social_signal_never_direct_buy", policy["source_boundary_rules"])

    def test_context_pack_embeds_tool_policy(self):
        roster = read_yaml(REPO_ROOT / "specs" / "agents" / "default-roster.yaml")
        agent = next(item for item in roster["agents"] if item["id"] == "tech_growth_analyst")
        pack = make_evidence_pack("tool-policy-run", "topic", "机器人产业链投资机会")

        context = make_context_pack("tool-policy-run", agent, pack)

        self.assertIn("tool_policy", context)
        self.assertEqual(context["tool_policy"]["source_path"], "specs/agents/tool-policies/tech_growth_analyst.yaml")
        self.assertIn("web_search", context["tool_policy"]["allowed_tools"])
        self.assertIn("announcement_search", context["tool_policy"]["required_tools"])
        self.assertFalse(context["tool_policy"]["real_trade_allowed"])
        self.assertFalse(context["tool_policy"]["broker_integration"])
        self.assertIn("tool_policy_loaded", context["tool_quality_controls"])

    def test_agent_output_reports_tool_policy_checks(self):
        roster = read_yaml(REPO_ROOT / "specs" / "agents" / "default-roster.yaml")
        agent = next(item for item in roster["agents"] if item["id"] == "position_trend_trader")
        pack = make_evidence_pack("tool-output-run", "topic", "机器人产业链投资机会")
        context = make_context_pack("tool-output-run", agent, pack)

        output = make_structured_agent_output(agent, context, pack, "机器人产业链投资机会")

        for key in [
            "tool_policy",
            "allowed_tools",
            "required_tools",
            "missing_tool_calls",
            "tool_permission_checks",
            "forbidden_tool_actions",
        ]:
            self.assertIn(key, output)
        self.assertEqual(output["tool_policy"]["source_path"], "specs/agents/tool-policies/position_trend_trader.yaml")
        self.assertIn("market_data_query", output["allowed_tools"])
        self.assertFalse(output["tool_permission_checks"]["real_trade_allowed"])
        self.assertFalse(output["tool_permission_checks"]["broker_integration"])
        self.assertTrue(output["tool_permission_checks"]["forbidden_tools_respected"])
        self.assertTrue(output["missing_tool_calls"])
        self.assertTrue(any(item["reason"] == "tool_call_ledger_not_available_v1" for item in output["missing_tool_calls"]))

    def test_agent_harness_scores_tool_policy_alignment(self):
        context = {
            "role": "PositionTrendTrader",
            "tool_policy": {
                "available": True,
                "source_path": "specs/agents/tool-policies/position_trend_trader.yaml",
                "allowed_tools": ["market_data_query", "chart_summary", "case_library_reader"],
                "required_tools": ["market_data_query", "chart_summary"],
                "forbidden_tools": ["broker_api", "order_placement", "real_trade_execution"],
                "harness_checks": ["tool_policy_loaded", "allowed_tools_declared", "forbidden_tools_respected", "no_real_trade_action", "broker_integration_disabled"],
                "real_trade_allowed": False,
                "broker_integration": False,
            },
            "included_evidence": [{"evidence_id": "E001", "allowed_claims": ["C001"], "policy_matched_tags": ["trading"]}],
            "missing_evidence": ["实时行情"],
            "contradiction_table": [{"issue": "stub"}],
            "excluded_evidence_summary": [{"category": "irrelevant"}],
            "agent_card": {"available": True, "source_path": "specs/agents/agent-cards/position_trend_trader/agent.md", "declared_skills": ["trend_template"], "declared_tools": ["market_data_query", "chart_summary", "case_library_reader"]},
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
            "agent_declared_tools": ["market_data_query", "chart_summary", "case_library_reader"],
            "allowed_tools": ["market_data_query", "chart_summary", "case_library_reader"],
            "required_tools": ["market_data_query", "chart_summary"],
            "missing_tool_calls": [{"tool": "market_data_query", "reason": "tool_call_ledger_not_available_v1"}],
            "tool_permission_checks": {"forbidden_tools_respected": True, "real_trade_allowed": False, "broker_integration": False},
            "forbidden_tool_actions": [],
            "forbidden_actions_checked": ["no_real_trade_action"],
            "disclaimer": "研究分析，不构成投资建议；不接真实交易，不自动下单。",
        }

        result = evaluate_agent("position_trend_trader", context, output)

        self.assertIn("tool_policy_quality", result)
        self.assertGreaterEqual(result["tool_policy_quality"]["score"], 80)
        self.assertTrue(result["tool_policy_quality"]["tool_policy_available"])
        self.assertTrue(result["tool_policy_quality"]["allowed_tools_declared"])
        self.assertTrue(result["tool_policy_quality"]["forbidden_tools_respected"])
        self.assertTrue(result["tool_policy_quality"]["real_trade_disabled"])
        self.assertTrue(result["tool_policy_quality"]["broker_integration_disabled"])


if __name__ == "__main__":
    unittest.main()
