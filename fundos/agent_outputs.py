from __future__ import annotations

from pathlib import Path
from typing import Any

from fundos.io import DISCLAIMER, write_yaml
from fundos.learning import compact_pattern, patterns_for_agent


def evidence_lookup(evidence_pack: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in evidence_pack.get("evidence_items", [])}


def summarize_context_evidence(context: dict[str, Any], evidence_pack: dict[str, Any]) -> dict[str, Any]:
    lookup = evidence_lookup(evidence_pack)
    coverage = {
        "tier_1_primary_fact": 0,
        "tier_2_canonical_framework": 0,
        "tier_3_verified_public_practitioner": 0,
        "tier_4_expert_opinion": 0,
        "tier_5_social_signal": 0,
        "tier_6_unverified": 0,
    }
    source_types: dict[str, int] = {}
    key_claims = []
    for included in context.get("included_evidence", []):
        item = lookup.get(included["evidence_id"])
        if not item:
            continue
        tier = item.get("source_tier", "tier_6_unverified")
        coverage[tier] = coverage.get(tier, 0) + 1
        source_type = item.get("source_type", "unknown")
        source_types[source_type] = source_types.get(source_type, 0) + 1
        allowed = set(included.get("allowed_claims", []))
        for claim in item.get("claims", []):
            if allowed and claim.get("claim_id") not in allowed:
                continue
            key_claims.append(
                {
                    "evidence_id": item["id"],
                    "claim_id": claim["claim_id"],
                    "source_tier": tier,
                    "source_type": source_type,
                    "claim_type": claim.get("claim_type"),
                    "confidence": claim.get("confidence"),
                    "claim_text": claim.get("claim_text"),
                }
            )
            break
    return {"coverage": coverage, "source_types": source_types, "key_claims": key_claims}


def agent_stance(agent: dict[str, Any], summary: dict[str, Any]) -> str:
    role = agent.get("role", "")
    primary = summary["coverage"].get("tier_1_primary_fact", 0)
    social = summary["coverage"].get("tier_5_social_signal", 0)
    if "Bear" in role:
        return "cautious_attack" if primary else "evidence_gap_attack"
    if "Risk" in role or "Defensive" in role:
        return "risk_control_first"
    if "Trader" in role:
        return "wait_for_price_confirmation" if primary else "no_trade_without_confirmation"
    if "FundManager" in role:
        return "continue_research" if primary else "needs_more_evidence"
    if social and not primary:
        return "hypothesis_only"
    return "constructive_but_evidence_capped" if primary else "needs_more_evidence"


def make_structured_agent_output(agent: dict[str, Any], context: dict[str, Any], evidence_pack: dict[str, Any], query: str) -> dict[str, Any]:
    summary = summarize_context_evidence(context, evidence_pack)
    primary = summary["coverage"].get("tier_1_primary_fact", 0)
    low_tier = summary["coverage"].get("tier_5_social_signal", 0) + summary["coverage"].get("tier_6_unverified", 0)
    confidence = "medium" if primary >= 1 else "low"
    learning_patterns = [compact_pattern(pattern) for pattern in patterns_for_agent(agent["id"], context_focus_tags(context))]
    return {
        "run_id": context["run_id"],
        "agent_id": agent["id"],
        "agent_name": agent.get("name"),
        "role": agent.get("role"),
        "query": query,
        "stance": agent_stance(agent, summary),
        "confidence": confidence,
        "required_focus": context.get("required_focus", []),
        "evidence_coverage": summary["coverage"],
        "source_type_coverage": summary["source_types"],
        "key_claims": summary["key_claims"][:8],
        "learning_patterns": learning_patterns,
        "pattern_application_notes": pattern_application_notes(agent, learning_patterns),
        "analysis_points": analysis_points_for(agent, summary),
        "risks_or_gaps": context.get("missing_evidence", []) + risk_gaps_for(agent, primary, low_tier),
        "forbidden_actions_checked": context.get("forbidden_focus", []),
        "disclaimer": DISCLAIMER,
    }



