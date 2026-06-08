import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from fundos.capability_benchmark import run_capability_benchmark_fixture
from fundos.io import REPO_ROOT, read_yaml
from fundos.system_audit import run_system_audit


class CapabilityBenchmarkFixtureTests(unittest.TestCase):
    def test_fixture_compares_before_after_human_apply_without_mutating_source_assets(self):
        source_skill = REPO_ROOT / "specs" / "skills" / "position_trend_trader" / "SKILL.md"
        source_card = REPO_ROOT / "specs" / "agents" / "agent-cards" / "position_trend_trader" / "agent.md"
        before_skill = source_skill.read_text(encoding="utf-8")
        before_card = source_card.read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            report = run_capability_benchmark_fixture(REPO_ROOT, fixture_name=root.name)

            self.assertEqual(report["artifact_type"], "capability_benchmark_fixture_report")
            self.assertEqual(report["status"], "passed")
            self.assertEqual(report["regression_status"], "passed")
            self.assertEqual(report["skill_benchmark_status"], "passed")
            self.assertEqual(report["application_status"], "applied")
            self.assertFalse(report["baseline"]["managed_skill_block_present"])
            self.assertTrue(report["after_apply"]["managed_skill_block_present"])
            self.assertTrue(report["improvement"]["managed_skill_block_added"])
            self.assertGreater(report["improvement"]["skill_text_length_delta"], 0)
            self.assertFalse(report["real_trade_allowed"])
            self.assertEqual(report["broker_integration"], "disabled")

            runtime_skill = REPO_ROOT / report["workspace_path"] / "skills" / report["target_agent"] / "SKILL.md"
            self.assertTrue(runtime_skill.exists())
            self.assertIn(f"FUNDOS_CAPABILITY:{report['candidate_id']} START", runtime_skill.read_text(encoding="utf-8"))
            artifact = REPO_ROOT / report["workspace_path"] / "runs" / report["run_id"] / "harness" / "capability-benchmark-fixture.yaml"
            self.assertEqual(read_yaml(artifact)["status"], "passed")

        self.assertEqual(source_skill.read_text(encoding="utf-8"), before_skill)
        self.assertEqual(source_card.read_text(encoding="utf-8"), before_card)

    def test_cli_runs_capability_benchmark_fixture(self):
        with tempfile.TemporaryDirectory() as d:
            fixture_name = Path(d).name
            proc = subprocess.run(
                [sys.executable, "-m", "fundos.cli", "harness", "capability-benchmark", "--fixture-name", fixture_name],
                cwd=REPO_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        self.assertIn("capability_benchmark_status=passed", proc.stdout)
        self.assertIn("regression_status=passed", proc.stdout)
        self.assertIn("skill_benchmark_status=passed", proc.stdout)
        self.assertIn("application_status=applied", proc.stdout)
        self.assertIn("managed_skill_block_added=True", proc.stdout)
        self.assertIn("real_trade_allowed=False", proc.stdout)
        self.assertIn("broker_integration=disabled", proc.stdout)

    def test_system_audit_includes_capability_benchmark_fixture_requirement(self):
        report = run_system_audit(REPO_ROOT)
        by_id = {row["requirement_id"]: row for row in report["requirements"]}
        row = by_id["evolution.capability_benchmark_fixture_before_after_apply"]

        self.assertEqual(row["status"], "pass")
        self.assertEqual(row["details"]["regression_status"], "passed")
        self.assertEqual(row["details"]["skill_benchmark_status"], "passed")
        self.assertEqual(row["details"]["application_status"], "applied")
        self.assertTrue(row["details"]["managed_skill_block_added"])
        self.assertFalse(row["details"]["real_trade_allowed"])
        self.assertEqual(row["details"]["broker_integration"], "disabled")


if __name__ == "__main__":
    unittest.main()
