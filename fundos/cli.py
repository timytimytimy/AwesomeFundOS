from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from fundos.agent_outputs import refresh_agent_outputs_with_tool_use, write_agent_output
from fundos.agent_governance import load_governance_summary, write_agent_governance
from fundos.agent_harness import write_agent_harness
from fundos.agent_learning import generate_agent_learning_candidates
from fundos.agent_tool_use import write_agent_tool_use_report
from fundos.agent_performance import load_performance_summary, write_agent_performance
from fundos.agent_threads import load_agent_thread_summary, materialize_agent_threads, record_run_threads
from fundos.capability_apply import apply_approved_capability, list_pending_capabilities
from fundos.case_replay import run_case_replay
from fundos.case_library import build_case_library_index, load_case_library
from fundos.claim_graph import write_claim_graph
from fundos.committee import write_committee_artifacts
from fundos.context import context_focus, make_context_pack
from fundos.context_policies import load_context_policy
from fundos.decision import make_decision_memo, write_decision_markdown
from fundos.evidence import load_seed_library, make_evidence_pack, now_iso
from fundos.evolution import run_evolution_gate
from fundos.failure_patterns import load_failure_summary, write_failure_patterns
from fundos.harness import make_evaluation, make_evaluation_for_run
from fundos.io import DISCLAIMER, REPO_ROOT, read_yaml, write_yaml
from fundos.learning import build_learning_source_registry, write_run_learning_patterns, write_run_learning_source_registry
from fundos.market_state import write_market_state_report
from fundos.memory import load_agent_memory_summary, load_memory_writeback_summary
from fundos.memory_policies import load_memory_policy
from fundos.outcomes import run_outcome_tracking
from fundos.os_manifest import write_operating_system_manifest
from fundos.pm_competition import write_pm_competition
from fundos.portfolio import load_portfolio_state, write_portfolio_artifacts, write_portfolio_review
from fundos.public_research import PublicResearchClient, build_research_plan
from fundos.research_cache import write_run_research_manifest
from fundos.reporting import write_first_version_report
from fundos.skill_benchmark import run_skill_benchmark
from fundos.source_ingestion import ingest_source_candidates
from fundos.system_audit import run_system_audit
from fundos.tool_adapters import load_tool_adapter_contracts, write_tool_adapter_manifest
from fundos.tool_harness import write_tool_harness
from fundos.task_dag import (
    close_research_gap_followup_with_evidence,
    load_research_gap_task_manifest,
    reconcile_research_gap_followups,
    write_research_gap_followup_result,
    write_task_dag,
)
from fundos.tool_runtime import run_fixture_tool_runtime
from fundos.tool_policies import load_tool_policy

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
    write_tool_adapter_manifest(cwd, roster)
    materialize_learning_assets(cwd)
    thread_summary = materialize_agent_threads(cwd, roster)
    print(f"loaded {len(roster.get('agents', []))} agents from specs/agents/default-roster.yaml")
    print(f"materialized {materialized} agent asset sets")
    print(f"materialized {thread_summary['created_or_existing_threads']} agent threads")
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
        memory_policy_path = agent_dir / "memory-policy.yaml"
        tool_path = agent_dir / "tool-policy.yaml"
        model_path = agent_dir / "model-policy.yaml"
        agent_md_path = agent_dir / "agent.md"
        skill_dir = root / "skills" / agent["id"]
        skill_path = skill_dir / "SKILL.md"
        memory_path = memory_dir / "semantic_memory.md"
        profile = build_agent_profile(agent)
        context_policy = build_context_policy(agent)
        memory_policy = build_memory_policy(agent)
        tool_policy = build_tool_policy(agent)
        model_policy = build_model_policy(agent)
        for path, data in [(profile_path, profile), (context_path, context_policy), (memory_policy_path, memory_policy), (tool_path, tool_policy), (model_path, model_policy)]:
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
    policy = load_context_policy(agent)
    policy["id"] = policy.get("context_policy_id")
    policy["max_token_budget"] = policy.get("token_budget")
    return policy

def build_memory_policy(agent: dict[str, Any]) -> dict[str, Any]:
    policy = load_memory_policy(agent)
    policy["id"] = policy.get("memory_policy_id")
    return policy

def build_tool_policy(agent: dict[str, Any]) -> dict[str, Any]:
    policy = load_tool_policy(agent)
    policy["id"] = policy.get("tool_policy_id")
    return policy

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

