import json
import tempfile
import unittest
from pathlib import Path

import yaml

from fundos.capabilities import append_jsonl
from fundos.capability_regression import load_capability_regression, run_capability_regression
from fundos.evolution import run_evolution_gate, write_jsonl


class CapabilityRegressionTests(unittest.TestCase):
    def test_regression_blocks_accepted_skill_candidate_missing_required_run_artifacts(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            run_path = root / "runs" / "run-regression"
            evo_dir = run_path / "evolution"
            evo_dir.mkdir(parents=True)
            write_jsonl(evo_dir / "candidates.jsonl", [
                {
                    "candidate_id": "cand_skill_regress",
                    "run_id": "run-regression",
                    "source_agent": "learning_curator",
                    "target_agent": "swing_trader",
                    "candidate_type": "skill_update",
                    "target_scope": "skill",
                    "proposal": "增加事件催化后的量价确认 checklist。",
                    "source_basis": [{"evidence_id": "E001", "source_tier": "tier_1_primary_fact"}],
                    "required_tests": ["historical_case_replay", "role_drift_check", "evidence_quality_check"],
                }
            ])

            run_evolution_gate(run_path)
            report = run_capability_regression(run_path)

            self.assertEqual(report["artifact_type"], "capability_regression_report")
            self.assertEqual(report["candidates_total"], 1)
            self.assertEqual(report["passed_candidates"], 0)
            self.assertEqual(report["blocked_candidates"], 1)
            row = report["candidate_results"][0]
            self.assertEqual(row["candidate_id"], "cand_skill_regress")
            self.assertEqual(row["regression_status"], "blocked")
            self.assertIn("missing_artifact:harness/historical-case-replay.yaml", row["blocking_issues"])
            self.assertIn("missing_artifact:harness/agent-harness.yaml", row["blocking_issues"])
            self.assertTrue((run_path / "harness" / "capability-regression.yaml").exists())
            registry_rows = [json.loads(line) for line in (root / "memory" / "agents" / "swing_trader" / "capabilities" / "skill.jsonl").read_text().splitlines() if line.strip()]
            self.assertEqual(registry_rows[0]["application_status"], "blocked_regression")
            self.assertIn("capability_regression_required", registry_rows[0]["required_follow_up_tests"])

    def test_regression_passes_candidate_when_required_artifacts_and_scores_exist(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            run_path = root / "runs" / "run-regression-pass"
            (run_path / "harness").mkdir(parents=True)
            (run_path / "evidence").mkdir(parents=True)
            (run_path / "evaluations").mkdir(parents=True)
            (run_path / "harness" / "historical-case-replay.yaml").write_text(yaml.safe_dump({"case_replay_score": 82, "case_results_total": 3}, allow_unicode=True), encoding="utf-8")
            (run_path / "harness" / "agent-harness.yaml").write_text(yaml.safe_dump({"aggregate_scores": {"role_consistency": 88, "skill_invocation": 91, "context_compression": 84}}, allow_unicode=True), encoding="utf-8")
            (run_path / "evaluations" / "evaluation-report.yaml").write_text(yaml.safe_dump({"source_coverage": {"tier_1_primary_fact": 2}, "dimension_scores": {"evidence_quality": 86}}, allow_unicode=True), encoding="utf-8")
            registry = root / "memory" / "agents" / "fund_manager" / "capabilities" / "workflow.jsonl"
            append_jsonl(registry, [
                {
                    "candidate_id": "cand_workflow_regress",
                    "run_id": "run-regression-pass",
                    "source_agent": "evaluation_harness",
                    "target_agent": "fund_manager",
                    "capability_kind": "workflow",
                    "candidate_type": "workflow_update",
                    "target_scope": "workflow",
                    "application_status": "pending_human_apply",
                    "proposal": "结论前检查 Harness。",
                    "required_tests": ["historical_case_replay", "role_drift_check", "evidence_quality_check"],
                    "controls": ["no_direct_profile_mutation", "no_real_trade_action"],
                }
            ])

            report = run_capability_regression(run_path)

            self.assertEqual(report["passed_candidates"], 1)
            self.assertEqual(report["blocked_candidates"], 0)
            self.assertEqual(report["candidate_results"][0]["regression_status"], "passed")
            rows = [json.loads(line) for line in registry.read_text().splitlines() if line.strip()]
            self.assertEqual(rows[0]["application_status"], "pending_human_apply")
            self.assertEqual(rows[0]["regression_status"], "passed")

    def test_load_capability_regression_returns_default_without_artifact(self):
        with tempfile.TemporaryDirectory() as d:
            report = load_capability_regression(Path(d))
            self.assertEqual(report["regression_status"], "missing")
            self.assertEqual(report["candidates_total"], 0)


if __name__ == "__main__":
    unittest.main()
