import tempfile
import unittest
from pathlib import Path

import yaml
import json

from fundos.agent_harness import evaluate_agent_harness, write_agent_harness
from fundos.agent_outputs import write_agent_output
from fundos.context import make_context_pack
from fundos.evidence import make_evidence_pack
from fundos.harness import make_evaluation_for_run
from fundos.io import write_yaml
from fundos.os_manifest import write_operating_system_manifest


AGENT = {
    "id": "tech_growth_analyst",
    "name": "林知远",
    "role": "TechGrowthAnalyst",
    "skills": ["supply_chain_chokepoint", "technology_cycle", "research_gap_identification"],
    "tools": ["web_search", "announcement_search", "evidence_pack_reader"],
}


class AgentHarnessTests(unittest.TestCase):
    def test_evaluate_agent_harness_scores_context_skill_and_role_quality(self):
        pack = make_evidence_pack(
            "run-agent-harness",
            "topic",
            "机器人产业链投资机会",
            public_results=[{"title": "机器人公告", "url": "https://www.cninfo.com.cn/new/disclosure/detail", "snippet": "公告验证机器人订单。"}],
        )
        context = make_context_pack("run-agent-harness", AGENT, pack)
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            write_yaml(run_path / "run.yaml", {"run_id": "run-agent-harness", "selected_agents": [{"agent_id": "tech_growth_analyst", "role": "TechGrowthAnalyst"}], "model_records": []})
            write_yaml(run_path / "context" / "tech_growth_analyst.context-pack.yaml", context)
            output = write_agent_output(run_path / "agent_work" / "tech_growth_analyst.md", AGENT, context, "机器人产业链投资机会", pack)
            write_operating_system_manifest(run_path)

            report = evaluate_agent_harness(run_path, selected=[{"agent_id": "tech_growth_analyst", "role": "TechGrowthAnalyst"}])

            self.assertEqual(report["artifact_type"], "agent_harness_report")
            self.assertEqual(report["agent_count"], 1)
            row = report["agent_results"][0]
            self.assertEqual(row["agent_id"], "tech_growth_analyst")
            self.assertGreaterEqual(row["context_compression_quality"]["score"], 70)
            self.assertGreaterEqual(row["skill_invocation_quality"]["score"], 70)
            self.assertGreaterEqual(row["agent_os_contract_quality"]["score"], 90)
            self.assertGreaterEqual(row["role_consistency_quality"]["score"], 70)
            self.assertTrue(row["context_compression_quality"]["evidence_traceability"])
            self.assertTrue(row["skill_invocation_quality"]["required_sections_present"])
            self.assertTrue(row["skill_invocation_quality"]["guardrails_present"])
            self.assertTrue(row["skill_invocation_quality"]["guardrails_applied"])
            self.assertTrue(row["skill_invocation_quality"]["guardrail_safety_respected"])
            self.assertTrue(row["skill_invocation_quality"]["procedure_executed"])
            self.assertTrue(row["skill_invocation_quality"]["quality_gates_checked"])
            self.assertTrue(row["skill_invocation_quality"]["quality_gate_safety_respected"])
            self.assertIn("Guardrails", row["skill_invocation_quality"]["runtime_sections"])
            self.assertIn("Procedure", row["skill_invocation_quality"]["runtime_sections"])
            self.assertIn("Quality Gates", row["skill_invocation_quality"]["runtime_sections"])
            self.assertGreaterEqual(report["aggregate_scores"]["skill_guardrails"], 90)
            self.assertGreaterEqual(report["aggregate_scores"]["skill_execution"], 90)
            self.assertGreaterEqual(report["aggregate_scores"]["agent_os_contract"], 90)
            self.assertIn("skill_guardrails_required", report["controls"])
            self.assertIn("skill_procedure_quality_gates_required", report["controls"])
            self.assertIn("agent_os_contract_required", report["controls"])
            self.assertTrue(row["agent_os_contract_quality"]["valid"])
            self.assertTrue(row["agent_os_contract_quality"]["agent_card_matches_roster"])
            self.assertTrue(row["agent_os_contract_quality"]["skill_references_agent_card"])
            self.assertTrue(row["agent_os_contract_quality"]["tool_policy_matches_roster_tools"])
            self.assertTrue(row["agent_os_contract_quality"]["memory_policy_matches_agent_namespace"])
            self.assertTrue(row["agent_os_contract_quality"]["context_policy_preserves_kol_methodology_boundary"])
            self.assertTrue(row["agent_os_contract_quality"]["safety_boundaries_disabled"])
            self.assertTrue(row["role_consistency_quality"]["agent_card_loaded"])
            self.assertEqual(output["agent_id"], row["agent_id"])

    def test_agent_harness_reads_os_manifest_contract_checks_and_blocks_invalid_contracts(self):
        pack = make_evidence_pack("run-agent-os-contract", "topic", "机器人产业链投资机会")
        context = make_context_pack("run-agent-os-contract", AGENT, pack)
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            write_yaml(run_path / "run.yaml", {"run_id": "run-agent-os-contract", "selected_agents": [{"agent_id": "tech_growth_analyst", "role": "TechGrowthAnalyst"}], "model_records": []})
            write_yaml(run_path / "context" / "tech_growth_analyst.context-pack.yaml", context)
            write_agent_output(run_path / "agent_work" / "tech_growth_analyst.md", AGENT, context, "机器人产业链投资机会", pack)
            manifest = write_operating_system_manifest(run_path)
            manifest["agents"][0]["os_contract_checks"]["valid"] = False
            manifest["agents"][0]["os_contract_checks"]["tool_policy_matches_roster_tools"] = False
            manifest["agents"][0]["os_contract_checks"]["mismatches"] = ["tool_policy_allowed_tools_mismatch"]
            manifest["all_agent_os_contracts_valid"] = False
            manifest["agent_os_contract_summary"]["valid_contracts"] = 0
            manifest["agent_os_contract_summary"]["invalid_contracts"] = 1
            write_yaml(run_path / "system" / "operating-system-manifest.yaml", manifest)

            report = evaluate_agent_harness(run_path, selected=[{"agent_id": "tech_growth_analyst", "role": "TechGrowthAnalyst"}])

        quality = report["agent_results"][0]["agent_os_contract_quality"]
        self.assertFalse(quality["valid"])
        self.assertFalse(quality["tool_policy_matches_roster_tools"])
        self.assertIn("tool_policy_allowed_tools_mismatch", quality["mismatches"])
        self.assertIn("agent_os_contract_invalid", report["agent_results"][0]["blocking_issues"])
        self.assertLess(report["aggregate_scores"]["agent_os_contract"], 60)

    def test_agent_harness_penalizes_missing_runtime_guardrail_application(self):
        pack = make_evidence_pack("run-agent-guardrail-miss", "topic", "机器人产业链投资机会")
        context = make_context_pack("run-agent-guardrail-miss", AGENT, pack)
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            write_yaml(run_path / "context" / "tech_growth_analyst.context-pack.yaml", context)
            output = write_agent_output(run_path / "agent_work" / "tech_growth_analyst.md", AGENT, context, "机器人产业链投资机会", pack)
            output.pop("skill_guardrails_applied", None)
            output["guardrail_checks"] = {"real_trade_disabled": False, "broker_integration_disabled": False}
            write_yaml(run_path / "agent_work" / "tech_growth_analyst.structured.yaml", output)

            report = evaluate_agent_harness(run_path, selected=[{"agent_id": "tech_growth_analyst", "role": "TechGrowthAnalyst"}])

        quality = report["agent_results"][0]["skill_invocation_quality"]
        self.assertTrue(quality["guardrails_present"])
        self.assertFalse(quality["guardrails_applied"])
        self.assertFalse(quality["guardrail_safety_respected"])
        self.assertIn("skill_guardrails_not_applied", report["agent_results"][0]["blocking_issues"])

    def test_agent_harness_blocks_missing_runtime_procedure_and_quality_gates(self):
        pack = make_evidence_pack("run-agent-procedure-gate-miss", "topic", "机器人产业链投资机会")
        context = make_context_pack("run-agent-procedure-gate-miss", AGENT, pack)
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            write_yaml(run_path / "context" / "tech_growth_analyst.context-pack.yaml", context)
            output = write_agent_output(run_path / "agent_work" / "tech_growth_analyst.md", AGENT, context, "机器人产业链投资机会", pack)
            output.pop("procedure_steps_executed", None)
            output.pop("quality_gates_checked", None)
            output["quality_gate_checks"] = {"identity_gate": True, "evidence_gate": False}
            write_yaml(run_path / "agent_work" / "tech_growth_analyst.structured.yaml", output)

            report = evaluate_agent_harness(run_path, selected=[{"agent_id": "tech_growth_analyst", "role": "TechGrowthAnalyst"}])

        quality = report["agent_results"][0]["skill_invocation_quality"]
        self.assertFalse(quality["procedure_executed"])
        self.assertFalse(quality["quality_gates_checked"])
        self.assertFalse(quality["quality_gate_safety_respected"])
        self.assertIn("skill_procedure_or_quality_gates_missing", report["agent_results"][0]["blocking_issues"])

    def test_write_agent_harness_creates_artifact_and_evaluation_summary_reads_it(self):
        pack = make_evidence_pack("run-agent-harness", "topic", "机器人产业链投资机会")
        context = make_context_pack("run-agent-harness", AGENT, pack)
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            write_yaml(run_path / "context" / "tech_growth_analyst.context-pack.yaml", context)
            write_agent_output(run_path / "agent_work" / "tech_growth_analyst.md", AGENT, context, "机器人产业链投资机会", pack)

            report = write_agent_harness(run_path, selected=[{"agent_id": "tech_growth_analyst", "role": "TechGrowthAnalyst"}])
            path = run_path / "harness" / "agent-harness.yaml"
            self.assertTrue(path.exists())
            self.assertIn("aggregate_scores", report)
            self.assertIn("context_compression", report["aggregate_scores"])

            evaluation = make_evaluation_for_run("run-agent-harness", [{"agent_id": "tech_growth_analyst", "role": "TechGrowthAnalyst"}], pack, run_path)
            self.assertIn("agent_harness_quality", evaluation)
            self.assertEqual(evaluation["agent_harness_quality"]["agent_count"], 1)
            self.assertIn("agent_harness", evaluation["accepted_outputs"])

    def test_agent_harness_scores_output_memory_lesson_traceability(self):
        pack = make_evidence_pack("run-agent-memory-trace", "topic", "机器人产业链投资机会")
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            thread_dir = run_path / "memory" / "agents" / "tech_growth_analyst"
            thread_dir.mkdir(parents=True, exist_ok=True)
            (thread_dir / "thread-events.jsonl").write_text(json.dumps({
                "timestamp": "2026-06-06T00:00:00+00:00",
                "event_type": "memory_writeback_applied",
                "agent_id": "tech_growth_analyst",
                "run_id": "run-agent-memory-trace",
                "payload": {"candidate_id": "cand_supply_chain_lesson", "approval_mode": "evolution_gate_v1_auto_controlled"},
                "real_trade_allowed": False,
                "broker_integration": "disabled",
            }, ensure_ascii=False) + "\n", encoding="utf-8")
            context = make_context_pack("run-agent-memory-trace", AGENT, pack, runtime_root=run_path)
            write_yaml(run_path / "context" / "tech_growth_analyst.context-pack.yaml", context)
            write_agent_output(run_path / "agent_work" / "tech_growth_analyst.md", AGENT, context, "机器人产业链投资机会", pack)

            report = write_agent_harness(run_path, selected=[{"agent_id": "tech_growth_analyst", "role": "TechGrowthAnalyst"}])
            evaluation = make_evaluation_for_run("run-agent-memory-trace", [{"agent_id": "tech_growth_analyst", "role": "TechGrowthAnalyst"}], pack, run_path)

            self.assertIn("memory_lesson_traceability", report["aggregate_scores"])
            self.assertGreaterEqual(report["aggregate_scores"]["memory_lesson_traceability"], 90)
            row = report["agent_results"][0]
            quality = row["memory_lesson_traceability_quality"]
            self.assertTrue(quality["accepted_lessons_declared"])
            self.assertTrue(quality["candidate_ids_match_context"])
            self.assertTrue(quality["retrieval_only_usage"])
            self.assertTrue(quality["safety_boundaries_respected"])
            self.assertEqual(quality["accepted_lesson_count"], 1)
            self.assertIn("memory_lesson_traceability_quality", evaluation["agent_harness_quality"])
            self.assertGreaterEqual(evaluation["agent_harness_quality"]["memory_lesson_traceability_quality"], 90)
            self.assertIn("memory_lesson_traceability", evaluation["accepted_outputs"])

    def test_agent_harness_scores_reasoning_layer_separation(self):
        pack = make_evidence_pack(
            "run-agent-reasoning-layer-harness",
            "topic",
            "机器人产业链投资机会",
            public_results=[
                {"title": "机器人公告", "url": "https://www.cninfo.com.cn/new/disclosure/detail", "snippet": "公告验证机器人订单。"},
                {"title": "X讨论", "url": "https://x.com/example/status/robotics", "snippet": "社媒显示机器人热度。"},
            ],
        )
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            context = make_context_pack("run-agent-reasoning-layer-harness", AGENT, pack, runtime_root=run_path)
            write_yaml(run_path / "context" / "tech_growth_analyst.context-pack.yaml", context)
            write_agent_output(run_path / "agent_work" / "tech_growth_analyst.md", AGENT, context, "机器人产业链投资机会", pack)

            report = write_agent_harness(run_path, selected=[{"agent_id": "tech_growth_analyst", "role": "TechGrowthAnalyst"}])
            evaluation = make_evaluation_for_run("run-agent-reasoning-layer-harness", [{"agent_id": "tech_growth_analyst", "role": "TechGrowthAnalyst"}], pack, run_path)

            self.assertIn("reasoning_layer_separation", report["aggregate_scores"])
            self.assertGreaterEqual(report["aggregate_scores"]["reasoning_layer_separation"], 90)
            quality = report["agent_results"][0]["reasoning_layer_separation_quality"]
            self.assertTrue(quality["current_evidence_layer_present"])
            self.assertTrue(quality["hypothesis_layer_present"])
            self.assertTrue(quality["current_evidence_has_traceable_claims"])
            self.assertTrue(quality["hypotheses_have_validation_requirements"])
            self.assertTrue(quality["safety_boundaries_respected"])
            self.assertIn("reasoning_layer_separation_quality", evaluation["agent_harness_quality"])
            self.assertGreaterEqual(evaluation["agent_harness_quality"]["reasoning_layer_separation_quality"], 90)
            self.assertIn("reasoning_layer_separation", evaluation["accepted_outputs"])


if __name__ == "__main__":
    unittest.main()
