from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from fundos.public_research import PublicResearchClient, tool_result_to_evidence

DISCLAIMER = "研究分析，不构成投资建议；不接真实交易，不自动下单。"
RUNTIME_DIRS = ["agents", "configs", "harness", "memory", "runs", "skills", "tools"]
REPO_ROOT = Path(__file__).resolve().parents[1]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def today_prefix() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def slugify(value: str) -> str:
    value = value.strip().lower()
    ascii_part = re.sub(r"[^a-z0-9]+", "-", value)
    ascii_part = ascii_part.strip("-")
    if ascii_part:
        return ascii_part[:48]
    return "cn-topic"


def write_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def read_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_roster() -> dict[str, Any]:
    return read_yaml(REPO_ROOT / "specs" / "agents" / "default-roster.yaml")


def load_seed_library() -> dict[str, Any]:
    return read_yaml(REPO_ROOT / "specs" / "learning" / "seed-library.yaml")


def source_by_id(source_id: str) -> dict[str, Any]:
    for source in load_seed_library().get("sources", []):
        if source.get("id") == source_id:
            return source
    raise KeyError(source_id)


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
        memory_path = memory_dir / "semantic_memory.md"
        profile = build_agent_profile(agent)
        context_policy = build_context_policy(agent)
        model_policy = build_model_policy(agent)
        for path, data in [(profile_path, profile), (context_path, context_policy), (model_path, model_policy)]:
            if not path.exists():
                write_yaml(path, data)
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


