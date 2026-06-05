import tempfile
import unittest
from pathlib import Path

import yaml

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


if __name__ == "__main__":
    unittest.main()
