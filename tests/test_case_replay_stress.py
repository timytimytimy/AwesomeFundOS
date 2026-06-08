import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from fundos.case_replay_stress import CRITICAL_CASE_TYPES, run_case_replay_stress_fixture
from fundos.io import REPO_ROOT, read_yaml
from fundos.system_audit import run_system_audit

CLI = [sys.executable, "-m", "fundos.cli"]


class CaseReplayStressFixtureTests(unittest.TestCase):
    def test_fixture_replays_required_failure_cases_and_preserves_safety(self):
        with tempfile.TemporaryDirectory() as d:
            fixture_name = Path(d).name
            report = run_case_replay_stress_fixture(REPO_ROOT, fixture_name=fixture_name)

        self.assertEqual(report["artifact_type"], "case_replay_stress_report")
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["missing_required_case_types"], [])
        self.assertEqual(report["missing_critical_replay_types"], [])
        self.assertTrue(set(CRITICAL_CASE_TYPES).issubset(set(report["matched_case_types"])))
        self.assertGreaterEqual(report["case_count"], 10)
        self.assertGreaterEqual(report["case_results_total"], report["case_count"])
        self.assertTrue(report["checks"]["failure_modes_checked"])
        self.assertTrue(report["checks"]["methodology_only_controls_ok"])
        self.assertTrue(report["checks"]["kol_thesis_hypothesis_only_ok"])
        self.assertTrue(report["checks"]["no_direct_mapping_ok"])
        self.assertTrue(report["checks"]["source_controlled_case_files_replayed"])
        self.assertFalse(report["real_trade_allowed"])
        self.assertEqual(report["broker_integration"], "disabled")
        self.assertEqual(report["blocking_issues"], [])

        artifact = REPO_ROOT / report["workspace_path"] / "runs" / report["run_id"] / "harness" / "case-replay-stress.yaml"
        replay = REPO_ROOT / report["workspace_path"] / "runs" / report["run_id"] / "harness" / "historical-case-replay.yaml"
        self.assertTrue(artifact.exists())
        self.assertTrue(replay.exists())
        self.assertEqual(read_yaml(artifact)["status"], "passed")

    def test_cli_runs_case_replay_stress_fixture(self):
        with tempfile.TemporaryDirectory() as d:
            fixture_name = Path(d).name
            env = os.environ.copy()
            env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
            proc = subprocess.run(
                CLI + ["harness", "case-replay-stress", "--fixture-name", fixture_name],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                env=env,
            )

        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        self.assertIn("case_replay_stress_status=passed", proc.stdout)
        self.assertIn("missing_required_case_types=none", proc.stdout)
        self.assertIn("missing_critical_replay_types=none", proc.stdout)
        self.assertIn("missing_critical_failure_modes=none", proc.stdout)
        self.assertIn("blocking_issues=none", proc.stdout)
        self.assertIn("real_trade_allowed=False", proc.stdout)
        self.assertIn("broker_integration=disabled", proc.stdout)

    def test_system_audit_includes_case_replay_stress_requirement(self):
        report = run_system_audit(REPO_ROOT)
        by_id = {row["requirement_id"]: row for row in report["requirements"]}

        self.assertIn("cases.historical_case_replay_coverage_stress", by_id)
        row = by_id["cases.historical_case_replay_coverage_stress"]
        self.assertEqual(row["status"], "pass")
        self.assertEqual(row["details"]["status"], "passed")
        self.assertEqual(row["details"]["missing_required_case_types"], [])
        self.assertEqual(row["details"]["missing_critical_replay_types"], [])
        self.assertTrue(set(CRITICAL_CASE_TYPES).issubset(set(row["details"]["matched_case_types"])))
        self.assertFalse(row["details"]["real_trade_allowed"])
        self.assertEqual(row["details"]["broker_integration"], "disabled")


if __name__ == "__main__":
    unittest.main()
