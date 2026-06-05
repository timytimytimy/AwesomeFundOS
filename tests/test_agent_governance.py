import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from fundos.agent_governance import evaluate_agent_governance, load_governance_summary, write_agent_governance
from fundos.harness import make_evaluation_for_run
from fundos.io import write_yaml

ROOT = Path(__file__).resolve().parents[1]
CLI = [sys.executable, "-m", "fundos.cli"]


def run_cli(args, cwd):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(CLI + args, cwd=cwd, text=True, capture_output=True, env=env)


class AgentGovernanceTests(unittest.TestCase):
    def test_evaluate_agent_governance_groups_agents_by_seat_and_recommends_actions(self):
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d) / "runs" / "governance-run"
            (run_path / "harness").mkdir(parents=True)
            write_yaml(run_path / "harness" / "agent-performance.yaml", {
                "artifact_type": "agent_performance_report",
                "agent_results": [
                    {"agent_id": "tech_growth_analyst", "role": "TechGrowthAnalyst", "final_score": 92, "recommended_action": "promote_watch", "blocking_issues": [], "real_trade_allowed": False},
                    {"agent_id": "advanced_manufacturing_analyst", "role": "AdvancedManufacturingAnalyst", "final_score": 83, "recommended_action": "maintain", "blocking_issues": [], "real_trade_allowed": False},
                    {"agent_id": "swing_trader", "role": "SwingTrader", "final_score": 54, "recommended_action": "retrain_or_downgrade_watch", "blocking_issues": ["agent_harness_score_below_60"], "real_trade_allowed": False},
                    {"agent_id": "position_trend_trader", "role": "PositionTrendTrader", "final_score": 86, "recommended_action": "maintain", "blocking_issues": [], "real_trade_allowed": False},
                ],
            })

            report = evaluate_agent_governance(run_path)

            self.assertEqual(report["artifact_type"], "agent_governance_report")
            self.assertEqual(report["agent_count"], 4)
            self.assertIn("research", report["seat_groups"])
            self.assertIn("trading", report["seat_groups"])
            actions = {row["agent_id"]: row["governance_action"] for row in report["agent_reviews"]}
            self.assertEqual(actions["tech_growth_analyst"], "promotion_watch")
            self.assertEqual(actions["swing_trader"], "retrain_and_downgrade_watch")
            self.assertFalse(report["real_trade_allowed"])
            self.assertIn("promotion_does_not_change_capital_authority", report["controls"])
            trading = report["seat_competitions"]["trading"]
            self.assertEqual(trading["leader_agent_id"], "position_trend_trader")
            self.assertIn("swing_trader", trading["retrain_watch_agents"])

    def test_write_agent_governance_materializes_run_and_org_ledgers(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            run_path = root / "runs" / "governance-write"
            (run_path / "harness").mkdir(parents=True)
            write_yaml(run_path / "harness" / "agent-performance.yaml", {
                "agent_results": [
                    {"agent_id": "tech_growth_analyst", "role": "TechGrowthAnalyst", "final_score": 91, "recommended_action": "promote_watch", "blocking_issues": [], "real_trade_allowed": False},
                    {"agent_id": "swing_trader", "role": "SwingTrader", "final_score": 45, "recommended_action": "retrain_or_downgrade_watch", "blocking_issues": ["x"], "real_trade_allowed": False},
                ]
            })

            report = write_agent_governance(run_path)

            self.assertTrue((run_path / "harness" / "agent-governance.yaml").exists())
            self.assertTrue((root / "memory" / "organization" / "agent-governance-ledger.jsonl").exists())
            self.assertTrue((root / "agents" / "tech_growth_analyst" / "governance" / "seat-history.jsonl").exists())
            self.assertTrue((root / "agents" / "swing_trader" / "governance" / "seat-history.jsonl").exists())
            rows = [json.loads(line) for line in (root / "memory" / "organization" / "agent-governance-ledger.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(rows), 2)
            self.assertTrue(all(row["real_trade_allowed"] is False for row in rows))
            summary = load_governance_summary(run_path)
            self.assertEqual(summary["agent_count"], report["agent_count"])
            self.assertIn("promotion_watch", summary["governance_action_counts"])

    def test_evaluation_includes_agent_governance_quality(self):
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d) / "runs" / "governance-eval"
            (run_path / "harness").mkdir(parents=True)
            write_yaml(run_path / "harness" / "agent-performance.yaml", {
                "agent_results": [
                    {"agent_id": "tech_growth_analyst", "role": "TechGrowthAnalyst", "final_score": 91, "recommended_action": "promote_watch", "blocking_issues": [], "real_trade_allowed": False},
                ]
            })
            governance = write_agent_governance(run_path)
            evidence_pack = {"evidence_items": [{"source_id": "public_research", "source_tier": "tier_1_primary_fact"}]}

            evaluation = make_evaluation_for_run("governance-eval", [{"agent_id": "tech_growth_analyst"}], evidence_pack, run_path)

            self.assertIn("agent_governance_quality", evaluation)
            self.assertEqual(evaluation["agent_governance_quality"]["agent_count"], governance["agent_count"])
            self.assertIn("agent_governance", evaluation["accepted_outputs"])
            self.assertFalse(evaluation["agent_governance_quality"]["real_trade_allowed"])

    def test_governance_summary_cli_after_evolve(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            init_result = run_cli(["init"], root)
            self.assertEqual(init_result.returncode, 0, init_result.stderr)
            run_result = run_cli(["run", "--topic", "机器人产业链投资机会"], root)
            self.assertEqual(run_result.returncode, 0, run_result.stderr)
            run_rel = [line for line in run_result.stdout.splitlines() if line.startswith("run_path=")][-1].split("=", 1)[1]
            evolve_result = run_cli(["evolve", "--run", str(root / run_rel)], root)
            self.assertEqual(evolve_result.returncode, 0, evolve_result.stderr)

            result = run_cli(["governance", "summary", "--run", str(root / run_rel)], root)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("agent_governance_report=", result.stdout)
            self.assertIn("seat_competitions=", result.stdout)
            self.assertIn("real_trade_allowed=False", result.stdout)


if __name__ == "__main__":
    unittest.main()
