import tempfile
import unittest
from pathlib import Path

import yaml

from fundos.reporting import build_first_version_report, write_first_version_report


class ReportingTests(unittest.TestCase):
    def test_build_first_version_report_summarizes_run_learning_harness_and_evolution(self):
        run_path = Path("examples/robotics-fixture-run")
        report = build_first_version_report(run_path)
        self.assertIn("# AwesomeFundOS 第一版结果报告", report)
        self.assertIn("## 系统能力总览", report)
        self.assertIn("## Agent Runtime Assets", report)
        self.assertIn("agent.md / SKILL.md", report)
        self.assertIn("19", report)
        self.assertIn("## 学习源与蒸馏 Pattern", report)
        self.assertIn("serenity_scheme_first_chokepoint", report)
        self.assertIn("howard_marks_cycle_risk", report)
        self.assertIn("## 示例运行：机器人产业链投资机会", report)
        self.assertIn("tech_growth_analyst", report)
        self.assertIn("## Harness / Evaluation", report)
        self.assertIn("case_replay_quality", report)
        self.assertIn("agent_harness_quality", report)
        self.assertIn("historical_case_replay", report)
        self.assertIn("## Watchlist / Paper Portfolio", report)
        self.assertIn("portfolio/watchlist.yaml", report)
        self.assertIn("real_trade_allowed", report)
        self.assertIn("overall_score", report)
        self.assertIn("## EvolutionGate", report)
        self.assertIn("memory_writes", report)
        self.assertIn("approval_mode", report)
        self.assertIn("quarantine", report)
        self.assertIn("研究分析，不构成投资建议", report)

    def test_write_first_version_report_creates_markdown_file(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "reports" / "first-version-result.md"
            result = write_first_version_report(Path("examples/robotics-fixture-run"), out)
            self.assertEqual(result, out)
            self.assertTrue(out.exists())
            text = out.read_text()
            self.assertIn("## V2 Gaps", text)
            self.assertIn("真实公告", text)
            self.assertIn("Paper Portfolio", text)


if __name__ == "__main__":
    unittest.main()
