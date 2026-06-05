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
    agent_card = context.get("agent_card", {})
    skill_contract = context.get("skill_contract", {})
    memory_policy = context.get("memory_policy", {})
    tool_policy = context.get("tool_policy", {})
    missing_tool_calls = missing_required_tool_calls(tool_policy)
    forbidden_tool_actions = forbidden_tool_actions_for(tool_policy)
    tool_permission_checks = tool_permission_checks_for(agent_card, tool_policy, missing_tool_calls, forbidden_tool_actions)
    memory_permission_checks = memory_permission_checks_for(memory_policy)
    return {
        "run_id": context["run_id"],
        "agent_id": agent["id"],
        "agent_name": agent.get("name"),
        "role": agent.get("role"),
        "agent_runtime": {
            "agent_card_path": agent_card.get("source_path"),
            "agent_card_title": agent_card.get("title"),
            "skill_path": skill_contract.get("source_path"),
            "skill_name": skill_contract.get("name"),
            "skill_sections": skill_contract.get("sections", []),
        },
        "query": query,
        "stance": agent_stance(agent, summary),
        "confidence": confidence,
        "required_focus": context.get("required_focus", []),
        "decision_principles_applied": agent_card.get("decision_principles", [])[:8],
        "role_checklist_applied": skill_contract.get("role_checklist", [])[:8],
        "skill_evidence_rules": skill_contract.get("evidence_rules", [])[:8],
        "agent_declared_skills": agent_card.get("declared_skills", []),
        "agent_declared_tools": agent_card.get("declared_tools", []),
        "memory_policy": compact_memory_policy(memory_policy),
        "memory_namespaces": {
            "read": memory_policy.get("read_namespaces", []),
            "write": memory_policy.get("write_namespaces", []),
        },
        "memory_retrieval_contract": memory_policy.get("retrieval_contract", {}),
        "memory_writeback_rules": memory_policy.get("writeback_rules", {}),
        "memory_permission_checks": memory_permission_checks,
        "forbidden_memory_writes": memory_policy.get("forbidden_memory_writes", []),
        "tool_policy": compact_tool_policy(tool_policy),
        "allowed_tools": tool_policy.get("allowed_tools", []),
        "required_tools": tool_policy.get("required_tools", []),
        "missing_tool_calls": missing_tool_calls,
        "tool_permission_checks": tool_permission_checks,
        "forbidden_tool_actions": forbidden_tool_actions,
        "agent_declared_learning_patterns": agent_card.get("learning_patterns", []),
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


def compact_memory_policy(policy: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_path": policy.get("source_path"),
        "available": bool(policy.get("available", False)),
        "memory_policy_id": policy.get("memory_policy_id"),
        "role_family": policy.get("role_family"),
        "real_trade_allowed": policy.get("real_trade_allowed"),
        "broker_integration": policy.get("broker_integration"),
    }


def memory_permission_checks_for(policy: dict[str, Any]) -> dict[str, Any]:
    writeback = policy.get("writeback_rules", {})
    forbidden = set(policy.get("forbidden_memory_writes", []))
    retrieval = policy.get("retrieval_contract", {})
    return {
        "memory_policy_available": bool(policy.get("available")),
        "retrieval_contract_declared": bool(retrieval.get("max_memory_items")) and bool(retrieval.get("retrieval_tags")),
        "evolution_gate_required": writeback.get("requires_evolution_gate") is True,
        "reversible_ledger_required": writeback.get("requires_reversible_ledger") is True,
        "forbidden_memory_writes_declared": {"core_profile", "tool_permissions", "risk_limits"} <= forbidden,
        "direct_profile_mutation_disabled": writeback.get("allow_direct_profile_mutation") is False,
        "real_trade_allowed": bool(policy.get("real_trade_allowed")),
        "broker_integration": bool(policy.get("broker_integration")),
    }


def compact_tool_policy(policy: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_path": policy.get("source_path"),
        "available": bool(policy.get("available", False)),
        "tool_policy_id": policy.get("tool_policy_id"),
        "permission_level": policy.get("permission_level"),
        "real_trade_allowed": policy.get("real_trade_allowed"),
        "broker_integration": policy.get("broker_integration"),
        "source_boundary_rules": policy.get("source_boundary_rules", []),
    }


def missing_required_tool_calls(policy: dict[str, Any]) -> list[dict[str, str]]:
    # V1 records tool permissions before a concrete tool-call ledger exists.
    # Reporting required tools as missing keeps confidence capped and makes the
    # missing runtime adapter explicit instead of silently pretending tools ran.
    if not policy:
        return []
    reason = policy.get("missing_tool_reporting", {}).get("v1_reason", "tool_call_ledger_not_available_v1")
    return [{"tool": tool, "reason": reason} for tool in policy.get("required_tools", [])]


def forbidden_tool_actions_for(policy: dict[str, Any]) -> list[dict[str, str]]:
    actions = []
    if policy.get("real_trade_allowed") is not False:
        actions.append({"action": "real_trade_execution", "status": "forbidden_policy_not_disabled"})
    if policy.get("broker_integration") is not False:
        actions.append({"action": "broker_integration", "status": "forbidden_policy_not_disabled"})
    return actions


def tool_permission_checks_for(agent_card: dict[str, Any], policy: dict[str, Any], missing: list[dict[str, str]], forbidden_actions: list[dict[str, str]]) -> dict[str, Any]:
    allowed = set(policy.get("allowed_tools", []))
    declared = set(agent_card.get("declared_tools", []))
    forbidden = set(policy.get("forbidden_tools", []))
    return {
        "tool_policy_available": bool(policy.get("available")),
        "allowed_tools_declared": bool(allowed) and declared <= allowed,
        "forbidden_tools_respected": not bool(allowed & forbidden) and not forbidden_actions,
        "missing_required_tools_reported": bool(missing) if policy.get("required_tools") else True,
        "real_trade_allowed": bool(policy.get("real_trade_allowed")),
        "broker_integration": bool(policy.get("broker_integration")),
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


def runtime_lines(structured: dict[str, Any]) -> list[str]:
    runtime = structured.get("agent_runtime", {})
    return [
        f"- agent_card: {runtime.get('agent_card_path')}",
        f"- skill: {runtime.get('skill_path')}",
        f"- skill_sections: {', '.join(runtime.get('skill_sections', []))}",
    ]


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
    text += "\n\n## Agent Card / Skill 已加载\n\n" + "\n".join(runtime_lines(structured))
    text += "\n\n## Skill 角色检查清单\n\n" + "\n".join(f"- {item}" for item in structured.get("role_checklist_applied", []))
    text += "\n\n## Memory Policy 已加载\n\n"
    text += f"- memory_policy: {structured.get('memory_policy', {}).get('source_path')}\n"
    text += "- read_namespaces: " + ", ".join(structured.get("memory_namespaces", {}).get("read", [])) + "\n"
    text += "- writeback_requires_evolution_gate: " + str(structured.get("memory_writeback_rules", {}).get("requires_evolution_gate")) + "\n"
    text += "\n\n## Tool Policy 已加载\n\n"
    text += f"- tool_policy: {structured.get('tool_policy', {}).get('source_path')}\n"
    text += "- allowed_tools: " + ", ".join(structured.get("allowed_tools", [])) + "\n"
    text += "- missing_tool_calls: " + str(len(structured.get("missing_tool_calls", []))) + "\n"
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
