import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from fundos.agent_threads import load_agent_thread_summary, materialize_agent_threads, record_run_threads
from fundos.harness import make_evaluation_for_run
from fundos.io import REPO_ROOT, read_yaml

ROOT = Path(__file__).resolve().parents[1]
CLI = [sys.executable, "-m", "fundos.cli"]


def run_cli(args, cwd):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(CLI + args, cwd=cwd, text=True, capture_output=True, env=env)


class AgentThreadTests(unittest.TestCase):
    def test_materialize_agent_threads_creates_persistent_thread_for_every_agent(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            roster = read_yaml(REPO_ROOT / "specs" / "agents" / "default-roster.yaml")

            summary = materialize_agent_threads(root, roster)

            self.assertEqual(summary["artifact_type"], "agent_thread_materialization_summary")
            self.assertEqual(summary["agent_count"], 19)
            self.assertEqual(summary["created_or_existing_threads"], 19)
            for agent in roster["agents"]:
                thread_path = root / "memory" / "agents" / agent["id"] / "thread.yaml"
                events_path = root / "memory" / "agents" / agent["id"] / "thread-events.jsonl"
                self.assertTrue(thread_path.exists(), agent["id"])
                self.assertTrue(events_path.exists(), agent["id"])
                doc = yaml.safe_load(thread_path.read_text(encoding="utf-8"))
                self.assertEqual(doc["agent_id"], agent["id"])
                self.assertEqual(doc["artifact_type"], "agent_thread")
                self.assertIn("profile", doc["continuity_scope"])
                self.assertIn("memory", doc["continuity_scope"])
                self.assertFalse(doc["real_trade_allowed"])

    def test_record_run_threads_appends_run_event_and_run_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            run_path = root / "runs" / "thread-run"
            roster = read_yaml(REPO_ROOT / "specs" / "agents" / "default-roster.yaml")
            selected = [
                {"agent_id": "fund_manager", "role": "FundManager"},
                {"agent_id": "tech_growth_analyst", "role": "TechGrowthAnalyst"},
            ]
            materialize_agent_threads(root, roster)

            manifest = record_run_threads(run_path, selected, event_type="run_participation", payload={"input": "机器人"})

            self.assertEqual(manifest["artifact_type"], "run_agent_thread_manifest")
            self.assertEqual(manifest["thread_count"], 2)
            self.assertTrue((run_path / "memory" / "agent-thread-manifest.yaml").exists())
            for item in manifest["threads"]:
                events = [json.loads(line) for line in (root / item["event_log_path"]).read_text(encoding="utf-8").splitlines() if line.strip()]
                self.assertEqual(events[-1]["event_type"], "run_participation")
                self.assertEqual(events[-1]["run_id"], "thread-run")
                self.assertEqual(events[-1]["real_trade_allowed"], False)

    def test_run_and_evolve_update_thread_continuity_and_cli_summary(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            init_result = run_cli(["init"], root)
            self.assertEqual(init_result.returncode, 0, init_result.stderr)
            run_result = run_cli(["run", "--topic", "机器人产业链投资机会"], root)
            self.assertEqual(run_result.returncode, 0, run_result.stderr)
            run_rel = [line for line in run_result.stdout.splitlines() if line.startswith("run_path=")][-1].split("=", 1)[1]
            run_path = root / run_rel

            manifest = yaml.safe_load((run_path / "memory" / "agent-thread-manifest.yaml").read_text(encoding="utf-8"))
            self.assertGreaterEqual(manifest["thread_count"], 7)
            eval_report = yaml.safe_load((run_path / "evaluations" / "evaluation-report.yaml").read_text(encoding="utf-8"))
            self.assertIn("agent_thread_quality", eval_report)
            self.assertIn("agent_threads", eval_report["accepted_outputs"])

            evolve_result = run_cli(["evolve", "--run", str(run_path)], root)
            self.assertEqual(evolve_result.returncode, 0, evolve_result.stderr)
            show_result = run_cli(["threads", "show", "--agent", "fund_manager"], root)
            self.assertEqual(show_result.returncode, 0, show_result.stderr)
            self.assertIn("agent_id=fund_manager", show_result.stdout)
            self.assertIn("event_count=", show_result.stdout)
            self.assertIn("latest_event_type=evolution", show_result.stdout)
            self.assertIn("real_trade_allowed=False", show_result.stdout)

    def test_evaluation_reports_missing_thread_manifest_as_quality_gap(self):
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d) / "runs" / "missing-thread-run"
            run_path.mkdir(parents=True)
            evidence_pack = {"evidence_items": [{"source_id": "public_research", "source_tier": "tier_1_primary_fact"}]}

            report = make_evaluation_for_run("missing-thread-run", [{"agent_id": "fund_manager"}], evidence_pack, run_path)

            self.assertIn("agent_thread_quality", report)
            self.assertEqual(report["agent_thread_quality"]["thread_count"], 0)
            self.assertIn("missing_agent_thread_manifest", report["agent_thread_quality"]["blocking_issues"])


if __name__ == "__main__":
    unittest.main()
