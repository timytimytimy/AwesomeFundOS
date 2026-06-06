import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from fundos.agent_threads import load_agent_thread_summary, materialize_agent_threads, record_run_threads
from fundos.evolution import run_evolution_gate, write_jsonl
from fundos.harness import make_evaluation_for_run
from fundos.io import REPO_ROOT, read_yaml, write_yaml

ROOT = Path(__file__).resolve().parents[1]
CLI = [sys.executable, "-m", "fundos.cli"]


def run_cli(args, cwd):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(CLI + args, cwd=cwd, text=True, capture_output=True, env=env)


class AgentThreadTests(unittest.TestCase):
    def test_materialize_agent_threads_creates_persistent_thread_for_every_agent(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            roster = read_yaml(REPO_ROOT / "specs" / "agents" / "default-roster.yaml")

            summary = materialize_agent_threads(root, roster)

            self.assertEqual(summary["artifact_type"], "agent_thread_materialization_summary")
            self.assertEqual(summary["agent_count"], 19)
            self.assertEqual(summary["created_or_existing_threads"], 19)
            for agent in roster["agents"]:
                thread_path = root / "memory" / "agents" / agent["id"] / "thread.yaml"
                events_path = root / "memory" / "agents" / agent["id"] / "thread-events.jsonl"
                self.assertTrue(thread_path.exists(), agent["id"])
                self.assertTrue(events_path.exists(), agent["id"])
                doc = yaml.safe_load(thread_path.read_text(encoding="utf-8"))
                self.assertEqual(doc["agent_id"], agent["id"])
                self.assertEqual(doc["artifact_type"], "agent_thread")
                self.assertIn("profile", doc["continuity_scope"])
                self.assertIn("memory", doc["continuity_scope"])
                self.assertFalse(doc["real_trade_allowed"])

    def test_record_run_threads_appends_run_event_and_run_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            run_path = root / "runs" / "thread-run"
            roster = read_yaml(REPO_ROOT / "specs" / "agents" / "default-roster.yaml")
            selected = [
                {"agent_id": "fund_manager", "role": "FundManager"},
                {"agent_id": "tech_growth_analyst", "role": "TechGrowthAnalyst"},
            ]
            materialize_agent_threads(root, roster)

            manifest = record_run_threads(run_path, selected, event_type="run_participation", payload={"input": "机器人"})

            self.assertEqual(manifest["artifact_type"], "run_agent_thread_manifest")
            self.assertEqual(manifest["thread_count"], 2)
            self.assertTrue((run_path / "memory" / "agent-thread-manifest.yaml").exists())
            for item in manifest["threads"]:
                events = [json.loads(line) for line in (root / item["event_log_path"]).read_text(encoding="utf-8").splitlines() if line.strip()]
                self.assertEqual(events[-1]["event_type"], "run_participation")
                self.assertEqual(events[-1]["run_id"], "thread-run")
                self.assertEqual(events[-1]["real_trade_allowed"], False)

    def test_run_and_evolve_update_thread_continuity_and_cli_summary(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            init_result = run_cli(["init"], root)
            self.assertEqual(init_result.returncode, 0, init_result.stderr)
            run_result = run_cli(["run", "--topic", "机器人产业链投资机会"], root)
            self.assertEqual(run_result.returncode, 0, run_result.stderr)
            run_rel = [line for line in run_result.stdout.splitlines() if line.startswith("run_path=")][-1].split("=", 1)[1]
            run_path = root / run_rel

            manifest = yaml.safe_load((run_path / "memory" / "agent-thread-manifest.yaml").read_text(encoding="utf-8"))
            self.assertGreaterEqual(manifest["thread_count"], 7)
            eval_report = yaml.safe_load((run_path / "evaluations" / "evaluation-report.yaml").read_text(encoding="utf-8"))
            self.assertIn("agent_thread_quality", eval_report)
            self.assertIn("agent_threads", eval_report["accepted_outputs"])

            evolve_result = run_cli(["evolve", "--run", str(run_path)], root)
            self.assertEqual(evolve_result.returncode, 0, evolve_result.stderr)
            show_result = run_cli(["threads", "show", "--agent", "fund_manager"], root)
            self.assertEqual(show_result.returncode, 0, show_result.stderr)
            self.assertIn("agent_id=fund_manager", show_result.stdout)
            self.assertIn("event_count=", show_result.stdout)
            self.assertIn("latest_event_type=evolution", show_result.stdout)
            self.assertIn("real_trade_allowed=False", show_result.stdout)

    def test_evaluation_reports_missing_thread_manifest_as_quality_gap(self):
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d) / "runs" / "missing-thread-run"
            run_path.mkdir(parents=True)
            evidence_pack = {"evidence_items": [{"source_id": "public_research", "source_tier": "tier_1_primary_fact"}]}

            report = make_evaluation_for_run("missing-thread-run", [{"agent_id": "fund_manager"}], evidence_pack, run_path)

            self.assertIn("agent_thread_quality", report)
            self.assertEqual(report["agent_thread_quality"]["thread_count"], 0)
            self.assertIn("missing_agent_thread_manifest", report["agent_thread_quality"]["blocking_issues"])

    def test_followup_answer_and_close_append_owner_agent_thread_events(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            init_result = run_cli(["init"], root)
            self.assertEqual(init_result.returncode, 0, init_result.stderr)
            fixture = root / "research.json"
            fixture.write_text(json.dumps([
                {"title": "机器人公告", "url": "https://www.cninfo.com.cn/new/disclosure/detail", "snippet": "公告验证机器人订单。"},
                {"title": "机器人政策", "url": "https://www.gov.cn/zhengce/content/test.htm", "snippet": "政策支持机器人。"},
                {"title": "机器人新闻", "url": "https://example.com/news", "snippet": "新闻关注机器人。", "fixture_category": "news"},
                {"title": "机器人热度", "url": "https://x.com/example/status/1", "snippet": "社媒热度。"},
            ]), encoding="utf-8")
            run_result = run_cli(["run", "--topic", "机器人产业链投资机会", "--research-fixture", str(fixture)], root)
            self.assertEqual(run_result.returncode, 0, run_result.stderr)
            run_rel = [line for line in run_result.stdout.splitlines() if line.startswith("run_path=")][-1].split("=", 1)[1]
            run_path = root / run_rel
            task = yaml.safe_load((run_path / "workflow" / "research-gap-tasks.yaml").read_text(encoding="utf-8"))["tasks"][0]
            agent_id = task["owner_agent_id"]

            answer_result = run_cli(["followups", "answer", "--run", run_rel, "--task-id", task["task_id"]], root)

            self.assertEqual(answer_result.returncode, 0, answer_result.stderr)
            events_path = root / "memory" / "agents" / agent_id / "thread-events.jsonl"
            events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(events[-1]["event_type"], "research_gap_followup_answered")
            self.assertEqual(events[-1]["run_id"], run_path.name)
            self.assertEqual(events[-1]["payload"]["task_id"], task["task_id"])
            self.assertEqual(events[-1]["payload"]["category"], task["category"])
            self.assertEqual(events[-1]["payload"]["status"], "needs_evidence")
            self.assertEqual(events[-1]["payload"]["result_path"], f"follow_up/results/{task['task_id'].replace(':', '_')}.yaml")
            self.assertFalse(events[-1]["real_trade_allowed"])
            self.assertEqual(events[-1]["broker_integration"], "disabled")
            thread_manifest = yaml.safe_load((run_path / "memory" / "agent-thread-manifest.yaml").read_text(encoding="utf-8"))
            self.assertEqual(thread_manifest["event_type"], "research_gap_followup_answered")
            self.assertEqual(thread_manifest["threads"][0]["agent_id"], agent_id)

            evidence_file = root / "accepted-evidence.yaml"
            write_yaml(evidence_file, {
                "evidence_items": [
                    {
                        "id": "FGTHREAD001",
                        "source_type": task["category"],
                        "source_tier": "tier_1_primary_fact",
                        "source_id": "accepted_followup_evidence",
                        "title": "机器人主题缺口证据",
                        "url": "https://example.com/thread-evidence",
                        "published_at": "2026-06-06",
                        "retrieved_at": "2026-06-06T00:00:00+00:00",
                        "summary": "补齐该研究缺口所需的已验收事实证据。",
                        "confidence": "high",
                        "claims": [
                            {
                                "claim_id": "CFGTHREAD001",
                                "claim_text": "补齐该研究缺口所需的已验收事实证据。",
                                "claim_type": "fact",
                                "confidence": "high",
                                "relevant_to": ["research_gap", task["category"]],
                                "supports": [],
                                "contradicts": [],
                            }
                        ],
                    }
                ]
            })

            close_result = run_cli(["followups", "close", "--run", run_rel, "--task-id", task["task_id"], "--evidence", str(evidence_file)], root)

            self.assertEqual(close_result.returncode, 0, close_result.stderr)
            events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(events[-1]["event_type"], "research_gap_followup_closed")
            self.assertEqual(events[-1]["payload"]["task_id"], task["task_id"])
            self.assertEqual(events[-1]["payload"]["category"], task["category"])
            self.assertEqual(events[-1]["payload"]["closure_status"], "closed_by_accepted_evidence")
            self.assertEqual(events[-1]["payload"]["accepted_evidence_ids"], ["FGTHREAD001"])
            self.assertFalse(events[-1]["real_trade_allowed"])
            self.assertEqual(events[-1]["broker_integration"], "disabled")
            thread_manifest = yaml.safe_load((run_path / "memory" / "agent-thread-manifest.yaml").read_text(encoding="utf-8"))
            self.assertEqual(thread_manifest["event_type"], "research_gap_followup_closed")

            eval_result = run_cli(["eval", "--run", run_rel], root)
            self.assertEqual(eval_result.returncode, 0, eval_result.stderr)
            evaluation = yaml.safe_load((run_path / "evaluations" / "evaluation-report.yaml").read_text(encoding="utf-8"))
            self.assertIn("agent_threads", evaluation["accepted_outputs"])
            self.assertIn("research_gap_closures", evaluation["accepted_outputs"])
            self.assertFalse(evaluation["agent_thread_quality"]["real_trade_allowed"])
            self.assertEqual(evaluation["agent_thread_quality"]["broker_integration"], "disabled")

    def test_evolution_gate_appends_result_and_memory_writeback_events_to_agent_thread(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            run_path = root / "runs" / "thread-evolution-run"
            run_path.mkdir(parents=True)
            roster = read_yaml(REPO_ROOT / "specs" / "agents" / "default-roster.yaml")
            materialize_agent_threads(root, roster)
            write_acceptance_artifacts(run_path)
            write_jsonl(run_path / "evolution" / "candidates.jsonl", [
                {
                    "candidate_id": "agent_learning_thread_memory_route",
                    "run_id": "thread-evolution-run",
                    "source_agent": "evaluation_harness",
                    "target_agent": "fund_manager",
                    "candidate_type": "reflection_update",
                    "target_scope": "agent_memory",
                    "proposal": "复盘时记录一手证据缺口，防止方法论源替代事实。",
                    "source_basis": [{"evidence_id": "memory/agents/fund_manager/thread-events.jsonl", "source_tier": "tier_2_canonical_framework"}],
                    "required_tests": ["historical_case_replay", "role_drift_check", "evidence_quality_check"],
                    "adoption_route": "memory_writeback_after_evolution",
                    "memory_write_policy": "auto_after_evolution_accept",
                    "human_approval_required": False,
                    "protected_mutation_allowed": False,
                    "controls": ["no_direct_profile_mutation", "no_real_trade_action"],
                    "real_trade_allowed": False,
                    "broker_integration": "disabled",
                }
            ])

            results = run_evolution_gate(run_path)

            self.assertEqual(results[0]["decision"], "accept")
            events_path = root / "memory" / "agents" / "fund_manager" / "thread-events.jsonl"
            events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            event_types = [row["event_type"] for row in events]
            self.assertIn("evolution_candidate_accepted", event_types)
            self.assertIn("memory_writeback_applied", event_types)
            accepted_event = next(row for row in events if row["event_type"] == "evolution_candidate_accepted")
            self.assertEqual(accepted_event["run_id"], "thread-evolution-run")
            self.assertEqual(accepted_event["payload"]["candidate_id"], "agent_learning_thread_memory_route")
            self.assertEqual(accepted_event["payload"]["decision"], "accept")
            writeback_event = next(row for row in events if row["event_type"] == "memory_writeback_applied")
            self.assertEqual(writeback_event["payload"]["candidate_id"], "agent_learning_thread_memory_route")
            self.assertEqual(writeback_event["payload"]["approval_mode"], "evolution_gate_v1_auto_controlled")
            self.assertFalse(writeback_event["real_trade_allowed"])
            self.assertEqual(writeback_event["broker_integration"], "disabled")

            manifest = yaml.safe_load((run_path / "memory" / "agent-thread-manifest.yaml").read_text(encoding="utf-8"))
            self.assertEqual(manifest["event_type"], "memory_writeback_applied")
            self.assertEqual(manifest["threads"][0]["agent_id"], "fund_manager")
            self.assertEqual(load_agent_thread_summary(root, "fund_manager")["latest_event_type"], "memory_writeback_applied")


def write_acceptance_artifacts(run_path: Path) -> None:
    (run_path / "evolution").mkdir(parents=True, exist_ok=True)
    (run_path / "harness").mkdir(parents=True, exist_ok=True)
    (run_path / "evaluations").mkdir(parents=True, exist_ok=True)
    write_yaml(run_path / "run.yaml", {"run_id": run_path.name, "selected_agents": []})
    write_yaml(run_path / "harness" / "historical-case-replay.yaml", {"case_replay_score": 82, "case_results_total": 3})
    write_yaml(run_path / "harness" / "agent-harness.yaml", {"aggregate_scores": {"role_consistency": 88, "skill_invocation": 90}})
    write_yaml(run_path / "evaluations" / "evaluation-report.yaml", {"source_coverage": {"tier_1_primary_fact": 2}, "dimension_scores": {"evidence_quality": 86}})


if __name__ == "__main__":
    unittest.main()
