import json
import tempfile
import unittest
from pathlib import Path

import yaml

from fundos.failure_patterns import extract_failure_patterns, load_failure_summary, write_failure_patterns
from fundos.io import write_yaml
from fundos.system_audit import validate_runtime_schema

ROOT = Path(__file__).resolve().parents[1]


class FailurePatternTests(unittest.TestCase):
    def test_extract_failure_patterns_from_reflections_evaluation_and_outcomes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            run_path = root / "runs" / "run-failure"
            (run_path / "reflections").mkdir(parents=True)
            (run_path / "evaluations").mkdir(parents=True)
            (run_path / "portfolio").mkdir(parents=True)
            write_yaml(run_path / "run.yaml", {"run_id": "run-failure"})
            write_yaml(run_path / "reflections" / "swing_trader.reflection.yaml", {
                "agent_id": "swing_trader",
                "missed_evidence": ["真实公告", "行情摘要"],
                "reasoning_errors": ["过度外推趋势"],
                "tool_usage_errors": ["未调用公告检索"],
                "bias_detected": ["追涨偏差"],
            })
            write_yaml(run_path / "evaluations" / "evaluation-report.yaml", {
                "blocking_issues": ["缺少 tier_1_primary_fact，不能形成高置信结论。"],
                "source_coverage": {"tier_1_primary_fact": 0, "low_tier_items": 2},
            })
            write_yaml(run_path / "portfolio" / "outcome-tracking.yaml", {
                "results": [
                    {"action_id": "a1", "subject": "机器人", "review_verdict": "missed_opportunity_review", "return_pct": 12.0},
                    {"action_id": "a2", "subject": "低空", "review_verdict": "risk_control_review", "max_drawdown_pct": -13.0},
                ]
            })

            report = extract_failure_patterns(run_path)

            self.assertEqual(report["artifact_type"], "failure_pattern_report")
            categories = {row["category"] for row in report["patterns"]}
            self.assertIn("missing_evidence", categories)
            self.assertIn("reasoning_error", categories)
            self.assertIn("tool_usage_error", categories)
            self.assertIn("evaluation_blocking_issue", categories)
            self.assertIn("missed_opportunity", categories)
            self.assertIn("risk_control_failure", categories)
            first = report["patterns"][0]
            self.assertIn("pattern_id", first)
            self.assertFalse(report["real_trade_allowed"])
            self.assertEqual(report["broker_integration"], "disabled")
            self.assertFalse(first["real_trade_allowed"])
            self.assertIn("review_before_evolution", report["controls"])

    def test_failure_pattern_schema_exists_and_validates_report_and_rows(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            run_path = root / "runs" / "run-schema"
            (run_path / "reflections").mkdir(parents=True)
            write_yaml(run_path / "run.yaml", {"run_id": "run-schema"})
            write_yaml(run_path / "reflections" / "risk_manager.reflection.yaml", {
                "agent_id": "risk_manager",
                "missed_evidence": ["流动性和持仓集中度数据"],
                "reasoning_errors": [],
                "tool_usage_errors": [],
                "bias_detected": [],
            })

            report = extract_failure_patterns(run_path)
            schema_path = ROOT / "specs" / "schemas" / "failure-pattern-report.schema.yaml"

            self.assertTrue(schema_path.exists())
            result = validate_runtime_schema(schema_path, report)
            self.assertTrue(result["ok"], result["schema_errors"])
            self.assertFalse(report["real_trade_allowed"])
            self.assertEqual(report["broker_integration"], "disabled")
            self.assertIn("failure_patterns_are_not_trade_signals", report["controls"])
            for pattern in report["patterns"]:
                self.assertTrue(pattern["review_before_evolution"])
                self.assertFalse(pattern["real_trade_allowed"])
                self.assertEqual(pattern["broker_integration"], "disabled")

    def test_extract_failure_patterns_from_agent_harness_guardrail_violations(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            run_path = root / "runs" / "run-guardrail-failure"
            (run_path / "harness").mkdir(parents=True)
            write_yaml(run_path / "run.yaml", {"run_id": "run-guardrail-failure"})
            write_yaml(run_path / "harness" / "agent-harness.yaml", {
                "artifact_type": "agent_harness_report",
                "agent_count": 1,
                "agent_results": [
                    {
                        "agent_id": "swing_trader",
                        "role": "SwingTrader",
                        "overall_score": 61,
                        "skill_invocation_quality": {
                            "score": 62,
                            "guardrails_present": True,
                            "guardrails_applied": False,
                            "guardrail_safety_respected": False,
                        },
                        "blocking_issues": ["skill_guardrails_not_applied"],
                    }
                ],
                "aggregate_scores": {"skill_guardrails": 0},
                "controls": ["skill_guardrails_required", "no_real_trade_action"],
            })

            report = extract_failure_patterns(run_path)

            guardrail_patterns = [row for row in report["patterns"] if row["category"] == "skill_guardrail_violation"]
            self.assertEqual(len(guardrail_patterns), 1)
            pattern = guardrail_patterns[0]
            self.assertEqual(pattern["agent_id"], "swing_trader")
            self.assertEqual(pattern["severity"], "high")
            self.assertIn("skill_guardrails_not_applied", pattern["description"])
            self.assertEqual(pattern["metadata"]["source"], "agent_harness")
            self.assertEqual(pattern["metadata"]["artifact_path"], "harness/agent-harness.yaml")
            self.assertFalse(pattern["metadata"]["guardrails_applied"])
            self.assertFalse(pattern["metadata"]["guardrail_safety_respected"])
            self.assertIn("skill_guardrail", pattern["tags"])
            self.assertFalse(pattern["real_trade_allowed"])
            self.assertEqual(pattern["broker_integration"], "disabled")

    def test_write_failure_patterns_updates_run_and_organization_ledgers_idempotently(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            run_path = root / "runs" / "run-failure-ledger"
            (run_path / "reflections").mkdir(parents=True)
            write_yaml(run_path / "run.yaml", {"run_id": "run-failure-ledger"})
            write_yaml(run_path / "reflections" / "risk_manager.reflection.yaml", {
                "agent_id": "risk_manager",
                "missed_evidence": ["流动性数据"],
                "reasoning_errors": [],
                "tool_usage_errors": [],
                "bias_detected": [],
            })

            first = write_failure_patterns(run_path)
            second = write_failure_patterns(run_path)

            self.assertEqual(first["pattern_count"], second["pattern_count"])
            self.assertTrue((run_path / "learning" / "failure-patterns.yaml").exists())
            org_path = root / "memory" / "organization" / "failure-pattern-library.jsonl"
            self.assertTrue(org_path.exists())
            rows = [json.loads(line) for line in org_path.read_text().splitlines() if line.strip()]
            self.assertEqual(len(rows), first["pattern_count"])
            self.assertEqual(rows[0]["run_id"], "run-failure-ledger")
            self.assertIn("failure_pattern", rows[0]["tags"])

    def test_load_failure_summary_counts_categories(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            org = root / "memory" / "organization"
            org.mkdir(parents=True)
            rows = [
                {"pattern_id": "p1", "category": "missing_evidence", "severity": "medium"},
                {"pattern_id": "p2", "category": "missing_evidence", "severity": "medium"},
                {"pattern_id": "p3", "category": "risk_control_failure", "severity": "high"},
            ]
            (org / "failure-pattern-library.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")

            summary = load_failure_summary(root)

            self.assertEqual(summary["pattern_count"], 3)
            self.assertEqual(summary["category_counts"]["missing_evidence"], 2)
            self.assertEqual(summary["severity_counts"]["high"], 1)
            self.assertFalse(summary["real_trade_allowed"])
            self.assertEqual(summary["broker_integration"], "disabled")


if __name__ == "__main__":
    unittest.main()
