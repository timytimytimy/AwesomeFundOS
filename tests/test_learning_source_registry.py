import tempfile
import unittest
from pathlib import Path

import yaml

from fundos.learning import build_learning_source_registry, write_run_learning_source_registry
from fundos.evolution import evaluate_candidate, run_evolution_gate, write_jsonl


class LearningSourceRegistryTests(unittest.TestCase):
    def test_registry_classifies_sources_and_enforces_learning_boundaries(self):
        registry = build_learning_source_registry()

        self.assertEqual(registry["artifact_type"], "learning_source_registry")
        self.assertGreaterEqual(registry["source_count"], 10)
        self.assertIn("tier_3_verified_public_practitioner", registry["source_tier_counts"])
        self.assertIn("public_practitioner", registry["source_type_counts"])
        self.assertEqual(registry["boundary_policy"]["real_trade_allowed"], False)

        serenity = next(source for source in registry["sources"] if source["id"] == "serenity_aleabitoreddit")
        self.assertIn("research_lens", serenity["allowed_learning_outputs"])
        self.assertIn("direct_a_share_buy_signal", serenity["not_allowed_outputs"])
        self.assertIn("primary_evidence_check", serenity["validation_required"])
        self.assertEqual(serenity["adoption_policy"], "methodology_only_until_validated")
        self.assertIn("target_market_adaptation", serenity["required_gates_for_evolution"])
        self.assertTrue(serenity["requires_primary_validation"])

    def test_write_run_learning_source_registry_materializes_artifact(self):
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            registry = write_run_learning_source_registry(run_path)
            path = run_path / "learning" / "source-registry.yaml"

            self.assertTrue(path.exists())
            doc = yaml.safe_load(path.read_text())
            self.assertEqual(doc["source_count"], registry["source_count"])
            self.assertIn("historical_case_replay", doc["required_default_gates"])
            self.assertIn("no_direct_trade_signal", doc["boundary_policy"]["controls"])

    def test_evolution_gate_blocks_candidate_missing_source_registry_gates(self):
        candidate = {
            "candidate_id": "cand_missing_registry_gate",
            "candidate_type": "principle_update",
            "proposal": "把 Serenity 的瓶颈映射方法加入产业研究 checklist。",
            "source_basis": [{"source_id": "serenity_aleabitoreddit", "source_tier": "tier_3_verified_public_practitioner"}],
            "required_tests": ["historical_case_replay"],
            "target_scope": "agent_memory",
        }

        decision = evaluate_candidate(candidate)

        self.assertEqual(decision["decision"], "quarantine")
        self.assertIn("missing_source_registry_required_gate", decision["reasons"])
        self.assertIn("primary_evidence_check", decision["required_follow_up_tests"])
        self.assertIn("target_market_adaptation", decision["required_follow_up_tests"])

    def test_evolution_gate_accepts_practitioner_candidate_after_registry_gates(self):
        candidate = {
            "candidate_id": "cand_serenity_validated",
            "candidate_type": "principle_update",
            "proposal": "产业研究先做系统架构和瓶颈拆解，再用公告、财报和政策验证。",
            "source_basis": [
                {"source_id": "serenity_aleabitoreddit", "source_tier": "tier_3_verified_public_practitioner"},
                {"evidence_id": "E001", "source_tier": "tier_1_primary_fact"},
                {"evidence_id": "E002", "source_tier": "tier_1_primary_fact"},
            ],
            "required_tests": ["historical_case_replay", "primary_evidence_check", "target_market_adaptation", "bear_case_review", "role_drift_check", "evidence_quality_check"],
            "target_scope": "agent_memory",
        }

        decision = evaluate_candidate(candidate)

        self.assertEqual(decision["decision"], "accept")
        self.assertNotIn("missing_source_registry_required_gate", decision["reasons"])
        self.assertIn("source_registry_gate_check", decision["controls"])

    def test_run_evolution_gate_writes_source_registry_decisions(self):
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            evo_dir = run_path / "evolution"
            evo_dir.mkdir(parents=True)
            write_jsonl(evo_dir / "candidates.jsonl", [
                {
                    "candidate_id": "cand_missing_registry_gate",
                    "candidate_type": "principle_update",
                    "proposal": "把某大V框架直接加入研究原则，但尚未做一手验证。",
                    "source_basis": [{"source_id": "serenity_aleabitoreddit", "source_tier": "tier_3_verified_public_practitioner"}],
                    "required_tests": ["historical_case_replay"],
                    "target_scope": "agent_memory",
                }
            ])

            results = run_evolution_gate(run_path)

            self.assertEqual(results[0]["decision"], "quarantine")
            self.assertTrue((run_path / "learning" / "source-registry.yaml").exists())
            self.assertIn("missing_source_registry_required_gate", results[0]["reasons"])


if __name__ == "__main__":
    unittest.main()
