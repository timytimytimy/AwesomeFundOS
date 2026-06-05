import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CLI = [sys.executable, "-m", "fundos.cli"]


def run_cli(args, cwd):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(CLI + args, cwd=cwd, text=True, capture_output=True, env=env)


class FundosCliTests(unittest.TestCase):
    def test_init_creates_runtime_dirs_idempotently(self):
        with tempfile.TemporaryDirectory() as d:
            tmp_path = Path(d)
            result = run_cli(["init"], tmp_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            for name in ["agents", "configs", "harness", "memory", "runs", "skills", "tools"]:
                self.assertTrue((tmp_path / name).is_dir(), name)

            second = run_cli(["init"], tmp_path)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertIn("skipped", second.stdout)

    def test_roster_list_loads_default_agents(self):
        result = run_cli(["roster", "list"], ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("chief_of_staff", result.stdout)
        self.assertIn("fund_manager", result.stdout)
        self.assertIn("19 agents", result.stdout)

    def test_run_topic_creates_complete_workspace(self):
        with tempfile.TemporaryDirectory() as d:
            tmp_path = Path(d)
            result = run_cli(["run", "--topic", "机器人产业链投资机会"], tmp_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            lines = [line for line in result.stdout.splitlines() if line.startswith("run_path=")]
            self.assertTrue(lines, result.stdout)
            run_path = tmp_path / lines[-1].split("=", 1)[1]
            self.assertTrue(run_path.is_dir())

            expected = [
                "run.yaml",
                "task-brief.md",
                "selected-agents.yaml",
                "evidence/evidence-pack.yaml",
                "learning/patterns.yaml",
                "portfolio/watchlist.yaml",
                "portfolio/paper-portfolio.yaml",
                "portfolio/portfolio-actions.jsonl",
                "decision/final-decision-memo.md",
                "decision/final-decision-memo.yaml",
                "evaluations/evaluation-report.yaml",
                "archive/run-summary.md",
                "evolution/candidates.jsonl",
            ]
            for rel in expected:
                self.assertTrue((run_path / rel).exists(), rel)

            run_doc = yaml.safe_load((run_path / "run.yaml").read_text())
            self.assertEqual(run_doc["input"]["input_type"], "topic")
            self.assertEqual(run_doc["market"], "CN_A_SHARE")
            self.assertGreaterEqual(len(run_doc["selected_agents"]), 7)
            self.assertLessEqual(len(run_doc["selected_agents"]), 10)

            selected = yaml.safe_load((run_path / "selected-agents.yaml").read_text())
            ids = {item["agent_id"] for item in selected["selected_agents"]}
            self.assertTrue({"chief_of_staff", "fund_manager", "risk_manager", "bear_debater", "evaluation_harness", "review_archivist"}.issubset(ids))
            self.assertTrue("tech_growth_analyst" in ids or "advanced_manufacturing_analyst" in ids)

            evidence = yaml.safe_load((run_path / "evidence/evidence-pack.yaml").read_text())
            self.assertTrue(evidence["evidence_items"])
            self.assertTrue(any(item["source_tier"] == "tier_3_verified_public_practitioner" for item in evidence["evidence_items"]))
            self.assertTrue(any(item.get("source_type") == "learning_pattern" for item in evidence["evidence_items"]))
            learning = yaml.safe_load((run_path / "learning/patterns.yaml").read_text())
            self.assertTrue(learning["patterns"])

            for agent_id in ids:
                self.assertTrue((run_path / "context" / f"{agent_id}.context-pack.yaml").exists(), agent_id)
                self.assertTrue((run_path / "agent_work" / f"{agent_id}.md").exists(), agent_id)

            memo = yaml.safe_load((run_path / "decision/final-decision-memo.yaml").read_text())
            self.assertEqual(memo["memo_type"], "simulated_investment_committee_memo")
            self.assertIn("不构成投资建议", memo["disclaimer"])
            self.assertTrue(memo["evidence_references"])
            watchlist = yaml.safe_load((run_path / "portfolio/watchlist.yaml").read_text())
            paper = yaml.safe_load((run_path / "portfolio/paper-portfolio.yaml").read_text())
            self.assertTrue(watchlist["items"])
            self.assertTrue(paper["actions"])
            self.assertFalse(paper["actions"][0]["real_trade_allowed"])

    def test_eval_and_evolve_can_reprocess_run(self):
        with tempfile.TemporaryDirectory() as d:
            tmp_path = Path(d)
            result = run_cli(["run", "--question", "当前A股低空经济是否值得进入观察池？"], tmp_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            run_rel = [line for line in result.stdout.splitlines() if line.startswith("run_path=")][-1].split("=", 1)[1]
            run_path = tmp_path / run_rel

            eval_result = run_cli(["eval", "--run", str(run_path)], tmp_path)
            self.assertEqual(eval_result.returncode, 0, eval_result.stderr)
            report = yaml.safe_load((run_path / "evaluations/evaluation-report.yaml").read_text())
            self.assertGreaterEqual(report["overall_score"], 0)
            self.assertIn("context_quality", report["dimension_scores"])

            evolve_result = run_cli(["evolve", "--run", str(run_path)], tmp_path)
            self.assertEqual(evolve_result.returncode, 0, evolve_result.stderr)
            self.assertIn("memory_writes=", evolve_result.stdout)
            gate_path = run_path / "evolution/evolution-gate-results.jsonl"
            self.assertTrue(gate_path.exists())
            self.assertTrue((run_path / "evolution/memory-writeback-summary.yaml").exists())
            for rel in ["accepted.jsonl", "quarantine.jsonl", "rejected.jsonl"]:
                self.assertTrue((run_path / "evolution" / rel).exists(), rel)
            rows = [json.loads(line) for line in gate_path.read_text().splitlines() if line.strip()]
            self.assertTrue(rows)
            self.assertIn(rows[0]["decision"], {"accept", "reject", "quarantine"})
            self.assertIn("memory_write_allowed", rows[0])

    def test_init_materializes_agent_profiles_and_context_policies(self):
        with tempfile.TemporaryDirectory() as d:
            tmp_path = Path(d)
            result = run_cli(["init"], tmp_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            profile = tmp_path / "agents" / "fund_manager" / "profile.yaml"
            agent_md = tmp_path / "agents" / "fund_manager" / "agent.md"
            context_policy = tmp_path / "agents" / "fund_manager" / "context-policy.yaml"
            model_policy = tmp_path / "agents" / "fund_manager" / "model-policy.yaml"
            skill_md = tmp_path / "skills" / "fund_manager" / "SKILL.md"
            memory = tmp_path / "memory" / "agents" / "fund_manager" / "semantic_memory.md"
            self.assertTrue(profile.exists())
            self.assertTrue(agent_md.exists())
            self.assertTrue(context_policy.exists())
            self.assertTrue(model_policy.exists())
            self.assertTrue(skill_md.exists())
            self.assertTrue(memory.exists())
            self.assertIn("## Memory and Evolution", agent_md.read_text())
            self.assertIn("name: fundos-fund_manager", skill_md.read_text())
            profile_doc = yaml.safe_load(profile.read_text())
            self.assertEqual(profile_doc["id"], "fund_manager")
            self.assertIn("decision_principles", profile_doc)
            policy_doc = yaml.safe_load(context_policy.read_text())
            self.assertIn("must_preserve", policy_doc)
            self.assertIn("contradictions", policy_doc["must_preserve"])

    def test_run_evidence_pack_uses_seed_library_source_metadata(self):
        with tempfile.TemporaryDirectory() as d:
            tmp_path = Path(d)
            result = run_cli(["run", "--topic", "机器人产业链投资机会"], tmp_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            run_rel = [line for line in result.stdout.splitlines() if line.startswith("run_path=")][-1].split("=", 1)[1]
            evidence = yaml.safe_load((tmp_path / run_rel / "evidence" / "evidence-pack.yaml").read_text())
            source_ids = {item.get("source_id") for item in evidence["evidence_items"]}
            self.assertIn("serenity_aleabitoreddit", source_ids)
            self.assertIn("howard_marks", source_ids)
            serenity_item = next(item for item in evidence["evidence_items"] if item.get("source_id") == "serenity_aleabitoreddit")
            self.assertEqual(serenity_item["source_tier"], "tier_3_verified_public_practitioner")
            self.assertIn("not_allowed_outputs", serenity_item)
            self.assertIn("direct_a_share_buy_signal", serenity_item["not_allowed_outputs"])
            self.assertTrue(serenity_item["source_url"])

    def test_run_accepts_research_fixture_cli_argument(self):
        with tempfile.TemporaryDirectory() as d:
            tmp_path = Path(d)
            fixture = tmp_path / "research.json"
            fixture.write_text(json.dumps([
                {"title": "机器人公告", "url": "https://www.cninfo.com.cn/new/disclosure/detail", "snippet": "公告验证机器人订单。"},
                {"title": "机器人政策", "url": "https://www.gov.cn/zhengce/content/test.htm", "snippet": "政策支持机器人产业。"}
            ], ensure_ascii=False))
            result = run_cli(["run", "--topic", "机器人产业链投资机会", "--research-fixture", str(fixture)], tmp_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            run_rel = [line for line in result.stdout.splitlines() if line.startswith("run_path=")][-1].split("=", 1)[1]
            evidence = yaml.safe_load((tmp_path / run_rel / "evidence" / "evidence-pack.yaml").read_text())
            public_items = [item for item in evidence["evidence_items"] if item.get("source_id") == "public_research"]
            self.assertEqual(len(public_items), 2)
            self.assertTrue(all(item["source_tier"] == "tier_1_primary_fact" for item in public_items))
            self.assertIn("public_research", evidence["retrieval_plan"])

    def test_agent_outputs_are_evidence_aware_structured_yaml(self):
        with tempfile.TemporaryDirectory() as d:
            tmp_path = Path(d)
            fixture = tmp_path / "research.json"
            fixture.write_text(json.dumps([
                {"title": "机器人公告", "url": "https://www.cninfo.com.cn/new/disclosure/detail", "snippet": "公告验证机器人订单。"},
                {"title": "X讨论", "url": "https://x.com/example/status/robotics", "snippet": "社媒显示机器人热度。"}
            ], ensure_ascii=False))
            result = run_cli(["run", "--topic", "机器人产业链投资机会", "--research-fixture", str(fixture)], tmp_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            run_rel = [line for line in result.stdout.splitlines() if line.startswith("run_path=")][-1].split("=", 1)[1]
            agent_yaml = tmp_path / run_rel / "agent_work" / "tech_growth_analyst.structured.yaml"
            self.assertTrue(agent_yaml.exists())
            doc = yaml.safe_load(agent_yaml.read_text())
            self.assertEqual(doc["agent_id"], "tech_growth_analyst")
            self.assertIn("evidence_coverage", doc)
            self.assertGreaterEqual(doc["evidence_coverage"]["tier_1_primary_fact"], 1)
            self.assertGreaterEqual(doc["evidence_coverage"]["tier_5_social_signal"], 1)
            self.assertTrue(doc["key_claims"])
            self.assertTrue(all("evidence_id" in claim and "claim_id" in claim for claim in doc["key_claims"]))

    def test_evaluation_scores_reflect_public_evidence_coverage(self):
        with tempfile.TemporaryDirectory() as d:
            tmp_path = Path(d)
            fixture = tmp_path / "research.json"
            fixture.write_text(json.dumps([
                {"title": "机器人公告", "url": "https://www.cninfo.com.cn/new/disclosure/detail", "snippet": "公告验证机器人订单。"}
            ], ensure_ascii=False))
            result = run_cli(["run", "--topic", "机器人产业链投资机会", "--research-fixture", str(fixture)], tmp_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            run_rel = [line for line in result.stdout.splitlines() if line.startswith("run_path=")][-1].split("=", 1)[1]
            report = yaml.safe_load((tmp_path / run_rel / "evaluations" / "evaluation-report.yaml").read_text())
            self.assertGreaterEqual(report["dimension_scores"]["evidence_quality"], 75)
            self.assertNotIn("真实公开数据检索工具尚未接入，当前为 EvidencePack stub。", report["blocking_issues"])
            self.assertIn("source_coverage", report)
            self.assertGreaterEqual(report["source_coverage"]["public_research_items"], 1)


    def test_report_command_writes_first_version_result(self):
        with tempfile.TemporaryDirectory() as d:
            tmp_path = Path(d)
            result = run_cli(["run", "--topic", "机器人产业链投资机会"], tmp_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            run_rel = [line for line in result.stdout.splitlines() if line.startswith("run_path=")][-1].split("=", 1)[1]
            evolve_result = run_cli(["evolve", "--run", run_rel], tmp_path)
            self.assertEqual(evolve_result.returncode, 0, evolve_result.stderr)
            report_result = run_cli(["report", "--run", run_rel, "--out", "reports/first-version-result.md"], tmp_path)
            self.assertEqual(report_result.returncode, 0, report_result.stderr)
            report_path = tmp_path / "reports" / "first-version-result.md"
            self.assertTrue(report_path.exists())
            text = report_path.read_text()
            self.assertIn("AwesomeFundOS 第一版结果报告", text)
            self.assertIn("EvolutionGate", text)

    def test_seed_library_contains_verified_practitioner_and_classics(self):
        seed_path = ROOT / "specs" / "learning" / "seed-library.yaml"
        self.assertTrue(seed_path.exists())
        seed = yaml.safe_load(seed_path.read_text())
        ids = {item["id"] for item in seed["sources"]}
        self.assertIn("serenity_aleabitoreddit", ids)
        self.assertIn("lihai_a_share", ids)
        self.assertIn("howard_marks", ids)
        self.assertIn("william_oneil_canslim", ids)
        serenity = next(item for item in seed["sources"] if item["id"] == "serenity_aleabitoreddit")
        self.assertEqual(serenity["source_tier"], "tier_3_verified_public_practitioner")
        self.assertIn("direct_a_share_buy_signal", serenity["not_allowed_outputs"])


if __name__ == "__main__":
    unittest.main()
