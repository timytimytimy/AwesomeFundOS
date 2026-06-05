from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from fundos.agent_outputs import write_agent_output
from fundos.agent_harness import write_agent_harness
from fundos.case_replay import run_case_replay
from fundos.context import context_focus, make_context_pack
from fundos.decision import make_decision_memo, write_decision_markdown
from fundos.evidence import load_seed_library, make_evidence_pack, now_iso
from fundos.evolution import run_evolution_gate
from fundos.harness import make_evaluation, make_evaluation_for_run
from fundos.io import DISCLAIMER, REPO_ROOT, read_yaml, write_yaml
from fundos.learning import build_learning_source_registry, write_run_learning_patterns, write_run_learning_source_registry
from fundos.memory import load_agent_memory_summary, load_memory_writeback_summary
from fundos.outcomes import run_outcome_tracking
from fundos.portfolio import load_portfolio_state, write_portfolio_artifacts, write_portfolio_review
from fundos.public_research import PublicResearchClient
from fundos.reporting import write_first_version_report
from fundos.tool_harness import write_tool_harness

RUNTIME_DIRS = ["agents", "configs", "harness", "memory", "runs", "skills", "tools"]

def today_prefix() -> str:
    return datetime.now().strftime("%Y-%m-%d")

def slugify(value: str) -> str:
    value = value.strip().lower()
    ascii_part = re.sub(r"[^a-z0-9]+", "-", value)
    ascii_part = ascii_part.strip("-")
    if ascii_part:
        return ascii_part[:48]
    return "cn-topic"

def load_roster() -> dict[str, Any]:
    return read_yaml(REPO_ROOT / "specs" / "agents" / "default-roster.yaml")

def command_init(args: argparse.Namespace) -> int:
    cwd = Path.cwd()
    for name in RUNTIME_DIRS:
        path = cwd / name
        if path.exists():
            print(f"skipped {name}/")
        else:
            path.mkdir(parents=True)
            print(f"created {name}/")
    roster = load_roster()
    materialized = materialize_agent_assets(cwd, roster)
    materialize_learning_assets(cwd)
    print(f"loaded {len(roster.get('agents', []))} agents from specs/agents/default-roster.yaml")
    print(f"materialized {materialized} agent asset sets")
    return 0

def materialize_agent_assets(root: Path, roster: dict[str, Any]) -> int:
    count = 0
    for agent in roster.get("agents", []):
        agent_dir = root / "agents" / agent["id"]
        memory_dir = root / "memory" / "agents" / agent["id"]
        agent_dir.mkdir(parents=True, exist_ok=True)
        memory_dir.mkdir(parents=True, exist_ok=True)
        profile_path = agent_dir / "profile.yaml"
        context_path = agent_dir / "context-policy.yaml"
        model_path = agent_dir / "model-policy.yaml"
        agent_md_path = agent_dir / "agent.md"
        skill_dir = root / "skills" / agent["id"]
        skill_path = skill_dir / "SKILL.md"
        memory_path = memory_dir / "semantic_memory.md"
        profile = build_agent_profile(agent)
        context_policy = build_context_policy(agent)
        model_policy = build_model_policy(agent)
        for path, data in [(profile_path, profile), (context_path, context_policy), (model_path, model_policy)]:
            if not path.exists():
                write_yaml(path, data)
        source_agent_md = REPO_ROOT / "specs" / "agents" / "agent-cards" / agent["id"] / "agent.md"
        if source_agent_md.exists() and not agent_md_path.exists():
            shutil.copyfile(source_agent_md, agent_md_path)
        source_skill_md = REPO_ROOT / "specs" / "skills" / agent["id"] / "SKILL.md"
        if source_skill_md.exists() and not skill_path.exists():
            skill_dir.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_skill_md, skill_path)
        if not memory_path.exists():
            memory_path.write_text(f"# {agent['name']} / {agent['role']} Long-term Memory\n\nNo accepted lessons yet. EvolutionGate must approve updates before they are written here.\n", encoding="utf-8")
        count += 1
    return count

