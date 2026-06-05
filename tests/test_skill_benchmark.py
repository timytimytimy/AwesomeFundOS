import json
import tempfile
import unittest
from pathlib import Path

from fundos.io import REPO_ROOT, read_yaml, write_yaml
from fundos.skill_benchmark import (
    load_skill_benchmark_report,
    load_skill_regression_benchmarks,
    run_skill_benchmark,
)
from fundos.harness import make_evaluation_for_run
from fundos.evidence import make_evidence_pack


class SkillBenchmarkTests(unittest.TestCase):
    def test_source_controlled_skill_regression_benchmarks_define_role_families_and_gates(self):
        path = REPO_ROOT / "specs" / "skills" / "regression-benchmarks.yaml"
        self.assertTrue(path.exists(), path)
        spec = load_skill_regression_benchmarks()
        self.assertEqual(spec["benchmark_id"], "skill_regression_benchmarks_v1")
        self.assertIn("global_gates", spec)
        self.assertIn("role_family_benchmarks", spec)
        families = {row["role_family"] for row in spec["role_family_benchmarks"]}
        self.assertTrue({"core_operating", "research", "company", "trading"} <= families)
        gate_ids = {gate["gate_id"] for gate in spec["global_gates"]}
        self.assertTrue({
            "role_consistency",
            "evidence_traceability",
            "context_management",
            "forbidden_output_control",
            "tool_usage_quality",
        } <= gate_ids)
        self.assertFalse(spec["real_trade_allowed"])
        self.assertEqual(spec["broker_integration"], "disabled")

    def test_run_skill_benchmark_scores_agents_and_blocks_low_skill_invocation(self):
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            (run_path / "harness").mkdir(parents=True)
            write_yaml(run_path / "harness" / "agent-harness.yaml", {
                "artifact_type": "agent_harness_report",
                "agent_count": 2,
                "agent_results": [
                    {
                        "agent_id": "tech_growth_analyst",
                        "role": "TechGrowthAnalyst",
                        "overall_score": 88,
                        "skill_invocation_quality": {"score": 92, "required_sections_present": True},
                        "role_consistency_quality": {"score": 86},
                        "context_management_quality": {"score": 84},
                        "tool_policy_quality": {"score": 82, "forbidden_tools_respected": True, "real_trade_disabled": True},
                        "context_compression_quality": {"score": 83, "evidence_traceability": True},
                        "blocking_issues": [],
                    },
                    {
                        "agent_id": "swing_trader",
                        "role": "SwingTrader",
                        "overall_score": 62,
                        "skill_invocation_quality": {"score": 55, "required_sections_present": False},
                        "role_consistency_quality": {"score": 72},
                        "context_management_quality": {"score": 70},
                        "tool_policy_quality": {"score": 80, "forbidden_tools_respected": True, "real_trade_disabled": True},
                        "context_compression_quality": {"score": 75, "evidence_traceability": True},
                        "blocking_issues": ["skill_invocation_score_below_threshold"],
                    },
                ],
            })
            report = run_skill_benchmark(run_path)

            self.assertEqual(report["artifact_type"], "skill_benchmark_report")
            self.assertEqual(report["agents_evaluated"], 2)
            self.assertEqual(report["passed_agents"], 1)
            self.assertEqual(report["blocked_agents"], 1)
            self.assertFalse(report["real_trade_allowed"])
            self.assertTrue((run_path / "harness" / "skill-benchmark.yaml").exists())
            by_agent = {row["agent_id"]: row for row in report["agent_skill_results"]}
            self.assertEqual(by_agent["tech_growth_analyst"]["benchmark_status"], "passed")
            self.assertEqual(by_agent["swing_trader"]["benchmark_status"], "blocked")
            self.assertIn("skill_invocation_below_threshold", by_agent["swing_trader"]["blocking_issues"])
            self.assertIn("context_management", by_agent["tech_growth_analyst"]["gate_scores"])

    def test_skill_benchmark_annotates_capability_regression_candidates(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            run_path = root / "runs" / "run-skill-benchmark"
            (run_path / "harness").mkdir(parents=True)
            write_yaml(run_path / "harness" / "agent-harness.yaml", {
                "artifact_type": "agent_harness_report",
                "agent_count": 1,
                "agent_results": [
                    {
                        "agent_id": "fund_manager",
                        "role": "FundManagerAgent",
                        "overall_score": 90,
                        "skill_invocation_quality": {"score": 94, "required_sections_present": True},
                        "role_consistency_quality": {"score": 91},
                        "context_management_quality": {"score": 88},
                        "tool_policy_quality": {"score": 86, "forbidden_tools_respected": True, "real_trade_disabled": True},
                        "context_compression_quality": {"score": 87, "evidence_traceability": True},
                        "blocking_issues": [],
                    }
                ],
            })
            regression = {
                "artifact_type": "capability_regression_report",
                "candidate_results": [
                    {
                        "candidate_id": "cand_skill_ok",
                        "target_agent": "fund_manager",
                        "capability_kind": "skill",
                        "regression_status": "passed",
                        "blocking_issues": [],
                    }
                ],
            }
            write_yaml(run_path / "harness" / "capability-regression.yaml", regression)

            report = run_skill_benchmark(run_path)

            self.assertEqual(report["capability_candidate_results"][0]["candidate_id"], "cand_skill_ok")
            self.assertEqual(report["capability_candidate_results"][0]["skill_benchmark_status"], "passed")
            self.assertEqual(report["capability_candidate_results"][0]["application_status_after_skill_benchmark"], "pending_human_apply")

    def test_evaluation_reads_skill_benchmark_quality_and_accepts_output(self):
        pack = make_evidence_pack("skill-eval", "topic", "机器人产业链投资机会")
        selected = [{"agent_id": "fund_manager", "role": "FundManagerAgent"}]
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            (run_path / "harness").mkdir(parents=True)
            write_yaml(run_path / "harness" / "skill-benchmark.yaml", {
                "artifact_type": "skill_benchmark_report",
                "overall_score": 89,
                "agents_evaluated": 1,
                "passed_agents": 1,
                "blocked_agents": 0,
                "skill_candidates_evaluated": 1,
                "blocked_skill_candidates": 0,
                "blocking_issues": [],
                "real_trade_allowed": False,
                "broker_integration": "disabled",
            })

            evaluation = make_evaluation_for_run("skill-eval", selected, pack, run_path)

        self.assertIn("skill_benchmark_quality", evaluation)
        self.assertEqual(evaluation["skill_benchmark_quality"]["overall_score"], 89)
        self.assertIn("skill_benchmark", evaluation["accepted_outputs"])


if __name__ == "__main__":
    unittest.main()
