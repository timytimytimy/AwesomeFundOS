import tempfile
import unittest
from pathlib import Path

from fundos.evidence import make_evidence_pack
from fundos.harness import make_evaluation_for_run
from fundos.io import REPO_ROOT, read_yaml, write_yaml
from fundos.market_state import (
    classify_market_series,
    load_market_state_report,
    load_market_state_taxonomy,
    write_market_state_report,
)
from fundos.outcomes import write_market_replay_fixture


class MarketStateTests(unittest.TestCase):
    def test_source_controlled_market_state_taxonomy_defines_states_and_controls(self):
        path = REPO_ROOT / "specs" / "market" / "market-state-taxonomy.yaml"
        self.assertTrue(path.exists(), path)
        taxonomy = load_market_state_taxonomy()
        self.assertEqual(taxonomy["taxonomy_id"], "market_state_taxonomy_v1")
        states = {row["state_id"] for row in taxonomy["states"]}
        self.assertTrue({
            "uptrend_accumulation",
            "bull_breakout",
            "range_bound_rotation",
            "distribution_top",
            "downtrend_risk_off",
            "panic_capitulation",
            "insufficient_data",
        } <= states)
        self.assertIn("market_state_is_context_not_trade_signal", taxonomy["controls"])
        self.assertFalse(taxonomy["real_trade_allowed"])
        self.assertEqual(taxonomy["broker_integration"], "disabled")

    def test_classify_market_series_identifies_trend_and_risk_off_states(self):
        up = [
            {"date": "2026-06-01", "close": 100, "volume": 1000},
            {"date": "2026-06-02", "close": 104, "volume": 1200},
            {"date": "2026-06-03", "close": 108, "volume": 1400},
            {"date": "2026-06-04", "close": 116, "volume": 1800},
        ]
        down = [
            {"date": "2026-06-01", "close": 100, "volume": 1000},
            {"date": "2026-06-02", "close": 94, "volume": 1300},
            {"date": "2026-06-03", "close": 88, "volume": 1700},
            {"date": "2026-06-04", "close": 82, "volume": 2100},
        ]

        up_state = classify_market_series("robotics", up)
        down_state = classify_market_series("risk-off", down)

        self.assertIn(up_state["state_id"], {"bull_breakout", "uptrend_accumulation"})
        self.assertEqual(up_state["trend_direction"], "up")
        self.assertGreater(up_state["return_pct"], 10)
        self.assertIn(down_state["state_id"], {"downtrend_risk_off", "panic_capitulation"})
        self.assertEqual(down_state["trend_direction"], "down")
        self.assertLess(down_state["return_pct"], -10)
        self.assertFalse(up_state["real_trade_allowed"])
        self.assertFalse(down_state["real_trade_allowed"])

    def test_write_market_state_report_from_fixture_creates_harness_artifact(self):
        pack = make_evidence_pack("market-run", "topic", "机器人产业链投资机会")
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            fixture_path = run_path / "fixtures" / "market.yaml"
            write_market_replay_fixture(fixture_path, {
                "机器人产业链投资机会": [
                    {"date": "2026-06-01", "close": 100, "volume": 1000},
                    {"date": "2026-06-02", "close": 106, "volume": 1500},
                    {"date": "2026-06-03", "close": 103, "volume": 1200},
                    {"date": "2026-06-04", "close": 114, "volume": 1800},
                ]
            })

            report = write_market_state_report(run_path, pack, fixture_path)

            self.assertEqual(report["artifact_type"], "market_state_report")
            self.assertEqual(report["subjects_evaluated"], 1)
            self.assertGreaterEqual(report["market_state_quality_score"], 70)
            self.assertTrue((run_path / "harness" / "market-state.yaml").exists())
            self.assertEqual(report["subject_states"][0]["subject"], "机器人产业链投资机会")
            self.assertIn("state_id", report["subject_states"][0])
            self.assertFalse(report["real_trade_allowed"])

            loaded = load_market_state_report(run_path)
            self.assertEqual(loaded["artifact_type"], "market_state_report")
            self.assertEqual(loaded["subjects_evaluated"], 1)

    def test_evaluation_reads_market_state_quality_and_accepts_output_when_data_exists(self):
        pack = make_evidence_pack("market-eval", "topic", "机器人产业链投资机会")
        selected = [{"agent_id": "position_trend_trader", "role": "PositionTrendTrader"}]
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            (run_path / "harness").mkdir(parents=True)
            write_yaml(run_path / "harness" / "market-state.yaml", {
                "artifact_type": "market_state_report",
                "market_state_quality_score": 88,
                "subjects_evaluated": 1,
                "subject_states": [{"subject": "机器人产业链投资机会", "state_id": "bull_breakout"}],
                "blocking_issues": [],
                "real_trade_allowed": False,
                "broker_integration": "disabled",
            })

            evaluation = make_evaluation_for_run("market-eval", selected, pack, run_path)

        self.assertIn("market_state_quality", evaluation)
        self.assertEqual(evaluation["market_state_quality"]["market_state_quality_score"], 88)
        self.assertIn("market_state", evaluation["accepted_outputs"])


if __name__ == "__main__":
    unittest.main()
