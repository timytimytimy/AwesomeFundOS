import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


def load_yaml(path):
    return yaml.safe_load(Path(path).read_text())

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
                "evidence/public-research-manifest.yaml",
                "learning/source-registry.yaml",
                "learning/patterns.yaml",
                "learning/failure-patterns.yaml",
                "learning/agent-learning-candidates.jsonl",
                "learning/agent-learning-report.yaml",
                "portfolio/watchlist.yaml",
                "portfolio/paper-portfolio.yaml",
                "portfolio/portfolio-actions.jsonl",
                "portfolio/portfolio-review.yaml",
                "portfolio/attribution.jsonl",
                "portfolio/review-candidates.jsonl",
                "portfolio/outcome-tracking.yaml",
                "portfolio/outcome-attribution.jsonl",
                "harness/historical-case-replay.yaml",
                "harness/agent-harness.yaml",
                "tools/tool-adapter-manifest.yaml",
                "harness/tool-harness.yaml",
                "harness/pm-competition-harness.yaml",
                "harness/skill-benchmark.yaml",
                "harness/market-state.yaml",
                "harness/agent-tool-use.yaml",
                "committee/pm-competition.yaml",
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
            research_manifest = yaml.safe_load((run_path / "evidence/public-research-manifest.yaml").read_text())
            self.assertTrue(evidence["evidence_items"])
            self.assertIn("claim_index", evidence)
            self.assertIn("source_coverage", evidence)
            self.assertTrue(evidence["schema_validation"]["valid"])
            self.assertEqual(evidence["schema_validation"]["error_count"], 0)
            first_claim = evidence["evidence_items"][0]["claims"][0]
            self.assertIn(first_claim["claim_id"], evidence["claim_index"])
            self.assertEqual(evidence["claim_index"][first_claim["claim_id"]]["evidence_id"], evidence["evidence_items"][0]["id"])
            self.assertEqual(research_manifest["artifact_type"], "public_research_manifest")
            self.assertIn("cache_is_audit_trail_not_truth_source", research_manifest["boundary_controls"])
            self.assertIn("research_plan_coverage", research_manifest)
            self.assertGreaterEqual(research_manifest["research_plan_coverage"]["planned_categories"], 5)
            self.assertTrue(any(item["source_tier"] == "tier_3_verified_public_practitioner" for item in evidence["evidence_items"]))
            self.assertTrue(any(item.get("source_type") == "learning_pattern" for item in evidence["evidence_items"]))
            learning = yaml.safe_load((run_path / "learning/patterns.yaml").read_text())
            self.assertTrue(learning["patterns"])
            source_registry = yaml.safe_load((run_path / "learning/source-registry.yaml").read_text())
            self.assertEqual(source_registry["artifact_type"], "learning_source_registry")
            self.assertIn("no_direct_trade_signal", source_registry["boundary_policy"]["controls"])
            market_state = yaml.safe_load((run_path / "harness/market-state.yaml").read_text())
            self.assertEqual(market_state["artifact_type"], "market_state_report")
            self.assertFalse(market_state["real_trade_allowed"])
            replay = yaml.safe_load((run_path / "harness/historical-case-replay.yaml").read_text())
            self.assertGreaterEqual(replay["patterns_replayed"], 1)
            self.assertIn("direct_case_mapping_forbidden", replay["controls"])
            agent_harness = yaml.safe_load((run_path / "harness/agent-harness.yaml").read_text())
            self.assertEqual(agent_harness["agent_count"], len(run_doc["selected_agents"]))
            self.assertIn("skill_invocation", agent_harness["aggregate_scores"])
            skill_benchmark = yaml.safe_load((run_path / "harness/skill-benchmark.yaml").read_text())
            self.assertEqual(skill_benchmark["artifact_type"], "skill_benchmark_report")
            self.assertEqual(skill_benchmark["agents_evaluated"], len(run_doc["selected_agents"]))
            self.assertFalse(skill_benchmark["real_trade_allowed"])
            tool_adapter_manifest = yaml.safe_load((run_path / "tools/tool-adapter-manifest.yaml").read_text())
            self.assertEqual(tool_adapter_manifest["artifact_type"], "tool_adapter_contract_report")
            self.assertTrue(tool_adapter_manifest["all_agent_required_tools_mapped"])
            self.assertFalse(tool_adapter_manifest["real_trade_allowed"])
            tool_harness = yaml.safe_load((run_path / "harness/tool-harness.yaml").read_text())
            self.assertIn("adapter_coverage", tool_harness)
            self.assertIn("source_boundary_quality", tool_harness)
            self.assertGreaterEqual(tool_harness["source_tier_counts"].get("tier_1_primary_fact", 0), 6)
            tool_runtime = yaml.safe_load((run_path / "tools/tool-runtime-report.yaml").read_text())
            self.assertEqual(tool_runtime["artifact_type"], "tool_runtime_report")
            self.assertGreaterEqual(tool_runtime["tool_call_count"], 5)
            self.assertFalse(tool_runtime["real_trade_allowed"])
            self.assertTrue((run_path / "tools/tool-call-ledger.jsonl").exists())
            self.assertTrue((run_path / "evidence/tool-runtime-evidence.yaml").exists())
            refreshed_evidence = yaml.safe_load((run_path / "evidence/evidence-pack.yaml").read_text())
            self.assertTrue(any(item.get("source_id") == "fixture_tool_runtime" for item in refreshed_evidence["evidence_items"]))
            claim_graph = yaml.safe_load((run_path / "harness/claim-graph.yaml").read_text())
            self.assertEqual(claim_graph["artifact_type"], "claim_graph_report")
            self.assertGreaterEqual(claim_graph["traceability_score"], 85)
            self.assertFalse(claim_graph["real_trade_allowed"])
            self.assertTrue((run_path / "evidence/claim-graph.yaml").exists())
            agent_tool_use = yaml.safe_load((run_path / "harness/agent-tool-use.yaml").read_text())
            self.assertEqual(agent_tool_use["artifact_type"], "agent_tool_use_report")
            self.assertEqual(agent_tool_use["agent_count"], len(run_doc["selected_agents"]))
            self.assertGreaterEqual(agent_tool_use["overall_score"], 85)
            self.assertFalse(agent_tool_use["real_trade_allowed"])
            agent_learning = yaml.safe_load((run_path / "learning/agent-learning-report.yaml").read_text())
            self.assertEqual(agent_learning["artifact_type"], "agent_learning_candidate_report")
            self.assertGreaterEqual(agent_learning["candidate_count"], 1)
            self.assertIn("route_counts", agent_learning)
            self.assertFalse(agent_learning["real_trade_allowed"])
            self.assertEqual(agent_learning["broker_integration"], "disabled")
            pm_competition = yaml.safe_load((run_path / "committee/pm-competition.yaml").read_text())
            self.assertEqual(pm_competition["artifact_type"], "pm_style_competition_report")
            self.assertGreaterEqual(pm_competition["style_count"], 4)
            self.assertFalse(pm_competition["real_trade_allowed"])

            for agent_id in ids:
                self.assertTrue((run_path / "context" / f"{agent_id}.context-pack.yaml").exists(), agent_id)
                self.assertTrue((run_path / "agent_work" / f"{agent_id}.md").exists(), agent_id)

            memo = yaml.safe_load((run_path / "decision/final-decision-memo.yaml").read_text())
            self.assertEqual(memo["memo_type"], "simulated_investment_committee_memo")
            self.assertIn("不构成投资建议", memo["disclaimer"])
            self.assertTrue(memo["evidence_references"])
            watchlist = yaml.safe_load((run_path / "portfolio/watchlist.yaml").read_text())
            paper = yaml.safe_load((run_path / "portfolio/paper-portfolio.yaml").read_text())
            review = yaml.safe_load((run_path / "portfolio/portfolio-review.yaml").read_text())
            outcome = yaml.safe_load((run_path / "portfolio/outcome-tracking.yaml").read_text())
            self.assertTrue(watchlist["items"])
            self.assertTrue(paper["actions"])
            self.assertFalse(paper["actions"][0]["real_trade_allowed"])
            self.assertEqual(review["artifact_type"], "portfolio_review")
            self.assertEqual(review["reviewed_actions"], 1)
            self.assertEqual(review["real_trade_violations"], 0)
            self.assertEqual(outcome["artifact_type"], "portfolio_outcome_tracking")
            self.assertIn("outcome_tracking", review)

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
            self.assertIn("case_replay_quality", report)
            self.assertIn("portfolio_review_quality", report)
            self.assertIn("outcome_tracking_quality", report)
            self.assertIn("agent_harness_quality", report)
            self.assertIn("tool_harness_quality", report)
            self.assertIn("tool_runtime_quality", report)
            self.assertIn("claim_graph_quality", report)
            self.assertIn("agent_tool_use_quality", report)
            self.assertIn("agent_learning_quality", report)
            self.assertIn("route_counts", report["agent_learning_quality"])
            self.assertIn("pm_competition_quality", report)
            self.assertIn("skill_benchmark_quality", report)
            self.assertIn("market_state_quality", report)
            self.assertIn("pm_competition", report["accepted_outputs"])
            self.assertIn("skill_benchmark", report["accepted_outputs"])
            self.assertIn("tool_runtime", report["accepted_outputs"])
            self.assertIn("claim_graph", report["accepted_outputs"])
            self.assertIn("agent_tool_use", report["accepted_outputs"])
            self.assertIn("agent_learning_candidates", report["accepted_outputs"])
            self.assertIn("portfolio_review", report["accepted_outputs"])
            self.assertIn("agent_harness", report["accepted_outputs"])

            evolve_result = run_cli(["evolve", "--run", str(run_path)], tmp_path)
            self.assertEqual(evolve_result.returncode, 0, evolve_result.stderr)
            self.assertIn("memory_writes=", evolve_result.stdout)
            gate_path = run_path / "evolution/evolution-gate-results.jsonl"
            self.assertTrue(gate_path.exists())
            self.assertTrue((run_path / "evolution/memory-writeback-summary.yaml").exists())
            self.assertTrue((run_path / "evolution/capability-version-summary.yaml").exists())
            self.assertTrue((run_path / "evolution/capability-candidates.jsonl").exists())
            self.assertTrue((run_path / "harness/capability-regression.yaml").exists())
            self.assertTrue((run_path / "harness/agent-performance.yaml").exists())
            self.assertTrue((run_path / "harness/skill-benchmark.yaml").exists())
            self.assertTrue((run_path / "learning/failure-patterns.yaml").exists())
            self.assertTrue((tmp_path / "memory" / "organization" / "failure-pattern-library.jsonl").exists())
            regression = load_yaml(run_path / "harness/capability-regression.yaml")
            performance = load_yaml(run_path / "harness/agent-performance.yaml")
            failures = load_yaml(run_path / "learning/failure-patterns.yaml")
            self.assertIn("candidate_results", regression)
            self.assertGreaterEqual(regression["candidates_total"], 1)
            self.assertEqual(performance["artifact_type"], "agent_performance_report")
            self.assertGreaterEqual(performance["agent_count"], 1)
            self.assertEqual(failures["artifact_type"], "failure_pattern_report")
            self.assertGreaterEqual(failures["pattern_count"], 1)
            for rel in ["accepted.jsonl", "quarantine.jsonl", "rejected.jsonl"]:
                self.assertTrue((run_path / "evolution" / rel).exists(), rel)
            rows = [json.loads(line) for line in gate_path.read_text().splitlines() if line.strip()]
            self.assertTrue(rows)
            self.assertTrue(any(row["candidate_id"].startswith("portfolio_review_") for row in rows))
            self.assertIn(rows[0]["decision"], {"accept", "reject", "quarantine"})
            self.assertIn("memory_write_allowed", rows[0])
            self.assertGreaterEqual(load_yaml(run_path / "evolution/memory-writeback-summary.yaml")["memory_writes"], 1)
            cap_summary = load_yaml(run_path / "evolution/capability-version-summary.yaml")
            self.assertGreaterEqual(cap_summary["approved_candidates"], 1)
            self.assertGreaterEqual(cap_summary["pending_human_apply"], 1)

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
            source_registry = tmp_path / "memory" / "organization" / "learning-source-registry.yaml"
            tool_adapter_manifest = tmp_path / "tools" / "tool-adapter-manifest.yaml"
            self.assertTrue(profile.exists())
            self.assertTrue(agent_md.exists())
            self.assertTrue(context_policy.exists())
            self.assertTrue(model_policy.exists())
            self.assertTrue(skill_md.exists())
            self.assertTrue(memory.exists())
            self.assertTrue(source_registry.exists())
            self.assertTrue(tool_adapter_manifest.exists())
            self.assertIn("## Memory and Evolution", agent_md.read_text())
            self.assertIn("name: fundos-fund_manager", skill_md.read_text())
            profile_doc = yaml.safe_load(profile.read_text())
            self.assertEqual(profile_doc["id"], "fund_manager")
            self.assertIn("decision_principles", profile_doc)
            policy_doc = yaml.safe_load(context_policy.read_text())
            self.assertIn("must_preserve", policy_doc)
            self.assertIn("contradictions", policy_doc["must_preserve"])


    def test_capabilities_list_and_apply_cli_require_human_approval(self):
        with tempfile.TemporaryDirectory() as d:
            tmp_path = Path(d)
            result = run_cli(["run", "--topic", "机器人产业链投资机会"], tmp_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            run_rel = [line for line in result.stdout.splitlines() if line.startswith("run_path=")][-1].split("=", 1)[1]
            evolve_result = run_cli(["evolve", "--run", str(tmp_path / run_rel)], tmp_path)
            self.assertEqual(evolve_result.returncode, 0, evolve_result.stderr)

            list_result = run_cli(["capabilities", "list"], tmp_path)
            self.assertEqual(list_result.returncode, 0, list_result.stderr)
            self.assertIn("pending_human_apply", list_result.stdout)
            self.assertIn("route=", list_result.stdout)
            self.assertIn("regression=", list_result.stdout)
            self.assertIn("ready=", list_result.stdout)

            apply_without_approval = run_cli(["capabilities", "apply", "cand_" + Path(run_rel).name + "_002"], tmp_path)
            self.assertNotEqual(apply_without_approval.returncode, 0)
            self.assertIn("--approver is required", apply_without_approval.stderr)

            apply_result = run_cli(["capabilities", "apply", "cand_" + Path(run_rel).name + "_002", "--approver", "human-test"], tmp_path)
            self.assertEqual(apply_result.returncode, 0, apply_result.stderr)
            self.assertIn("application_status=applied", apply_result.stdout)
            self.assertIn("adoption_route=", apply_result.stdout)
            self.assertIn("regression_status=passed", apply_result.stdout)
            applied_policy = yaml.safe_load((tmp_path / "agents" / "evaluation_harness" / "applied-capabilities.yaml").read_text())
            self.assertEqual(applied_policy["applied_capabilities"][0]["candidate_id"], "cand_" + Path(run_rel).name + "_002")
            self.assertFalse(applied_policy["applied_capabilities"][0]["real_trade_allowed"])


    def test_performance_show_cli_reads_agent_performance_summary(self):
        with tempfile.TemporaryDirectory() as d:
            tmp_path = Path(d)
            run_result = run_cli(["run", "--topic", "机器人产业链投资机会"], tmp_path)
            self.assertEqual(run_result.returncode, 0, run_result.stderr)
            run_rel = [line for line in run_result.stdout.splitlines() if line.startswith("run_path=")][-1].split("=", 1)[1]
            evolve_result = run_cli(["evolve", "--run", str(tmp_path / run_rel)], tmp_path)
            self.assertEqual(evolve_result.returncode, 0, evolve_result.stderr)

            show_result = run_cli(["performance", "show", "--agent", "tech_growth_analyst"], tmp_path)

            self.assertEqual(show_result.returncode, 0, show_result.stderr)
            self.assertIn("agent_id=tech_growth_analyst", show_result.stdout)
            self.assertIn("runs_evaluated=", show_result.stdout)
            self.assertIn("latest_action=", show_result.stdout)

    def test_sources_ingest_cli_materializes_quarantined_learning_pipeline(self):
        with tempfile.TemporaryDirectory() as d:
            tmp_path = Path(d)
            run_path = tmp_path / "runs" / "manual-source-run"
            fixture = tmp_path / "source-candidates.yaml"
            fixture.write_text(yaml.safe_dump({
                "candidates": [
                    {
                        "source_id": "serenity_x_thread_robotics",
                        "display_name": "Serenity robotics X thread",
                        "source_type": "public_practitioner",
                        "url": "https://x.com/aleabitoreddit/status/123",
                        "author": "Serenity",
                        "summary": "机器人产业链瓶颈研究思路",
                        "claims": ["先从系统架构找瓶颈，再映射公司"],
                        "requested_outputs": ["research_lens", "checklist"],
                        "target_agents": ["tech_growth_analyst"],
                    },
                    {
                        "source_id": "unknown_hot_tip",
                        "source_type": "social_signal",
                        "summary": "直接买入某股票",
                        "claims": ["直接买入"],
                        "requested_outputs": ["direct_buy_signal"],
                    },
                ]
            }, allow_unicode=True), encoding="utf-8")

            result = run_cli(["sources", "ingest", "--run", str(run_path), "--fixture", str(fixture)], tmp_path)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("source_ingestion_report=", result.stdout)
            self.assertIn("pattern_candidates=1", result.stdout)
            report = yaml.safe_load((run_path / "learning" / "source-ingestion-report.yaml").read_text())
            self.assertEqual(report["artifact_type"], "source_ingestion_report")
            self.assertEqual(report["ingested_sources"], 2)
            self.assertEqual(report["quarantined_sources"], 1)
            self.assertFalse(report["real_trade_allowed"])


    def test_failures_summary_cli_reads_organization_library(self):
        with tempfile.TemporaryDirectory() as d:
            tmp_path = Path(d)
            run_result = run_cli(["run", "--topic", "机器人产业链投资机会"], tmp_path)
            self.assertEqual(run_result.returncode, 0, run_result.stderr)
            run_rel = [line for line in run_result.stdout.splitlines() if line.startswith("run_path=")][-1].split("=", 1)[1]
            evolve_result = run_cli(["evolve", "--run", str(tmp_path / run_rel)], tmp_path)
            self.assertEqual(evolve_result.returncode, 0, evolve_result.stderr)

            summary_result = run_cli(["failures", "summary"], tmp_path)

            self.assertEqual(summary_result.returncode, 0, summary_result.stderr)
            self.assertIn("pattern_count=", summary_result.stdout)
            self.assertIn("category_counts=", summary_result.stdout)
            self.assertIn("real_trade_allowed=False", summary_result.stdout)

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
            manifest = yaml.safe_load((tmp_path / run_rel / "evidence" / "public-research-manifest.yaml").read_text())
            public_items = [item for item in evidence["evidence_items"] if item.get("source_id") == "public_research"]
            self.assertEqual(len(public_items), 2)
            self.assertTrue(all(item["source_tier"] == "tier_1_primary_fact" for item in public_items))
            self.assertIn("public_research", evidence["retrieval_plan"])
            self.assertEqual(manifest["result_count"], 2)
            self.assertEqual(manifest["cache_status_counts"]["hit"], 2)
            self.assertEqual(manifest["research_plan_coverage"]["categories_covered"], 2)
            self.assertEqual(manifest["research_plan_coverage"]["category_counts"]["announcement"], 1)
            self.assertEqual(manifest["research_plan_coverage"]["category_counts"]["policy"], 1)

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
            self.assertIn("tool_runtime_reconciliation", doc)
            self.assertIn("tool_use_reconciliation", doc["agent_runtime"])
            self.assertFalse(any(row.get("reason") == "tool_call_ledger_not_available_v1" for row in doc.get("missing_tool_calls", [])))

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
            self.assertIn("portfolio_review_quality", text)
            self.assertIn("agent_harness_quality", text)
            self.assertIn("tool_harness_quality", text)
            self.assertIn("outcome_tracking_quality", text)

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

    def test_system_audit_cli_reports_requirement_coverage(self):
        with tempfile.TemporaryDirectory() as d:
            tmp_path = Path(d)
            result = run_cli(["system", "audit", "--repo", str(ROOT), "--out", "audit"], tmp_path)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("system_audit=", result.stdout)
            self.assertIn("overall_coverage_score=", result.stdout)
            self.assertIn("real_trade_allowed=False", result.stdout)
            self.assertTrue((tmp_path / "audit" / "system-audit.yaml").exists())


if __name__ == "__main__":
    unittest.main()
