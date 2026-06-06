import tempfile
import unittest
from pathlib import Path

import yaml
import json

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
        self.assertTrue(context["agent_card"]["identity"])
        self.assertTrue(context["agent_card"]["role_mandate"])
        self.assertTrue(context["agent_card"]["investment_style"])
        self.assertTrue(context["agent_card"]["risk_preference"])
        self.assertTrue(context["agent_card"]["ability_boundaries"])
        self.assertTrue(context["agent_card"]["track_record_and_growth"])
        self.assertTrue(context["agent_card"]["memory_and_thread"])
        self.assertIn("Evidence Rules", context["skill_contract"]["sections"])
        self.assertIn("Forbidden Outputs", context["skill_contract"]["sections"])
        self.assertIn("Guardrails", context["skill_contract"]["sections"])
        self.assertIn("Harness Hooks", context["skill_contract"]["sections"])
        self.assertIn("Failure Modes", context["skill_contract"]["sections"])
        self.assertTrue(context["agent_card"]["harness_and_evaluation"])
        self.assertTrue(context["agent_card"]["context_management_policy"])
        self.assertTrue(context["agent_card"]["evolution_path"])
        self.assertTrue(context["skill_contract"]["inputs"])
        self.assertTrue(context["skill_contract"]["output_schema"])
        self.assertTrue(context["skill_contract"]["harness_hooks"])
        self.assertTrue(context["skill_contract"]["guardrails"])
        self.assertTrue(any("real_trade_allowed=false" in item for item in context["skill_contract"]["guardrails"]))
        self.assertTrue(any("broker_integration=disabled" in item for item in context["skill_contract"]["guardrails"]))
        self.assertTrue(any("EvolutionGate" in item for item in context["skill_contract"]["guardrails"]))
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
        self.assertIn("Guardrails", output["agent_runtime"]["skill_sections"])
        self.assertIn("Harness Hooks", output["agent_runtime"]["skill_sections"])
        self.assertIn("skill_guardrails_applied", output)
        self.assertTrue(any("real_trade_allowed=false" in item for item in output["skill_guardrails_applied"]))
        self.assertTrue(output["guardrail_checks"]["real_trade_disabled"])
        self.assertTrue(output["guardrail_checks"]["broker_integration_disabled"])
        self.assertTrue(output["guardrail_checks"]["evolution_gate_required"])
        self.assertTrue(output["guardrail_checks"]["boundaries_preserved"])
        self.assertTrue(output["role_checklist_applied"])
        self.assertTrue(any("趋势" in item or "止损" in item or "仓位" in item for item in output["role_checklist_applied"]))
        self.assertTrue(any("lihai_a_share_market_state" in item for item in output["agent_declared_learning_patterns"]))

    def test_agent_output_cites_accepted_thread_memory_lessons_as_auditable_influence(self):
        roster = read_yaml(REPO_ROOT / "specs" / "agents" / "default-roster.yaml")
        agent = next(item for item in roster["agents"] if item["id"] == "position_trend_trader")
        pack = make_evidence_pack("run-agent-thread-lessons", "topic", "机器人产业链投资机会")
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            thread_dir = root / "memory" / "agents" / "position_trend_trader"
            thread_dir.mkdir(parents=True, exist_ok=True)
            (thread_dir / "thread-events.jsonl").write_text(json.dumps({
                "timestamp": "2026-06-06T00:00:00+00:00",
                "event_type": "memory_writeback_applied",
                "agent_id": "position_trend_trader",
                "run_id": "run-agent-thread-lessons",
                "payload": {
                    "candidate_id": "cand_stop_loss_lesson",
                    "approval_mode": "evolution_gate_v1_auto_controlled",
                    "semantic_memory_path": "memory/agents/position_trend_trader/semantic-memory.yaml",
                },
                "real_trade_allowed": False,
                "broker_integration": "disabled",
            }, ensure_ascii=False) + "\n", encoding="utf-8")
            context = make_context_pack("run-agent-thread-lessons", agent, pack, runtime_root=root)

            output = make_structured_agent_output(agent, context, pack, "机器人产业链投资机会")

        self.assertIn("thread_memory_influence", output)
        self.assertEqual(output["thread_memory_influence"]["summary_available"], True)
        self.assertEqual(output["thread_memory_influence"]["accepted_lesson_count"], 1)
        lesson = output["thread_memory_influence"]["accepted_lessons_used"][0]
        self.assertEqual(lesson["candidate_id"], "cand_stop_loss_lesson")
        self.assertEqual(lesson["semantic_memory_path"], "memory/agents/position_trend_trader/semantic-memory.yaml")
        self.assertEqual(lesson["usage"], "retrieval_context_only")
        self.assertFalse(output["thread_memory_influence"]["real_trade_allowed"])
        self.assertEqual(output["thread_memory_influence"]["broker_integration"], "disabled")

    def test_agent_output_separates_current_evidence_memory_influence_and_hypotheses(self):
        roster = read_yaml(REPO_ROOT / "specs" / "agents" / "default-roster.yaml")
        agent = next(item for item in roster["agents"] if item["id"] == "tech_growth_analyst")
        pack = make_evidence_pack(
            "run-agent-reasoning-layers",
            "topic",
            "机器人产业链投资机会",
            public_results=[
                {"title": "机器人公告", "url": "https://www.cninfo.com.cn/new/disclosure/detail", "snippet": "公告验证机器人订单。"},
                {"title": "X讨论", "url": "https://x.com/example/status/robotics", "snippet": "社媒显示机器人热度。"},
            ],
        )
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            thread_dir = root / "memory" / "agents" / "tech_growth_analyst"
            thread_dir.mkdir(parents=True, exist_ok=True)
            (thread_dir / "thread-events.jsonl").write_text(json.dumps({
                "timestamp": "2026-06-06T00:00:00+00:00",
                "event_type": "memory_writeback_applied",
                "agent_id": "tech_growth_analyst",
                "run_id": "run-agent-reasoning-layers",
                "payload": {"candidate_id": "cand_chokepoint_lesson", "approval_mode": "evolution_gate_v1_auto_controlled"},
                "real_trade_allowed": False,
                "broker_integration": "disabled",
            }, ensure_ascii=False) + "\n", encoding="utf-8")
            context = make_context_pack("run-agent-reasoning-layers", agent, pack, runtime_root=root)

            output = make_structured_agent_output(agent, context, pack, "机器人产业链投资机会")

        layers = output["reasoning_layers"]
        self.assertIn("current_evidence_conclusions", layers)
        self.assertIn("thread_memory_influences", layers)
        self.assertIn("hypotheses_to_validate", layers)
        self.assertTrue(layers["current_evidence_conclusions"])
        self.assertTrue(all(row["layer"] == "current_evidence" for row in layers["current_evidence_conclusions"]))
        self.assertTrue(all("evidence_id" in row and "claim_id" in row for row in layers["current_evidence_conclusions"]))
        self.assertEqual(layers["thread_memory_influences"][0]["candidate_id"], "cand_chokepoint_lesson")
        self.assertEqual(layers["thread_memory_influences"][0]["usage"], "retrieval_context_only")
        self.assertTrue(layers["hypotheses_to_validate"])
        self.assertTrue(all(row["layer"] == "hypothesis_to_validate" for row in layers["hypotheses_to_validate"]))
        self.assertFalse(layers["real_trade_allowed"])
        self.assertEqual(layers["broker_integration"], "disabled")

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

