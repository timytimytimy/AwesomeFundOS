import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PackagingTests(unittest.TestCase):
    def test_pyproject_exposes_fundos_console_script(self):
        pyproject = ROOT / "pyproject.toml"
        self.assertTrue(pyproject.exists(), "pyproject.toml must exist for installable CLI usage")
        text = pyproject.read_text(encoding="utf-8")
        self.assertIn('[project.scripts]', text)
        self.assertIn('fundos = "fundos.cli:main"', text)
        self.assertIn('PyYAML>=6.0', text)

    def test_module_help_still_exposes_cli_name(self):
        result = subprocess.run(
            [sys.executable, "-m", "fundos.cli", "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("usage: fundos", result.stdout)
        self.assertIn("skills", result.stdout)


if __name__ == "__main__":
    unittest.main()
