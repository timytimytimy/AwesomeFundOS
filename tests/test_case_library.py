import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from fundos.case_library import build_case_library_index, load_case_library, write_run_case_library
from fundos.case_replay import run_case_replay
from fundos.harness import make_evaluation_for_run
from fundos.io import read_yaml
from fundos.system_audit import validate_runtime_schema

ROOT = Path(__file__).resolve().parents[1]
CLI = [sys.executable, "-m", "fundos.cli"]


def run_cli(args, cwd):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(CLI + args, cwd=cwd, text=True, capture_output=True, env=env)


class HistoricalCaseLibraryTests(unittest.TestCase):
    def test_case_library_schemas_validate_source_and_runtime_artifacts(self):
        schema_dir = ROOT / "specs" / "schemas"
        manifest_schema = schema_dir / "historical-case-library-manifest.schema.yaml"
        case_schema = schema_dir / "historical-case.schema.yaml"
        index_schema = schema_dir / "case-library-index.schema.yaml"
        replay_schema = schema_dir / "historical-case-replay.schema.yaml"

        source_manifest = read_yaml(ROOT / "specs" / "cases" / "historical-case-library.yaml")
        self.assertTrue(validate_runtime_schema(manifest_schema, source_manifest)["ok"])
        for rel in source_manifest["case_files"]:
            with self.subTest(case_file=rel):
                source_case = read_yaml(ROOT / "specs" / "cases" / rel)
                result = validate_runtime_schema(case_schema, source_case)
                self.assertTrue(result["ok"], result["schema_errors"])

        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d) / "runs" / "case-schema"
            (run_path / "learning").mkdir(parents=True)
            (run_path / "harness").mkdir(parents=True)
            (run_path / "learning" / "patterns.yaml").write_text(yaml.safe_dump({
                "patterns": [{
                    "id": "serenity_scheme_first_chokepoint",
                    "validation_gates": ["historical_case_replay"],
                    "tags": ["industry", "company", "chokepoint"],
                    "target_agents": ["tech_growth_analyst"],
                }]
            }, allow_unicode=True), encoding="utf-8")

            replay = run_case_replay(run_path)
            index = read_yaml(run_path / "learning" / "case-library-index.yaml")

            index_result = validate_runtime_schema(index_schema, index)
            self.assertTrue(index_result["ok"], index_result["schema_errors"])
            replay_result = validate_runtime_schema(replay_schema, replay)
            self.assertTrue(replay_result["ok"], replay_result["schema_errors"])
            self.assertFalse(replay["real_trade_allowed"])
            self.assertEqual(replay["broker_integration"], "disabled")
            for row in replay["case_results"]:
                self.assertFalse(row["real_trade_allowed"])
                self.assertEqual(row["broker_integration"], "disabled")

    def test_source_controlled_case_library_has_required_case_types_and_controls(self):
        library = load_case_library()

        self.assertEqual(library["artifact_type"], "historical_case_library")
        self.assertGreaterEqual(library["case_count"], 8)
        case_types = {case["case_type"] for case in library["cases"]}
        self.assertTrue({
            "early_compounder_identification",
            "theme_diffusion",
            "supply_chain_chokepoint",
            "fraud_blowup",
            "bubble_breakdown",
            "policy_driven_cycle",
            "turnaround",
            "failed_breakout",
            "kol_thesis_failure",
            "methodology_transfer_failure",
        }.issubset(case_types))
        self.assertIn("direct_case_mapping_forbidden", library["controls"])
        self.assertIn("case_library_is_training_and_evaluation_not_trade_signal", library["controls"])
        for case in library["cases"]:
            with self.subTest(case_id=case["case_id"]):
                for key in [
                    "case_id",
                    "case_type",
                    "market",
                    "time_range",
                    "market_state",
                    "summary",
                    "evidence_requirements",
                    "known_lessons",
                    "failure_modes",
                    "replay_questions",
                    "applicable_agents",
                    "forbidden_uses",
                ]:
                    self.assertIn(key, case)
                self.assertIn("direct_buy_sell_signal", case["forbidden_uses"])
                self.assertFalse(case["real_trade_allowed"])

    def test_build_case_library_index_and_write_run_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d) / "runs" / "case-index"
            index = write_run_case_library(run_path)

            self.assertEqual(index["artifact_type"], "historical_case_library_index")
            self.assertGreaterEqual(index["case_count"], 8)
            self.assertIn("theme_diffusion", index["case_type_counts"])
            self.assertIn("tech_growth_analyst", index["agent_case_counts"])
            self.assertTrue((run_path / "learning" / "case-library-index.yaml").exists())
            self.assertFalse(index["real_trade_allowed"])

    def test_case_replay_uses_source_controlled_case_library_and_scores_coverage(self):
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d) / "runs" / "case-replay-library"
            (run_path / "learning").mkdir(parents=True)
            (run_path / "learning" / "patterns.yaml").write_text(yaml.safe_dump({
                "patterns": [
                    {
                        "id": "serenity_scheme_first_chokepoint",
                        "validation_gates": ["historical_case_replay"],
                        "tags": ["industry", "company", "chokepoint"],
                        "target_agents": ["tech_growth_analyst", "advanced_manufacturing_analyst"],
                    },
                    {
                        "id": "minervini_trend_template",
                        "validation_gates": ["historical_case_replay"],
                        "tags": ["trading", "risk", "failed_breakout"],
                        "target_agents": ["position_trend_trader"],
                    },
                ]
            }, allow_unicode=True), encoding="utf-8")

            replay = run_case_replay(run_path)

            self.assertEqual(replay["case_replay_version"], "0.2.0")
            self.assertGreaterEqual(replay["cases_available"], 8)
            self.assertIn("case_library_coverage", replay)
            coverage = replay["case_library_coverage"]
            self.assertGreaterEqual(coverage["matched_case_types"], 2)
            self.assertGreaterEqual(coverage["agent_coverage"]["position_trend_trader"], 1)
            self.assertIn("case_library_is_training_and_evaluation_not_trade_signal", replay["controls"])
            self.assertTrue((run_path / "learning" / "case-library-index.yaml").exists())
            result = next(row for row in replay["case_results"] if row["pattern_id"] == "minervini_trend_template")
            self.assertIn("case_evidence_requirements", result)
            self.assertIn("replay_questions", result)
            self.assertEqual(result["real_trade_allowed"], False)

    def test_evaluation_reports_case_library_coverage(self):
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d) / "runs" / "case-eval-library"
            (run_path / "learning").mkdir(parents=True)
            (run_path / "learning" / "patterns.yaml").write_text(yaml.safe_dump({
                "patterns": [{
                    "id": "serenity_scheme_first_chokepoint",
                    "validation_gates": ["historical_case_replay"],
                    "tags": ["industry", "company", "chokepoint"],
                    "target_agents": ["tech_growth_analyst"],
                }]
            }, allow_unicode=True), encoding="utf-8")
            replay = run_case_replay(run_path)
            evidence_pack = {"evidence_items": [{"source_id": "public_research", "source_tier": "tier_1_primary_fact"}]}

            evaluation = make_evaluation_for_run("case-eval-library", [{"agent_id": "tech_growth_analyst"}], evidence_pack, run_path)

            self.assertIn("case_library_quality", evaluation)
            self.assertEqual(evaluation["case_library_quality"]["case_count"], replay["cases_available"])
            self.assertGreaterEqual(evaluation["case_library_quality"]["matched_case_types"], 1)
            self.assertIn("case_library", evaluation["accepted_outputs"])

    def test_cases_list_cli_prints_library_summary(self):
        result = run_cli(["cases", "list"], ROOT)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("case_count=", result.stdout)
        self.assertIn("theme_diffusion", result.stdout)
        self.assertIn("real_trade_allowed=False", result.stdout)


if __name__ == "__main__":
    unittest.main()
