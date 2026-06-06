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
                    "## Identity",
                    "## Role Mandate",
                    "## Investment Style",
                    "## Risk Preference",
                    "## Decision Principles",
                    "## Personality",
                    "## Skills",
                    "## Tools",
                    "## Learning Patterns",
                    "## Ability Boundaries",
                    "## Biases and Weaknesses",
                    "## Track Record and Growth",
                    "## Memory and Thread",
                    "## Harness and Evaluation",
                    "## Context Management Policy",
                    "## Evolution Path",
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

    def test_agent_os_assets_cross_reference_roster_contract(self):
        roster = yaml.safe_load((ROOT / "specs" / "agents" / "default-roster.yaml").read_text(encoding="utf-8"))["agents"]
        for agent in roster:
            aid = agent["id"]
            with self.subTest(agent_id=aid):
                agent_text = (ROOT / "specs" / "agents" / "agent-cards" / aid / "agent.md").read_text(encoding="utf-8")
                skill_text = (ROOT / "specs" / "skills" / aid / "SKILL.md").read_text(encoding="utf-8")
                context_policy = yaml.safe_load((ROOT / "specs" / "agents" / "context-policies" / f"{aid}.yaml").read_text(encoding="utf-8"))
                tool_policy = yaml.safe_load((ROOT / "specs" / "agents" / "tool-policies" / f"{aid}.yaml").read_text(encoding="utf-8"))
                memory_policy = yaml.safe_load((ROOT / "specs" / "agents" / "memory-policies" / f"{aid}.yaml").read_text(encoding="utf-8"))

                self.assertIn(f"canonical_agent_id: `{aid}`", agent_text)
                self.assertIn(f"organization_role: {agent['role']}", agent_text)
                self.assertIn(f"persistent_thread_manifest: `memory/agents/{aid}/thread.yaml`", agent_text)
                self.assertIn(f"long_term_namespace: `memory/agents/{aid}`", agent_text)
                for skill in agent.get("skills", []):
                    self.assertIn(f"`{skill}`", agent_text)
                for tool in agent.get("tools", []):
                    self.assertIn(f"`{tool}`", agent_text)
                self.assertIn(f"Agent card: `specs/agents/agent-cards/{aid}/agent.md`", skill_text)
                self.assertIn(f"Relevant long-term memory summary from `memory/agents/{aid}`", skill_text)

                for policy in [context_policy, tool_policy, memory_policy]:
                    self.assertEqual(policy["agent_id"], aid)
                    self.assertEqual(policy["role"], agent["role"])
                    self.assertFalse(policy["real_trade_allowed"])
                    self.assertFalse(policy["broker_integration"])
                self.assertEqual(set(tool_policy["allowed_tools"]), set(agent.get("tools", [])))
                self.assertTrue(set(tool_policy["required_tools"]).issubset(set(agent.get("tools", []))))
                self.assertIn(f"memory/agents/{aid}", memory_policy["read_namespaces"])
                self.assertEqual(memory_policy["write_namespaces"], [f"memory/agents/{aid}"])
                self.assertFalse(memory_policy["writeback_rules"]["allow_direct_profile_mutation"])
                self.assertTrue(memory_policy["writeback_rules"]["requires_evolution_gate"])
                self.assertTrue(context_policy["evidence_selection"]["kol_and_books_as_methodology_only"])

if __name__ == "__main__":
    unittest.main()
