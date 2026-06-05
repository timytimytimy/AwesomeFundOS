import json
import tempfile
import unittest
from pathlib import Path

from fundos.agent_tool_use import (
    load_agent_tool_use_report,
    load_agent_tool_use_spec,
    write_agent_tool_use_report,
)
from fundos.claim_graph import write_claim_graph
from fundos.evidence import make_evidence_pack
from fundos.harness import make_evaluation_for_run
from fundos.io import REPO_ROOT, read_yaml, write_yaml
from fundos.tool_runtime import run_fixture_tool_runtime


class AgentToolUseTests(unittest.TestCase):
    def test_spec_defines_reconciliation_controls(self):
        path = REPO_ROOT / "specs" / "tools" / "agent-tool-use-reconciliation.yaml"
        self.assertTrue(path.exists(), path)
        spec = load_agent_tool_use_spec()
        self.assertEqual(spec["reconciliation_id"], "agent_tool_use_reconciliation_v1")
        self.assertIn("agent_required_tools_must_be_reconciled_with_ledger", spec["controls"])
        self.assertIn("forbidden_tool_use_blocks_agent_tool_quality", spec["controls"])
        self.assertIn("missing_required_tool_caps_confidence", spec["controls"])
        self.assertIn("tool_result_must_enter_claim_graph", spec["controls"])
        self.assertFalse(spec["real_trade_allowed"])
        self.assertEqual(spec["broker_integration"], "disabled")

    def test_runtime_ledger_records_agent_id_for_each_tool_call(self):
        pack = make_evidence_pack("agent-tool-run", "topic", "机器人产业链投资机会")
        selected = [
            {"agent_id": "position_trend_trader", "id": "position_trend_trader", "role": "PositionTrendTrader"},
            {"agent_id": "risk_manager", "id": "risk_manager", "role": "RiskManagerAgent"},
        ]
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            write_yaml(run_path / "evidence" / "evidence-pack.yaml", pack)
            report = run_fixture_tool_runtime(run_path, selected, pack)
            rows = [json.loads(line) for line in (run_path / "tools" / "tool-call-ledger.jsonl").read_text().splitlines() if line.strip()]

        self.assertGreaterEqual(report["tool_call_count"], 5)
        self.assertTrue(all(row.get("agent_id") for row in rows))
        by_agent = {(row["agent_id"], row["adapter_id"]) for row in rows if row["status"] == "succeeded"}
        self.assertIn(("position_trend_trader", "market_data_query"), by_agent)
        self.assertIn(("position_trend_trader", "chart_summary"), by_agent)
        self.assertIn(("risk_manager", "risk_checklist"), by_agent)
        self.assertTrue(all(row["real_trade_allowed"] is False for row in rows))
        self.assertTrue(all(row["broker_integration"] == "disabled" for row in rows))

    def test_write_agent_tool_use_report_reconciles_policy_ledger_and_claim_graph(self):
        pack = make_evidence_pack("agent-tool-report", "topic", "机器人产业链投资机会")
        selected = [
            {"agent_id": "position_trend_trader", "id": "position_trend_trader", "role": "PositionTrendTrader"},
            {"agent_id": "risk_manager", "id": "risk_manager", "role": "RiskManagerAgent"},
        ]
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            write_yaml(run_path / "run.yaml", {"run_id": "agent-tool-report", "selected_agents": selected})
            write_yaml(run_path / "evidence" / "evidence-pack.yaml", pack)
            run_fixture_tool_runtime(run_path, selected, pack)
            refreshed = read_yaml(run_path / "evidence" / "evidence-pack.yaml")
            write_claim_graph(run_path, refreshed)

            report = write_agent_tool_use_report(run_path, selected)
            loaded = load_agent_tool_use_report(run_path)

        self.assertEqual(report["artifact_type"], "agent_tool_use_report")
        self.assertEqual(loaded["agent_count"], 2)
        self.assertGreaterEqual(report["overall_score"], 85)
        self.assertFalse(report["real_trade_allowed"])
        self.assertEqual(report["broker_integration"], "disabled")
        self.assertIn("tool_result_must_enter_claim_graph", report["controls"])
        rows = {row["agent_id"]: row for row in report["agent_results"]}
        position = rows["position_trend_trader"]
        self.assertEqual(position["missing_required_tools"], [])
        self.assertEqual(position["forbidden_called_tools"], [])
        self.assertIn("market_data_query", position["called_tools"])
        self.assertIn("chart_summary", position["called_tools"])
        self.assertGreaterEqual(position["tool_results_linked_to_claim_graph"], 2)
        self.assertFalse(position["confidence_cap_required"])
        self.assertGreaterEqual(position["score"], 85)
        risk = rows["risk_manager"]
        self.assertEqual(risk["missing_required_tools"], [])
        self.assertIn("risk_checklist", risk["called_tools"])
        self.assertGreaterEqual(report["linked_tool_results"], report["succeeded_tool_calls"])

    def test_report_flags_forbidden_tool_use_and_missing_required_tools(self):
        selected = [{"agent_id": "position_trend_trader", "id": "position_trend_trader", "role": "PositionTrendTrader"}]
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            (run_path / "tools").mkdir(parents=True)
            rows = [
                {
                    "run_id": "rogue-agent-tool",
                    "agent_id": "position_trend_trader",
                    "adapter_id": "broker_api",
                    "tool_result_id": "rogue-agent-tool:broker_api:001",
                    "query": "place order",
                    "status": "succeeded",
                    "permission_level": "read_only_analysis",
                    "evidence_item_ids": [],
                    "real_trade_allowed": False,
                    "broker_integration": "disabled",
                    "called_at": "2026-01-01T00:00:00+00:00",
                }
            ]
            (run_path / "tools" / "tool-call-ledger.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            write_yaml(run_path / "evidence" / "claim-graph.yaml", {"nodes": [], "edges": []})

            report = write_agent_tool_use_report(run_path, selected)

        row = report["agent_results"][0]
        self.assertIn("market_data_query", row["missing_required_tools"])
        self.assertIn("chart_summary", row["missing_required_tools"])
        self.assertIn("broker_api", row["forbidden_called_tools"])
        self.assertTrue(row["confidence_cap_required"])
        self.assertLess(row["score"], 60)
        self.assertIn("forbidden_tool_call:position_trend_trader:broker_api", report["blocking_issues"])
        self.assertIn("missing_required_tool:position_trend_trader:market_data_query", report["blocking_issues"])
        self.assertFalse(report["real_trade_allowed"])

    def test_evaluation_reads_agent_tool_use_quality_and_accepts_output(self):
        pack = make_evidence_pack("agent-tool-eval", "topic", "机器人产业链投资机会")
        selected = [{"agent_id": "fund_manager", "id": "fund_manager", "role": "FundManagerAgent"}]
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            write_yaml(run_path / "harness" / "agent-tool-use.yaml", {
                "artifact_type": "agent_tool_use_report",
                "overall_score": 91,
                "agent_count": 1,
                "agents_with_missing_required_tools": 0,
                "agents_with_forbidden_tool_calls": 0,
                "linked_tool_results": 3,
                "succeeded_tool_calls": 3,
                "blocking_issues": [],
                "controls": ["agent_required_tools_must_be_reconciled_with_ledger"],
                "real_trade_allowed": False,
                "broker_integration": "disabled",
            })

            evaluation = make_evaluation_for_run("agent-tool-eval", selected, pack, run_path)

        self.assertIn("agent_tool_use_quality", evaluation)
        self.assertEqual(evaluation["agent_tool_use_quality"]["overall_score"], 91)
        self.assertEqual(evaluation["dimension_scores"]["agent_tool_use"], 91)
        self.assertIn("agent_tool_use", evaluation["accepted_outputs"])


if __name__ == "__main__":
    unittest.main()