def build_agent_profile(agent: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": agent["id"],
        "name": agent["name"],
        "role": agent["role"],
        "mandate": agent.get("mandate", ""),
        "investment_style": agent.get("investment_style", ""),
        "risk_preference": agent.get("risk_preference", "medium"),
        "time_horizon": agent.get("time_horizon", "cross_horizon"),
        "personality": personality_for(agent),
        "decision_principles": principles_for(agent),
        "capability_boundaries": [
            "Do not produce real investment advice or real trade orders.",
            "Use assigned ContextPack only; cite Evidence ID and Claim ID for important claims.",
            "Treat practitioner sources as learning sources unless verified by primary evidence.",
        ],
        "biases": biases_for(agent),
        "weaknesses": ["V1 profile is bootstrapped from roster and requires future performance calibration."],
        "skills": agent.get("skills", []),
        "tools": agent.get("tools", []),
        "context_policy_id": agent.get("context_policy_id"),
        "model_policy_id": agent.get("model_policy_id"),
        "memory_namespace": f"memory/agents/{agent['id']}",
        "performance_metrics": ["role_consistency", "evidence_traceability", "contribution_quality", "learning_quality"],
    }

def personality_for(agent: dict[str, Any]) -> list[str]:
    role = agent.get("role", "")
    if "Bear" in role or "Risk" in role or "Governance" in role:
        return ["skeptical", "evidence-demanding", "risk-aware"]
    if "Trader" in role:
        return ["disciplined", "timing-sensitive", "loss-aware"]
    if "Analyst" in role:
        return ["curious", "structured", "source-driven"]
    return ["calm", "process-oriented", "accountable"]

def principles_for(agent: dict[str, Any]) -> list[str]:
    role = agent.get("role", "")
    base = [
        "No source, no confidence.",
        "Separate fact, opinion, inference, and hypothesis.",
        "Preserve uncertainty and contradictions instead of smoothing them away.",
    ]
    if "Trader" in role:
        base.append("A trade view must include trigger, invalidation, and risk boundary.")
    if "Risk" in role:
        base.append("Downside and liquidity constraints override narrative strength.")
    if "Bear" in role:
        base.append("Attack the strongest version of the thesis, not a straw man.")
    if "Analyst" in role:
        base.append("Map claims from public evidence before upgrading a thesis.")
    return base

def biases_for(agent: dict[str, Any]) -> list[str]:
    role = agent.get("role", "")
    if "Trader" in role:
        return ["May over-weight recent price action."]
    if "Analyst" in role:
        return ["May over-build narratives from incomplete evidence."]
    if "Bear" in role or "Risk" in role:
        return ["May under-weight strong trend persistence."]
    return ["May overweight well-structured team inputs."]

def build_context_policy(agent: dict[str, Any]) -> dict[str, Any]:
    focus = context_focus(agent["id"], agent["role"])
    return {
        "id": agent.get("context_policy_id"),
        "agent_id": agent["id"],
        "preferred_context_tags": focus["tags"],
        "preferred_evidence_tiers": ["tier_1_primary_fact", "tier_2_canonical_framework", "tier_3_verified_public_practitioner"],
        "preferred_claim_types": ["fact", "inference", "hypothesis", "opinion"],
        "max_token_budget": 8000,
        "compression_style": ["claim_table", "bullet_summary", "contradiction_table"],
        "must_preserve": ["evidence_ids", "claim_ids", "contradictions", "low_confidence_claims", "missing_evidence"],
        "required_focus": focus["required"],
        "forbidden_focus": ["real_trade_orders", "personal_financial_advice", "uncited_high_confidence_claims"],
    }

def build_model_policy(agent: dict[str, Any]) -> dict[str, Any]:
    role = agent.get("role", "")
    effort = "high" if any(key in role for key in ["FundManager", "Risk", "Bear", "Evaluation", "Governance"]) else "medium"
    return {
        "id": agent.get("model_policy_id"),
        "provider": "codex",
        "default_model": "codex-default",
        "reasoning_effort": effort,
        "context_budget_tokens": 8000,
        "tool_use_allowed": True,
        "code_execution_allowed": agent["id"] in {"chief_of_staff", "evaluation_harness", "review_archivist"},
        "web_research_allowed": True,
        "task_overrides": {"final_decision": {"reasoning_effort": "high"}, "self_reflection": {"reasoning_effort": "medium"}},
    }

