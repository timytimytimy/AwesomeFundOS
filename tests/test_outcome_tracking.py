import json
import tempfile
import unittest
from pathlib import Path

import yaml

from fundos.decision import make_decision_memo
from fundos.evidence import make_evidence_pack
from fundos.harness import make_evaluation_for_run
from fundos.outcomes import load_outcome_tracking, run_outcome_tracking, write_market_replay_fixture
from fundos.portfolio import write_portfolio_artifacts, write_portfolio_review


class OutcomeTrackingTests(unittest.TestCase):
    def test_run_outcome_tracking_scores_watchlist_with_market_fixture(self):
        pack = make_evidence_pack(
            "run-outcome",
            "topic",
            "机器人产业链投资机会",
            public_results=[{"title": "机器人公告", "url": "https://www.cninfo.com.cn/new/disclosure/detail", "snippet": "公告验证机器人订单。"}],
        )
        memo = make_decision_memo("run-outcome", "机器人产业链投资机会", pack, agent_outputs=[])
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            write_portfolio_artifacts(run_path, memo, pack)
            fixture_path = run_path / "fixtures" / "market-replay.yaml"
            write_market_replay_fixture(fixture_path, {
                "机器人产业链投资机会": [
                    {"date": "2026-06-01", "close": 100, "volume": 1000},
                    {"date": "2026-06-02", "close": 108, "volume": 1500},
                    {"date": "2026-06-03", "close": 104, "volume": 1200},
                    {"date": "2026-06-04", "close": 112, "volume": 1700},
                ]
            })

            outcome = run_outcome_tracking(run_path, fixture_path)

            self.assertEqual(outcome["artifact_type"], "portfolio_outcome_tracking")
            self.assertEqual(outcome["actions_evaluated"], 1)
            self.assertEqual(outcome["market_replay_items"], 1)
            self.assertEqual(outcome["results"][0]["outcome_status"], "evaluated_with_market_replay")
            self.assertEqual(outcome["results"][0]["return_pct"], 12.0)
            self.assertLessEqual(outcome["results"][0]["max_drawdown_pct"], 0)
            self.assertGreater(outcome["outcome_quality_score"], 60)
            self.assertFalse(outcome["results"][0]["real_trade_allowed"])
            self.assertIn("market_replay_is_not_trade_signal", outcome["controls"])
            self.assertTrue((run_path / "portfolio" / "outcome-tracking.yaml").exists())
            self.assertTrue((run_path / "portfolio" / "outcome-attribution.jsonl").exists())

    def test_outcome_tracking_records_missing_market_replay_without_accepting_output(self):
        pack = make_evidence_pack("run-outcome", "topic", "机器人产业链投资机会")
        memo = make_decision_memo("run-outcome", "机器人产业链投资机会", pack, agent_outputs=[])
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            write_portfolio_artifacts(run_path, memo, pack)

            outcome = run_outcome_tracking(run_path)
            evaluation = make_evaluation_for_run("run-outcome", [], pack, run_path)

            self.assertEqual(outcome["outcome_status"], "missing_market_replay")
            self.assertEqual(outcome["outcome_quality_score"], 0)
            self.assertIn("outcome_tracking_quality", evaluation)
            self.assertEqual(evaluation["outcome_tracking_quality"]["outcome_quality_score"], 0)
            self.assertNotIn("outcome_tracking", evaluation["accepted_outputs"])

    def test_portfolio_review_uses_outcome_tracking_when_available(self):
        pack = make_evidence_pack("run-outcome", "topic", "机器人产业链投资机会")
        memo = make_decision_memo("run-outcome", "机器人产业链投资机会", pack, agent_outputs=[])
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            write_portfolio_artifacts(run_path, memo, pack)
            fixture_path = run_path / "market.yaml"
            write_market_replay_fixture(fixture_path, {
                "机器人产业链投资机会": [
                    {"date": "2026-06-01", "close": 100},
                    {"date": "2026-06-02", "close": 95},
                    {"date": "2026-06-03", "close": 102},
                ]
            })
            run_outcome_tracking(run_path, fixture_path)

            review = write_portfolio_review(run_path)

            self.assertEqual(review["outcome_tracking"]["results_evaluated"], 1)
            self.assertEqual(review["attribution_items"][0]["outcome_status"], "evaluated_with_market_replay")
            self.assertIn("return_pct", review["attribution_items"][0])
            self.assertIn("outcome_review", review["learning_candidates"][0]["required_tests"])

    def test_evaluation_accepts_outcome_tracking_when_market_replay_exists(self):
        pack = make_evidence_pack("run-outcome", "topic", "机器人产业链投资机会")
        memo = make_decision_memo("run-outcome", "机器人产业链投资机会", pack, agent_outputs=[])
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            write_portfolio_artifacts(run_path, memo, pack)
            fixture_path = run_path / "market.yaml"
            write_market_replay_fixture(fixture_path, {
                "机器人产业链投资机会": [
                    {"date": "2026-06-01", "close": 100},
                    {"date": "2026-06-02", "close": 110},
                ]
            })
            outcome = run_outcome_tracking(run_path, fixture_path)

            evaluation = make_evaluation_for_run("run-outcome", [], pack, run_path)

            self.assertEqual(evaluation["outcome_tracking_quality"]["actions_evaluated"], outcome["actions_evaluated"])
            self.assertIn("outcome_tracking", evaluation["accepted_outputs"])
            self.assertGreater(evaluation["dimension_scores"]["outcome_tracking"], 0)


if __name__ == "__main__":
    unittest.main()
