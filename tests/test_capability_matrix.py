import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from fundos.capability_matrix import run_capability_matrix_fixture
from fundos.io import REPO_ROOT, read_yaml
from fundos.system_audit import run_system_audit

CLI = [sys.executable, "-m", "fundos.cli"]


class CapabilityMatrixFixtureTests(unittest.TestCase):
    def test_fixture_applies_non_skill_capabilities_and_blocks_negative_cases(self):
        with tempfile.TemporaryDirectory() as d:
            fixture_name = Path(d).name
            report = run_capability_matrix_fixture(REPO_ROOT, fixture_name=fixture_name)

        self.assertEqual(report["artifact_type"], "capability_matrix_fixture_report")
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["candidate_count"], 5)
        self.assertEqual(report["non_skill_applied_count"], 3)
        self.assertGreaterEqual(report["blocked_protected_scope_count"], 1)
        self.assertGreaterEqual(report["blocked_missing_artifact_count"], 1)
        self.assertFalse(report["real_trade_allowed"])
        self.assertEqual(report["broker_integration"], "disabled")
        self.assertEqual(report["blocking_issues"], [])
        self.assertEqual(set(report["improvement"]["applied_kinds"]), {"checklist", "principle", "workflow"})

        by_id = {row["candidate_id"]: row for row in report["candidate_results"]}
        self.assertEqual(by_id["cand_capability-matrix-fixture_principle"]["application_status"], "applied")
        self.assertEqual(by_id["cand_capability-matrix-fixture_workflow"]["application_status"], "applied")
        self.assertEqual(by_id["cand_capability-matrix-fixture_checklist"]["application_status"], "applied")
        protected = by_id["cand_capability-matrix-fixture_protected_tool_permission"]
        self.assertEqual(protected["application_status_after_regression"], "blocked_regression")
        self.assertIn("protected_scope_requires_separate_governance", protected["blocking_issues"])
        missing = by_id["cand_capability-matrix-fixture_missing_outcome_review"]
        self.assertEqual(missing["application_status_after_regression"], "blocked_regression")
        self.assertIn("missing_artifact:portfolio/portfolio-review.yaml", missing["blocking_issues"])

        artifact = REPO_ROOT / report["workspace_path"] / "runs" / report["run_id"] / "harness" / "capability-matrix-fixture.yaml"
        self.assertTrue(artifact.exists())
        self.assertEqual(read_yaml(artifact)["status"], "passed")
        applied_doc = read_yaml(REPO_ROOT / report["workspace_path"] / "agents" / "fund_manager" / "applied-capabilities.yaml")
        self.assertEqual(len(applied_doc["applied_capabilities"]), 3)

    def test_cli_runs_capability_matrix_fixture(self):
        with tempfile.TemporaryDirectory() as d:
            fixture_name = Path(d).name
            env = os.environ.copy()
            env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
            proc = subprocess.run(
                CLI + ["harness", "capability-matrix", "--fixture-name", fixture_name],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                env=env,
            )

        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        self.assertIn("capability_matrix_status=passed", proc.stdout)
        self.assertIn("non_skill_applied_count=3", proc.stdout)
        self.assertIn("blocked_protected_scope_count=1", proc.stdout)
        self.assertIn("blocked_missing_artifact_count=1", proc.stdout)
        self.assertIn("blocking_issues=none", proc.stdout)
        self.assertIn("real_trade_allowed=False", proc.stdout)
        self.assertIn("broker_integration=disabled", proc.stdout)

    def test_system_audit_includes_capability_matrix_requirement(self):
        report = run_system_audit(REPO_ROOT)
        by_id = {row["requirement_id"]: row for row in report["requirements"]}

        self.assertIn("evolution.capability_matrix_non_skill_and_blocking_fixture", by_id)
        row = by_id["evolution.capability_matrix_non_skill_and_blocking_fixture"]
        self.assertEqual(row["status"], "pass")
        self.assertEqual(row["details"]["status"], "passed")
        self.assertEqual(row["details"]["non_skill_applied_count"], 3)
        self.assertGreaterEqual(row["details"]["blocked_protected_scope_count"], 1)
        self.assertGreaterEqual(row["details"]["blocked_missing_artifact_count"], 1)
        self.assertFalse(row["details"]["real_trade_allowed"])
        self.assertEqual(row["details"]["broker_integration"], "disabled")


if __name__ == "__main__":
    unittest.main()