def materialize_learning_assets(root: Path) -> None:
    target = root / "memory" / "organization" / "seed-library.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        write_yaml(target, load_seed_library())
    registry = root / "memory" / "organization" / "learning-source-registry.yaml"
    if not registry.exists():
        write_yaml(registry, build_learning_source_registry())

def command_roster_list(args: argparse.Namespace) -> int:
    roster = load_roster()
    agents = roster.get("agents", [])
    print(f"{len(agents)} agents")
    for agent in agents:
        print(f"- {agent['id']} | {agent['role']} | {agent.get('category', '')}")
    return 0

def infer_input(args: argparse.Namespace) -> tuple[str, str]:
    provided = [("topic", args.topic), ("stock", args.stock), ("question", args.question)]
    non_empty = [(k, v) for k, v in provided if v]
    if len(non_empty) != 1:
        raise SystemExit("exactly one of --topic, --stock, --question is required")
    return non_empty[0]

def select_agents(input_type: str, value: str, roster: dict[str, Any]) -> list[dict[str, str]]:
    agents = {agent["id"]: agent for agent in roster["agents"]}
    selected: list[str] = list(roster.get("mandatory_agents", []))
    text = value.lower()

    def add(agent_id: str) -> None:
        if agent_id not in selected:
            selected.append(agent_id)

    tech_keywords = ["机器人", "ai", "算力", "半导体", "软件", "人工智能", "芯片"]
    manufacturing_keywords = ["低空", "制造", "新能源", "电力", "军工", "自动化", "工业"]
    consumer_keywords = ["消费", "医药", "医疗", "品牌", "服务"]
    cycle_keywords = ["煤", "有色", "化工", "资源", "地产", "金融", "周期"]
    policy_keywords = ["政策", "改革", "国企", "事件", "催化"]

    if input_type == "stock":
        add("quality_growth_company_analyst")
        add("position_trend_trader")
    if any(k in text for k in tech_keywords):
        add("tech_growth_analyst")
        add("quality_growth_company_analyst")
        add("position_trend_trader")
    if any(k in text for k in manufacturing_keywords):
        add("advanced_manufacturing_analyst")
        add("swing_trader")
    if any(k in text for k in consumer_keywords):
        add("consumer_healthcare_analyst")
        add("quality_growth_company_analyst")
    if any(k in text for k in cycle_keywords):
        add("cyclical_macro_analyst")
        add("turnaround_value_company_analyst")
    if any(k in text for k in policy_keywords):
        add("policy_event_analyst")
        add("event_driven_trader")

    if len(selected) < 7:
        add("tech_growth_analyst")
    if len(selected) < 8:
        add("quality_growth_company_analyst")
    if len(selected) < 9:
        add("position_trend_trader")

    selected = selected[: int(roster.get("max_agents_per_run", 10))]
    return [
        {
            "agent_id": agent_id,
            "role": agents[agent_id]["role"],
            "reason": selection_reason(agent_id, input_type, value),
            "context_pack_id": f"ctx_{agent_id}",
        }
        for agent_id in selected
    ]

def selection_reason(agent_id: str, input_type: str, value: str) -> str:
    if agent_id in {"chief_of_staff", "fund_manager", "risk_manager", "bear_debater", "evaluation_harness", "review_archivist"}:
        return "mandatory governance and committee role"
    return f"matched {input_type} task: {value}"

