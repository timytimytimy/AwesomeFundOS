import tempfile
import unittest
from pathlib import Path

from fundos.evidence import make_evidence_pack
from fundos.harness import make_evaluation_for_run
from fundos.io import REPO_ROOT, read_yaml, write_yaml
from fundos.task_dag import load_task_dag_harness, load_task_dag_spec, write_task_dag


class ResearchTaskDagTests(unittest.TestCase):
    def test_source_controlled_task_dag_spec_defines_org_workflow_and_controls(self):
        path = REPO_ROOT / "specs" / "workflows" / "research-task-dag.yaml"
        self.assertTrue(path.exists(), path)
        spec = load_task_dag_spec()
        self.assertEqual(spec["workflow_id"], "research_task_dag_v1")
        node_ids = {node["node_id"] for node in spec["nodes"]}
        self.assertTrue({
            "task_intake",
            "agent_staffing",
            "evidence_retrieval",
            "tool_adapter_manifest",
            "context_packaging",
            "agent_analysis",
            "committee_collaboration",
            "pm_style_competition",
            "risk_review",
            "market_state_recognition",
            "portfolio_review",
            "evaluation",
            "evolution_candidate_generation",
        } <= node_ids)
        self.assertIn("no_real_trade_action", spec["controls"])
        self.assertIn("broker_integration_disabled", spec["controls"])
        self.assertIn("human_approval_required_for_evolution_apply", spec["controls"])
        self.assertFalse(spec["real_trade_allowed"])
        self.assertEqual(spec["broker_integration"], "disabled")

    def test_write_task_dag_materializes_runtime_dag_and_harness(self):
        pack = make_evidence_pack("dag-run", "topic", "机器人产业链投资机会")
        selected = [
            {"agent_id": "fund_manager", "role": "FundManager"},
            {"agent_id": "tech_growth_analyst", "role": "IndustryAnalyst"},
            {"agent_id": "position_trend_trader", "role": "Trader"},
            {"agent_id": "risk_manager", "role": "RiskManager"},
            {"agent_id": "bear_debater", "role": "BearDebater"},
        ]
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            (run_path / "run.yaml").parent.mkdir(parents=True, exist_ok=True)
            write_yaml(run_path / "run.yaml", {"run_id": "dag-run", "input": {"value": "机器人产业链投资机会"}})
            write_yaml(run_path / "evidence" / "evidence-pack.yaml", pack)
            write_yaml(run_path / "tools" / "tool-adapter-manifest.yaml", {"artifact_type": "tool_adapter_contract_report"})
            write_yaml(run_path / "harness" / "agent-harness.yaml", {"artifact_type": "agent_harness_report"})
            write_yaml(run_path / "committee" / "pm-competition.yaml", {"artifact_type": "pm_style_competition_report"})
            write_yaml(run_path / "harness" / "market-state.yaml", {"artifact_type": "market_state_report", "subjects_evaluated": 1})
            write_yaml(run_path / "portfolio" / "portfolio-review.yaml", {"artifact_type": "portfolio_review", "reviewed_actions": 1})

            report = write_task_dag(run_path, selected, pack)

            self.assertEqual(report["artifact_type"], "research_task_dag")
            self.assertEqual(report["run_id"], "dag-run")
            self.assertGreaterEqual(report["node_count"], 13)
            self.assertGreaterEqual(report["edge_count"], 12)
            self.assertEqual(report["blocked_node_count"], 0)
            self.assertGreaterEqual(report["task_dag_quality_score"], 85)
            self.assertFalse(report["real_trade_allowed"])
            self.assertEqual(report["broker_integration"], "disabled")
            self.assertTrue((run_path / "workflow" / "task-dag.yaml").exists())
            self.assertTrue((run_path / "harness" / "task-dag-harness.yaml").exists())

            dag = read_yaml(run_path / "workflow" / "task-dag.yaml")
            by_id = {node["node_id"]: node for node in dag["nodes"]}
            self.assertEqual(by_id["agent_analysis"]["assigned_agents"], [row["agent_id"] for row in selected])
            self.assertIn("context_packaging", by_id["agent_analysis"]["depends_on"])
            self.assertIn("risk_review", by_id["portfolio_review"]["depends_on"])

            harness = load_task_dag_harness(run_path)
            self.assertEqual(harness["artifact_type"], "research_task_dag_harness")
            self.assertEqual(harness["task_dag_quality_score"], report["task_dag_quality_score"])
            self.assertTrue(harness["topological_order_valid"])
            self.assertFalse(harness["real_trade_allowed"])

    def test_evaluation_reads_task_dag_quality_and_accepts_output(self):
        pack = make_evidence_pack("dag-eval", "topic", "机器人产业链投资机会")
        selected = [{"agent_id": "fund_manager", "role": "FundManager"}]
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            write_yaml(run_path / "harness" / "task-dag-harness.yaml", {
                "artifact_type": "research_task_dag_harness",
                "task_dag_quality_score": 91,
                "node_count": 14,
                "edge_count": 15,
                "blocked_node_count": 0,
                "topological_order_valid": True,
                "missing_artifacts": [],
                "controls": ["no_real_trade_action", "broker_integration_disabled"],
                "real_trade_allowed": False,
                "broker_integration": "disabled",
            })

            evaluation = make_evaluation_for_run("dag-eval", selected, pack, run_path)

        self.assertIn("task_dag_quality", evaluation)
        self.assertEqual(evaluation["task_dag_quality"]["task_dag_quality_score"], 91)
        self.assertIn("task_dag", evaluation["accepted_outputs"])
        self.assertEqual(evaluation["dimension_scores"]["workflow_orchestration"], 91)


if __name__ == "__main__":
    unittest.main()
