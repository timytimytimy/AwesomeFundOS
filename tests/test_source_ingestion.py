import json
import tempfile
import unittest
from pathlib import Path

import yaml

from fundos.harness import make_evaluation_for_run
from fundos.io import REPO_ROOT
from fundos.source_ingestion import ingest_source_candidates, load_ingestion_report
from fundos.system_audit import validate_runtime_schema


class SourceIngestionTests(unittest.TestCase):
    def test_source_acquisition_specs_exist_and_define_quarantine_pipeline(self):
        root = Path("specs/learning")
        acquisition = yaml.safe_load((root / "source-acquisition.yaml").read_text(encoding="utf-8"))
        pipeline = yaml.safe_load((root / "ingestion-pipeline.yaml").read_text(encoding="utf-8"))
        review = yaml.safe_load((root / "source-review-protocol.yaml").read_text(encoding="utf-8"))

        categories = {item["id"] for item in acquisition["source_categories"]}
        self.assertTrue({
            "public_practitioner",
            "canonical_framework",
            "book",
            "course",
            "historical_case",
            "social_signal",
        }.issubset(categories))

        stages = [stage["id"] for stage in pipeline["pipeline_stages"]]
        self.assertEqual(stages, [
            "intake",
            "classification",
            "copyright_boundary_check",
            "source_tier_assignment",
            "quarantine",
            "pattern_candidate_generation",
            "review",
            "evolution_candidate_creation",
        ])

        controls = set(acquisition["global_controls"] + pipeline["global_controls"] + review["mandatory_controls"])
        self.assertIn("no_direct_trade_signal", controls)
        self.assertIn("no_copied_paid_text", controls)
        self.assertIn("primary_evidence_validation_required", controls)
        self.assertIn("historical_case_replay_required", controls)
        self.assertIn("social_or_kol_cannot_direct_buy_sell", controls)

    def test_ingest_source_candidates_classifies_and_quarantines_learning_sources(self):
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            candidates = [
                {
                    "source_id": "serenity_x_thread_robotics",
                    "display_name": "Serenity robotics X thread",
                    "source_type": "public_practitioner",
                    "url": "https://x.com/aleabitoreddit/status/123",
                    "author": "Serenity",
                    "summary": "机器人产业链瓶颈研究思路",
                    "claims": ["先从系统架构找瓶颈，再映射公司"],
                    "requested_outputs": ["research_lens", "checklist"],
                    "target_agents": ["tech_growth_analyst", "advanced_manufacturing_analyst"],
                },
                {
                    "source_id": "unknown_hot_tip",
                    "source_type": "social_signal",
                    "url": "https://x.com/foo/status/999",
                    "summary": "直接买入某股票",
                    "claims": ["直接买入"],
                    "requested_outputs": ["direct_buy_signal"],
                },
            ]

            report = ingest_source_candidates(run_path, candidates)

            self.assertEqual(report["artifact_type"], "source_ingestion_report")
            self.assertEqual(report["ingested_sources"], 2)
            self.assertEqual(report["quarantined_sources"], 1)
            self.assertEqual(report["pattern_candidates"], 1)
            self.assertEqual(report["evolution_candidates"], 1)
            self.assertTrue(report["direct_trade_signal_blocked"])
            self.assertFalse(report["real_trade_allowed"])

            source_rows = read_jsonl(run_path / "learning" / "source-candidates.jsonl")
            quarantine_rows = read_jsonl(run_path / "learning" / "source-quarantine.jsonl")
            pattern_rows = read_jsonl(run_path / "learning" / "pattern-candidates.jsonl")
            evolution_rows = read_jsonl(run_path / "evolution" / "candidates.jsonl")

            self.assertEqual(len(source_rows), 2)
            source_schema = REPO_ROOT / "specs" / "schemas" / "source-candidate.schema.yaml"
            pattern_schema = REPO_ROOT / "specs" / "schemas" / "pattern-candidate.schema.yaml"
            for row in source_rows + quarantine_rows:
                schema_result = validate_runtime_schema(source_schema, row)
                self.assertTrue(schema_result["ok"], schema_result)
            for row in pattern_rows:
                schema_result = validate_runtime_schema(pattern_schema, row)
                self.assertTrue(schema_result["ok"], schema_result)
            serenity = next(row for row in source_rows if row["source_id"] == "serenity_x_thread_robotics")
            self.assertEqual(serenity["source_tier"], "tier_3_verified_public_practitioner")
            self.assertIn("research_lens", serenity["allowed_learning_outputs"])
            self.assertIn("direct_buy_signal", serenity["not_allowed_outputs"])
            self.assertEqual(serenity["classification_status"], "quarantine")

            hot_tip = quarantine_rows[0]
            self.assertEqual(hot_tip["source_id"], "unknown_hot_tip")
            self.assertIn("direct_trade_signal", hot_tip["violations"])
            self.assertIn("requested_forbidden_output", hot_tip["violations"])

            self.assertEqual(len(pattern_rows), 1)
            pattern = pattern_rows[0]
            self.assertEqual(pattern["status"], "quarantine")
            self.assertIn("checklist", pattern["allowed_learning_outputs"])
            self.assertIn("direct_buy_signal", pattern["not_allowed_outputs"])
            self.assertTrue({
                "historical_case_replay",
                "primary_evidence_check",
                "role_drift_check",
                "evidence_quality_check",
            }.issubset(set(pattern["required_gates"])))

            self.assertEqual(len(evolution_rows), 1)
            evo = evolution_rows[0]
            self.assertIn(evo["candidate_type"], {"skill_update", "principle_update"})
            self.assertIn(evo["target_scope"], {"agent_memory", "workflow"})
            self.assertEqual(evo["source_basis"][0]["source_id"], "serenity_x_thread_robotics")
            self.assertEqual(evo["source_basis"][0]["source_tier"], "tier_3_verified_public_practitioner")
            self.assertTrue(set(pattern["required_gates"]).issubset(set(evo["required_tests"])))
            self.assertEqual(evo["status"], "proposed")
            self.assertFalse(evo["real_trade_allowed"])

            loaded = load_ingestion_report(run_path)
            self.assertEqual(loaded["report_path"], "learning/source-ingestion-report.yaml")
            self.assertEqual(loaded["pattern_candidates"], 1)

    def test_run_ingestion_is_read_by_evaluation_harness(self):
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            ingest_source_candidates(run_path, [
                {
                    "source_id": "serenity_x_thread_robotics",
                    "display_name": "Serenity robotics X thread",
                    "source_type": "public_practitioner",
                    "url": "https://x.com/aleabitoreddit/status/123",
                    "author": "Serenity",
                    "summary": "机器人产业链瓶颈研究思路",
                    "claims": ["先从系统架构找瓶颈，再映射公司"],
                    "requested_outputs": ["research_lens", "checklist"],
                    "target_agents": ["tech_growth_analyst"],
                },
                {
                    "source_id": "unknown_hot_tip",
                    "source_type": "social_signal",
                    "summary": "直接买入某股票",
                    "claims": ["直接买入"],
                    "requested_outputs": ["direct_buy_signal"],
                },
            ])
            evidence_pack = {
                "evidence_items": [
                    {"evidence_id": "E1", "source_id": "public_research", "source_tier": "tier_1_primary_fact"}
                ]
            }
            report = make_evaluation_for_run(
                "run_source_ingestion",
                [{"agent_id": "tech_growth_analyst"}],
                evidence_pack,
                run_path,
            )

            self.assertIn("source_ingestion_quality", report)
            quality = report["source_ingestion_quality"]
            self.assertEqual(quality["ingested_sources"], 2)
            self.assertEqual(quality["quarantined_sources"], 1)
            self.assertEqual(quality["pattern_candidates"], 1)
            self.assertEqual(quality["evolution_candidates"], 1)
            self.assertTrue(quality["direct_trade_signal_blocked"])
            self.assertIn("source_ingestion", report["accepted_outputs"])


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


if __name__ == "__main__":
    unittest.main()