def write_reflections(run_path: Path, selected: list[dict[str, str]], run_id: str) -> None:
    ref_dir = run_path / "reflections"
    ref_dir.mkdir(parents=True, exist_ok=True)
    for item in selected:
        agent_id = item["agent_id"]
        reflection = {
            "run_id": run_id,
            "agent_id": agent_id,
            "what_i_believed": "需要先建立证据追溯再形成判断。",
            "what_i_got_right": "保持了模拟研究和真实投资建议的边界。",
            "what_i_got_wrong": "真实数据工具尚未接入，证据密度不足。",
            "missed_evidence": ["真实公告", "实时新闻", "行情摘要"],
            "reasoning_errors": [],
            "tool_usage_errors": ["tool interface is stub"],
            "bias_detected": ["可能高估 seed methodology 的可迁移性"],
            "proposed_memory_updates": ["方法论源必须回到一手事实验证。"],
            "proposed_skill_updates": ["增加真实公告检索工具适配器。"],
            "proposed_principle_updates": ["没有一手证据时不得升级为高置信结论。"],
            "confidence": "medium",
        }
        write_yaml(ref_dir / f"{agent_id}.reflection.yaml", reflection)
    candidate = {
        "candidate_id": f"cand_{run_id}_001",
        "run_id": run_id,
        "source_agent": "learning_curator",
        "candidate_type": "principle_update",
        "target_agent": "fund_manager",
        "target_scope": "principle",
        "proposal": "方法论源可用于生成研究问题，但最终结论必须由一手事实或多源交叉验证支持。",
        "source_basis": [{"evidence_id": "E004", "source_id": "serenity_aleabitoreddit", "source_tier": "tier_3_verified_public_practitioner", "rationale": "Serenity seed source boundary"}],
        "expected_benefit": "降低大V方法论被误用为事实证据的风险。",
        "risk_notes": "需要更多案例回放验证。",
        "required_tests": ["historical_case_replay", "role_drift_check", "evidence_quality_check"],
        "status": "proposed",
    }
    skill_candidate = {
        "candidate_id": f"cand_{run_id}_002",
        "run_id": run_id,
        "source_agent": "learning_curator",
        "target_agent": "evaluation_harness",
        "candidate_type": "workflow_update",
        "target_scope": "workflow",
        "proposal": "投委会最终结论前必须检查 Tool Harness、Learning Source Registry 和反方阻断项。",
        "source_basis": [{"evidence_id": "E001", "source_tier": "tier_1_primary_fact", "rationale": "governed evidence and harness process"}],
        "expected_benefit": "让能力升级和最终决策显式受来源、工具和反方质量约束。",
        "risk_notes": "仅进入 capability candidate，不直接改写 agent.md 或 SKILL.md。",
        "required_tests": ["historical_case_replay", "role_drift_check", "evidence_quality_check"],
        "status": "proposed",
    }
    evo = run_path / "evolution" / "candidates.jsonl"
    evo.parent.mkdir(parents=True, exist_ok=True)
    evo.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in [candidate, skill_candidate]), encoding="utf-8")

