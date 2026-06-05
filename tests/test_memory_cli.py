import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = [sys.executable, "-m", "fundos.cli"]


def run_cli(args, cwd):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(CLI + args, cwd=cwd, text=True, capture_output=True, env=env)


class MemoryCliTests(unittest.TestCase):
    def test_memory_show_displays_semantic_memory_and_ledger_summary(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            memory_dir = root / "memory" / "agents" / "risk_manager"
            memory_dir.mkdir(parents=True)
            (memory_dir / "semantic_memory.md").write_text(
                "# risk_manager Long-term Memory\n\n"
                "## Accepted Evolution Lesson: cand_accept\n\n"
                "- proposal: 一手公告证据不足时必须将模拟仓位限制为0。\n",
                encoding="utf-8",
            )
            ledger_row = {
                "candidate_id": "cand_accept",
                "run_id": "run-1",
                "source_agent": "evaluation_harness",
                "target_agent": "risk_manager",
                "candidate_type": "principle_update",
                "proposal": "一手公告证据不足时必须将模拟仓位限制为0。",
                "approval_mode": "evolution_gate_v1_auto_controlled",
                "reversible": True,
                "real_trade_allowed": False,
                "broker_integration": "disabled",
            }
            (memory_dir / "evolution-ledger.jsonl").write_text(json.dumps(ledger_row, ensure_ascii=False) + "\n", encoding="utf-8")

            result = run_cli(["memory", "show", "--agent", "risk_manager"], root)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("agent_id=risk_manager", result.stdout)
            self.assertIn("accepted_lessons=1", result.stdout)
            self.assertIn("ledger_entries=1", result.stdout)
            self.assertIn("latest_candidate=cand_accept", result.stdout)
            self.assertIn("real_trade_allowed=False", result.stdout)
            self.assertIn("一手公告证据不足", result.stdout)

    def test_memory_show_returns_error_for_missing_agent_memory(self):
        with tempfile.TemporaryDirectory() as d:
            result = run_cli(["memory", "show", "--agent", "unknown_agent"], Path(d))

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("memory_not_found", result.stderr)
            self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