def context_focus_tags(context: dict[str, Any]) -> list[str]:
    tags = set()
    for included in context.get("included_evidence", []):
        reason = included.get("reason", "")
        if "Trader" in reason:
            tags.update(["trading", "risk"])
        elif "Risk" in reason:
            tags.update(["risk", "company", "trading"])
        elif "Bear" in reason:
            tags.update(["bear_case", "risk", "company"])
        elif "Analyst" in reason:
            tags.update(["industry", "company"])
    if not tags:
        tags.update(["industry", "company", "trading", "risk", "bear_case"])
    return sorted(tags)


def pattern_application_notes(agent: dict[str, Any], patterns: list[dict[str, Any]]) -> list[str]:
    if not patterns:
        return ["No role-specific distilled learning pattern selected for this agent."]
    notes = []
    for pattern in patterns[:3]:
        gates = ", ".join(pattern.get("validation_gates", [])[:3])
        notes.append(f"Apply {pattern['pattern_id']} as checklist only; validate with gates: {gates}.")
    return notes

def analysis_points_for(agent: dict[str, Any], summary: dict[str, Any]) -> list[str]:
    role = agent.get("role", "")
    claims = summary.get("key_claims", [])
    first_claim = claims[0]["claim_text"] if claims else "当前缺少可引用 claim。"
    if "Trader" in role:
        return ["只在一手事实和量价证据同时支持时讨论模拟入场触发。", first_claim]
    if "Risk" in role:
        return ["优先检查一手证据覆盖、低等级来源占比和仓位边界。", first_claim]
    if "Bear" in role:
        return ["攻击方法论源替代事实源、社媒热度替代订单验证的风险。", first_claim]
    if "Company" in role or "Governance" in role:
        return ["公司映射必须由公告、财报、订单、客户或收入证据验证。", first_claim]
    if "Analyst" in role:
        return ["产业链/chokepoint 假设必须从政策、公告、产业资料逐层验证。", first_claim]
    return ["综合各角色证据覆盖和未解决争议后再形成模拟投委会结论。", first_claim]


def risk_gaps_for(agent: dict[str, Any], primary: int, low_tier: int) -> list[str]:
    gaps = []
    if primary == 0:
        gaps.append("缺少 tier_1_primary_fact，一切结论只能作为假设。")
    if low_tier > 0:
        gaps.append("存在 tier_5/tier_6 低等级信号，只能用于情绪或线索。")
    if "Trader" in agent.get("role", ""):
        gaps.append("V1 尚未接入真实价格序列，不能形成具体买卖点。")
    return gaps


def write_agent_output(path: Path, agent: dict[str, Any], context: dict[str, Any], query: str, evidence_pack: dict[str, Any]) -> dict[str, Any]:
    structured = make_structured_agent_output(agent, context, evidence_pack, query)
    evidence_refs = [f"{claim['evidence_id']}:{claim['claim_id']}" for claim in structured["key_claims"][:5]]
    text = f"""# {agent['name']} / {agent['role']} 输出

任务：{query}

## 角色聚焦

{', '.join(context['required_focus'])}

## 立场与置信度

- stance: {structured['stance']}
- confidence: {structured['confidence']}

## 证据覆盖

"""
    text += "\n".join(f"- {tier}: {count}" for tier, count in structured["evidence_coverage"].items())
    text += "\n\n## 分析要点\n\n" + "\n".join(f"- {point}" for point in structured["analysis_points"])
    text += "\n\n## 证据引用\n\n" + (", ".join(evidence_refs) if evidence_refs else "无")
    text += f"\n\n## 边界\n\n{DISCLAIMER}\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    write_yaml(path.with_suffix(".structured.yaml"), structured)
    return structured


def summarize_agent_outputs(agent_outputs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "agent_id": output["agent_id"],
            "stance": output["stance"],
            "confidence": output["confidence"],
            "primary_evidence_count": output["evidence_coverage"].get("tier_1_primary_fact", 0),
        }
        for output in agent_outputs
    ]