def command_run(args: argparse.Namespace) -> int:
    input_type, value = infer_input(args)
    run_id = f"{today_prefix()}-{slugify(value)}"
    run_path = Path.cwd() / "runs" / run_id
    suffix = 1
    base = run_path
    while run_path.exists():
        suffix += 1
        run_path = Path(f"{base}-{suffix}")
        run_id = run_path.name

    for sub in ["evidence", "context", "agent_work", "debate", "risk", "decision", "evaluations", "archive", "reflections", "evolution", "learning", "portfolio", "harness"]:
        (run_path / sub).mkdir(parents=True, exist_ok=True)

    roster = load_roster()
    selected = select_agents(input_type, value, roster)
    agents_by_id = {agent["id"]: agent for agent in roster["agents"]}
    fixture_path = Path(args.research_fixture) if getattr(args, "research_fixture", None) else None
    market_replay_path = Path(args.market_replay_fixture) if getattr(args, "market_replay_fixture", None) else None
    public_results = PublicResearchClient(fixture_path=fixture_path).search(value)
    evidence_pack = make_evidence_pack(run_id, input_type, value, public_results=public_results)

    run_doc = {
        "run_id": run_id,
        "created_at": now_iso(),
        "input": {"input_type": input_type, "value": value},
        "market": "CN_A_SHARE",
        "selected_agents": selected,
        "status": "archived",
        "artifacts": [],
        "model_records": [
            {
                "agent_id": item["agent_id"],
                "model": "codex-default-stub",
                "reasoning_effort": "medium",
                "skill_versions": ["v0.1.0"],
                "tool_versions": ["stub-v0.1.0"],
            }
            for item in selected
        ],
    }
    write_yaml(run_path / "run.yaml", run_doc)
    (run_path / "task-brief.md").write_text(f"# Task Brief\n\n{DISCLAIMER}\n\n- input_type: {input_type}\n- value: {value}\n", encoding="utf-8")
    write_yaml(run_path / "selected-agents.yaml", {"selected_agents": selected})
    write_yaml(run_path / "evidence" / "evidence-pack.yaml", evidence_pack)
    write_tool_harness(run_path, evidence_pack)
    write_run_learning_patterns(run_path, [item["agent_id"] for item in selected])
    write_run_learning_source_registry(run_path)
    run_case_replay(run_path)

    agent_outputs = []
    for item in selected:
        agent = agents_by_id[item["agent_id"]]
        context = make_context_pack(run_id, agent, evidence_pack)
        write_yaml(run_path / "context" / f"{agent['id']}.context-pack.yaml", context)
        agent_outputs.append(write_agent_output(run_path / "agent_work" / f"{agent['id']}.md", agent, context, value, evidence_pack))
    write_agent_harness(run_path, selected)

    (run_path / "debate" / "bear-case.md").write_text(f"# Bear Case\n\n- 当前证据为 stub，不能形成高置信结论。\n- 方法论源不能替代一手事实。\n\n{DISCLAIMER}\n", encoding="utf-8")
    write_yaml(run_path / "debate" / "issue-table.yaml", {"issues": [{"issue": "evidence stub", "status": "unresolved"}]})
    (run_path / "risk" / "risk-review.md").write_text(f"# Risk Review\n\n真实数据工具未接入，模拟仓位为 0%。\n\n{DISCLAIMER}\n", encoding="utf-8")
    write_yaml(run_path / "risk" / "position-risk.yaml", {"hypothetical_max_position": "0%", "reason": "stub evidence only"})

    memo = make_decision_memo(run_id, value, evidence_pack, agent_outputs=agent_outputs)
    write_yaml(run_path / "decision" / "final-decision-memo.yaml", memo)
    write_decision_markdown(run_path / "decision" / "final-decision-memo.md", memo)
    write_portfolio_artifacts(run_path, memo, evidence_pack)
    run_outcome_tracking(run_path, market_replay_path)
    write_portfolio_review(run_path)

    evaluation = make_evaluation_for_run(run_id, selected, evidence_pack, run_path)
    write_yaml(run_path / "evaluations" / "evaluation-report.yaml", evaluation)
    (run_path / "evaluations" / "evaluation-report.md").write_text(f"# Evaluation Report\n\nOverall score: {evaluation['overall_score']}\n\nBlocking issues:\n" + "\n".join(f"- {x}" for x in evaluation["blocking_issues"]), encoding="utf-8")

    write_reflections(run_path, selected, run_id)
    (run_path / "archive" / "run-summary.md").write_text(f"# Run Summary\n\nrun_id: {run_id}\nquery: {value}\nselected_agents: {len(selected)}\n", encoding="utf-8")

    print(f"run_id={run_id}")
    print(f"run_path={run_path.relative_to(Path.cwd())}")
    return 0

def command_eval(args: argparse.Namespace) -> int:
    run_path = Path(args.run)
    if not run_path.is_absolute():
        run_path = Path.cwd() / run_path
    run_doc = read_yaml(run_path / "run.yaml")
    evidence = read_yaml(run_path / "evidence" / "evidence-pack.yaml")
    selected = run_doc["selected_agents"]
    run_case_replay(run_path)
    write_tool_harness(run_path, evidence)
    write_run_learning_source_registry(run_path)
    run_outcome_tracking(run_path)
    write_portfolio_review(run_path)
    write_agent_harness(run_path, selected)
    evaluation = make_evaluation_for_run(run_doc["run_id"], selected, evidence, run_path)
    write_yaml(run_path / "evaluations" / "evaluation-report.yaml", evaluation)
    print(f"evaluation_report={run_path / 'evaluations' / 'evaluation-report.yaml'}")
    return 0

def command_evolve(args: argparse.Namespace) -> int:
    run_path = Path(args.run)
    if not run_path.is_absolute():
        run_path = Path.cwd() / run_path
    results = run_evolution_gate(run_path)
    memory_summary = load_memory_writeback_summary(run_path)
    print(f"evolution_results={run_path / 'evolution' / 'evolution-gate-results.jsonl'}")
    print(f"candidates={len(results)}")
    print(f"memory_writes={memory_summary['memory_writes']}")
    print(f"memory_writeback_summary={run_path / 'evolution' / 'memory-writeback-summary.yaml'}")
    return 0

