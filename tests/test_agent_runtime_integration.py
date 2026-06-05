import tempfile
import unittest
from pathlib import Path

import yaml

from fundos.agent_outputs import make_structured_agent_output, write_agent_output
from fundos.context import make_context_pack
from fundos.evidence import make_evidence_pack
from fundos.io import REPO_ROOT, read_yaml


class AgentRuntimeIntegrationTests(unittest.TestCase):
    def test_context_pack_embeds_agent_card_and_skill_runtime_contract(self):
        roster = read_yaml(REPO_ROOT / "specs" / "agents" / "default-roster.yaml")
        agent = next(item for item in roster["agents"] if item["id"] == "tech_growth_analyst")
        pack = make_evidence_pack("run-agent-assets", "topic", "机器人产业链投资机会")
        context = make_context_pack("run-agent-assets", agent, pack)

        self.assertIn("agent_card", context)
        self.assertIn("skill_contract", context)
        self.assertEqual(context["agent_card"]["source_path"], "specs/agents/agent-cards/tech_growth_analyst/agent.md")
        self.assertEqual(context["skill_contract"]["source_path"], "specs/skills/tech_growth_analyst/SKILL.md")
        self.assertIn("Serenity-style chokepoint", context["agent_card"]["profile_summary"])
        self.assertIn("Evidence Rules", context["skill_contract"]["sections"])
        self.assertIn("Forbidden Outputs", context["skill_contract"]["sections"])
        self.assertTrue(any("先定义下游系统" in item for item in context["skill_contract"]["role_checklist"]))
        self.assertTrue(any("serenity_scheme_first_chokepoint" in item for item in context["agent_card"]["learning_patterns"]))

    def test_agent_output_uses_agent_card_and_skill_contract(self):
        roster = read_yaml(REPO_ROOT / "specs" / "agents" / "default-roster.yaml")
        agent = next(item for item in roster["agents"] if item["id"] == "position_trend_trader")
        pack = make_evidence_pack("run-agent-output", "topic", "机器人产业链投资机会")
        context = make_context_pack("run-agent-output", agent, pack)
        output = make_structured_agent_output(agent, context, pack, "机器人产业链投资机会")

        self.assertEqual(output["agent_runtime"]["agent_card_path"], "specs/agents/agent-cards/position_trend_trader/agent.md")
        self.assertEqual(output["agent_runtime"]["skill_path"], "specs/skills/position_trend_trader/SKILL.md")
        self.assertIn("PositionTrendTrader", output["agent_runtime"]["agent_card_title"])
        self.assertIn("Evidence Rules", output["agent_runtime"]["skill_sections"])
        self.assertTrue(output["role_checklist_applied"])
        self.assertTrue(any("趋势" in item or "止损" in item or "仓位" in item for item in output["role_checklist_applied"]))
        self.assertTrue(any("lihai_a_share_market_state" in item for item in output["agent_declared_learning_patterns"]))

    def test_written_markdown_shows_agent_card_and_skill_used(self):
        roster = read_yaml(REPO_ROOT / "specs" / "agents" / "default-roster.yaml")
        agent = next(item for item in roster["agents"] if item["id"] == "bear_debater")
        pack = make_evidence_pack("run-write", "topic", "机器人产业链投资机会")
        context = make_context_pack("run-write", agent, pack)
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "agent_work" / "bear_debater.md"
            write_agent_output(out, agent, context, "机器人产业链投资机会", pack)
            text = out.read_text(encoding="utf-8")
            structured = yaml.safe_load(out.with_suffix(".structured.yaml").read_text(encoding="utf-8"))

        self.assertIn("## Agent Card / Skill 已加载", text)
        self.assertIn("specs/agents/agent-cards/bear_debater/agent.md", text)
        self.assertIn("specs/skills/bear_debater/SKILL.md", text)
        self.assertIn("## Skill 角色检查清单", text)
        self.assertEqual(structured["agent_runtime"]["skill_path"], "specs/skills/bear_debater/SKILL.md")


if __name__ == "__main__":
    unittest.main()
