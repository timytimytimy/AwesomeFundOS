import json
import tempfile
import unittest
from pathlib import Path

import yaml

from fundos.decision import make_decision_memo
from fundos.evidence import make_evidence_pack
from fundos.portfolio import build_portfolio_artifacts, write_portfolio_artifacts, load_portfolio_state, write_portfolio_review
from fundos.harness import make_evaluation_for_run


class PortfolioArtifactTests(unittest.TestCase):
    def test_build_portfolio_artifacts_from_decision_memo(self):
        pack = make_evidence_pack(
            "run-portfolio",
            "topic",
            "机器人产业链投资机会",
            public_results=[
                {"title": "机器人公告", "url": "https://www.cninfo.com.cn/new/disclosure/detail", "snippet": "公告验证机器人订单。"}
            ],
        )
        memo = make_decision_memo("run-portfolio", "机器人产业链投资机会", pack, agent_outputs=[])
        artifacts = build_portfolio_artifacts(memo, pack)

        self.assertEqual(artifacts["watchlist"]["run_id"], "run-portfolio")
        self.assertEqual(artifacts["paper_portfolio"]["run_id"], "run-portfolio")
        self.assertTrue(artifacts["watchlist"]["items"])
        item = artifacts["watchlist"]["items"][0]
        self.assertEqual(item["status"], "active_research")
        self.assertEqual(item["source_decision_label"], memo["final_decision"]["label"])
        self.assertIn("review_date", item)
        self.assertIn("kill_criteria", item)
        self.assertIn("evidence_references", item)

        action = artifacts["paper_portfolio"]["actions"][0]
        self.assertEqual(action["action_type"], "watchlist_only")
        self.assertEqual(action["target_weight"], 0.0)
        self.assertFalse(action["real_trade_allowed"])
        self.assertIn("不构成投资建议", action["disclaimer"])

    def test_write_and_load_portfolio_artifacts(self):
        pack = make_evidence_pack("run-portfolio", "question", "当前A股低空经济是否值得进入观察池？")
        memo = make_decision_memo("run-portfolio", "当前A股低空经济是否值得进入观察池？", pack, agent_outputs=[])
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            written = write_portfolio_artifacts(run_path, memo, pack)
            self.assertTrue((run_path / "portfolio" / "watchlist.yaml").exists())
            self.assertTrue((run_path / "portfolio" / "paper-portfolio.yaml").exists())
            self.assertTrue((run_path / "portfolio" / "portfolio-actions.jsonl").exists())
            self.assertEqual(set(written), {"watchlist", "paper_portfolio", "actions"})
            state = load_portfolio_state(run_path)
            self.assertTrue(state["watchlist"]["items"])
            self.assertTrue(state["paper_portfolio"]["actions"])
            row = json.loads((run_path / "portfolio" / "portfolio-actions.jsonl").read_text().splitlines()[0])
            self.assertEqual(row["run_id"], "run-portfolio")

    def test_harness_reads_portfolio_state_and_blocks_real_trade_leakage(self):
        pack = make_evidence_pack("run-portfolio", "topic", "机器人产业链投资机会")
        memo = make_decision_memo("run-portfolio", "机器人产业链投资机会", pack, agent_outputs=[])
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            write_portfolio_artifacts(run_path, memo, pack)
            report = make_evaluation_for_run("run-portfolio", [], pack, run_path)
            self.assertEqual(report["portfolio_quality"]["watchlist_items"], 1)
            self.assertEqual(report["portfolio_quality"]["paper_actions"], 1)
            self.assertEqual(report["portfolio_quality"]["real_trade_violations"], 0)
            paper_path = run_path / "portfolio" / "paper-portfolio.yaml"
            paper = yaml.safe_load(paper_path.read_text())
            paper["actions"][0]["real_trade_allowed"] = True
            paper_path.write_text(yaml.safe_dump(paper, allow_unicode=True, sort_keys=False))
            blocked = make_evaluation_for_run("run-portfolio", [], pack, run_path)
            self.assertEqual(blocked["portfolio_quality"]["real_trade_violations"], 1)
            self.assertTrue(any("real_trade_allowed" in item for item in blocked["blocking_issues"]))

    def test_write_portfolio_review_creates_attribution_and_learning_candidates(self):
        pack = make_evidence_pack(
            "run-portfolio",
            "topic",
            "机器人产业链投资机会",
            public_results=[{"title": "机器人公告", "url": "https://www.cninfo.com.cn/new/disclosure/detail", "snippet": "公告验证机器人订单。"}],
        )
        memo = make_decision_memo("run-portfolio", "机器人产业链投资机会", pack, agent_outputs=[])
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            write_portfolio_artifacts(run_path, memo, pack)

            review = write_portfolio_review(run_path)

            review_path = run_path / "portfolio" / "portfolio-review.yaml"
            attribution_path = run_path / "portfolio" / "attribution.jsonl"
            candidates_path = run_path / "portfolio" / "review-candidates.jsonl"
            self.assertTrue(review_path.exists())
            self.assertTrue(attribution_path.exists())
            self.assertTrue(candidates_path.exists())
            self.assertEqual(review["artifact_type"], "portfolio_review")
            self.assertEqual(review["reviewed_actions"], 1)
            self.assertEqual(review["real_trade_violations"], 0)
            self.assertTrue(review["attribution_items"])
            self.assertTrue(review["learning_candidates"])
            self.assertEqual(review["learning_candidates"][0]["target_scope"], "agent_memory")
            self.assertIn("outcome_review", review["learning_candidates"][0]["required_tests"])

            state = load_portfolio_state(run_path)
            self.assertEqual(state["portfolio_review"]["reviewed_actions"], 1)
            self.assertEqual(len(state["attribution"]), 1)
            self.assertEqual(len(state["review_candidates"]), 1)

    def test_harness_reads_portfolio_review_quality(self):
        pack = make_evidence_pack("run-portfolio", "topic", "机器人产业链投资机会")
        memo = make_decision_memo("run-portfolio", "机器人产业链投资机会", pack, agent_outputs=[])
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            write_portfolio_artifacts(run_path, memo, pack)
            write_portfolio_review(run_path)

            report = make_evaluation_for_run("run-portfolio", [], pack, run_path)

            self.assertIn("portfolio_review_quality", report)
            self.assertEqual(report["portfolio_review_quality"]["reviewed_actions"], 1)
            self.assertEqual(report["portfolio_review_quality"]["attribution_items"], 1)
            self.assertEqual(report["portfolio_review_quality"]["learning_candidates"], 1)


if __name__ == "__main__":
    unittest.main()