def command_inspect(args: argparse.Namespace) -> int:
    run_path = Path(args.run)
    if not run_path.is_absolute():
        run_path = Path.cwd() / run_path
    run_doc = read_yaml(run_path / "run.yaml")
    print(f"run_id={run_doc['run_id']}")
    print(f"status={run_doc['status']}")
    print(f"selected_agents={len(run_doc['selected_agents'])}")
    portfolio = load_portfolio_state(run_path)
    print(f"watchlist_items={len(portfolio['watchlist'].get('items', []))}")
    print(f"paper_actions={len(portfolio['paper_portfolio'].get('actions', []))}")
    memory_summary = load_memory_writeback_summary(run_path)
    print(f"memory_writes={memory_summary['memory_writes']}")
    return 0

def command_report(args: argparse.Namespace) -> int:
    run_path = Path(args.run)
    if not run_path.is_absolute():
        run_path = Path.cwd() / run_path
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = Path.cwd() / out_path
    written = write_first_version_report(run_path, out_path)
    print(f"report_path={written}")
    return 0

def command_memory_show(args: argparse.Namespace) -> int:
    try:
        summary = load_agent_memory_summary(Path.cwd(), args.agent)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"agent_id={summary['agent_id']}")
    print(f"semantic_memory_path={summary['semantic_memory_path']}")
    print(f"ledger_path={summary['ledger_path']}")
    print(f"accepted_lessons={summary['accepted_lessons']}")
    print(f"ledger_entries={summary['ledger_entries']}")
    print(f"latest_candidate={summary['latest_candidate']}")
    print(f"latest_run_id={summary['latest_run_id']}")
    print(f"latest_candidate_type={summary['latest_candidate_type']}")
    print(f"approval_mode={summary['approval_mode']}")
    print(f"reversible={summary['reversible']}")
    print(f"real_trade_allowed={summary['real_trade_allowed']}")
    print(f"broker_integration={summary['broker_integration']}")
    if summary["latest_proposal"]:
        print(f"latest_proposal={summary['latest_proposal']}")
    print("semantic_preview:")
    print(summary["semantic_preview"])
    return 0

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fundos")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init")
    p_init.set_defaults(func=command_init)

    p_run = sub.add_parser("run")
    p_run.add_argument("--topic")
    p_run.add_argument("--stock")
    p_run.add_argument("--question")
    p_run.add_argument("--research-fixture", help="Path to a JSON array of public research results for deterministic offline runs")
    p_run.add_argument("--market-replay-fixture", help="Path to a YAML market replay fixture for deterministic offline outcome tracking")
    p_run.set_defaults(func=command_run)

    p_eval = sub.add_parser("eval")
    p_eval.add_argument("--run", required=True)
    p_eval.set_defaults(func=command_eval)

    p_evolve = sub.add_parser("evolve")
    p_evolve.add_argument("--run", required=True)
    p_evolve.set_defaults(func=command_evolve)

    p_inspect = sub.add_parser("inspect")
    p_inspect.add_argument("--run", required=True)
    p_inspect.set_defaults(func=command_inspect)

    p_report = sub.add_parser("report")
    p_report.add_argument("--run", required=True)
    p_report.add_argument("--out", default="reports/first-version-result.md")
    p_report.set_defaults(func=command_report)

    p_roster = sub.add_parser("roster")
    roster_sub = p_roster.add_subparsers(dest="roster_command", required=True)
    p_roster_list = roster_sub.add_parser("list")
    p_roster_list.set_defaults(func=command_roster_list)

    p_memory = sub.add_parser("memory")
    memory_sub = p_memory.add_subparsers(dest="memory_command", required=True)
    p_memory_show = memory_sub.add_parser("show")
    p_memory_show.add_argument("--agent", required=True)
    p_memory_show.set_defaults(func=command_memory_show)

    return parser

def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)

if __name__ == "__main__":
    raise SystemExit(main())
