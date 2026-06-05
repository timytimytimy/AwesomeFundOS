import tempfile
import unittest
from pathlib import Path

import yaml

from fundos.agent_outputs import make_structured_agent_output
from fundos.case_replay import run_case_replay
from fundos.context import make_context_pack
from fundos.evidence import make_evidence_pack
from fundos.harness import make_evaluation


class FundosModuleBoundaryTests(unittest.TestCase):
    def test_core_run_modules_can_be_used_without_cli_import(self):
        public_results = [
            {
                "title": "机器人公告",
                "url": "https://www.cninfo.com.cn/new/disclosure/detail",
                "snippet": "公告验证机器人订单。",
                "source_type": "announcement",
                "source_tier": "tier_1_primary_fact",
            }
        ]
        pack = make_evidence_pack("run1", "topic", "机器人产业链投资机会", public_results=public_results)
        agent = {"id": "tech_growth_analyst", "name": "Tech", "role": "TechnologyGrowthAnalyst"}
        context = make_context_pack("run1", agent, pack)
        output = make_structured_agent_output(agent, context, pack, "机器人产业链投资机会")
        evaluation = make_evaluation("run1", [{"agent_id": agent["id"]}], pack)

        self.assertEqual(output["agent_id"], "tech_growth_analyst")
        self.assertGreaterEqual(output["evidence_coverage"]["tier_1_primary_fact"], 1)
        self.assertGreaterEqual(evaluation["source_coverage"]["public_research_items"], 1)

    def test_case_replay_module_can_be_used_without_cli_import(self):
        from fundos.io import write_yaml

        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d) / "runs" / "run1"
            write_yaml(run_path / "learning" / "patterns.yaml", {"patterns": [{"id": "a_share_theme_diffusion_case", "validation_gates": ["historical_case_replay"], "tags": ["industry"]}]})
            replay = run_case_replay(run_path)
            self.assertGreaterEqual(replay["patterns_replayed"], 1)
            self.assertTrue((run_path / "harness" / "historical-case-replay.yaml").exists())

    def test_yaml_artifacts_written_by_modules_are_parseable(self):
        from fundos.agent_outputs import write_agent_output
        from fundos.io import write_yaml

        public_results = [{"title": "X讨论", "url": "https://x.com/example/status/1", "snippet": "社媒热度。"}]
        pack = make_evidence_pack("run2", "topic", "机器人产业链投资机会", public_results=public_results)
        agent = {"id": "bear_debater", "name": "Bear", "role": "BearDebater"}
        context = make_context_pack("run2", agent, pack)
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "agent_work" / "bear_debater.md"
            structured = write_agent_output(out, agent, context, "机器人产业链投资机会", pack)
            self.assertTrue(out.exists())
            self.assertTrue(out.with_suffix(".structured.yaml").exists())
            loaded = yaml.safe_load(out.with_suffix(".structured.yaml").read_text())
            self.assertEqual(loaded["stance"], structured["stance"])
            write_yaml(Path(d) / "tmp.yaml", {"ok": True})
            self.assertTrue(yaml.safe_load((Path(d) / "tmp.yaml").read_text())["ok"])


if __name__ == "__main__":
    unittest.main()
