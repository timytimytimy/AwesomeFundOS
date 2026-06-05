import json
import tempfile
import unittest
from pathlib import Path

from fundos.evolution import run_evolution_gate, write_jsonl
from fundos.memory import load_memory_writeback_summary


class MemoryWritebackTests(unittest.TestCase):
    def test_accepted_candidate_writes_agent_memory_and_ledgers_without_profile_mutation(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            run_path = root / "runs" / "run-accept"
            evo_dir = run_path / "evolution"
            profile_dir = root / "agents" / "risk_manager"
            evo_dir.mkdir(parents=True)
            profile_dir.mkdir(parents=True)
            profile_path = profile_dir / "profile.yaml"
            profile_before = "id: risk_manager\nrisk_preference: low\n"
            profile_path.write_text(profile_before, encoding="utf-8")

            write_jsonl(evo_dir / "candidates.jsonl", [
                {
                    "candidate_id": "cand_accept",
                    "run_id": "run-accept",
                    "source_agent": "evaluation_harness",
                    "target_agent": "risk_manager",
                    "candidate_type": "principle_update",
                    "target_scope": "agent_memory",
                    "proposal": "一手公告证据不足时必须将模拟仓位限制为0并保留复盘任务。",
                    "source_basis": [
                        {"evidence_id": "E001", "source_tier": "tier_1_primary_fact", "rationale": "primary evidence"}
                    ],
                    "required_tests": ["historical_case_replay", "role_drift_check", "evidence_quality_check"],
                    "status": "proposed",
                }
            ])

            results = run_evolution_gate(run_path)

            self.assertEqual(results[0]["decision"], "accept")
            self.assertTrue(results[0]["memory_write_allowed"])
            self.assertEqual(profile_path.read_text(encoding="utf-8"), profile_before)

            memory_path = root / "memory" / "agents" / "risk_manager" / "semantic_memory.md"
            agent_ledger_path = root / "memory" / "agents" / "risk_manager" / "evolution-ledger.jsonl"
            org_ledger_path = root / "memory" / "organization" / "evolution-ledger.jsonl"
            summary_path = run_path / "evolution" / "memory-writeback-summary.yaml"

            self.assertTrue(memory_path.exists())
            self.assertIn("cand_accept", memory_path.read_text(encoding="utf-8"))
            self.assertIn("一手公告证据不足", memory_path.read_text(encoding="utf-8"))
            self.assertTrue(agent_ledger_path.exists())
            self.assertTrue(org_ledger_path.exists())
            self.assertTrue(summary_path.exists())

            agent_rows = [json.loads(line) for line in agent_ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            org_rows = [json.loads(line) for line in org_ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(agent_rows[0]["candidate_id"], "cand_accept")
            self.assertEqual(agent_rows[0]["target_agent"], "risk_manager")
            self.assertEqual(agent_rows[0]["approval_mode"], "evolution_gate_v1_auto_controlled")
            self.assertTrue(agent_rows[0]["reversible"])
            self.assertEqual(org_rows[0]["candidate_id"], "cand_accept")

            summary = load_memory_writeback_summary(run_path)
            self.assertEqual(summary["memory_writes"], 1)
            self.assertEqual(summary["agent_writes"]["risk_manager"], 1)

    def test_quarantined_and_rejected_candidates_do_not_write_memory(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            run_path = root / "runs" / "run-no-write"
            evo_dir = run_path / "evolution"
            evo_dir.mkdir(parents=True)
            write_jsonl(evo_dir / "candidates.jsonl", [
                {
                    "candidate_id": "cand_quarantine",
                    "run_id": "run-no-write",
                    "source_agent": "learning_curator",
                    "target_agent": "swing_trader",
                    "candidate_type": "skill_update",
                    "target_scope": "agent_memory",
                    "proposal": "把某大V交易口号加入交易员 checklist，但还需要历史验证。",
                    "source_basis": [{"evidence_id": "E008", "source_tier": "tier_3_verified_public_practitioner"}],
                    "required_tests": ["historical_case_replay", "role_drift_check", "evidence_quality_check"],
                },
                {
                    "candidate_id": "cand_reject",
                    "run_id": "run-no-write",
                    "source_agent": "learning_curator",
                    "target_agent": "fund_manager",
                    "candidate_type": "profile_update",
                    "target_scope": "core_profile",
                    "proposal": "根据X热帖直接买入并放宽风控。",
                    "source_basis": [{"evidence_id": "E777", "source_tier": "tier_5_social_signal"}],
                    "required_tests": [],
                },
            ])

            results = run_evolution_gate(run_path)

            self.assertEqual({row["decision"] for row in results}, {"quarantine", "reject"})
            self.assertFalse((root / "memory" / "agents" / "swing_trader" / "semantic_memory.md").exists())
            self.assertFalse((root / "memory" / "agents" / "fund_manager" / "semantic_memory.md").exists())
            summary = load_memory_writeback_summary(run_path)
            self.assertEqual(summary["memory_writes"], 0)
            self.assertEqual(summary["skipped_non_accepted"], 2)

    def test_evolution_writeback_is_idempotent_for_same_candidate(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            run_path = root / "runs" / "run-idempotent"
            evo_dir = run_path / "evolution"
            evo_dir.mkdir(parents=True)
            write_jsonl(evo_dir / "candidates.jsonl", [
                {
                    "candidate_id": "cand_once",
                    "run_id": "run-idempotent",
                    "source_agent": "evaluation_harness",
                    "target_agent": "risk_manager",
                    "candidate_type": "principle_update",
                    "target_scope": "agent_memory",
                    "proposal": "若关键风险证据缺失，模拟仓位必须保持0直到复核完成。",
                    "source_basis": [{"evidence_id": "E001", "source_tier": "tier_1_primary_fact"}],
                    "required_tests": ["historical_case_replay", "role_drift_check", "evidence_quality_check"],
                }
            ])

            run_evolution_gate(run_path)
            run_evolution_gate(run_path)

            memory_path = root / "memory" / "agents" / "risk_manager" / "semantic_memory.md"
            ledger_path = root / "memory" / "agents" / "risk_manager" / "evolution-ledger.jsonl"
            memory_text = memory_path.read_text(encoding="utf-8")
            ledger_rows = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(memory_text.count("cand_once"), 1)
            self.assertEqual([row["candidate_id"] for row in ledger_rows], ["cand_once"])
            summary = load_memory_writeback_summary(run_path)
            self.assertEqual(summary["memory_writes"], 0)
            self.assertEqual(summary["skipped_existing"], 1)


if __name__ == "__main__":
    unittest.main()
