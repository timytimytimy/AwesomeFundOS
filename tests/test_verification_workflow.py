import stat
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class VerificationWorkflowTests(unittest.TestCase):
    def test_verify_script_runs_full_v1_quality_gate(self):
        script = ROOT / "scripts" / "verify_v1.sh"

        self.assertTrue(script.exists(), "scripts/verify_v1.sh must exist")
        mode = script.stat().st_mode
        self.assertTrue(mode & stat.S_IXUSR, "scripts/verify_v1.sh must be executable by owner")
        text = script.read_text(encoding="utf-8")

        self.assertIn("set -euo pipefail", text)
        self.assertIn("python3 -m pip install -e .", text)
        self.assertIn("python3 -m unittest discover -s tests -q", text)
        self.assertIn("python3 -m fundos.cli system audit --strict", text)
        self.assertIn("git diff --check", text)
        self.assertIn("real_trade_allowed=False", text)
        self.assertIn("broker_integration=disabled", text)
        self.assertNotIn("pytest", text)

    def test_github_ci_uses_same_verify_script_and_preserves_safety_gate(self):
        workflow = ROOT / ".github" / "workflows" / "ci.yml"

        self.assertTrue(workflow.exists(), ".github/workflows/ci.yml must exist")
        text = workflow.read_text(encoding="utf-8")

        self.assertIn("AwesomeFundOS V1 Verification", text)
        self.assertIn("actions/setup-python", text)
        self.assertIn("python-version: '3.11'", text)
        self.assertIn("scripts/verify_v1.sh", text)
        self.assertIn("real_trade_allowed=false", text)
        self.assertIn("broker_integration=disabled", text)
        self.assertNotIn("broker_api", text)


if __name__ == "__main__":
    unittest.main()
