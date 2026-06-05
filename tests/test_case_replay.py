import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from fundos.case_replay import run_case_replay
from fundos.harness import make_evaluation_for_run

ROOT = Path(__file__).resolve().parents[1]
CLI = [sys.executable, "-m", "fundos.cli"]


def run_cli(args, cwd):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(CLI + args, cwd=cwd, text=True, capture_output=True, env=env)


class HistoricalCaseReplayTests(unittest.TestCase):
    def test_run_case_replay_maps_patterns_to_case_results_and_writes_artifact(self):
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d) / "runs" / "run-case"
            (run_path / "learning").mkdir(parents=True)
            (run_path / "harness").mkdir(parents=True)
            (run_path / "learning" / "patterns.yaml").write_text(yaml.safe_dump({
                "patterns": [
                    {
                        "id": "a_share_theme_diffusion_case",
                        "validation_gates": ["historical_case_replay", "evidence_quality_check"],
                        "tags": ["industry", "trading"],
                    },
                    {
                        "id": "serenity_scheme_first_chokepoint",
                        "validation_gates": ["historical_case_replay"],
                        "tags": ["industry"],
                    },
                ]
            }, allow_unicode=True), encoding="utf-8")

            replay = run_case_replay(run_path)

            self.assertEqual(replay["case_replay_version"], "0.2.0")
            self.assertEqual(replay["patterns_replayed"], 2)
            self.assertGreaterEqual(replay["case_results_total"], 2)
            self.assertIn("case_replay_score", replay)
            self.assertTrue((run_path / "harness" / "historical-case-replay.yaml").exists())
            for result in replay["case_results"]:
                self.assertIn("pattern_id", result)
                self.assertIn("case_id", result)
                self.assertIn("fit_score", result)
                self.assertIn("overfit_risk", result)
                self.assertIn("verdict", result)
                self.assertNotEqual(result["verdict"], "direct_mapping_allowed")

    def test_evaluation_includes_case_replay_quality_when_run_artifact_exists(self):
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d) / "runs" / "run-eval"
            (run_path / "learning").mkdir(parents=True)
            (run_path / "harness").mkdir(parents=True)
            (run_path / "portfolio").mkdir(parents=True)
            (run_path / "learning" / "patterns.yaml").write_text(yaml.safe_dump({
                "patterns": [{"id": "a_share_theme_diffusion_case", "validation_gates": ["historical_case_replay"], "tags": ["industry"]}]
            }, allow_unicode=True), encoding="utf-8")
            replay = run_case_replay(run_path)
            evidence_pack = {
                "evidence_items": [
                    {"source_id": "public_research", "source_tier": "tier_1_primary_fact"},
                    {"source_id": "historical_case_library", "source_tier": "tier_2_canonical_framework"},
                ]
            }

            evaluation = make_evaluation_for_run("run-eval", [{"agent_id": "fund_manager"}], evidence_pack, run_path)

            self.assertIn("case_replay_quality", evaluation)
            self.assertEqual(evaluation["case_replay_quality"]["patterns_replayed"], replay["patterns_replayed"])
            self.assertGreater(evaluation["dimension_scores"]["historical_case_replay"], 0)
            self.assertIn("historical_case_replay", evaluation["accepted_outputs"])

    def test_run_command_creates_historical_case_replay_artifact(self):
        with tempfile.TemporaryDirectory() as d:
            tmp_path = Path(d)
            fixture = tmp_path / "research.json"
            fixture.write_text(json.dumps([
                {"title": "机器人公告", "url": "https://www.cninfo.com.cn/new/disclosure/detail", "snippet": "公告验证机器人订单。"}
            ], ensure_ascii=False), encoding="utf-8")

            result = run_cli(["run", "--topic", "机器人产业链投资机会", "--research-fixture", str(fixture)], tmp_path)

            self.assertEqual(result.returncode, 0, result.stderr)
            run_rel = [line for line in result.stdout.splitlines() if line.startswith("run_path=")][-1].split("=", 1)[1]
            run_path = tmp_path / run_rel
            replay_path = run_path / "harness" / "historical-case-replay.yaml"
            self.assertTrue(replay_path.exists())
            replay = yaml.safe_load(replay_path.read_text(encoding="utf-8"))
            evaluation = yaml.safe_load((run_path / "evaluations" / "evaluation-report.yaml").read_text(encoding="utf-8"))
            self.assertGreaterEqual(replay["patterns_replayed"], 1)
            self.assertIn("case_replay_quality", evaluation)
            self.assertIn("historical_case_replay", evaluation["dimension_scores"])


if __name__ == "__main__":
    unittest.main()
