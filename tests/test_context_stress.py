import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
import os

import yaml

from fundos.context_stress import make_dense_evidence_pack, run_context_stress
from fundos.io import REPO_ROOT
from fundos.system_audit import run_system_audit

CLI = [sys.executable, "-m", "fundos.cli"]


def run_cli(args, cwd):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(CLI + args, cwd=cwd, text=True, capture_output=True, env=env)


class ContextStressTests(unittest.TestCase):
    def test_dense_evidence_pack_contains_many_traceable_items(self):
        pack = make_dense_evidence_pack(item_count=36)

        self.assertEqual(pack["source_coverage"]["total_items"], 36)
        self.assertEqual(pack["source_coverage"]["public_research_items"], 0)
        self.assertTrue(pack["schema_validation"]["valid"], pack["schema_validation"])
        self.assertGreaterEqual(pack["source_coverage"]["tier_counts"]["tier_1_primary_fact"], 18)
        self.assertTrue(all(item["source_id"] == "context_stress_fixture" for item in pack["evidence_items"]))

    def test_context_stress_scores_vertical_agents_and_writes_report(self):
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d) / "runs" / "stress"

            report = run_context_stress(run_path=run_path, item_count=72, fail_under=80)

            self.assertEqual(report["artifact_type"], "context_stress_report")
            self.assertEqual(report["status"], "passed")
            self.assertEqual(report["blocked_agents"], [])
            self.assertFalse(report["real_trade_allowed"])
            self.assertEqual(report["broker_integration"], "disabled")
            self.assertTrue((run_path / "harness" / "context-stress.yaml").exists())
            by_agent = {row["agent_id"]: row for row in report["agent_results"]}
            for agent_id in ["tech_growth_analyst", "position_trend_trader", "risk_manager", "bear_debater"]:
                self.assertIn(agent_id, by_agent)
                self.assertGreaterEqual(by_agent[agent_id]["score"], 80)
                self.assertEqual(by_agent[agent_id]["missing_required_context_dimensions"], [])
                self.assertEqual(by_agent[agent_id]["forbidden_drop_violations"], [])
                self.assertGreater(by_agent[agent_id]["excluded_items"], 0)
                self.assertIn("role_specific_context_compression", by_agent[agent_id]["controls"])

    def test_context_stress_cli_prints_summary_and_optional_artifact(self):
        with tempfile.TemporaryDirectory() as d:
            tmp_path = Path(d)

            result = run_cli(["harness", "context-stress", "--items", "48", "--out-run", "runs/context-stress-cli"], tmp_path)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("context_stress_status=passed", result.stdout)
            self.assertIn("blocked_agents=none", result.stdout)
            self.assertIn("real_trade_allowed=False", result.stdout)
            path = tmp_path / "runs" / "context-stress-cli" / "harness" / "context-stress.yaml"
            self.assertTrue(path.exists())
            doc = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertEqual(doc["item_count"], 48)
            self.assertEqual(doc["status"], "passed")

    def test_system_audit_includes_context_stress_requirement(self):
        report = run_system_audit(REPO_ROOT)
        by_id = {row["requirement_id"]: row for row in report["requirements"]}

        self.assertIn("context.dense_vertical_context_stress_harness", by_id)
        requirement = by_id["context.dense_vertical_context_stress_harness"]
        self.assertEqual(requirement["status"], "pass")
        details = requirement["details"]
        self.assertEqual(details["status"], "passed")
        self.assertEqual(details["blocked_agents"], [])
        self.assertEqual(details["missing_required_context_dimensions"], {})
        self.assertFalse(details["real_trade_allowed"])
        self.assertEqual(details["broker_integration"], "disabled")


if __name__ == "__main__":
    unittest.main()