class AgentToolUseRuntimeRefreshTests(unittest.TestCase):
    def test_refresh_agent_outputs_replaces_v1_missing_tools_with_runtime_reconciliation(self):
        from fundos.agent_outputs import refresh_agent_outputs_with_tool_use
        from fundos.agent_tool_use import write_agent_tool_use_report
        from fundos.claim_graph import write_claim_graph
        from fundos.tool_runtime import run_fixture_tool_runtime

        roster = read_yaml(REPO_ROOT / "specs" / "agents" / "default-roster.yaml")
        agent = next(item for item in roster["agents"] if item["id"] == "position_trend_trader")
        selected = [{"agent_id": agent["id"], "role": agent["role"]}]
        pack = make_evidence_pack("agent-refresh", "topic", "机器人产业链投资机会")
        context = make_context_pack("agent-refresh", agent, pack)
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            write_yaml = __import__("fundos.io", fromlist=["write_yaml"]).write_yaml
            write_yaml(run_path / "run.yaml", {"run_id": "agent-refresh", "selected_agents": selected})
            write_yaml(run_path / "evidence" / "evidence-pack.yaml", pack)
            write_agent_output(run_path / "agent_work" / "position_trend_trader.md", agent, context, "机器人产业链投资机会", pack)
            before = yaml.safe_load((run_path / "agent_work" / "position_trend_trader.structured.yaml").read_text())
            self.assertTrue(before["missing_tool_calls"])
            self.assertTrue(any(row["reason"] == "tool_call_ledger_not_available_v1" for row in before["missing_tool_calls"]))

            run_fixture_tool_runtime(run_path, selected, pack)
            refreshed_pack = read_yaml(run_path / "evidence" / "evidence-pack.yaml")
            write_claim_graph(run_path, refreshed_pack)
            write_agent_tool_use_report(run_path, selected)
            summary = refresh_agent_outputs_with_tool_use(run_path)
            after = yaml.safe_load((run_path / "agent_work" / "position_trend_trader.structured.yaml").read_text())
            markdown = (run_path / "agent_work" / "position_trend_trader.md").read_text(encoding="utf-8")

        self.assertEqual(summary["updated_outputs"], 1)
        self.assertEqual(after["missing_tool_calls"], [])
        self.assertEqual(after["tool_permission_checks"]["missing_required_tools_reported"], True)
        self.assertFalse(after["tool_permission_checks"]["confidence_cap_required"])
        self.assertEqual(after["tool_runtime_reconciliation"]["score"], 100)
        self.assertIn("tool_use_reconciliation", after["agent_runtime"])
        self.assertIn("harness/agent-tool-use.yaml", after["agent_runtime"]["tool_use_reconciliation"])
        self.assertIn("missing_tool_calls: 0", markdown)

    def test_refresh_agent_outputs_preserves_missing_runtime_tools_when_reconciliation_fails(self):
        from fundos.agent_outputs import refresh_agent_outputs_with_tool_use

        roster = read_yaml(REPO_ROOT / "specs" / "agents" / "default-roster.yaml")
        agent = next(item for item in roster["agents"] if item["id"] == "position_trend_trader")
        pack = make_evidence_pack("agent-refresh-missing", "topic", "机器人产业链投资机会")
        context = make_context_pack("agent-refresh-missing", agent, pack)
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            write_agent_output(run_path / "agent_work" / "position_trend_trader.md", agent, context, "机器人产业链投资机会", pack)
            __import__("fundos.io", fromlist=["write_yaml"]).write_yaml(run_path / "harness" / "agent-tool-use.yaml", {
                "artifact_type": "agent_tool_use_report",
                "overall_score": 30,
                "agent_results": [{
                    "agent_id": "position_trend_trader",
                    "missing_required_tools": ["market_data_query", "chart_summary"],
                    "forbidden_called_tools": [],
                    "confidence_cap_required": True,
                    "score": 30,
                    "called_tools": [],
                    "tool_results_linked_to_claim_graph": 0,
                }],
                "real_trade_allowed": False,
                "broker_integration": "disabled",
            })
            refresh_agent_outputs_with_tool_use(run_path)
            after = yaml.safe_load((run_path / "agent_work" / "position_trend_trader.structured.yaml").read_text())

        self.assertEqual(
            after["missing_tool_calls"],
            [
                {"tool": "market_data_query", "reason": "missing_in_agent_tool_use_reconciliation"},
                {"tool": "chart_summary", "reason": "missing_in_agent_tool_use_reconciliation"},
            ],
        )
        self.assertTrue(after["tool_permission_checks"]["confidence_cap_required"])
        self.assertEqual(after["tool_runtime_reconciliation"]["score"], 30)
