import json
import tempfile
import unittest
from pathlib import Path

from fundos.evolution import evaluate_candidate, run_evolution_gate, write_jsonl


class EvolutionGateTests(unittest.TestCase):
    def test_evaluate_candidate_accepts_testable_primary_evidence_principle_update(self):
        candidate = {
            "candidate_id": "cand_accept",
            "candidate_type": "principle_update",
            "proposal": "所有主题研究必须先列出公告、财报、政策三类一手证据。",
            "source_basis": [
                {"evidence_id": "E001", "source_tier": "tier_1_primary_fact"},
                {"evidence_id": "E002", "source_tier": "tier_1_primary_fact"},
            ],
            "required_tests": ["evidence_quality_check", "role_drift_check"],
            "target_scope": "agent_memory",
        }
        decision = evaluate_candidate(candidate)
        self.assertEqual(decision["decision"], "accept")
        self.assertGreaterEqual(decision["scores"]["source_quality"], 85)
        self.assertGreaterEqual(decision["scores"]["testability"], 70)
        self.assertFalse(decision["memory_write_allowed"])
        self.assertIn("approval_required", decision["controls"])

    def test_evaluate_candidate_rejects_social_buy_signal_and_profile_mutation(self):
        candidate = {
            "candidate_id": "cand_reject",
            "candidate_type": "profile_update",
            "proposal": "把某大V热帖作为直接A股买入信号，并提高交易员风险偏好。",
            "source_basis": [{"evidence_id": "E999", "source_tier": "tier_5_social_signal"}],
            "required_tests": [],
            "target_scope": "core_profile",
        }
        decision = evaluate_candidate(candidate)
        self.assertEqual(decision["decision"], "reject")
        self.assertIn("social_signal_direct_buy", decision["reasons"])
        self.assertIn("core_profile_mutation", decision["reasons"])

    def test_run_evolution_gate_writes_partitioned_jsonl_outputs(self):
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            evo_dir = run_path / "evolution"
            evo_dir.mkdir()
            write_jsonl(evo_dir / "candidates.jsonl", [
                {
                    "candidate_id": "cand_accept",
                    "candidate_type": "principle_update",
                    "proposal": "方法论源只能生成研究问题，结论必须由一手证据验证。",
                    "source_basis": [{"evidence_id": "E001", "source_tier": "tier_1_primary_fact"}],
                    "required_tests": ["evidence_quality_check", "role_drift_check"],
                    "target_scope": "agent_memory",
                },
                {
                    "candidate_id": "cand_quarantine",
                    "candidate_type": "skill_update",
                    "proposal": "把趋势模板加入交易员 checklist，但需要历史案例回放。",
                    "source_basis": [{"evidence_id": "E008", "source_tier": "tier_3_verified_public_practitioner"}],
                    "required_tests": ["historical_case_replay"],
                    "target_scope": "skill",
                },
                {
                    "candidate_id": "cand_reject",
                    "candidate_type": "profile_update",
                    "proposal": "根据X热帖直接买入并放宽风控。",
                    "source_basis": [{"evidence_id": "E777", "source_tier": "tier_5_social_signal"}],
                    "required_tests": [],
                    "target_scope": "core_profile",
                },
            ])

            results = run_evolution_gate(run_path)
            self.assertEqual({row["candidate_id"] for row in results}, {"cand_accept", "cand_quarantine", "cand_reject"})
            for name in ["accepted.jsonl", "quarantine.jsonl", "rejected.jsonl", "evolution-gate-results.jsonl"]:
                self.assertTrue((evo_dir / name).exists(), name)

            accepted = [json.loads(line) for line in (evo_dir / "accepted.jsonl").read_text().splitlines() if line.strip()]
            quarantined = [json.loads(line) for line in (evo_dir / "quarantine.jsonl").read_text().splitlines() if line.strip()]
            rejected = [json.loads(line) for line in (evo_dir / "rejected.jsonl").read_text().splitlines() if line.strip()]
            self.assertEqual([row["candidate_id"] for row in accepted], ["cand_accept"])
            self.assertEqual([row["candidate_id"] for row in quarantined], ["cand_quarantine"])
            self.assertEqual([row["candidate_id"] for row in rejected], ["cand_reject"])
            self.assertIn("historical_case_replay", quarantined[0]["required_follow_up_tests"])


if __name__ == "__main__":
    unittest.main()
