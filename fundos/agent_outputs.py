from __future__ import annotations

from pathlib import Path
from typing import Any

from fundos.io import DISCLAIMER, read_yaml, write_yaml
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
    maturity_contract = compact_maturity_contract(agent_card, skill_contract)
    memory_policy = context.get("memory_policy", {})
    thread_memory_summary = context.get("thread_memory_summary", {})
    tool_policy = context.get("tool_policy", {})
    missing_tool_calls = missing_required_tool_calls(tool_policy)
    forbidden_tool_actions = forbidden_tool_actions_for(tool_policy)
    tool_permission_checks = tool_permission_checks_for(agent_card, tool_policy, missing_tool_calls, forbidden_tool_actions)
    memory_permission_checks = memory_permission_checks_for(memory_policy)
    thread_influence = thread_memory_influence(thread_memory_summary)
    skill_guardrails = skill_contract.get("guardrails", [])
    guardrail_checks = guardrail_checks_for(skill_guardrails)
    procedure_steps = skill_contract.get("procedure", [])
    quality_gates = skill_contract.get("quality_gates", [])
    quality_gate_checks = quality_gate_checks_for(agent, context, summary, agent_card, skill_contract, guardrail_checks)
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
        "procedure_steps_executed": procedure_steps[:8],
        "quality_gates_checked": quality_gates[:8],
        "quality_gate_checks": quality_gate_checks,
        "skill_evidence_rules": skill_contract.get("evidence_rules", [])[:8],
        "skill_guardrails_applied": skill_guardrails[:8],
        "guardrail_checks": guardrail_checks,
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
        "thread_memory_influence": thread_influence,
        "tool_policy": compact_tool_policy(tool_policy),
        "allowed_tools": tool_policy.get("allowed_tools", []),
        "required_tools": tool_policy.get("required_tools", []),
        "missing_tool_calls": missing_tool_calls,
        "tool_permission_checks": tool_permission_checks,
        "forbidden_tool_actions": forbidden_tool_actions,
        "agent_declared_learning_patterns": agent_card.get("learning_patterns", []),
        "maturity_contract": maturity_contract,
        "evidence_coverage": summary["coverage"],
        "source_type_coverage": summary["source_types"],
        "key_claims": summary["key_claims"][:8],
        "reasoning_layers": reasoning_layers(summary, thread_influence, context),
        "learning_patterns": learning_patterns,
        "pattern_application_notes": pattern_application_notes(agent, learning_patterns),
        "analysis_points": analysis_points_for(agent, summary),
        "risks_or_gaps": context.get("missing_evidence", []) + risk_gaps_for(agent, primary, low_tier),
        "forbidden_actions_checked": context.get("forbidden_focus", []),
        "disclaimer": DISCLAIMER,
}


