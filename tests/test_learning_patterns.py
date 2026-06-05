import json
import tempfile
import unittest
from pathlib import Path

import yaml

from fundos.agent_outputs import make_structured_agent_output
from fundos.context import make_context_pack
from fundos.evidence import make_evidence_pack
from fundos.learning import load_learning_patterns, patterns_for_agent, write_run_learning_patterns


class LearningPatternTests(unittest.TestCase):
    def test_load_learning_patterns_includes_classics_practitioners_and_cases(self):
        patterns = load_learning_patterns()
        ids = {pattern["id"] for pattern in patterns}
        self.assertIn("serenity_scheme_first_chokepoint", ids)
        self.assertIn("howard_marks_cycle_risk", ids)
        self.assertIn("oneil_canslim_growth", ids)
        self.assertIn("minervini_trend_template", ids)
        self.assertIn("lihai_a_share_market_state", ids)
        self.assertIn("a_share_theme_diffusion_case", ids)
        serenity = next(pattern for pattern in patterns if pattern["id"] == "serenity_scheme_first_chokepoint")
        self.assertEqual(serenity["source_id"], "serenity_aleabitoreddit")
        self.assertIn("tech_growth_analyst", serenity["target_agents"])
        self.assertTrue(serenity["checklist"])
        self.assertTrue(serenity["validation_gates"])

    def test_patterns_for_agent_filters_by_role_and_tags(self):
        tech = patterns_for_agent("tech_growth_analyst", ["industry", "company"])
        trader = patterns_for_agent("position_trend_trader", ["trading", "risk"])
        tech_ids = {pattern["id"] for pattern in tech}
        trader_ids = {pattern["id"] for pattern in trader}
        self.assertIn("serenity_scheme_first_chokepoint", tech_ids)
        self.assertIn("minervini_trend_template", trader_ids)
        self.assertIn("lihai_a_share_market_state", trader_ids)
        self.assertNotIn("serenity_scheme_first_chokepoint", trader_ids)

    def test_evidence_pack_contains_learning_pattern_items(self):
        pack = make_evidence_pack("run1", "topic", "机器人产业链投资机会")
        pattern_items = [item for item in pack["evidence_items"] if item.get("source_type") == "learning_pattern"]
        self.assertGreaterEqual(len(pattern_items), 5)
        serenity = next(item for item in pattern_items if item.get("pattern_id") == "serenity_scheme_first_chokepoint")
        self.assertEqual(serenity["source_id"], "serenity_aleabitoreddit")
        self.assertIn("checklist", serenity)
        self.assertIn("validation_gates", serenity)
        self.assertEqual(serenity["claims"][0]["claim_type"], "methodology_pattern")

    def test_agent_output_includes_role_relevant_learning_patterns(self):
        pack = make_evidence_pack("run2", "topic", "机器人产业链投资机会")
        agent = {"id": "tech_growth_analyst", "name": "Tech", "role": "TechnologyGrowthAnalyst"}
        context = make_context_pack("run2", agent, pack)
        output = make_structured_agent_output(agent, context, pack, "机器人产业链投资机会")
        pattern_ids = {pattern["pattern_id"] for pattern in output["learning_patterns"]}
        self.assertIn("serenity_scheme_first_chokepoint", pattern_ids)
        self.assertTrue(all("checklist" in pattern for pattern in output["learning_patterns"]))
        self.assertTrue(output["pattern_application_notes"])

    def test_write_run_learning_patterns_materializes_run_artifact(self):
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            written = write_run_learning_patterns(run_path, ["tech_growth_analyst", "position_trend_trader"])
            self.assertTrue((run_path / "learning" / "patterns.yaml").exists())
            doc = yaml.safe_load((run_path / "learning" / "patterns.yaml").read_text())
            ids = {pattern["id"] for pattern in doc["patterns"]}
            self.assertIn("serenity_scheme_first_chokepoint", ids)
            self.assertIn("minervini_trend_template", ids)
            self.assertEqual(len(written), len(doc["patterns"]))


if __name__ == "__main__":
    unittest.main()
