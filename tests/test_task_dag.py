import tempfile
import unittest
from pathlib import Path

from fundos.evidence import make_evidence_pack
from fundos.harness import make_evaluation_for_run
from fundos.io import REPO_ROOT, read_yaml, write_yaml
from fundos.task_dag import (
    close_research_gap_followup_with_evidence,
    load_task_dag_harness,
    load_task_dag_spec,
    reconcile_research_gap_followups,
    write_research_gap_followup_result,
    write_task_dag,
)


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

    def test_write_task_dag_materializes_research_gap_followup_tasks(self):
        pack = make_evidence_pack("dag-gap", "topic", "机器人产业链投资机会")
        pack["research_plan_coverage"] = {
            "planned_categories": 6,
            "categories_covered": 4,
            "missing_categories": ["market_data", "case_library"],
            "category_counts": {"announcement": 1, "policy": 1, "news": 1, "social_signal": 1},
            "plan_step_count": 6,
        }
        selected = [
            {"agent_id": "fund_manager", "role": "FundManager"},
            {"agent_id": "position_trend_trader", "role": "Trader"},
            {"agent_id": "review_archivist", "role": "ReviewArchivist"},
        ]
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            write_yaml(run_path / "run.yaml", {"run_id": "dag-gap", "input": {"value": "机器人产业链投资机会"}})

            report = write_task_dag(run_path, selected, pack)

            by_id = {node["node_id"]: node for node in report["nodes"]}
            self.assertIn("research_gap:market_data", by_id)
            self.assertIn("research_gap:case_library", by_id)
            self.assertEqual(by_id["research_gap:market_data"]["owner_agent_id"], "position_trend_trader")
            self.assertEqual(by_id["research_gap:case_library"]["owner_agent_id"], "review_archivist")
            self.assertEqual(by_id["research_gap:market_data"]["status"], "planned")
            self.assertEqual(by_id["research_gap:case_library"]["status"], "planned")
            self.assertIn({"from": "evaluation", "to": "research_gap:market_data"}, report["edges"])
            self.assertIn({"from": "evaluation", "to": "research_gap:case_library"}, report["edges"])
            self.assertEqual(report["research_gap_count"], 2)
            self.assertEqual([task["category"] for task in report["next_research_tasks"]], ["market_data", "case_library"])
            self.assertFalse(report["real_trade_allowed"])
            self.assertEqual(report["broker_integration"], "disabled")

            harness = load_task_dag_harness(run_path)
            self.assertEqual(harness["research_gap_count"], 2)
            self.assertEqual([task["owner_agent_id"] for task in harness["next_research_tasks"]], ["position_trend_trader", "review_archivist"])
            self.assertFalse(harness["real_trade_allowed"])

            task_manifest = read_yaml(run_path / "workflow" / "research-gap-tasks.yaml")
            self.assertEqual(task_manifest["artifact_type"], "research_gap_task_manifest")
            self.assertEqual(task_manifest["research_gap_count"], 2)
            self.assertEqual(task_manifest["tasks"][0]["brief_path"], "follow_up/research_gap_market_data.md")
            self.assertFalse(task_manifest["real_trade_allowed"])
            market_brief = run_path / "follow_up" / "research_gap_market_data.md"
            case_brief = run_path / "follow_up" / "research_gap_case_library.md"
            self.assertTrue(market_brief.exists())
            self.assertTrue(case_brief.exists())
            market_text = market_brief.read_text(encoding="utf-8")
            self.assertIn("owner_agent_id: position_trend_trader", market_text)
            self.assertIn("category: market_data", market_text)
            self.assertIn("Allowed output", market_text)
            self.assertIn("no real trade", market_text.lower())

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

    def test_evaluation_reads_research_gap_followup_results(self):
        pack = make_evidence_pack("dag-followup-eval", "topic", "机器人产业链投资机会")
        pack["research_plan_coverage"] = {
            "planned_categories": 6,
            "categories_covered": 5,
            "missing_categories": ["market_data"],
            "category_counts": {"announcement": 1, "policy": 1, "news": 1, "social_signal": 1, "case_library": 1},
            "plan_step_count": 6,
        }
        selected = [{"agent_id": "position_trend_trader", "role": "Trader"}]
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            write_yaml(run_path / "run.yaml", {"run_id": "dag-followup-eval", "input": {"value": "机器人产业链投资机会"}})
            write_task_dag(run_path, selected, pack)
            task = read_yaml(run_path / "workflow" / "research-gap-tasks.yaml")["tasks"][0]
            write_research_gap_followup_result(run_path, task["task_id"])

            evaluation = make_evaluation_for_run("dag-followup-eval", selected, pack, run_path)

        self.assertIn("research_gap_followups", evaluation["accepted_outputs"])
        self.assertIn("research_gap_followup_quality", evaluation)
        self.assertEqual(evaluation["research_gap_followup_quality"]["result_count"], 1)
        self.assertEqual(evaluation["research_gap_followup_quality"]["owner_agent_count"], 1)
        self.assertTrue(evaluation["research_gap_followup_quality"]["all_safe"])
        self.assertFalse(evaluation["research_gap_followup_quality"]["real_trade_allowed"])
        self.assertEqual(evaluation["dimension_scores"]["research_gap_followup"], 75)

    def test_reconcile_research_gap_followups_updates_manifest_dag_and_harness(self):
        pack = make_evidence_pack("dag-followup-reconcile", "topic", "机器人产业链投资机会")
        pack["research_plan_coverage"] = {
            "planned_categories": 6,
            "categories_covered": 5,
            "missing_categories": ["market_data"],
            "category_counts": {"announcement": 1, "policy": 1, "news": 1, "social_signal": 1, "case_library": 1},
            "plan_step_count": 6,
        }
        selected = [{"agent_id": "position_trend_trader", "role": "Trader"}]
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            write_yaml(run_path / "run.yaml", {"run_id": "dag-followup-reconcile", "input": {"value": "机器人产业链投资机会"}})
            write_task_dag(run_path, selected, pack)
            task = read_yaml(run_path / "workflow" / "research-gap-tasks.yaml")["tasks"][0]
            result = write_research_gap_followup_result(run_path, task["task_id"])

            report = reconcile_research_gap_followups(run_path)

            self.assertEqual(report["artifact_type"], "research_gap_followup_reconciliation")
            self.assertEqual(report["answered_count"], 1)
            self.assertEqual(report["pending_count"], 0)
            self.assertEqual(report["unsafe_blocked_count"], 0)
            self.assertFalse(report["real_trade_allowed"])
            self.assertEqual(report["broker_integration"], "disabled")

            manifest = read_yaml(run_path / "workflow" / "research-gap-tasks.yaml")
            reconciled_task = manifest["tasks"][0]
            self.assertEqual(reconciled_task["status"], "answered_needs_evidence")
            self.assertEqual(reconciled_task["answer_status"], "needs_evidence")
            self.assertEqual(reconciled_task["result_path"], f"follow_up/results/{task['task_id'].replace(':', '_')}.yaml")
            self.assertEqual(reconciled_task["result_category"], "market_data")
            self.assertFalse(reconciled_task["real_trade_allowed"])

            dag = read_yaml(run_path / "workflow" / "task-dag.yaml")
            node = {row["node_id"]: row for row in dag["nodes"]}["research_gap:market_data"]
            self.assertEqual(node["status"], "answered_needs_evidence")
            self.assertEqual(node["answer_status"], "needs_evidence")
            self.assertEqual(node["result_path"], result["result_path"])
            self.assertFalse(node["real_trade_allowed"])

            harness = load_task_dag_harness(run_path)
            self.assertEqual(harness["research_gap_answered_count"], 1)
            self.assertEqual(harness["research_gap_pending_count"], 0)
            self.assertEqual(harness["research_gap_unsafe_blocked_count"], 0)
            self.assertFalse(harness["real_trade_allowed"])

    def test_close_research_gap_followup_with_accepted_evidence_updates_pack_manifest_dag_and_harness(self):
        pack = make_evidence_pack("dag-gap-close", "topic", "机器人产业链投资机会")
        pack["research_plan_coverage"] = {
            "planned_categories": 6,
            "categories_covered": 5,
            "missing_categories": ["market_data"],
            "category_counts": {"announcement": 1, "policy": 1, "news": 1, "social_signal": 1, "case_library": 1},
            "plan_step_count": 6,
        }
        selected = [{"agent_id": "position_trend_trader", "role": "Trader"}]
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            write_yaml(run_path / "run.yaml", {"run_id": "dag-gap-close", "input": {"value": "机器人产业链投资机会"}})
            write_yaml(run_path / "evidence" / "evidence-pack.yaml", pack)
            write_task_dag(run_path, selected, pack)
            task = read_yaml(run_path / "workflow" / "research-gap-tasks.yaml")["tasks"][0]
            write_research_gap_followup_result(run_path, task["task_id"])
            accepted_evidence = {
                "id": "FG001",
                "source_type": "market_data",
                "source_tier": "tier_1_primary_fact",
                "source_id": "accepted_followup_evidence",
                "title": "机器人主题量价摘要",
                "url": "https://example.com/market-data",
                "published_at": "2026-06-06",
                "retrieved_at": "2026-06-06T00:00:00+00:00",
                "raw_excerpt": "成交额放大但波动仍高。",
                "summary": "机器人主题成交额放大但波动仍高。",
                "confidence": "high",
                "claims": [
                    {
                        "claim_id": "CFG001",
                        "claim_text": "机器人主题成交额放大但波动仍高。",
                        "claim_type": "fact",
                        "confidence": "high",
                        "relevant_to": ["trading", "risk"],
                        "supports": [],
                        "contradicts": [],
                    }
                ],
            }

            report = close_research_gap_followup_with_evidence(run_path, task["task_id"], [accepted_evidence])

            self.assertEqual(report["artifact_type"], "research_gap_followup_evidence_closure")
            self.assertEqual(report["closed_count"], 1)
            self.assertEqual(report["accepted_evidence_count"], 1)
            self.assertFalse(report["real_trade_allowed"])
            self.assertEqual(report["broker_integration"], "disabled")

            updated_pack = read_yaml(run_path / "evidence" / "evidence-pack.yaml")
            self.assertTrue(any(item["id"] == "FG001" for item in updated_pack["evidence_items"]))
            self.assertNotIn("market_data", updated_pack["research_plan_coverage"]["missing_categories"])
            self.assertEqual(updated_pack["research_plan_coverage"]["category_counts"]["market_data"], 1)

            manifest = read_yaml(run_path / "workflow" / "research-gap-tasks.yaml")
            reconciled_task = manifest["tasks"][0]
            self.assertEqual(reconciled_task["status"], "closed_by_accepted_evidence")
            self.assertEqual(reconciled_task["closure_status"], "closed_by_accepted_evidence")
            self.assertEqual(reconciled_task["accepted_evidence_ids"], ["FG001"])
            self.assertFalse(reconciled_task["real_trade_allowed"])

            dag = read_yaml(run_path / "workflow" / "task-dag.yaml")
            node = {row["node_id"]: row for row in dag["nodes"]}["research_gap:market_data"]
            self.assertEqual(node["status"], "closed_by_accepted_evidence")
            self.assertEqual(node["accepted_evidence_ids"], ["FG001"])

            harness = load_task_dag_harness(run_path)
            self.assertEqual(harness["research_gap_closed_count"], 1)
            self.assertEqual(harness["research_gap_pending_count"], 0)
            self.assertEqual(harness["research_gap_accepted_evidence_count"], 1)

            regenerated = write_task_dag(run_path, selected, updated_pack)
            regenerated_node = {row["node_id"]: row for row in regenerated["nodes"]}["research_gap:market_data"]
            self.assertEqual(regenerated_node["status"], "closed_by_accepted_evidence")
            self.assertEqual(regenerated_node["accepted_evidence_ids"], ["FG001"])
            manifest_after_regen = read_yaml(run_path / "workflow" / "research-gap-tasks.yaml")
            self.assertEqual(manifest_after_regen["tasks"][0]["status"], "closed_by_accepted_evidence")

    def test_close_research_gap_followup_rejects_weak_or_mismatched_evidence(self):
        pack = make_evidence_pack("dag-gap-reject", "topic", "机器人产业链投资机会")
        pack["research_plan_coverage"] = {
            "planned_categories": 6,
            "categories_covered": 5,
            "missing_categories": ["market_data"],
            "category_counts": {"announcement": 1, "policy": 1, "news": 1, "social_signal": 1, "case_library": 1},
            "plan_step_count": 6,
        }
        selected = [{"agent_id": "position_trend_trader", "role": "Trader"}]
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            write_yaml(run_path / "run.yaml", {"run_id": "dag-gap-reject", "input": {"value": "机器人产业链投资机会"}})
            write_yaml(run_path / "evidence" / "evidence-pack.yaml", pack)
            write_task_dag(run_path, selected, pack)
            task = read_yaml(run_path / "workflow" / "research-gap-tasks.yaml")["tasks"][0]
            weak_evidence = {
                "id": "WEAK001",
                "source_type": "social_signal",
                "source_tier": "tier_5_social_signal",
                "source_id": "accepted_followup_evidence",
                "title": "论坛讨论",
                "summary": "有人说机器人很强。",
                "confidence": "low",
                "claims": [],
            }

            with self.assertRaises(ValueError) as ctx:
                close_research_gap_followup_with_evidence(run_path, task["task_id"], [weak_evidence])

            self.assertIn("evidence_validation_failed", str(ctx.exception))
            manifest = read_yaml(run_path / "workflow" / "research-gap-tasks.yaml")
            self.assertEqual(manifest["tasks"][0]["status"], "planned")
            updated_pack = read_yaml(run_path / "evidence" / "evidence-pack.yaml")
            self.assertFalse(any(item.get("id") == "WEAK001" for item in updated_pack["evidence_items"]))


if __name__ == "__main__":
    unittest.main()
