import tempfile
import unittest
from pathlib import Path

import yaml

from fundos.evidence import make_evidence_pack
from fundos.harness import make_evaluation_for_run
from fundos.io import write_yaml
from fundos.tool_harness import evaluate_tool_harness, write_tool_harness


class ToolHarnessTests(unittest.TestCase):
    def test_evaluate_tool_harness_scores_source_adapters_and_kol_boundaries(self):
        pack = make_evidence_pack(
            "run-tool-harness",
            "topic",
            "机器人产业链投资机会",
            public_results=[
                {"title": "机器人公告", "url": "https://www.cninfo.com.cn/new/disclosure/detail", "snippet": "公告验证机器人订单。"},
                {"title": "Serenity X讨论", "url": "https://x.com/aleabitoreddit/status/1", "snippet": "大V讨论机器人产业趋势。"},
            ],
        )

        report = evaluate_tool_harness(pack)

        self.assertEqual(report["artifact_type"], "tool_harness_report")
        self.assertEqual(report["adapter_coverage"]["public_research_items"], 2)
        self.assertGreaterEqual(report["adapter_coverage"]["primary_public_items"], 1)
        self.assertGreaterEqual(report["source_tier_counts"]["tier_5_social_signal"], 1)
        self.assertTrue(report["source_boundary_quality"]["kol_sources_downgraded"])
        self.assertIn("direct_buy_signal_forbidden", report["source_boundary_quality"]["controls"])
        self.assertGreaterEqual(report["overall_score"], 60)

    def test_write_tool_harness_creates_artifact_and_evaluation_reads_quality(self):
        pack = make_evidence_pack("run-tool-harness", "topic", "机器人产业链投资机会")
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            write_yaml(run_path / "evidence" / "evidence-pack.yaml", pack)

            report = write_tool_harness(run_path, pack)
            path = run_path / "harness" / "tool-harness.yaml"
            self.assertTrue(path.exists())
            self.assertEqual(report["adapter_coverage"]["public_research_items"], 0)

            evaluation = make_evaluation_for_run("run-tool-harness", [], pack, run_path)
            self.assertIn("tool_harness_quality", evaluation)
            self.assertEqual(evaluation["tool_harness_quality"]["public_research_items"], 0)
            self.assertIn("missing_public_research_adapter", evaluation["tool_harness_quality"]["blocking_issues"])
            self.assertNotIn("tool_harness", evaluation["accepted_outputs"])

    def test_tool_harness_blocks_social_only_public_research(self):
        pack = make_evidence_pack(
            "run-tool-harness",
            "topic",
            "机器人产业链投资机会",
            public_results=[{"title": "X热帖", "url": "https://x.com/example/status/1", "snippet": "社媒热度很高。"}],
        )
        report = evaluate_tool_harness(pack)

        self.assertIn("public_research_without_primary_source", report["blocking_issues"])
        self.assertEqual(report["high_confidence_allowed"], False)


if __name__ == "__main__":
    unittest.main()