def make_evidence_pack(run_id: str, input_type: str, value: str, public_results: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    retrieved_at = now_iso()
    base_relevance = ["industry", "company", "trading", "risk", "bear_case"]
    items = [
        evidence_item("E001", "policy", "tier_1_primary_fact", "A股公开政策与监管材料检索占位", "公开政策和交易所材料应作为事实验证的一手来源。", "政策和监管口径必须优先于市场传言。", "fact", retrieved_at, ["industry", "risk"]),
        evidence_item("E002", "financial_report", "tier_1_primary_fact", "公司公告与财报检索占位", "公司公告、定期报告、互动记录用于验证产品、订单、收入和治理。", "公司层面判断必须回到公告和财报。", "fact", retrieved_at, ["company", "risk"]),
        evidence_item("E003", "market_data", "tier_1_primary_fact", "行情与量价摘要占位", "价格、成交额、相对强弱和波动用于交易结构判断。", "交易判断必须和量价结构绑定。", "fact", retrieved_at, ["trading", "risk"]),
    ]
    seed_claims = [
        ("E004", "serenity_aleabitoreddit", "practitioner_source", "学习 secular trend、supply-chain chokepoint、research gap、anti-consensus 和 falsification。", "Serenity 可用于方法论蒸馏，不能直接作为 A 股买卖依据。", "opinion", ["industry", "bear_case"]),
        ("E005", "lihai_a_share", "practitioner_source", "学习市场状态、情绪周期、买卖点、仓位和复盘纪律。", "交易计划需要市场状态和仓位纪律约束。", "opinion", ["trading", "risk"]),
        ("E006", "howard_marks", "book_summary", "学习 second-level thinking、周期和风险控制。", "风险评估必须关注赔率、周期位置和下行情景。", "opinion", ["risk", "bear_case"]),
        ("E007", "william_oneil_canslim", "book_summary", "学习成长股基本面和量价确认结合。", "成长股观察需要基本面增长和市场方向共同确认。", "opinion", ["company", "trading"]),
        ("E008", "mark_minervini", "book_summary", "学习 trend template、VCP 和风险纪律。", "趋势交易必须有明确止损和结构确认。", "opinion", ["trading", "risk"]),
        ("E009", "buffett_munger", "book_summary", "学习商业质量、护城河、能力圈和管理层激励。", "公司研究必须评估质量、激励和可理解性。", "opinion", ["company", "risk"]),
        ("E010", "peter_lynch", "book_summary", "学习 scuttlebutt、公司故事和增长分类。", "公司故事需要渠道和经营事实验证。", "opinion", ["company", "industry"]),
    ]
    for eid, source_id, source_type, summary, claim, claim_type, relevant_to in seed_claims:
        items.append(seed_evidence_item(eid, source_id, source_type, summary, claim, claim_type, retrieved_at, relevant_to))
    next_id = 11
    for result in public_results or []:
        items.append(tool_result_to_evidence(f"E{next_id:03d}", result, retrieved_at, base_relevance))
        next_id += 1
    items.append(evidence_item(f"E{next_id:03d}", "case", "tier_2_canonical_framework", "经典历史案例库种子", "包含大牛股早期识别、主题扩散、产业链瓶颈、泡沫破裂、财务爆雷和政策驱动案例类型。", "历史案例用于形成可测试模式，不可单案过拟合。", "inference", retrieved_at, base_relevance))
    return {
        "run_id": run_id,
        "market": "CN_A_SHARE",
        "query": value,
        "retrieved_at": retrieved_at,
        "retrieval_plan": [
            "search primary announcements and filings",
            "search policy and news sources",
            "query market data summary",
            "load seed practitioner and historical case library",
        ] + (["public_research"] if public_results else []),
        "evidence_items": items,
        "unresolved_gaps": [
            "V1 当前为 public retrieval interface stub，后续需接入真实公告、行情、新闻和网页检索工具。"
        ],
    }


def seed_evidence_item(eid: str, source_id: str, source_type: str, summary: str, claim: str, claim_type: str, retrieved_at: str, relevant_to: list[str]) -> dict[str, Any]:
    source = source_by_id(source_id)
    item = evidence_item(
        eid,
        source_type,
        source["source_tier"],
        f"{source['display_name']} 学习源",
        summary,
        claim,
        claim_type,
        retrieved_at,
        relevant_to,
    )
    item["source_id"] = source_id
    item["source_url"] = source.get("source_url", "")
    item["primary_value"] = source.get("primary_value", [])
    item["allowed_learning_outputs"] = source.get("allowed_learning_outputs", [])
    item["not_allowed_outputs"] = source.get("not_allowed_outputs", [])
    item["validation_required"] = source.get("validation_required", [])
    return item


def evidence_item(eid: str, source_type: str, tier: str, title: str, summary: str, claim: str, claim_type: str, retrieved_at: str, relevant_to: list[str]) -> dict[str, Any]:
    return {
        "id": eid,
        "source_type": source_type,
        "source_tier": tier,
        "title": title,
        "url": "",
        "published_at": "",
        "retrieved_at": retrieved_at,
        "raw_excerpt": summary,
        "summary": summary,
        "confidence": "medium" if tier != "tier_1_primary_fact" else "high",
        "claims": [
            {
                "claim_id": f"C{eid[1:]}",
                "claim_text": claim,
                "claim_type": claim_type,
                "confidence": "medium" if tier != "tier_1_primary_fact" else "high",
                "relevant_to": relevant_to,
                "supports": [],
                "contradicts": [],
            }
        ],
    }


def make_context_pack(run_id: str, agent: dict[str, Any], evidence_pack: dict[str, Any]) -> dict[str, Any]:
    role = agent["role"]
    agent_id = agent["id"]
    focus = context_focus(agent_id, role)
    included = []
    for item in evidence_pack["evidence_items"]:
        claims = item.get("claims", [])
        allowed = [c["claim_id"] for c in claims if set(c.get("relevant_to", [])) & set(focus["tags"])]
        if allowed or agent_id in {"chief_of_staff", "fund_manager", "evaluation_harness", "review_archivist"}:
            included.append(
                {
                    "evidence_id": item["id"],
                    "reason": f"relevant to {role}",
                    "compressed_summary": item["summary"],
                    "allowed_claims": allowed or [c["claim_id"] for c in claims],
                }
            )
    return {
        "context_pack_id": f"ctx_{agent_id}",
        "run_id": run_id,
        "agent_id": agent_id,
        "role": role,
        "task_stage": "specialist_analysis",
        "context_budget_tokens": 8000,
        "included_evidence": included,
        "contradiction_table": [
            {
                "issue": "方法论来源不能替代一手事实",
                "supporting_claims": ["C004"],
                "opposing_claims": ["C001", "C002"],
            }
        ],
        "missing_evidence": evidence_pack.get("unresolved_gaps", []),
        "excluded_evidence_summary": [
            {"category": "irrelevant noise", "reason": "V1 context router excludes non-role evidence by relevance tags"}
        ],
        "required_focus": focus["required"],
        "forbidden_focus": ["不要输出真实交易指令", "不要把低等级来源当作一手事实"],
        "output_schema": f"{role}Output",
    }


def context_focus(agent_id: str, role: str) -> dict[str, Any]:
    if "Trader" in role:
        return {"tags": ["trading", "risk"], "required": ["量价结构", "买卖触发条件", "仓位纪律"]}
    if "Risk" in role:
        return {"tags": ["risk", "company", "trading"], "required": ["下行风险", "证据等级", "仓位上限"]}
    if "Bear" in role:
        return {"tags": ["bear_case", "risk", "company"], "required": ["攻击核心假设", "替代解释", "证据缺口"]}
    if "Company" in role or "Governance" in role:
        return {"tags": ["company", "risk"], "required": ["财报公告", "产品和订单", "治理风险"]}
    if "Analyst" in role:
        return {"tags": ["industry", "company"], "required": ["产业链", "chokepoint", "需求验证"]}
    return {"tags": ["industry", "company", "trading", "risk", "bear_case"], "required": ["综合判断", "证据追溯", "流程完整性"]}


def write_agent_output(path: Path, agent: dict[str, Any], context: dict[str, Any], query: str) -> None:
    evidence_refs = []
    for item in context["included_evidence"][:3]:
        for claim_id in item.get("allowed_claims", [])[:1]:
            evidence_refs.append(f"{item['evidence_id']}:{claim_id}")
    text = f"""# {agent['name']} / {agent['role']} 输出

任务：{query}

## 角色聚焦

{', '.join(context['required_focus'])}

## 初步结论

基于当前 EvidencePack stub，本 Agent 认为该议题应进入模拟研究流程，但需要真实公告、财报、新闻和行情工具进一步验证。

## 证据引用

{', '.join(evidence_refs) if evidence_refs else '无'}

## 边界

{DISCLAIMER}
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_decision_memo(run_id: str, query: str, evidence_pack: dict[str, Any]) -> dict[str, Any]:
    refs = []
    for item in evidence_pack["evidence_items"][:4]:
        claim = item["claims"][0]
        refs.append({"evidence_id": item["id"], "claim_id": claim["claim_id"], "usage": "supports simulated committee memo"})
    return {
        "run_id": run_id,
        "memo_type": "simulated_investment_committee_memo",
        "disclaimer": DISCLAIMER,
        "final_decision": {
            "label": "continue_research",
            "stance": "neutral",
            "conviction": "low",
            "hypothetical_position_range": "0%，仅进入观察和研究队列",
        },
        "thesis": f"{query} 需要通过一手公告、财报、行情和产业证据继续验证。",
        "bull_case": "若公开证据确认需求、订单、产业瓶颈和量价趋势，研究优先级可提升。",
        "bear_case": "当前真实外部数据接口尚未接入，证据完整性不足，不得形成高置信结论。",
        "risk_review": "主要风险是数据不足、叙事过强、方法论源被误用为事实源。",
        "trading_plan": {
            "entry_conditions": ["真实行情与基本面证据接入后再评估"],
            "add_conditions": ["核心假设被多源验证"],
            "reduce_conditions": ["证据等级下降或量价结构恶化"],
            "exit_conditions": ["核心假设被证伪"],
        },
        "kill_criteria": ["缺少一手证据", "关键假设被公告或财报证伪", "反方和风控提出未解决阻断项"],
        "evidence_references": refs,
    }


def write_decision_markdown(path: Path, memo: dict[str, Any]) -> None:
    fd = memo["final_decision"]
    text = f"""# 模拟投委会研究决策备忘录

{memo['disclaimer']}

## 最终标签

- label: {fd['label']}
- stance: {fd['stance']}
- conviction: {fd['conviction']}
- hypothetical_position_range: {fd['hypothetical_position_range']}

## Thesis

{memo['thesis']}

## Bull Case

{memo['bull_case']}

## Bear Case

{memo['bear_case']}

## Risk Review

{memo['risk_review']}

## Kill Criteria

"""
    text += "\n".join(f"- {item}" for item in memo["kill_criteria"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + "\n", encoding="utf-8")


def make_evaluation(run_id: str, selected: list[dict[str, str]], evidence_pack: dict[str, Any]) -> dict[str, Any]:
    has_primary = any(item["source_tier"] == "tier_1_primary_fact" for item in evidence_pack["evidence_items"])
    score = 72 if has_primary else 55
    return {
        "run_id": run_id,
        "overall_score": score,
        "dimension_scores": {
            "evidence_quality": 65,
            "reasoning_quality": 70,
            "role_consistency": 82,
            "decision_quality": 68,
            "collaboration_quality": 75,
            "tool_usage_quality": 50,
            "context_quality": 78,
        },
        "context_quality_scores": {
            "relevance": 80,
            "compression_fidelity": 75,
            "evidence_traceability": 82,
            "role_specificity": 80,
            "information_sufficiency": 60,
            "noise_control": 85,
            "leakage_control": 85,
            "contradiction_preservation": 78,
        },
        "agent_scores": [
            {
                "agent_id": item["agent_id"],
                "role_consistency": 80,
                "contribution_quality": 70,
                "context_fit": 78,
                "improvement_suggestions": ["接入真实工具后提升证据密度"],
            }
            for item in selected
        ],
        "blocking_issues": ["真实公开数据检索工具尚未接入，当前为 EvidencePack stub。"],
        "accepted_outputs": ["final-decision-memo"],
        "rejected_outputs": [],
    }


def write_reflections(run_path: Path, selected: list[dict[str, str]], run_id: str) -> None:
    ref_dir = run_path / "reflections"
    ref_dir.mkdir(parents=True, exist_ok=True)
    candidates = []
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
        "proposal": "方法论源可用于生成研究问题，但最终结论必须由一手事实或多源交叉验证支持。",
        "source_basis": [{"evidence_id": "E004", "source_tier": "tier_3_verified_public_practitioner", "rationale": "Serenity seed source boundary"}],
        "expected_benefit": "降低大V方法论被误用为事实证据的风险。",
        "risk_notes": "需要更多案例回放验证。",
        "required_tests": ["historical_case_replay", "role_drift_check", "evidence_quality_check"],
        "status": "proposed",
    }
    evo = run_path / "evolution" / "candidates.jsonl"
    evo.parent.mkdir(parents=True, exist_ok=True)
    evo.write_text(json.dumps(candidate, ensure_ascii=False) + "\n", encoding="utf-8")


def run_evolution_gate(run_path: Path) -> list[dict[str, Any]]:
    candidates_path = run_path / "evolution" / "candidates.jsonl"
    results = []
    if candidates_path.exists():
        for line in candidates_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            candidate = json.loads(line)
            decision = "quarantine" if len(candidate.get("required_tests", [])) >= 2 else "needs_more_evidence"
            results.append(
                {
                    "candidate_id": candidate["candidate_id"],
                    "decision": decision,
                    "scores": {
                        "source_quality": 75,
                        "testability": 70,
                        "overfitting_risk": 45,
                        "role_drift_risk": 20,
                        "expected_value": 72,
                    },
                    "required_follow_up_tests": candidate.get("required_tests", []),
                    "rationale": "V1 gate keeps candidate quarantined until historical replay is implemented.",
                }
            )
    out = run_path / "evolution" / "evolution-gate-results.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in results), encoding="utf-8")
    return results


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

    for sub in ["evidence", "context", "agent_work", "debate", "risk", "decision", "evaluations", "archive", "reflections", "evolution"]:
        (run_path / sub).mkdir(parents=True, exist_ok=True)

    roster = load_roster()
    selected = select_agents(input_type, value, roster)
    agents_by_id = {agent["id"]: agent for agent in roster["agents"]}
    public_results = PublicResearchClient().search(value)
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

    for item in selected:
        agent = agents_by_id[item["agent_id"]]
        context = make_context_pack(run_id, agent, evidence_pack)
        write_yaml(run_path / "context" / f"{agent['id']}.context-pack.yaml", context)
        write_agent_output(run_path / "agent_work" / f"{agent['id']}.md", agent, context, value)

    (run_path / "debate" / "bear-case.md").write_text(f"# Bear Case\n\n- 当前证据为 stub，不能形成高置信结论。\n- 方法论源不能替代一手事实。\n\n{DISCLAIMER}\n", encoding="utf-8")
    write_yaml(run_path / "debate" / "issue-table.yaml", {"issues": [{"issue": "evidence stub", "status": "unresolved"}]})
    (run_path / "risk" / "risk-review.md").write_text(f"# Risk Review\n\n真实数据工具未接入，模拟仓位为 0%。\n\n{DISCLAIMER}\n", encoding="utf-8")
    write_yaml(run_path / "risk" / "position-risk.yaml", {"hypothetical_max_position": "0%", "reason": "stub evidence only"})

    memo = make_decision_memo(run_id, value, evidence_pack)
    write_yaml(run_path / "decision" / "final-decision-memo.yaml", memo)
    write_decision_markdown(run_path / "decision" / "final-decision-memo.md", memo)

    evaluation = make_evaluation(run_id, selected, evidence_pack)
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
    evaluation = make_evaluation(run_doc["run_id"], selected, evidence)
    write_yaml(run_path / "evaluations" / "evaluation-report.yaml", evaluation)
    print(f"evaluation_report={run_path / 'evaluations' / 'evaluation-report.yaml'}")
    return 0


def command_evolve(args: argparse.Namespace) -> int:
    run_path = Path(args.run)
    if not run_path.is_absolute():
        run_path = Path.cwd() / run_path
    results = run_evolution_gate(run_path)
    print(f"evolution_results={run_path / 'evolution' / 'evolution-gate-results.jsonl'}")
    print(f"candidates={len(results)}")
    return 0


def command_inspect(args: argparse.Namespace) -> int:
    run_path = Path(args.run)
    if not run_path.is_absolute():
        run_path = Path.cwd() / run_path
    run_doc = read_yaml(run_path / "run.yaml")
    print(f"run_id={run_doc['run_id']}")
    print(f"status={run_doc['status']}")
    print(f"selected_agents={len(run_doc['selected_agents'])}")
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

    p_roster = sub.add_parser("roster")
    roster_sub = p_roster.add_subparsers(dest="roster_command", required=True)
    p_roster_list = roster_sub.add_parser("list")
    p_roster_list.set_defaults(func=command_roster_list)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
