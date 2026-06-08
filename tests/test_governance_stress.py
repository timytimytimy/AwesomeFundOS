import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from fundos.governance_stress import run_governance_stress_fixture
from fundos.io import REPO_ROOT, read_yaml
from fundos.system_audit import run_system_audit

CLI = [sys.executable, "-m", "fundos.cli"]


class GovernanceStressFixtureTests(unittest.TestCase):
    def test_fixture_blocks_tool_risk_dependency_and_real_trade_negative_cases(self):
        with tempfile.TemporaryDirectory() as d:
            fixture_name = Path(d).name
            report = run_governance_stress_fixture(REPO_ROOT, fixture_name=fixture_name)

        self.assertEqual(report["artifact_type"], "governance_stress_report")
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["candidate_count"], 5)
        self.assertEqual(report["applied_candidate_count"], 1)
        self.assertGreaterEqual(report["blocked_tool_policy_count"], 1)
        self.assertGreaterEqual(report["blocked_risk_limit_count"], 1)
        self.assertGreaterEqual(report["blocked_dependency_count"], 1)
        self.assertGreaterEqual(report["blocked_real_trade_count"], 1)
        self.assertEqual(report["blocking_issues"], [])
        self.assertFalse(report["real_trade_allowed"])
        self.assertEqual(report["broker_integration"], "disabled")

        by_id = {row["candidate_id"]: row for row in report["candidate_results"]}
        self.assertEqual(by_id["cand_governance_safe_workflow"]["application_status"], "applied")
        self.assertEqual(by_id["cand_governance_tool_policy_expansion"]["application_status_after_regression"], "blocked_regression")
        self.assertIn("protected_scope_requires_separate_governance", by_id["cand_governance_tool_policy_expansion"]["blocking_issues"])
        self.assertEqual(by_id["cand_governance_risk_limit_increase"]["application_status_after_regression"], "blocked_regression")
        self.assertIn("protected_scope_requires_separate_governance", by_id["cand_governance_risk_limit_increase"]["blocking_issues"])
        self.assertEqual(by_id["cand_governance_dependency_chain"]["application_status_after_regression"], "blocked_regression")
        self.assertIn("capability_dependency_attestation_required", by_id["cand_governance_dependency_chain"]["blocking_issues"])
        self.assertEqual(by_id["cand_governance_real_trade_request"]["application_status_after_regression"], "blocked_regression")
        self.assertIn("real_trade_allowed_forbidden", by_id["cand_governance_real_trade_request"]["blocking_issues"])

        artifact = REPO_ROOT / report["workspace_path"] / "runs" / report["run_id"] / "harness" / "governance-stress.yaml"
        self.assertTrue(artifact.exists())
        self.assertEqual(read_yaml(artifact)["status"], "passed")

    def test_cli_runs_governance_stress_fixture(self):
        with tempfile.TemporaryDirectory() as d:
            fixture_name = Path(d).name
            env = os.environ.copy()
            env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
            proc = subprocess.run(
                CLI + ["harness", "governance-stress", "--fixture-name", fixture_name],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                env=env,
            )

        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        self.assertIn("governance_stress_status=passed", proc.stdout)
        self.assertIn("applied_candidate_count=1", proc.stdout)
        self.assertRegex(proc.stdout, r"blocked_tool_policy_count=[1-9]")
        self.assertIn("blocked_risk_limit_count=1", proc.stdout)
        self.assertIn("blocked_dependency_count=1", proc.stdout)
        self.assertIn("blocked_real_trade_count=1", proc.stdout)
        self.assertIn("blocking_issues=none", proc.stdout)
        self.assertIn("real_trade_allowed=False", proc.stdout)
        self.assertIn("broker_integration=disabled", proc.stdout)

    def test_system_audit_includes_governance_stress_requirement(self):
        report = run_system_audit(REPO_ROOT)
        by_id = {row["requirement_id"]: row for row in report["requirements"]}

        self.assertIn("governance.tool_risk_dependency_stress_harness", by_id)
        row = by_id["governance.tool_risk_dependency_stress_harness"]
        self.assertEqual(row["status"], "pass")
        self.assertEqual(row["details"]["status"], "passed")
        self.assertEqual(row["details"]["applied_candidate_count"], 1)
        self.assertGreaterEqual(row["details"]["blocked_tool_policy_count"], 1)
        self.assertGreaterEqual(row["details"]["blocked_risk_limit_count"], 1)
        self.assertGreaterEqual(row["details"]["blocked_dependency_count"], 1)
        self.assertGreaterEqual(row["details"]["blocked_real_trade_count"], 1)
        self.assertFalse(row["details"]["real_trade_allowed"])
        self.assertEqual(row["details"]["broker_integration"], "disabled")


if __name__ == "__main__":
    unittest.main()
