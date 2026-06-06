from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]

class AgentAssetTests(unittest.TestCase):
    def test_each_default_agent_has_source_controlled_agent_md_and_skill(self):
        roster = yaml.safe_load((ROOT / "specs" / "agents" / "default-roster.yaml").read_text(encoding="utf-8"))["agents"]
        for agent in roster:
            aid = agent["id"]
            with self.subTest(agent_id=aid):
                agent_md = ROOT / "specs" / "agents" / "agent-cards" / aid / "agent.md"
                skill_md = ROOT / "specs" / "skills" / aid / "SKILL.md"
                self.assertTrue(agent_md.exists(), agent_md)
                self.assertTrue(skill_md.exists(), skill_md)
                agent_text = agent_md.read_text(encoding="utf-8")
                skill_text = skill_md.read_text(encoding="utf-8")
                for required in [
                    f"# {agent['name']} / {agent['role']}",
                    "## Profile",
                    "## Decision Principles",
                    "## Skills",
                    "## Tools",
                    "## Harness and Evaluation",
                    "## Context Management Policy",
                    "## Evolution Path",
                    "## Memory and Evolution",
                    "## Output Contract",
                    "不构成投资建议",
                ]:
                    self.assertIn(required, agent_text)
                self.assertTrue(skill_text.startswith("---\n"), skill_md)
                self.assertIn(f"name: fundos-{aid}", skill_text)
                self.assertIn("description:", skill_text)
                for required in [
                    "## When to Use This Skill",
                    "## Inputs",
                    "# Operating Workflow",
                    "## Evidence Rules",
                    "## Context Management",
                    "## Output Schema",
                    "## Failure Modes",
                    "## Learning Patterns",
                    "## Harness Hooks",
                    "## Guardrails",
                    "## Forbidden Outputs",
                    "## Safety",
                    "## Boundaries",
                ]:
                    self.assertIn(required, skill_text)
                for required_guardrail in [
                    "Research / watchlist / Paper Portfolio only",
                    "real_trade_allowed=false",
                    "broker_integration=disabled",
                    "Profile, Skill, Tool, Memory, Thread, Harness, and Evolution boundaries",
                    "EvolutionGate",
                ]:
                    self.assertIn(required_guardrail, skill_text)

if __name__ == "__main__":
    unittest.main()
