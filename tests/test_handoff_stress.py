import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from fundos.handoff_stress import run_handoff_stress_fixture
from fundos.io import REPO_ROOT, read_yaml
from fundos.system_audit import run_system_audit

CLI = [sys.executable, "-m", "fundos.cli"]


class HandoffStressTests(unittest.TestCase):
    def test_fixture_stresses_committee_handoffs_and_blocks_degradation(self):
        with tempfile.TemporaryDirectory() as d:
            fixture_name = Path(d).name
            report = run_handoff_stress_fixture(REPO_ROOT, fixture_name=fixture_name)

        self.assertEqual(report["artifact_type"], "handoff_stress_report")
        self.assertEqual(report["status"], "passed")
        self.assertGreaterEqual(report["scenario_count"], 9)
        self.assertGreaterEqual(report["extended_roster_agent_count"], 12)
        self.assertGreaterEqual(report["thread_carryover"]["agents_with_carryover"], 12)
        self.assertEqual(report["thread_carryover"]["missing_carryover_agents"], [])
        self.assertEqual(report["mismatched_scenarios"], [])
        self.assertFalse(report["real_trade_allowed"])
        self.assertEqual(report["broker_integration"], "disabled")

        by_id = {row["scenario_id"]: row for row in report["scenario_results"]}
        self.assertEqual(by_id["happy_path_committee"]["actual_status"], "passed")
        self.assertTrue(by_id["happy_path_committee"]["required_fields_ok"])
        self.assertTrue(by_id["happy_path_committee"]["blocking_handoffs_ok"])
        self.assertTrue(by_id["happy_path_committee"]["artifact_refs_exist"])
        self.assertTrue(by_id["happy_path_committee"]["cross_agent_context_trace_ok"])
        self.assertEqual(by_id["missing_required_field"]["actual_status"], "blocked")
        self.assertEqual(by_id["missing_blocking_handoff"]["actual_status"], "blocked")
        self.assertEqual(by_id["unsafe_trade_request"]["actual_status"], "blocked")
        self.assertEqual(by_id["cross_role_context_loss"]["actual_status"], "blocked")
        self.assertEqual(by_id["delayed_blocking_handoff"]["actual_status"], "blocked")
        self.assertFalse(by_id["delayed_blocking_handoff"]["delayed_blocking_handoffs_ok"])
        self.assertEqual(by_id["partial_research_handoff"]["actual_status"], "blocked")
        self.assertFalse(by_id["partial_research_handoff"]["partial_handoffs_ok"])
        self.assertEqual(by_id["thread_carryover_missing_previous_run"]["actual_status"], "blocked")
        self.assertFalse(by_id["thread_carryover_missing_previous_run"]["thread_carryover_ok"])
        self.assertEqual(by_id["larger_committee_roster"]["actual_status"], "passed")
        self.assertTrue(by_id["larger_committee_roster"]["larger_roster_ok"])

        artifact = REPO_ROOT / report["workspace_path"] / "runs" / report["run_id"] / "harness" / "handoff-stress.yaml"
        self.assertTrue(artifact.exists())
        self.assertEqual(read_yaml(artifact)["status"], "passed")

    def test_cli_runs_handoff_stress_fixture(self):
        with tempfile.TemporaryDirectory() as d:
            fixture_name = Path(d).name
            env = os.environ.copy()
            env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
            proc = subprocess.run(
                CLI + ["harness", "handoff-stress", "--fixture-name", fixture_name],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                env=env,
            )

        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        self.assertIn("handoff_stress_status=passed", proc.stdout)
        self.assertIn("mismatched_scenarios=none", proc.stdout)
        self.assertIn("real_trade_allowed=False", proc.stdout)
        self.assertIn("broker_integration=disabled", proc.stdout)

    def test_system_audit_includes_handoff_stress_requirement(self):
        report = run_system_audit(REPO_ROOT)
        by_id = {row["requirement_id"]: row for row in report["requirements"]}

        self.assertIn("committee.cross_agent_handoff_stress_harness", by_id)
        row = by_id["committee.cross_agent_handoff_stress_harness"]
        self.assertEqual(row["status"], "pass")
        self.assertEqual(row["details"]["status"], "passed")
        self.assertTrue(row["details"]["happy_path_context_trace_ok"])
        self.assertTrue(row["details"]["unsafe_request_blocked"])
        self.assertTrue(row["details"]["context_loss_blocked"])
        self.assertTrue(row["details"]["delayed_handoff_blocked"])
        self.assertTrue(row["details"]["partial_handoff_blocked"])
        self.assertTrue(row["details"]["thread_carryover_blocked"])
        self.assertTrue(row["details"]["larger_roster_passed"])
        self.assertGreaterEqual(row["details"]["extended_roster_agent_count"], 12)
        self.assertFalse(row["details"]["real_trade_allowed"])
        self.assertEqual(row["details"]["broker_integration"], "disabled")


if __name__ == "__main__":
    unittest.main()