def compact_maturity_contract(agent_card: dict[str, Any], skill_contract: dict[str, Any]) -> dict[str, Any]:
    card_maturity = agent_card.get("maturity_contract", {}) or {}
    edge = card_maturity.get("differentiated_edge", {}) or {}
    capability = card_maturity.get("capability_benchmarks", {}) or {}
    compression = card_maturity.get("context_compression", {}) or {}
    skill_benchmark = skill_contract.get("role_specific_benchmark", {}) or {}
    skill_compression = skill_contract.get("context_compression_recipe", {}) or {}
    evolution_rules = skill_contract.get("evolution_candidate_rules", {}) or {}
    return {
        "edge_signature": edge.get("edge_signature"),
        "edge_scope": edge.get("edge_scope"),
        "capability_benchmark_id": capability.get("benchmark_id"),
        "skill_benchmark_id": skill_benchmark.get("benchmark_id"),
        "minimum_pass_score": capability.get("minimum_pass_score") or skill_benchmark.get("minimum_pass_score"),
        "context_priority_order": compression.get("context_priority_order") or skill_compression.get("context_priority_order"),
        "must_preserve_context": compression.get("must_preserve_context") or skill_compression.get("must_preserve_context"),
        "compression_loss_budget": compression.get("compression_loss_budget") or skill_compression.get("compression_loss_budget"),
        "evolution_allowed_candidate_types": evolution_rules.get("allowed_candidate_types"),
        "evolution_forbidden_candidate_types": evolution_rules.get("forbidden_candidate_types"),
        "evolution_approval_route": evolution_rules.get("approval_route"),
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def quality_gate_checks_for(agent: dict[str, Any], context: dict[str, Any], summary: dict[str, Any], agent_card: dict[str, Any], skill_contract: dict[str, Any], guardrail_checks: dict[str, Any]) -> dict[str, Any]:
    quality_gates = "\n".join(skill_contract.get("quality_gates", []))
    guardrails = "\n".join(skill_contract.get("guardrails", []))
    key_claims = summary.get("key_claims", [])
    has_traceable_claims = bool(key_claims) and all(row.get("evidence_id") and row.get("claim_id") for row in key_claims)
    has_missing_or_hypothesis_context = bool(context.get("missing_evidence")) or bool(context.get("hypothesis_queue")) or bool(context.get("low_confidence_items"))
    return {
        "identity_gate": bool(agent.get("id")) and bool(agent.get("role")) and bool(agent_card.get("identity")),
        "evidence_gate": has_traceable_claims or has_missing_or_hypothesis_context,
        "source_boundary_gate": "KOL" in quality_gates and "hypothesis" in quality_gates and "direct" in quality_gates,
        "context_gate": bool(context.get("context_budget_manifest")) and bool(context.get("context_loss_accounting")),
        "safety_gate": guardrail_checks.get("real_trade_allowed") is False and guardrail_checks.get("broker_integration") == "disabled",
        "evolution_gate": "EvolutionGate" in guardrails or "Evolution gate" in quality_gates,
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def guardrail_checks_for(guardrails: list[str]) -> dict[str, Any]:
    text = "\n".join(guardrails)
    return {
        "guardrails_present": bool(guardrails),
        "real_trade_disabled": "real_trade_allowed=false" in text and "real-money instructions" in text,
        "broker_integration_disabled": "broker_integration=disabled" in text,
        "evolution_gate_required": "EvolutionGate" in text,
        "boundaries_preserved": "Profile, Skill, Tool, Memory, Thread, Harness, and Evolution boundaries" in text,
        "kol_not_direct_signal": "hypotheses" in text and "direct conclusions require primary or cross-validated evidence" in text,
        "context_gap_confidence_cap": "cap confidence" in text and "follow-up research task" in text,
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def thread_memory_influence(summary: dict[str, Any]) -> dict[str, Any]:
    accepted = summary.get("accepted_memory_lessons", []) or []
    return {
        "summary_available": bool(summary.get("available")),
        "event_count": int(summary.get("event_count", 0) or 0),
        "latest_event_type": summary.get("latest_event_type", "none"),
        "accepted_lesson_count": len(accepted),
        "accepted_lessons_used": [
            {
                "candidate_id": lesson.get("candidate_id"),
                "semantic_memory_path": lesson.get("semantic_memory_path"),
                "approval_mode": lesson.get("approval_mode"),
                "usage": "retrieval_context_only",
            }
            for lesson in accepted
            if lesson.get("candidate_id")
        ],
        "open_research_gap_count": len(summary.get("open_research_gaps", []) or []),
        "quarantined_candidate_count": len(summary.get("quarantined_candidates", []) or []),
        "rejected_candidate_count": len(summary.get("rejected_candidates", []) or []),
        "controls": summary.get("controls", []),
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def reasoning_layers(summary: dict[str, Any], thread_influence: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    conclusions = []
    hypotheses = []
    for claim in summary.get("key_claims", [])[:8]:
        row = {
            "evidence_id": claim.get("evidence_id"),
            "claim_id": claim.get("claim_id"),
            "source_tier": claim.get("source_tier"),
            "source_type": claim.get("source_type"),
            "claim_type": claim.get("claim_type"),
            "confidence": claim.get("confidence"),
            "claim_text": claim.get("claim_text"),
        }
        if claim.get("claim_type") == "fact" and claim.get("source_tier") == "tier_1_primary_fact":
            conclusions.append({"layer": "current_evidence", **row})
        else:
            hypotheses.append({
                "layer": "hypothesis_to_validate",
                **row,
                "validation_required": "primary_or_cross_validated_evidence_required",
            })
    for gap in context.get("missing_evidence", [])[:5]:
        hypotheses.append({
            "layer": "hypothesis_to_validate",
            "hypothesis": gap,
            "validation_required": "research_gap_followup_required",
        })
    return {
        "current_evidence_conclusions": conclusions,
        "thread_memory_influences": thread_influence.get("accepted_lessons_used", []),
        "hypotheses_to_validate": hypotheses,
        "controls": [
            "separate_current_evidence_from_memory",
            "hypotheses_require_validation",
            "memory_is_retrieval_context_only",
            "no_real_trade_action",
        ],
        "real_trade_allowed": False,
        "broker_integration": "disabled",
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


def render_agent_markdown(agent_name: str, agent_role: str, query: str, context_focus: list[str], structured: dict[str, Any]) -> str:
    evidence_refs = [f"{claim['evidence_id']}:{claim['claim_id']}" for claim in structured["key_claims"][:5]]
    text = f"""# {agent_name} / {agent_role} 输出

任务：{query}

## 角色聚焦

{', '.join(context_focus)}

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
    if structured.get("tool_runtime_reconciliation"):
        rec = structured["tool_runtime_reconciliation"]
        text += "- tool_use_reconciliation_score: " + str(rec.get("score")) + "\n"
        text += "- confidence_cap_required: " + str(rec.get("confidence_cap_required")) + "\n"
    text += "\n\n## 分析要点\n\n" + "\n".join(f"- {point}" for point in structured["analysis_points"])
    text += "\n\n## 证据引用\n\n" + (", ".join(evidence_refs) if evidence_refs else "无")
    text += f"\n\n## 边界\n\n{DISCLAIMER}\n"
    return text


def write_agent_output(path: Path, agent: dict[str, Any], context: dict[str, Any], query: str, evidence_pack: dict[str, Any]) -> dict[str, Any]:
    structured = make_structured_agent_output(agent, context, evidence_pack, query)
    text = render_agent_markdown(agent["name"], agent["role"], query, context["required_focus"], structured)
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


def load_agent_outputs(run_path: Path) -> list[dict[str, Any]]:
    outputs = []
    for path in sorted((run_path / "agent_work").glob("*.structured.yaml")):
        try:
            from fundos.io import read_yaml
            loaded = read_yaml(path)
        except FileNotFoundError:
            continue
        if loaded:
            outputs.append(loaded)
    return outputs


def refresh_agent_outputs_with_tool_use(run_path: Path) -> dict[str, Any]:
    report_path = run_path / "harness" / "agent-tool-use.yaml"
    if not report_path.exists():
        return {"updated_outputs": 0, "reason": "missing_agent_tool_use_report"}
    report = read_yaml(report_path) or {}
    results = {row.get("agent_id"): row for row in report.get("agent_results", [])}
    updated = 0
    for structured_path in sorted((run_path / "agent_work").glob("*.structured.yaml")):
        structured = read_yaml(structured_path) or {}
        agent_id = structured.get("agent_id")
        reconciliation = results.get(agent_id)
        if not reconciliation:
            continue
        apply_tool_reconciliation(structured, reconciliation)
        write_yaml(structured_path, structured)
        markdown_path = run_path / "agent_work" / f"{agent_id}.md"
        markdown_path.write_text(
            render_agent_markdown(
                structured.get("agent_name") or agent_id,
                structured.get("role") or "Agent",
                structured.get("query") or "",
                structured.get("required_focus", []),
                structured,
            ),
            encoding="utf-8",
        )
        updated += 1
    return {"updated_outputs": updated, "report_path": "harness/agent-tool-use.yaml"}


def apply_tool_reconciliation(structured: dict[str, Any], reconciliation: dict[str, Any]) -> None:
    missing = reconciliation.get("missing_required_tools", []) or []
    forbidden = reconciliation.get("forbidden_called_tools", []) or []
    structured["missing_tool_calls"] = [
        {"tool": tool, "reason": "missing_in_agent_tool_use_reconciliation"}
        for tool in missing
    ]
    structured["forbidden_tool_actions"] = list(structured.get("forbidden_tool_actions", [])) + [
        {"action": tool, "status": "forbidden_tool_called_in_runtime"}
        for tool in forbidden
    ]
    checks = dict(structured.get("tool_permission_checks", {}))
    checks["missing_required_tools_reported"] = bool(structured["missing_tool_calls"]) if missing else True
    checks["confidence_cap_required"] = bool(reconciliation.get("confidence_cap_required"))
    checks["runtime_reconciliation_available"] = True
    checks["tool_results_linked_to_claim_graph"] = reconciliation.get("tool_results_linked_to_claim_graph", 0)
    structured["tool_permission_checks"] = checks
    structured["tool_runtime_reconciliation"] = {
        "source_path": "harness/agent-tool-use.yaml",
        "score": reconciliation.get("score", 0),
        "called_tools": reconciliation.get("called_tools", []),
        "missing_required_tools": missing,
        "forbidden_called_tools": forbidden,
        "confidence_cap_required": bool(reconciliation.get("confidence_cap_required")),
        "tool_results_linked_to_claim_graph": reconciliation.get("tool_results_linked_to_claim_graph", 0),
    }
    runtime = dict(structured.get("agent_runtime", {}))
    runtime["tool_use_reconciliation"] = "harness/agent-tool-use.yaml"
    structured["agent_runtime"] = runtime
