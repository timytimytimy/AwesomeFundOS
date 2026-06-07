import tempfile
import unittest
from pathlib import Path

import yaml

from fundos.agent_outputs import write_agent_output
from fundos.context import make_context_pack
from fundos.evidence import make_evidence_pack
from fundos.harness import make_evaluation_for_run
from fundos.io import REPO_ROOT, read_yaml, write_yaml
from fundos.pm_competition import load_pm_competition, write_pm_competition


class PortfolioManagerCompetitionTests(unittest.TestCase):
    def test_source_controlled_pm_style_competition_spec_defines_four_styles_and_controls(self):
        spec_path = REPO_ROOT / "specs" / "committee" / "pm-style-competition.yaml"
        self.assertTrue(spec_path.exists(), spec_path)
        spec = read_yaml(spec_path)
        self.assertEqual(spec["competition_id"], "pm_style_competition_v1")
        style_ids = {style["style_id"] for style in spec["styles"]}
        self.assertTrue({
            "quality_growth_pm",
            "cycle_value_pm",
            "trend_following_pm",
            "defensive_risk_pm",
        } <= style_ids)
        self.assertIn("disagreement_preservation_required", spec["decision_controls"])
        self.assertIn("no_real_trade_action", spec["safety_controls"])
        self.assertFalse(spec["real_trade_allowed"])
        self.assertEqual(spec["broker_integration"], "disabled")

    def test_write_pm_competition_preserves_style_disagreement_and_paper_only_boundary(self):
        roster = read_yaml(REPO_ROOT / "specs" / "agents" / "default-roster.yaml")
        agents = {agent["id"]: agent for agent in roster["agents"]}
        selected_ids = [
            "fund_manager",
            "risk_manager",
            "bear_debater",
            "tech_growth_analyst",
            "cyclical_macro_analyst",
            "quality_growth_company_analyst",
            "position_trend_trader",
            "defensive_execution_trader",
        ]
        pack = make_evidence_pack("pm-run", "topic", "机器人产业链投资机会")
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            outputs = []
            selected = []
            for aid in selected_ids:
                agent = agents[aid]
                selected.append({"agent_id": aid, "role": agent["role"]})
                context = make_context_pack("pm-run", agent, pack)
                write_yaml(run_path / "context" / f"{aid}.context-pack.yaml", context)
                outputs.append(write_agent_output(run_path / "agent_work" / f"{aid}.md", agent, context, "机器人产业链投资机会", pack))

            report = write_pm_competition(run_path, "pm-run", "机器人产业链投资机会", pack, selected, outputs)

            self.assertEqual(report["artifact_type"], "pm_style_competition_report")
            self.assertTrue((run_path / "committee" / "pm-competition.yaml").exists())
            self.assertTrue((run_path / "harness" / "pm-competition-harness.yaml").exists())
            self.assertGreaterEqual(report["style_count"], 4)
            self.assertGreaterEqual(report["disagreement_count"], 2)
            self.assertEqual(report["winner"]["authority"], "simulation_only")
            self.assertFalse(report["real_trade_allowed"])
            self.assertEqual(report["broker_integration"], "disabled")
            style_ids = {item["style_id"] for item in report["style_views"]}
            self.assertIn("quality_growth_pm", style_ids)
            self.assertIn("defensive_risk_pm", style_ids)
            self.assertTrue(any(row["stance"] in {"avoid", "needs_research"} for row in report["style_views"]))
            self.assertFalse(any(row["stance"] in {"watchlist", "paper_candidate"} for row in report["style_views"]))
            self.assertTrue(any(row["stance"] == "needs_research" for row in report["style_views"]))
            self.assertIn("disagreement_register", report)
            self.assertTrue(report["checks"]["disagreement_preserved"])
            self.assertTrue(report["checks"]["risk_boundary_present"])
            self.assertTrue(report["checks"]["paper_only"])

            loaded = load_pm_competition(run_path)
            self.assertEqual(loaded["artifact_type"], "pm_style_competition_report")
            self.assertEqual(loaded["style_count"], report["style_count"])

    def test_evaluation_reads_pm_competition_quality_and_accepts_output(self):
        pack = make_evidence_pack("pm-eval-run", "topic", "机器人产业链投资机会")
        selected = [
            {"agent_id": "fund_manager", "role": "FundManagerAgent"},
            {"agent_id": "risk_manager", "role": "RiskManagerAgent"},
            {"agent_id": "bear_debater", "role": "BearDebaterAgent"},
            {"agent_id": "tech_growth_analyst", "role": "IndustryAnalystAgent"},
            {"agent_id": "position_trend_trader", "role": "TraderAgent"},
        ]
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            (run_path / "harness").mkdir(parents=True)
            write_yaml(run_path / "harness" / "pm-competition-harness.yaml", {
                "artifact_type": "pm_style_competition_harness",
                "overall_score": 91,
                "style_count": 4,
                "disagreement_count": 3,
                "risk_boundary_present": True,
                "no_real_trade_action": True,
                "checks": {
                    "minimum_style_count": True,
                    "disagreement_preserved": True,
                    "risk_boundary_present": True,
                    "paper_only": True,
                },
                "blocking_issues": [],
                "real_trade_allowed": False,
                "broker_integration": "disabled",
            })

            evaluation = make_evaluation_for_run("pm-eval-run", selected, pack, run_path)

        self.assertIn("pm_competition_quality", evaluation)
        self.assertEqual(evaluation["pm_competition_quality"]["overall_score"], 91)
        self.assertEqual(evaluation["pm_competition_quality"]["style_count"], 4)
        self.assertIn("pm_competition", evaluation["accepted_outputs"])


if __name__ == "__main__":
    unittest.main()
