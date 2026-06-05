import json
import tempfile
import unittest
from pathlib import Path

import yaml

from fundos.agent_performance import evaluate_agent_performance, load_performance_summary, write_agent_performance
from fundos.io import write_yaml


class AgentPerformanceTests(unittest.TestCase):
    def test_write_agent_performance_records_ledgers_and_promotion_actions(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            run_path = root / "runs" / "run-performance"
            (run_path / "harness").mkdir(parents=True)
            (run_path / "evaluations").mkdir(parents=True)
            selected = [
                {"agent_id": "tech_growth_analyst", "role": "TechGrowthAnalyst"},
                {"agent_id": "bear_debater", "role": "BearDebater"},
                {"agent_id": "swing_trader", "role": "SwingTrader"},
            ]
            write_yaml(run_path / "run.yaml", {"run_id": "run-performance", "selected_agents": selected})
            write_yaml(run_path / "harness" / "agent-harness.yaml", {
                "agent_results": [
                    {
                        "agent_id": "tech_growth_analyst",
                        "overall_score": 92,
                        "context_compression_quality": {"score": 90, "evidence_traceability": True},
                        "skill_invocation_quality": {"score": 93},
                        "role_consistency_quality": {"score": 94},
                        "blocking_issues": [],
                    },
                    {
                        "agent_id": "bear_debater",
                        "overall_score": 75,
                        "context_compression_quality": {"score": 76, "evidence_traceability": True},
                        "skill_invocation_quality": {"score": 78},
                        "role_consistency_quality": {"score": 72},
                        "blocking_issues": [],
                    },
                    {
                        "agent_id": "swing_trader",
                        "overall_score": 48,
                        "context_compression_quality": {"score": 50, "evidence_traceability": False},
                        "skill_invocation_quality": {"score": 52},
                        "role_consistency_quality": {"score": 42},
                        "blocking_issues": ["agent_harness_score_below_60"],
                    },
                ]
            })
            write_yaml(run_path / "evaluations" / "evaluation-report.yaml", {
                "agent_scores": [
                    {"agent_id": "tech_growth_analyst", "contribution_quality": 90, "context_fit": 88, "role_consistency": 91},
                    {"agent_id": "bear_debater", "contribution_quality": 73, "context_fit": 74, "role_consistency": 75},
                    {"agent_id": "swing_trader", "contribution_quality": 45, "context_fit": 55, "role_consistency": 50},
                ]
            })

            report = write_agent_performance(run_path)

            self.assertEqual(report["artifact_type"], "agent_performance_report")
            self.assertEqual(report["agent_count"], 3)
            actions = {row["agent_id"]: row["recommended_action"] for row in report["agent_results"]}
            self.assertEqual(actions["tech_growth_analyst"], "promote_watch")
            self.assertEqual(actions["bear_debater"], "maintain")
            self.assertEqual(actions["swing_trader"], "retrain_or_downgrade_watch")
            self.assertTrue((run_path / "harness" / "agent-performance.yaml").exists())
            for agent_id in actions:
                ledger = root / "agents" / agent_id / "performance" / "performance_ledger.jsonl"
                history = root / "agents" / agent_id / "performance" / "promotion_history.jsonl"
                self.assertTrue(ledger.exists(), agent_id)
                self.assertTrue(history.exists(), agent_id)
                row = json.loads(ledger.read_text().splitlines()[0])
                self.assertEqual(row["run_id"], "run-performance")
                self.assertFalse(row["real_trade_allowed"])

    def test_performance_summary_aggregates_existing_ledgers(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            perf_dir = root / "agents" / "fund_manager" / "performance"
            perf_dir.mkdir(parents=True)
            rows = [
                {"run_id": "r1", "final_score": 91, "recommended_action": "promote_watch", "blocking_issues": []},
                {"run_id": "r2", "final_score": 81, "recommended_action": "maintain", "blocking_issues": []},
                {"run_id": "r3", "final_score": 58, "recommended_action": "retrain_or_downgrade_watch", "blocking_issues": ["x"]},
            ]
            (perf_dir / "performance_ledger.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")

            summary = load_performance_summary(root, "fund_manager")

            self.assertEqual(summary["agent_id"], "fund_manager")
            self.assertEqual(summary["runs_evaluated"], 3)
            self.assertEqual(summary["latest_action"], "retrain_or_downgrade_watch")
            self.assertAlmostEqual(summary["average_score"], round((91 + 81 + 58) / 3, 1))
            self.assertEqual(summary["downgrade_watch_count"], 1)

    def test_evaluate_agent_performance_defaults_missing_artifacts_to_observation(self):
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d) / "runs" / "run-missing"
            run_path.mkdir(parents=True)
            write_yaml(run_path / "run.yaml", {"run_id": "run-missing", "selected_agents": [{"agent_id": "fund_manager", "role": "FundManager"}]})

            report = evaluate_agent_performance(run_path)

            self.assertEqual(report["agent_results"][0]["recommended_action"], "needs_more_observations")
            self.assertIn("missing_agent_harness", report["agent_results"][0]["blocking_issues"])


if __name__ == "__main__":
    unittest.main()