def research_plan_coverage(public_results: list[dict[str, Any]], research_plan: list[dict[str, Any]]) -> dict[str, Any]:
    planned = {row.get("category") for row in research_plan if row.get("category")}
    covered = {row.get("research_category") for row in public_results if row.get("research_category")}
    category_counts: dict[str, int] = {}
    for row in public_results:
        category = row.get("research_category")
        if category:
            category_counts[str(category)] = category_counts.get(str(category), 0) + 1
    return {
        "planned_categories": len(planned),
        "categories_covered": len(covered),
        "missing_categories": sorted(planned - covered),
        "category_counts": category_counts,
        "plan_step_count": len(research_plan),
    }

def write_reflections(run_path: Path, selected: list[dict[str, str]], run_id: str) -> None:
    ref_dir = run_path / "reflections"
    ref_dir.mkdir(parents=True, exist_ok=True)
    tool_runtime = read_yaml(run_path / "tools" / "tool-runtime-report.yaml") if (run_path / "tools" / "tool-runtime-report.yaml").exists() else {}
    tool_report = read_yaml(run_path / "harness" / "agent-tool-use.yaml") if (run_path / "harness" / "agent-tool-use.yaml").exists() else {}
    tool_errors = reflection_tool_usage_errors(tool_runtime, tool_report)
    for item in selected:
        agent_id = item["agent_id"]
        reflection = {
            "run_id": run_id,
            "agent_id": agent_id,
            "what_i_believed": "需要先建立证据追溯再形成判断。",
            "what_i_got_right": "保持了模拟研究和真实投资建议的边界。",
            "what_i_got_wrong": "仍需继续补齐公告、新闻、行情和财报等外部证据密度。",
            "missed_evidence": ["真实公告", "实时新闻", "行情摘要"],
            "reasoning_errors": [],
            "tool_usage_errors": tool_errors,
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


def reflection_tool_usage_errors(tool_runtime: dict[str, Any], tool_report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for issue in tool_runtime.get("blocking_issues", []) or []:
        if issue and issue != "missing_tool_runtime_report":
            errors.append(str(issue))
    for row in tool_report.get("agent_results", []) or []:
        for tool in row.get("forbidden_called_tools", []) or []:
            errors.append(f"forbidden_tool_called:{row.get('agent_id')}:{tool}")
        for tool in row.get("missing_required_tools", []) or []:
            errors.append(f"missing_required_tool:{row.get('agent_id')}:{tool}")
    return sorted(set(errors))


def build_model_records(selected: list[dict[str, str]], agents_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    contracts = load_tool_adapter_contracts()
    contract_id = contracts.get("contract_id", "tool_adapter_contracts_v1")
    records: list[dict[str, Any]] = []
    for item in selected:
        agent = agents_by_id[item["agent_id"]]
        model_policy = build_model_policy(agent)
        records.append({
            "agent_id": item["agent_id"],
            "model": model_policy["default_model"],
            "model_policy_id": model_policy.get("id"),
            "reasoning_effort": model_policy.get("reasoning_effort"),
            "skill_versions": [f"fundos-{item['agent_id']}@0.1.0"],
            "tool_versions": [contract_id],
            "tool_contract_id": contract_id,
            "runtime_mode": "local_file_protocol",
            "real_trade_allowed": False,
            "broker_integration": "disabled",
        })
    return records

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

    for sub in ["evidence", "context", "agent_work", "debate", "risk", "decision", "evaluations", "archive", "reflections", "evolution", "learning", "portfolio", "harness", "memory"]:
        (run_path / sub).mkdir(parents=True, exist_ok=True)

    roster = load_roster()
    selected = select_agents(input_type, value, roster)
    agents_by_id = {agent["id"]: agent for agent in roster["agents"]}
    fixture_path = Path(args.research_fixture) if getattr(args, "research_fixture", None) else None
    market_replay_path = Path(args.market_replay_fixture) if getattr(args, "market_replay_fixture", None) else None
    research_cache_root = Path(args.research_cache) if getattr(args, "research_cache", None) else Path.cwd() / "cache" / "research"
    research_client = PublicResearchClient(fixture_path=fixture_path, cache_root=research_cache_root, adapter_name="fixture" if fixture_path else "duckduckgo")
    research_plan = build_research_plan(value, input_type=input_type)
    public_results = research_client.search_plan(value, input_type=input_type)
    evidence_pack = make_evidence_pack(run_id, input_type, value, public_results=public_results)
    evidence_pack["research_plan_coverage"] = research_plan_coverage(public_results, research_plan)

    run_doc = {
        "run_id": run_id,
        "created_at": now_iso(),
        "input": {"input_type": input_type, "value": value},
        "market": "CN_A_SHARE",
        "selected_agents": selected,
        "status": "archived",
        "artifacts": [],
        "model_records": build_model_records(selected, agents_by_id),
    }
    write_yaml(run_path / "run.yaml", run_doc)
    materialize_agent_threads(Path.cwd(), roster)
    record_run_threads(run_path, selected, event_type="run_participation", payload={"input_type": input_type, "value": value})
    (run_path / "task-brief.md").write_text(f"# Task Brief\n\n{DISCLAIMER}\n\n- input_type: {input_type}\n- value: {value}\n", encoding="utf-8")
    write_yaml(run_path / "selected-agents.yaml", {"selected_agents": selected})
    write_yaml(run_path / "evidence" / "evidence-pack.yaml", evidence_pack)
    write_run_research_manifest(run_path, value, public_results, research_client.adapter_name, research_cache_root, research_plan=research_plan)
    write_tool_adapter_manifest(run_path, roster)
    run_fixture_tool_runtime(run_path, selected, evidence_pack)
    write_tool_harness(run_path, evidence_pack)
    write_run_learning_patterns(run_path, [item["agent_id"] for item in selected])
    write_run_learning_source_registry(run_path)
    run_case_replay(run_path)

    agent_outputs = []
    for item in selected:
        agent = agents_by_id[item["agent_id"]]
        context = make_context_pack(run_id, agent, evidence_pack, runtime_root=Path.cwd())
        write_yaml(run_path / "context" / f"{agent['id']}.context-pack.yaml", context)
        agent_outputs.append(write_agent_output(run_path / "agent_work" / f"{agent['id']}.md", agent, context, value, evidence_pack))
    write_agent_harness(run_path, selected)
    run_skill_benchmark(run_path)
    collaboration_report = write_committee_artifacts(run_path, run_id, value, selected, agent_outputs, evidence_pack)
    pm_competition_report = write_pm_competition(run_path, run_id, value, evidence_pack, selected, agent_outputs)
    (run_path / "risk" / "risk-review.md").write_text(f"# Risk Review\n\n真实数据工具未接入，模拟仓位为 0%。\n\n{DISCLAIMER}\n", encoding="utf-8")
    write_yaml(run_path / "risk" / "position-risk.yaml", {"hypothetical_max_position": "0%", "reason": "stub evidence only"})

    memo = make_decision_memo(run_id, value, evidence_pack, agent_outputs=agent_outputs, collaboration_report=collaboration_report)
    write_yaml(run_path / "decision" / "final-decision-memo.yaml", memo)
    write_decision_markdown(run_path / "decision" / "final-decision-memo.md", memo)
    write_portfolio_artifacts(run_path, memo, evidence_pack)
    write_market_state_report(run_path, evidence_pack, market_replay_path)
    run_outcome_tracking(run_path, market_replay_path)
    write_portfolio_review(run_path)
    write_task_dag(run_path, selected, evidence_pack)
    write_claim_graph(run_path, evidence_pack)
    write_agent_tool_use_report(run_path, selected)
    refresh_agent_outputs_with_tool_use(run_path)
    write_agent_harness(run_path, selected)
    run_skill_benchmark(run_path)

    evaluation = make_evaluation_for_run(run_id, selected, evidence_pack, run_path)
    write_yaml(run_path / "evaluations" / "evaluation-report.yaml", evaluation)
    (run_path / "evaluations" / "evaluation-report.md").write_text(f"# Evaluation Report\n\nOverall score: {evaluation['overall_score']}\n\nBlocking issues:\n" + "\n".join(f"- {x}" for x in evaluation["blocking_issues"]), encoding="utf-8")

    write_reflections(run_path, selected, run_id)
    write_failure_patterns(run_path)
    generate_agent_learning_candidates(run_path)
    evaluation = make_evaluation_for_run(run_id, selected, evidence_pack, run_path)
    write_yaml(run_path / "evaluations" / "evaluation-report.yaml", evaluation)
    (run_path / "evaluations" / "evaluation-report.md").write_text(f"# Evaluation Report\n\nOverall score: {evaluation['overall_score']}\n\nBlocking issues:\n" + "\n".join(f"- {x}" for x in evaluation["blocking_issues"]), encoding="utf-8")
    write_operating_system_manifest(run_path)
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
    write_tool_adapter_manifest(run_path, load_roster())
    run_fixture_tool_runtime(run_path, selected, evidence)
    write_tool_harness(run_path, evidence)
    write_run_learning_source_registry(run_path)
    if (run_path / "agent_work").exists():
        from fundos.agent_outputs import load_agent_outputs
        agent_outputs = load_agent_outputs(run_path)
        write_pm_competition(run_path, run_doc["run_id"], run_doc["input"]["value"], evidence, selected, agent_outputs)
    write_market_state_report(run_path, evidence)
    run_outcome_tracking(run_path)
    write_portfolio_review(run_path)
    write_agent_harness(run_path, selected)
    write_task_dag(run_path, selected, evidence)
    write_claim_graph(run_path, evidence)
    write_agent_tool_use_report(run_path, selected)
    refresh_agent_outputs_with_tool_use(run_path)
    write_agent_harness(run_path, selected)
    run_skill_benchmark(run_path)
    write_failure_patterns(run_path)
    generate_agent_learning_candidates(run_path)
    evaluation = make_evaluation_for_run(run_doc["run_id"], selected, evidence, run_path)
    write_yaml(run_path / "evaluations" / "evaluation-report.yaml", evaluation)
    write_operating_system_manifest(run_path)
    print(f"evaluation_report={run_path / 'evaluations' / 'evaluation-report.yaml'}")
    return 0

def command_evolve(args: argparse.Namespace) -> int:
    run_path = Path(args.run)
    if not run_path.is_absolute():
        run_path = Path.cwd() / run_path
    failure_report = write_failure_patterns(run_path)
    generate_agent_learning_candidates(run_path)
    results = run_evolution_gate(run_path)
    run_doc = read_yaml(run_path / "run.yaml") if (run_path / "run.yaml").exists() else {"selected_agents": []}
    if run_doc.get("selected_agents"):
        record_run_threads(run_path, run_doc["selected_agents"], event_type="evolution", payload={"candidate_count": len(results)})
    run_skill_benchmark(run_path)
    write_agent_performance(run_path)
    governance = write_agent_governance(run_path)
    if (run_path / "evidence" / "evidence-pack.yaml").exists():
        evidence = read_yaml(run_path / "evidence" / "evidence-pack.yaml")
        evaluation = make_evaluation_for_run(run_doc.get("run_id", run_path.name), run_doc.get("selected_agents", []), evidence, run_path)
        write_yaml(run_path / "evaluations" / "evaluation-report.yaml", evaluation)
    write_operating_system_manifest(run_path)
    memory_summary = load_memory_writeback_summary(run_path)
    print(f"evolution_results={run_path / 'evolution' / 'evolution-gate-results.jsonl'}")
    print(f"candidates={len(results)}")
    print(f"memory_writes={memory_summary['memory_writes']}")
    print(f"memory_writeback_summary={run_path / 'evolution' / 'memory-writeback-summary.yaml'}")
    print(f"agent_performance={run_path / 'harness' / 'agent-performance.yaml'}")
    print(f"agent_governance={run_path / 'harness' / 'agent-governance.yaml'}")
    print(f"skill_benchmark={run_path / 'harness' / 'skill-benchmark.yaml'}")
    print(f"governance_agents={governance['agent_count']}")
    print(f"failure_patterns={run_path / 'learning' / 'failure-patterns.yaml'}")
    print(f"failure_pattern_count={failure_report['pattern_count']}")
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
    manifest_path = run_path / "system" / "operating-system-manifest.yaml"
    if manifest_path.exists():
        manifest = read_yaml(manifest_path) or {}
        loaded_assets = manifest.get("loaded_asset_counts", {}) or {}
        evolution = manifest.get("evolution_summary", {}) or {}
        performance = manifest.get("agent_performance_summary", {}) or {}
        governance = manifest.get("agent_governance_summary", {}) or {}
        evaluation = manifest.get("evaluation_summary", {}) or {}
        safety = manifest.get("safety_invariants", {}) or {}
        print(f"os_manifest={manifest_path}")
        print(f"os_manifest_markdown={run_path / 'system' / 'operating-system-manifest.md'}")
        print(f"runtime_mode={manifest.get('runtime_mode')}")
        print(f"model_records={manifest.get('model_record_count', 0)}")
        print(f"all_runtime_assets={manifest.get('all_selected_agents_have_runtime_assets')}")
        contract_summary = manifest.get("agent_os_contract_summary", {}) or {}
        print(f"all_agent_os_contracts_valid={manifest.get('all_agent_os_contracts_valid')}")
        print("agent_os_contracts=" + inline_counts({"valid": contract_summary.get("valid_contracts", 0), "invalid": contract_summary.get("invalid_contracts", 0), "checked": contract_summary.get("checked_agents", 0)}))
        print("loaded_agent_assets=" + inline_counts(loaded_assets))
        print(f"harness_artifacts={len(manifest.get('harness_artifacts', []) or [])}")
        print(f"memory_thread_artifacts={len(manifest.get('memory_thread_artifacts', []) or [])}")
        print(f"evolution_artifacts={len(manifest.get('evolution_artifacts', []) or [])}")
        print(f"evolution_gate_results={evolution.get('gate_results', 0)}")
        print(f"pending_human_apply={evolution.get('pending_human_apply', 0)}")
        print(f"agent_performance_score={performance.get('average_final_score', 0)}")
        print(f"agent_governance_score={governance.get('governance_quality_score', 0)}")
        print(f"evaluation_overall_score={evaluation.get('overall_score', 0)}")
        print(f"evaluation_blocking_issues={evaluation.get('blocking_issue_count', 0)}")
        print(f"paper_portfolio_only={safety.get('paper_portfolio_only')}")
        print(f"kol_is_hypothesis_only={safety.get('kol_is_hypothesis_only')}")
        print(f"real_trade_allowed={manifest.get('real_trade_allowed')}")
        print(f"broker_integration={manifest.get('broker_integration')}")
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

def command_capabilities_list(args: argparse.Namespace) -> int:
    pending = list_pending_capabilities(Path.cwd())
    print(f"pending_human_apply={len(pending)}")
    for row in pending:
        print(
            "- "
            f"candidate_id={row.get('candidate_id')} "
            f"agent={row.get('target_agent')} "
            f"kind={row.get('capability_kind')} "
            f"status={row.get('application_status')} "
            f"route={row.get('adoption_route')} "
            f"regression={row.get('regression_status')} "
            f"ready={row.get('ready_for_apply')} "
            f"risk_flags={inline_counts({flag: 1 for flag in row.get('risk_flags', [])})} "
            f"registry={row.get('registry_path')}"
        )
    return 0

def command_capabilities_apply(args: argparse.Namespace) -> int:
    if not args.approver:
        print("--approver is required for human-approved capability application", file=sys.stderr)
        return 2
    try:
        result = apply_approved_capability(Path.cwd(), args.candidate_id, args.approver)
    except (FileNotFoundError, PermissionError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"candidate_id={result['candidate_id']}")
    print(f"application_status={result['application_status']}")
    print(f"adoption_route={result.get('adoption_route')}")
    print(f"memory_write_policy={result.get('memory_write_policy')}")
    print(f"regression_status={result.get('approval_snapshot', {}).get('regression_status')}")
    print(f"target_path={result['target_path']}")
    print(f"reversible={result['reversible']}")
    print(f"real_trade_allowed={result['real_trade_allowed']}")
    return 0

def command_performance_show(args: argparse.Namespace) -> int:
    summary = load_performance_summary(Path.cwd(), args.agent)
    print(f"agent_id={summary['agent_id']}")
    print(f"ledger_path={summary['ledger_path']}")
    print(f"runs_evaluated={summary['runs_evaluated']}")
    print(f"average_score={summary['average_score']}")
    print(f"latest_score={summary['latest_score']}")
    print(f"latest_action={summary['latest_action']}")
    print(f"promote_watch_count={summary['promote_watch_count']}")
    print(f"downgrade_watch_count={summary['downgrade_watch_count']}")
    print("real_trade_allowed=False")
    return 0

def command_failures_summary(args: argparse.Namespace) -> int:
    summary = load_failure_summary(Path.cwd())
    print(f"pattern_count={summary['pattern_count']}")
    print("category_counts=" + inline_counts(summary.get("category_counts", {})))
    print("severity_counts=" + inline_counts(summary.get("severity_counts", {})))
    print(f"latest_pattern_id={summary['latest_pattern_id']}")
    print("review_before_evolution=True")
    print("real_trade_allowed=False")
    print("broker_integration=disabled")
    return 0

def command_sources_ingest(args: argparse.Namespace) -> int:
    run_path = Path(args.run)
    if not run_path.is_absolute():
        run_path = Path.cwd() / run_path
    fixture_path = Path(args.fixture)
    if not fixture_path.is_absolute():
        fixture_path = Path.cwd() / fixture_path
    payload = read_yaml(fixture_path)
    candidates = payload.get("candidates", payload) if isinstance(payload, dict) else payload
    if not isinstance(candidates, list):
        print("source fixture must be a YAML list or a mapping with candidates: [...]", file=sys.stderr)
        return 2
    write_run_learning_source_registry(run_path)
    report = ingest_source_candidates(run_path, candidates)
    if (run_path / "run.yaml").exists():
        write_operating_system_manifest(run_path)
    print(f"source_ingestion_report={run_path / 'learning' / 'source-ingestion-report.yaml'}")
    print(f"ingested_sources={report['ingested_sources']}")
    print(f"quarantined_sources={report['quarantined_sources']}")
    print(f"pattern_candidates={report['pattern_candidates']}")
    print(f"evolution_candidates={report['evolution_candidates']}")
    print("real_trade_allowed=False")
    return 0

def command_threads_show(args: argparse.Namespace) -> int:
    try:
        summary = load_agent_thread_summary(Path.cwd(), args.agent)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"agent_id={summary['agent_id']}")
    print(f"thread_id={summary['thread_id']}")
    print(f"thread_path={summary['thread_path']}")
    print(f"event_log_path={summary['event_log_path']}")
    print(f"event_count={summary['event_count']}")
    print(f"latest_event_type={summary['latest_event_type']}")
    print(f"latest_run_id={summary['latest_run_id']}")
    print(f"continuity_scope={','.join(summary['continuity_scope'])}")
    print(f"real_trade_allowed={summary['real_trade_allowed']}")
    print(f"broker_integration={summary['broker_integration']}")
    return 0

def command_governance_summary(args: argparse.Namespace) -> int:
    run_path = Path(args.run)
    if not run_path.is_absolute():
        run_path = Path.cwd() / run_path
    summary = load_governance_summary(run_path)
    print(f"agent_governance_report={run_path / 'harness' / 'agent-governance.yaml'}")
    print(f"agent_count={summary['agent_count']}")
    print("governance_action_counts=" + inline_counts(summary.get("governance_action_counts", {})))
    print(f"seat_competitions={len(summary.get('seat_competitions', {}))}")
    print(f"real_trade_allowed={summary['real_trade_allowed']}")
    print(f"broker_integration={summary['broker_integration']}")
    return 0

def command_system_audit(args: argparse.Namespace) -> int:
    repo = Path(args.repo)
    if not repo.is_absolute():
        repo = Path.cwd() / repo
    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = Path.cwd() / out_dir
    run_path = Path(args.run) if getattr(args, "run", None) else None
    if run_path is not None and not run_path.is_absolute():
        run_path = Path.cwd() / run_path
    report = run_system_audit(repo, out_dir=out_dir, run_path=run_path)
    print(f"system_audit={out_dir / 'system-audit.yaml'}")
    print(f"overall_coverage_score={report['overall_coverage_score']}")
    print(f"passed_requirements={report['passed_requirements']}")
    print(f"failed_requirements={report['failed_requirements']}")
    print(f"real_trade_allowed={report['real_trade_allowed']}")
    print(f"broker_integration={report['broker_integration']}")
    if args.strict and report["failed_requirements"]:
        return 1
    return 0

def command_cases_list(args: argparse.Namespace) -> int:
    library = load_case_library()
    index = build_case_library_index(library)
    print(f"case_count={index['case_count']}")
    print("case_type_counts=" + inline_counts(index.get("case_type_counts", {})))
    print("agent_case_counts=" + inline_counts(index.get("agent_case_counts", {})))
    print("real_trade_allowed=False")
    print("broker_integration=disabled")
    return 0

def command_followups_list(args: argparse.Namespace) -> int:
    run_path = resolve_run_path(args.run)
    reconcile_research_gap_followups(run_path)
    manifest = load_research_gap_task_manifest(run_path)
    print(f"run_id={manifest.get('run_id')}")
    print(f"research_gap_count={manifest.get('research_gap_count', 0)}")
    for task in manifest.get("tasks", []):
        print(
            " ".join(
                [
                    f"task_id={task.get('task_id')}",
                    f"category={task.get('category')}",
                    f"owner_agent_id={task.get('owner_agent_id') or task.get('owner_agent')}",
                    f"priority={task.get('priority')}",
                    f"status={task.get('status')}",
                    f"brief_path={task.get('brief_path')}",
                    f"result_path={task.get('result_path', '')}",
                ]
            )
        )
    print(f"real_trade_allowed={manifest.get('real_trade_allowed', False)}")
    print(f"broker_integration={manifest.get('broker_integration', 'disabled')}")
    return 0

def command_followups_show(args: argparse.Namespace) -> int:
    run_path = resolve_run_path(args.run)
    reconcile_research_gap_followups(run_path)
    manifest = load_research_gap_task_manifest(run_path)
    task = next((row for row in manifest.get("tasks", []) if row.get("task_id") == args.task_id), None)
    if not task:
        print(f"followup_task_not_found: {args.task_id}", file=sys.stderr)
        return 1
    brief_path = run_path / task.get("brief_path", "")
    print(f"task_id={task.get('task_id')}")
    print(f"category={task.get('category')}")
    print(f"owner_agent_id={task.get('owner_agent_id') or task.get('owner_agent')}")
    print(f"priority={task.get('priority')}")
    print(f"status={task.get('status')}")
    print(f"answer_status={task.get('answer_status', '')}")
    print(f"brief_path={task.get('brief_path')}")
    print(f"result_path={task.get('result_path', '')}")
    print(f"real_trade_allowed={task.get('real_trade_allowed', False)}")
    print(f"broker_integration={task.get('broker_integration', 'disabled')}")
    if brief_path.exists():
        print("--- brief ---")
        print(brief_path.read_text(encoding="utf-8"))
    return 0

def command_followups_answer(args: argparse.Namespace) -> int:
    run_path = resolve_run_path(args.run)
    try:
        result = write_research_gap_followup_result(run_path, args.task_id)
    except KeyError:
        print(f"followup_task_not_found: {args.task_id}", file=sys.stderr)
        return 1
    reconciliation = reconcile_research_gap_followups(run_path)
    record_followup_thread_event(
        run_path,
        result.get("owner_agent_id"),
        event_type="research_gap_followup_answered",
        payload={
            "task_id": result.get("task_id"),
            "category": result.get("category"),
            "source": result.get("source"),
            "source_agent_id": result.get("source_agent_id"),
            "source_evidence_id": result.get("source_evidence_id"),
            "source_claim_id": result.get("source_claim_id"),
            "hypothesis": result.get("hypothesis"),
            "validation_required": result.get("validation_required"),
            "status": result.get("status"),
            "result_path": result.get("result_path"),
            "evidence_request_count": len(result.get("evidence_requests", []) or []),
            "real_trade_allowed": False,
            "broker_integration": "disabled",
        },
    )
    stem = args.task_id.replace(":", "_")
    print(f"followup_result={run_path / 'follow_up' / 'results' / (stem + '.yaml')}")
    print(f"task_id={result.get('task_id')}")
    print(f"owner_agent_id={result.get('owner_agent_id')}")
    print(f"status={result.get('status')}")
    print(f"reconciled_answered_count={reconciliation.get('answered_count')}")
    print(f"reconciled_pending_count={reconciliation.get('pending_count')}")
    print(f"real_trade_allowed={result.get('real_trade_allowed', False)}")
    print(f"broker_integration={result.get('broker_integration', 'disabled')}")
    return 0

def command_followups_close(args: argparse.Namespace) -> int:
    run_path = resolve_run_path(args.run)
    manifest_before_close = load_research_gap_task_manifest(run_path)
    task_before_close = next((row for row in manifest_before_close.get("tasks", []) if row.get("task_id") == args.task_id), {})
    evidence_doc = read_yaml(Path(args.evidence))
    evidence_items = evidence_doc.get("evidence_items") if isinstance(evidence_doc, dict) else evidence_doc
    if not isinstance(evidence_items, list) or not evidence_items:
        print("accepted_evidence_required", file=sys.stderr)
        return 1
    try:
        report = close_research_gap_followup_with_evidence(run_path, args.task_id, evidence_items)
    except KeyError:
        print(f"followup_task_not_found: {args.task_id}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    record_followup_thread_event(
        run_path,
        task_before_close.get("owner_agent_id") or task_before_close.get("owner_agent"),
        event_type="research_gap_followup_closed",
        payload={
            "task_id": report.get("task_id"),
            "category": report.get("category"),
            "source": report.get("source"),
            "source_agent_id": report.get("source_agent_id"),
            "source_evidence_id": report.get("source_evidence_id"),
            "source_claim_id": report.get("source_claim_id"),
            "hypothesis": report.get("hypothesis"),
            "validation_required": report.get("validation_required"),
            "closure_status": "closed_by_accepted_evidence",
            "accepted_evidence_count": report.get("accepted_evidence_count"),
            "accepted_evidence_ids": report.get("accepted_evidence_ids", []),
            "closed_count": report.get("closed_count"),
            "pending_count": report.get("pending_count"),
            "real_trade_allowed": False,
            "broker_integration": "disabled",
        },
    )
    print(f"task_id={report.get('task_id')}")
    print("closure_status=closed_by_accepted_evidence")
    print(f"accepted_evidence_count={report.get('accepted_evidence_count')}")
    print("accepted_evidence_ids=" + ",".join(report.get("accepted_evidence_ids", [])))
    print(f"closed_count={report.get('closed_count')}")
    print(f"pending_count={report.get('pending_count')}")
    print(f"real_trade_allowed={report.get('real_trade_allowed', False)}")
    print(f"broker_integration={report.get('broker_integration', 'disabled')}")
    return 0

def record_followup_thread_event(run_path: Path, owner_agent_id: Any, event_type: str, payload: dict[str, Any]) -> None:
    if not owner_agent_id:
        return
    record_run_threads(
        run_path,
        [{"agent_id": str(owner_agent_id), "role": "research_gap_followup_owner"}],
        event_type=event_type,
        payload=payload,
    )

def resolve_run_path(value: str) -> Path:
    run_path = Path(value)
    if not run_path.is_absolute():
        run_path = Path.cwd() / run_path
    return run_path

def inline_counts(counts: dict[str, Any]) -> str:
    if not counts:
        return "none"
    return ",".join(f"{key}:{value}" for key, value in counts.items())

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
    p_run.add_argument("--research-cache", help="Path to public research cache directory; defaults to ./cache/research")
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

    p_caps = sub.add_parser("capabilities")
    caps_sub = p_caps.add_subparsers(dest="capabilities_command", required=True)
    p_caps_list = caps_sub.add_parser("list")
    p_caps_list.set_defaults(func=command_capabilities_list)
    p_caps_apply = caps_sub.add_parser("apply")
    p_caps_apply.add_argument("candidate_id")
    p_caps_apply.add_argument("--approver", default="", help="Human approver name/id required to apply a pending capability candidate")
    p_caps_apply.set_defaults(func=command_capabilities_apply)

    p_perf = sub.add_parser("performance")
    perf_sub = p_perf.add_subparsers(dest="performance_command", required=True)
    p_perf_show = perf_sub.add_parser("show")
    p_perf_show.add_argument("--agent", required=True)
    p_perf_show.set_defaults(func=command_performance_show)

    p_failures = sub.add_parser("failures")
    failures_sub = p_failures.add_subparsers(dest="failures_command", required=True)
    p_failures_summary = failures_sub.add_parser("summary")
    p_failures_summary.set_defaults(func=command_failures_summary)

    p_sources = sub.add_parser("sources")
    sources_sub = p_sources.add_subparsers(dest="sources_command", required=True)
    p_sources_ingest = sources_sub.add_parser("ingest")
    p_sources_ingest.add_argument("--run", required=True, help="Run workspace where source-ingestion artifacts should be written")
    p_sources_ingest.add_argument("--fixture", required=True, help="YAML fixture containing a list or candidates: [...] mapping")
    p_sources_ingest.set_defaults(func=command_sources_ingest)

    p_cases = sub.add_parser("cases")
    cases_sub = p_cases.add_subparsers(dest="cases_command", required=True)
    p_cases_list = cases_sub.add_parser("list")
    p_cases_list.set_defaults(func=command_cases_list)

    p_followups = sub.add_parser("followups")
    followups_sub = p_followups.add_subparsers(dest="followups_command", required=True)
    p_followups_list = followups_sub.add_parser("list")
    p_followups_list.add_argument("--run", required=True)
    p_followups_list.set_defaults(func=command_followups_list)
    p_followups_show = followups_sub.add_parser("show")
    p_followups_show.add_argument("--run", required=True)
    p_followups_show.add_argument("--task-id", required=True)
    p_followups_show.set_defaults(func=command_followups_show)
    p_followups_answer = followups_sub.add_parser("answer")
    p_followups_answer.add_argument("--run", required=True)
    p_followups_answer.add_argument("--task-id", required=True)
    p_followups_answer.set_defaults(func=command_followups_answer)
    p_followups_close = followups_sub.add_parser("close")
    p_followups_close.add_argument("--run", required=True)
    p_followups_close.add_argument("--task-id", required=True)
    p_followups_close.add_argument("--evidence", required=True, help="YAML/JSON file with evidence_items used to close the research gap")
    p_followups_close.set_defaults(func=command_followups_close)

    p_threads = sub.add_parser("threads")
    threads_sub = p_threads.add_subparsers(dest="threads_command", required=True)
    p_threads_show = threads_sub.add_parser("show")
    p_threads_show.add_argument("--agent", required=True)
    p_threads_show.set_defaults(func=command_threads_show)

    p_governance = sub.add_parser("governance")
    governance_sub = p_governance.add_subparsers(dest="governance_command", required=True)
    p_governance_summary = governance_sub.add_parser("summary")
    p_governance_summary.add_argument("--run", required=True)
    p_governance_summary.set_defaults(func=command_governance_summary)

    p_system = sub.add_parser("system")
    system_sub = p_system.add_subparsers(dest="system_command", required=True)
    p_system_audit = system_sub.add_parser("audit")
    p_system_audit.add_argument("--repo", default=".")
    p_system_audit.add_argument("--out", default="audit")
    p_system_audit.add_argument("--run")
    p_system_audit.add_argument("--strict", action="store_true")
    p_system_audit.set_defaults(func=command_system_audit)

    return parser

def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)

if __name__ == "__main__":
    raise SystemExit(main())
