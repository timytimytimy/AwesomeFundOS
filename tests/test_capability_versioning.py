import json
import tempfile
import unittest
from pathlib import Path

import yaml

from fundos.capabilities import load_capability_summary
from fundos.evolution import run_evolution_gate, write_jsonl


class CapabilityVersioningTests(unittest.TestCase):
    def test_accepted_skill_candidate_is_versioned_without_mutating_skill_file(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            run_path = root / "runs" / "run-capability"
            evo_dir = run_path / "evolution"
            harness_dir = run_path / "harness"
            eval_dir = run_path / "evaluations"
            skill_dir = root / "skills" / "swing_trader"
            evo_dir.mkdir(parents=True)
            harness_dir.mkdir(parents=True)
            eval_dir.mkdir(parents=True)
            skill_dir.mkdir(parents=True)
            (harness_dir / "historical-case-replay.yaml").write_text(yaml.safe_dump({"case_replay_score": 82, "case_results_total": 3}, allow_unicode=True), encoding="utf-8")
            (harness_dir / "agent-harness.yaml").write_text(yaml.safe_dump({"aggregate_scores": {"role_consistency": 88, "skill_invocation": 90}}, allow_unicode=True), encoding="utf-8")
            (eval_dir / "evaluation-report.yaml").write_text(yaml.safe_dump({"source_coverage": {"tier_1_primary_fact": 2}, "dimension_scores": {"evidence_quality": 86}}, allow_unicode=True), encoding="utf-8")
            skill_path = skill_dir / "SKILL.md"
            original_skill = "# Swing Trader Skill\n\nExisting rules only.\n"
            skill_path.write_text(original_skill, encoding="utf-8")

            write_jsonl(evo_dir / "candidates.jsonl", [
                {
                    "candidate_id": "cand_skill_accept",
                    "run_id": "run-capability",
                    "source_agent": "learning_curator",
                    "target_agent": "swing_trader",
                    "candidate_type": "skill_update",
                    "target_scope": "skill",
                    "proposal": "增加事件催化后的量价确认 checklist，但必须保留一手公告验证。",
                    "source_basis": [
                        {"evidence_id": "E001", "source_tier": "tier_1_primary_fact"},
                        {"evidence_id": "E002", "source_tier": "tier_1_primary_fact"},
                    ],
                    "required_tests": ["historical_case_replay", "role_drift_check", "evidence_quality_check"],
                }
            ])

            results = run_evolution_gate(run_path)

            self.assertEqual(results[0]["decision"], "accept")
            self.assertIn("capability_version", results[0])
            self.assertEqual(skill_path.read_text(encoding="utf-8"), original_skill)

            registry_path = root / "memory" / "agents" / "swing_trader" / "capabilities" / "skill.jsonl"
            org_path = root / "memory" / "organization" / "capability-ledger.jsonl"
            run_queue_path = run_path / "evolution" / "capability-candidates.jsonl"
            summary_path = run_path / "evolution" / "capability-version-summary.yaml"
            self.assertTrue(registry_path.exists())
            self.assertTrue(org_path.exists())
            self.assertTrue(run_queue_path.exists())
            self.assertTrue(summary_path.exists())

            registry_rows = [json.loads(line) for line in registry_path.read_text().splitlines() if line.strip()]
            self.assertEqual(registry_rows[0]["candidate_id"], "cand_skill_accept")
            self.assertEqual(registry_rows[0]["status"], "approved_candidate")
            self.assertEqual(registry_rows[0]["application_status"], "pending_human_apply")
            self.assertFalse(registry_rows[0]["mutated_runtime_skill"])
            self.assertFalse(registry_rows[0]["real_trade_allowed"])

            summary = load_capability_summary(run_path)
            self.assertEqual(summary["approved_candidates"], 1)
            self.assertEqual(summary["pending_human_apply"], 1)
            self.assertEqual(summary["agent_versions"]["swing_trader"], 1)

    def test_quarantined_capability_candidate_stays_in_run_queue_only(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            run_path = root / "runs" / "run-capability-quarantine"
            evo_dir = run_path / "evolution"
            evo_dir.mkdir(parents=True)
            write_jsonl(evo_dir / "candidates.jsonl", [
                {
                    "candidate_id": "cand_skill_quarantine",
                    "run_id": "run-capability-quarantine",
                    "source_agent": "learning_curator",
                    "target_agent": "position_trend_trader",
                    "candidate_type": "skill_update",
                    "target_scope": "skill",
                    "proposal": "把 Serenity 的框架加入交易员 checklist，但尚未做一手验证。",
                    "source_basis": [{"source_id": "serenity_aleabitoreddit", "source_tier": "tier_3_verified_public_practitioner"}],
                    "required_tests": ["historical_case_replay"],
                }
            ])

            results = run_evolution_gate(run_path)

            self.assertEqual(results[0]["decision"], "quarantine")
            self.assertNotIn("capability_version", results[0])
            queue_rows = [json.loads(line) for line in (run_path / "evolution" / "capability-candidates.jsonl").read_text().splitlines() if line.strip()]
            self.assertEqual(queue_rows[0]["status"], "quarantine")
            self.assertIn("primary_evidence_check", queue_rows[0]["required_follow_up_tests"])
            self.assertFalse((root / "memory" / "agents" / "position_trend_trader" / "capabilities" / "skill.jsonl").exists())

            summary = yaml.safe_load((run_path / "evolution" / "capability-version-summary.yaml").read_text())
            self.assertEqual(summary["quarantined_candidates"], 1)
            self.assertEqual(summary["approved_candidates"], 0)

    def test_capability_versioning_is_idempotent_for_same_candidate(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            run_path = root / "runs" / "run-capability-idempotent"
            evo_dir = run_path / "evolution"
            evo_dir.mkdir(parents=True)
            write_jsonl(evo_dir / "candidates.jsonl", [
                {
                    "candidate_id": "cand_workflow_once",
                    "run_id": "run-capability-idempotent",
                    "source_agent": "evaluation_harness",
                    "target_agent": "fund_manager",
                    "candidate_type": "workflow_update",
                    "target_scope": "workflow",
                    "proposal": "投委会结论前必须检查 Tool Harness 和 Learning Source Registry。",
                    "source_basis": [{"evidence_id": "E001", "source_tier": "tier_1_primary_fact"}],
                    "required_tests": ["historical_case_replay", "role_drift_check", "evidence_quality_check"],
                }
            ])

            run_evolution_gate(run_path)
            run_evolution_gate(run_path)

            registry_path = root / "memory" / "agents" / "fund_manager" / "capabilities" / "workflow.jsonl"
            rows = [json.loads(line) for line in registry_path.read_text().splitlines() if line.strip()]
            self.assertEqual([row["candidate_id"] for row in rows], ["cand_workflow_once"])
            summary = load_capability_summary(run_path)
            self.assertEqual(summary["skipped_existing"], 1)


if __name__ == "__main__":
    unittest.main()
