import json
import tempfile
import unittest
from pathlib import Path

from fundos.evidence import make_evidence_pack
from fundos.harness import make_evaluation_for_run
from fundos.io import REPO_ROOT, read_yaml, write_yaml
from fundos.tool_runtime import (
    load_tool_runtime_report,
    load_tool_runtime_spec,
    run_fixture_tool_runtime,
)


class ToolRuntimeTests(unittest.TestCase):
    def test_fixture_runtime_spec_defines_read_only_adapters_and_controls(self):
        path = REPO_ROOT / "specs" / "tools" / "fixture-adapter-runtime.yaml"
        self.assertTrue(path.exists(), path)
        spec = load_tool_runtime_spec()
        self.assertEqual(spec["runtime_id"], "fixture_tool_adapter_runtime_v1")
        adapter_ids = {adapter["adapter_id"] for adapter in spec["fixture_adapters"]}
        self.assertTrue({
            "market_data_query",
            "announcement_search",
            "financial_report_parser",
            "news_search",
            "policy_search",
            "web_search",
            "case_library_reader",
            "memory_retrieval",
        } <= adapter_ids)
        self.assertIn("all_fixture_tools_are_read_only", spec["controls"])
        self.assertIn("tool_call_ledger_required", spec["controls"])
        self.assertFalse(spec["real_trade_allowed"])
        self.assertEqual(spec["broker_integration"], "disabled")

    def test_run_fixture_tool_runtime_writes_ledger_report_and_evidence_items(self):
        pack = make_evidence_pack("tool-run", "topic", "机器人产业链投资机会")
        selected = [
            {"agent_id": "tech_growth_analyst", "role": "IndustryAnalyst"},
            {"agent_id": "position_trend_trader", "role": "Trader"},
            {"agent_id": "risk_manager", "role": "RiskManager"},
        ]
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            write_yaml(run_path / "evidence" / "evidence-pack.yaml", pack)

            report = run_fixture_tool_runtime(run_path, selected, pack)

            self.assertEqual(report["artifact_type"], "tool_runtime_report")
            self.assertEqual(report["run_id"], "tool-run")
            self.assertGreaterEqual(report["tool_call_count"], 5)
            self.assertGreaterEqual(report["evidence_items_created"], 5)
            self.assertGreaterEqual(report["tool_runtime_quality_score"], 85)
            self.assertFalse(report["real_trade_allowed"])
            self.assertEqual(report["broker_integration"], "disabled")
            self.assertEqual(report["blocked_tool_calls"], 0)
            self.assertTrue((run_path / "tools" / "tool-call-ledger.jsonl").exists())
            self.assertTrue((run_path / "tools" / "tool-runtime-report.yaml").exists())
            self.assertTrue((run_path / "evidence" / "tool-runtime-evidence.yaml").exists())

            rows = [json.loads(line) for line in (run_path / "tools" / "tool-call-ledger.jsonl").read_text().splitlines() if line.strip()]
            self.assertEqual(len(rows), report["tool_call_count"])
            self.assertTrue(all(row["permission_level"] == "read_only_analysis" for row in rows))
            self.assertTrue(all(row["real_trade_allowed"] is False for row in rows))
            self.assertTrue(all(row["broker_integration"] == "disabled" for row in rows))
            self.assertTrue(all(row["status"] == "succeeded" for row in rows))
            self.assertTrue(all(row["tool_result_id"].startswith("tool-run:") for row in rows))
            self.assertIn("market_data_query", {row["adapter_id"] for row in rows})
            self.assertIn("announcement_search", {row["adapter_id"] for row in rows})
            self.assertIn("case_library_reader", {row["adapter_id"] for row in rows})

            evidence = read_yaml(run_path / "evidence" / "tool-runtime-evidence.yaml")
            tiers = {item["source_tier"] for item in evidence["evidence_items"]}
            self.assertIn("tier_1_primary_fact", tiers)
            self.assertTrue(all(item["source_id"] == "fixture_tool_runtime" for item in evidence["evidence_items"]))
            self.assertTrue(all(item["tool_result_id"] for item in evidence["evidence_items"]))

            updated_pack = read_yaml(run_path / "evidence" / "evidence-pack.yaml")
            self.assertTrue(any(item.get("source_id") == "fixture_tool_runtime" for item in updated_pack["evidence_items"]))
            self.assertIn("fixture_tool_runtime", updated_pack["retrieval_plan"])
            self.assertTrue(all(item.get("tool_result_id") for item in updated_pack["evidence_items"] if item.get("source_id") == "fixture_tool_runtime"))

            loaded = load_tool_runtime_report(run_path)
            self.assertEqual(loaded["artifact_type"], "tool_runtime_report")
            self.assertEqual(loaded["tool_call_count"], report["tool_call_count"])

    def test_runtime_blocks_forbidden_broker_like_tool_calls(self):
        pack = make_evidence_pack("rogue-tool-run", "topic", "机器人产业链投资机会")
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            report = run_fixture_tool_runtime(
                run_path,
                [{"agent_id": "rogue", "role": "Rogue", "tools": ["broker_api"]}],
                pack,
                requested_tools=["broker_api"],
            )

            self.assertEqual(report["blocked_tool_calls"], 1)
            self.assertIn("forbidden_or_unknown_tool:broker_api", report["blocking_issues"])
            self.assertFalse(report["real_trade_allowed"])
            rows = [json.loads(line) for line in (run_path / "tools" / "tool-call-ledger.jsonl").read_text().splitlines() if line.strip()]
            self.assertEqual(rows[0]["status"], "blocked")
            self.assertFalse(rows[0]["real_trade_allowed"])
            self.assertEqual(rows[0]["broker_integration"], "disabled")

    def test_evaluation_reads_tool_runtime_quality_and_accepts_output(self):
        pack = make_evidence_pack("tool-eval", "topic", "机器人产业链投资机会")
        selected = [{"agent_id": "fund_manager", "role": "FundManager"}]
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            write_yaml(run_path / "tools" / "tool-runtime-report.yaml", {
                "artifact_type": "tool_runtime_report",
                "tool_runtime_quality_score": 92,
                "tool_call_count": 7,
                "evidence_items_created": 7,
                "blocked_tool_calls": 0,
                "adapters_called": ["market_data_query", "announcement_search"],
                "source_tier_counts": {"tier_1_primary_fact": 5},
                "blocking_issues": [],
                "controls": ["read_only_analysis_only", "no_broker_integration"],
                "real_trade_allowed": False,
                "broker_integration": "disabled",
            })

            evaluation = make_evaluation_for_run("tool-eval", selected, pack, run_path)

        self.assertIn("tool_runtime_quality", evaluation)
        self.assertEqual(evaluation["tool_runtime_quality"]["tool_runtime_quality_score"], 92)
        self.assertIn("tool_runtime", evaluation["accepted_outputs"])
        self.assertEqual(evaluation["dimension_scores"]["tool_runtime_quality"], 92)


if __name__ == "__main__":
    unittest.main()
