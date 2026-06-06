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
            write_yaml(run_path / "context" / "tech_growth_analyst.context-pack.yaml", context)
            output = write_agent_output(run_path / "agent_work" / "tech_growth_analyst.md", AGENT, context, "机器人产业链投资机会", pack)

            report = evaluate_agent_harness(run_path, selected=[{"agent_id": "tech_growth_analyst", "role": "TechGrowthAnalyst"}])

            self.assertEqual(report["artifact_type"], "agent_harness_report")
            self.assertEqual(report["agent_count"], 1)
            row = report["agent_results"][0]
            self.assertEqual(row["agent_id"], "tech_growth_analyst")
            self.assertGreaterEqual(row["context_compression_quality"]["score"], 70)
            self.assertGreaterEqual(row["skill_invocation_quality"]["score"], 70)
            self.assertGreaterEqual(row["role_consistency_quality"]["score"], 70)
            self.assertTrue(row["context_compression_quality"]["evidence_traceability"])
            self.assertTrue(row["skill_invocation_quality"]["required_sections_present"])
            self.assertTrue(row["role_consistency_quality"]["agent_card_loaded"])
            self.assertEqual(output["agent_id"], row["agent_id"])

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
