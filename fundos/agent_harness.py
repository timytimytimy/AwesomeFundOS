from __future__ import annotations

from pathlib import Path
from typing import Any

from fundos.io import read_yaml, write_yaml

AGENT_HARNESS_VERSION = "0.1.0"
REQUIRED_SKILL_SECTIONS = {"Evidence Rules", "Context Management", "Role-Specific Checklist", "Forbidden Outputs"}


def evaluate_agent_harness(run_path: Path, selected: list[dict[str, str]]) -> dict[str, Any]:
    agent_results = []
    for item in selected:
        agent_id = item["agent_id"]
        context = read_optional_yaml(run_path / "context" / f"{agent_id}.context-pack.yaml", {})
        output = read_optional_yaml(run_path / "agent_work" / f"{agent_id}.structured.yaml", {})
        agent_results.append(evaluate_agent(agent_id, context, output))
    aggregate = aggregate_scores(agent_results)
    return {
        "version": AGENT_HARNESS_VERSION,
        "artifact_type": "agent_harness_report",
        "run_id": infer_run_id(run_path, agent_results),
        "agent_count": len(agent_results),
        "aggregate_scores": aggregate,
        "agent_results": agent_results,
        "controls": [
            "agent_specific_context_only",
            "context_management_required",
            "context_budget_manifest_required",
            "context_loss_accounting_required",
            "thread_summary_quality_required",
            "memory_lesson_traceability_required",
            "reasoning_layer_separation_required",
            "skill_contract_required",
            "agent_card_required",
            "evidence_traceability_required",
            "no_real_trade_action",
        ],
    }


def write_agent_harness(run_path: Path, selected: list[dict[str, str]]) -> dict[str, Any]:
    report = evaluate_agent_harness(run_path, selected)
    path = run_path / "harness" / "agent-harness.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    write_yaml(path, report)
    return report


def load_agent_harness(run_path: Path | None) -> dict[str, Any]:
    if not run_path:
        return default_report()
    path = run_path / "harness" / "agent-harness.yaml"
    if not path.exists():
        return default_report()
    return read_yaml(path) or default_report()


def default_report() -> dict[str, Any]:
    return {
        "version": AGENT_HARNESS_VERSION,
        "artifact_type": "agent_harness_report",
        "agent_count": 0,
        "aggregate_scores": {
            "context_compression": 0,
            "context_policy": 0,
            "context_management_quality": 0,
            "thread_memory_summary": 0,
            "memory_lesson_traceability": 0,
            "reasoning_layer_separation": 0,
            "memory_policy": 0,
            "tool_policy": 0,
            "skill_invocation": 0,
            "role_consistency": 0,
            "overall": 0,
        },
        "agent_results": [],
        "controls": [],
    }


def evaluate_agent(agent_id: str, context: dict[str, Any], output: dict[str, Any]) -> dict[str, Any]:
    context_quality = evaluate_context_compression(context, output)
    context_policy_quality = evaluate_context_policy(context)
    context_management_quality = evaluate_context_management(context)
    thread_memory_summary_quality = evaluate_thread_memory_summary(context)
    memory_lesson_traceability_quality = evaluate_memory_lesson_traceability(context, output)
    reasoning_layer_separation_quality = evaluate_reasoning_layer_separation(output)
    memory_policy_quality = evaluate_memory_policy(context, output)
    tool_policy_quality = evaluate_tool_policy(context, output)
    skill_quality = evaluate_skill_invocation(context, output)
    role_quality = evaluate_role_consistency(agent_id, context, output)
    overall = round((context_quality["score"] + context_policy_quality["score"] + context_management_quality["score"] + thread_memory_summary_quality["score"] + memory_lesson_traceability_quality["score"] + reasoning_layer_separation_quality["score"] + memory_policy_quality["score"] + tool_policy_quality["score"] + skill_quality["score"] + role_quality["score"]) / 10, 1)
    return {
        "agent_id": agent_id,
        "role": context.get("role") or output.get("role"),
        "overall_score": overall,
        "context_compression_quality": context_quality,
        "context_policy_quality": context_policy_quality,
        "context_management_quality": context_management_quality,
        "thread_memory_summary_quality": thread_memory_summary_quality,
        "memory_lesson_traceability_quality": memory_lesson_traceability_quality,
        "reasoning_layer_separation_quality": reasoning_layer_separation_quality,
        "memory_policy_quality": memory_policy_quality,
        "tool_policy_quality": tool_policy_quality,
        "skill_invocation_quality": skill_quality,
        "role_consistency_quality": role_quality,
        "blocking_issues": blocking_issues(context_quality, context_policy_quality, context_management_quality, thread_memory_summary_quality, memory_lesson_traceability_quality, reasoning_layer_separation_quality, memory_policy_quality, tool_policy_quality, skill_quality, role_quality),
    }


def evaluate_context_management(context: dict[str, Any]) -> dict[str, Any]:
    manifest = context.get("context_budget_manifest", {})
    loss = context.get("context_loss_accounting", {})
    controls = set(manifest.get("controls", []))
    token_budget = int(manifest.get("token_budget", context.get("context_budget_tokens", 0)) or 0)
    estimated_after = int(manifest.get("estimated_tokens_after", 0) or 0)
    excluded = loss.get("excluded_evidence", [])
    retained_claims = loss.get("retained_claim_ids", [])
    dropped_claims = loss.get("dropped_claim_ids", [])
    compression_style = manifest.get("compression_style", [])
    budget_manifest_present = bool(manifest)
    token_budget_respected = bool(token_budget) and estimated_after <= token_budget
    loss_accounting_present = bool(loss) and all(row.get("reason") for row in excluded)
    role_specific_compression_present = "role_specific_compression" in controls and bool(compression_style)
    evidence_loss_auditable = bool(retained_claims) and isinstance(dropped_claims, list)
    candidate_counted = manifest.get("candidate_items", 0) >= manifest.get("included_items", 0)
    score = 20
    if budget_manifest_present:
        score += 20
    if token_budget_respected:
        score += 15
    if loss_accounting_present:
        score += 20
    if role_specific_compression_present:
        score += 15
    if evidence_loss_auditable:
        score += 15
    if candidate_counted:
        score += 10
    return {
        "score": min(100, score),
        "budget_manifest_present": budget_manifest_present,
        "token_budget_respected": token_budget_respected,
        "loss_accounting_present": loss_accounting_present,
        "role_specific_compression_present": role_specific_compression_present,
        "evidence_loss_auditable": evidence_loss_auditable,
        "candidate_items": manifest.get("candidate_items", 0),
        "included_items": manifest.get("included_items", 0),
        "excluded_items": manifest.get("excluded_items", len(excluded)),
        "estimated_tokens_before": manifest.get("estimated_tokens_before", 0),
        "estimated_tokens_after": estimated_after,
        "compression_ratio": manifest.get("compression_ratio", 0),
        "compression_style": compression_style,
        "drop_reasons": sorted({row.get("reason") for row in excluded if row.get("reason")}),
    }


def evaluate_thread_memory_summary(context: dict[str, Any]) -> dict[str, Any]:
    summary = context.get("thread_memory_summary", {}) or {}
    manifest = context.get("context_budget_manifest", {}) or {}
    manifest_summary = manifest.get("thread_memory_summary", {}) or {}
    controls = set(summary.get("controls", []))
    manifest_controls = set(manifest.get("controls", []))
    available = bool(summary.get("available"))
    event_count = int(summary.get("event_count", 0) or 0)
    accepted = summary.get("accepted_memory_lessons", []) or []
    quarantined = summary.get("quarantined_candidates", []) or []
    rejected = summary.get("rejected_candidates", []) or []
    gaps = summary.get("open_research_gaps", []) or []
    recent = summary.get("recent_events", []) or []
    retrieval_only_control_present = "thread_summary_is_retrieval_input_only" in controls
    manifest_linked = (
        "thread_summary_included" in manifest_controls
        and bool(manifest_summary.get("included"))
        and int(manifest_summary.get("event_count", 0) or 0) == event_count
    )
    safety_boundaries_respected = summary.get("real_trade_allowed") is False and summary.get("broker_integration") == "disabled"
    summary_signal_present = bool(accepted or quarantined or rejected or gaps or recent)
    event_count_consistent = event_count >= len(recent)
    score = 20
    if available:
        score += 15
    if retrieval_only_control_present:
        score += 15
    if manifest_linked:
        score += 20
    if safety_boundaries_respected:
        score += 20
    if summary_signal_present:
        score += 15
    if event_count_consistent:
        score += 10
    return {
        "score": min(100, score),
        "available": available,
        "event_count": event_count,
        "latest_event_type": summary.get("latest_event_type", "none"),
        "retrieval_only_control_present": retrieval_only_control_present,
        "manifest_linked": manifest_linked,
        "safety_boundaries_respected": safety_boundaries_respected,
        "summary_signal_present": summary_signal_present,
        "event_count_consistent": event_count_consistent,
        "accepted_memory_lesson_count": len(accepted),
        "quarantined_candidate_count": len(quarantined),
        "rejected_candidate_count": len(rejected),
        "open_research_gap_count": len(gaps),
        "recent_event_count": len(recent),
    }


def evaluate_memory_lesson_traceability(context: dict[str, Any], output: dict[str, Any]) -> dict[str, Any]:
    summary = context.get("thread_memory_summary", {}) or {}
    influence = output.get("thread_memory_influence", {}) or {}
    context_lessons = summary.get("accepted_memory_lessons", []) or []
    output_lessons = influence.get("accepted_lessons_used", []) or []
    context_ids = {row.get("candidate_id") for row in context_lessons if row.get("candidate_id")}
    output_ids = {row.get("candidate_id") for row in output_lessons if row.get("candidate_id")}
    no_accepted_lessons = not context_ids
    accepted_lessons_declared = no_accepted_lessons or bool(output_ids)
    candidate_ids_match_context = output_ids <= context_ids and (no_accepted_lessons or context_ids <= output_ids)
    retrieval_only_usage = all(row.get("usage") == "retrieval_context_only" for row in output_lessons) and bool(influence.get("controls") or no_accepted_lessons)
    safety_boundaries_respected = influence.get("real_trade_allowed") is False and influence.get("broker_integration") == "disabled"
    summary_availability_matches = bool(influence.get("summary_available")) == bool(summary.get("available"))
    score = 20
    if accepted_lessons_declared:
        score += 20
    if candidate_ids_match_context:
        score += 20
    if retrieval_only_usage:
        score += 15
    if safety_boundaries_respected:
        score += 15
    if summary_availability_matches:
        score += 10
    return {
        "score": min(100, score),
        "accepted_lesson_count": len(context_ids),
        "output_lesson_count": len(output_ids),
        "accepted_lessons_declared": accepted_lessons_declared,
        "candidate_ids_match_context": candidate_ids_match_context,
        "retrieval_only_usage": retrieval_only_usage,
        "safety_boundaries_respected": safety_boundaries_respected,
        "summary_availability_matches": summary_availability_matches,
        "context_candidate_ids": sorted(context_ids),
        "output_candidate_ids": sorted(output_ids),
    }


def evaluate_reasoning_layer_separation(output: dict[str, Any]) -> dict[str, Any]:
    layers = output.get("reasoning_layers", {}) or {}
    current = layers.get("current_evidence_conclusions", []) or []
    memory = layers.get("thread_memory_influences", []) or []
    hypotheses = layers.get("hypotheses_to_validate", []) or []
    controls = set(layers.get("controls", []))
    current_evidence_layer_present = bool(current)
    hypothesis_layer_present = bool(hypotheses)
    current_evidence_has_traceable_claims = all(row.get("layer") == "current_evidence" and row.get("evidence_id") and row.get("claim_id") for row in current)
    memory_influences_retrieval_only = all(row.get("usage") == "retrieval_context_only" for row in memory)
    hypotheses_have_validation_requirements = all(row.get("layer") == "hypothesis_to_validate" and row.get("validation_required") for row in hypotheses)
    controls_present = {"separate_current_evidence_from_memory", "hypotheses_require_validation", "memory_is_retrieval_context_only"} <= controls
    safety_boundaries_respected = layers.get("real_trade_allowed") is False and layers.get("broker_integration") == "disabled"
    score = 10
    if current_evidence_layer_present:
        score += 15
    if hypothesis_layer_present:
        score += 15
    if current_evidence_has_traceable_claims:
        score += 20
    if memory_influences_retrieval_only:
        score += 15
    if hypotheses_have_validation_requirements:
        score += 15
    if controls_present:
        score += 10
    if safety_boundaries_respected:
        score += 10
    return {
        "score": min(100, score),
        "current_evidence_count": len(current),
        "memory_influence_count": len(memory),
        "hypothesis_count": len(hypotheses),
        "current_evidence_layer_present": current_evidence_layer_present,
        "hypothesis_layer_present": hypothesis_layer_present,
        "current_evidence_has_traceable_claims": current_evidence_has_traceable_claims,
        "memory_influences_retrieval_only": memory_influences_retrieval_only,
        "hypotheses_have_validation_requirements": hypotheses_have_validation_requirements,
        "controls_present": controls_present,
        "safety_boundaries_respected": safety_boundaries_respected,
    }


def evaluate_context_compression(context: dict[str, Any], output: dict[str, Any]) -> dict[str, Any]:
    included = context.get("included_evidence", [])
    missing = context.get("missing_evidence", [])
    contradictions = context.get("contradiction_table", [])
    key_claims = output.get("key_claims", [])
    allowed_claims = {claim for item in included for claim in item.get("allowed_claims", [])}
    output_claims = {claim.get("claim_id") for claim in key_claims if claim.get("claim_id")}
    evidence_ids = {item.get("evidence_id") for item in included if item.get("evidence_id")}
    output_evidence = {claim.get("evidence_id") for claim in key_claims if claim.get("evidence_id")}
    traceable = bool(output_evidence) and output_evidence <= evidence_ids
    claims_fit_context = bool(output_claims) and output_claims <= allowed_claims if allowed_claims else bool(output_claims)
    score = 40
    if included:
        score += 15
    if traceable:
        score += 15
    if claims_fit_context:
        score += 10
    if contradictions:
        score += 8
    if missing:
        score += 7
    if context.get("excluded_evidence_summary"):
        score += 5
    return {
        "score": min(100, score),
        "included_evidence": len(included),
        "allowed_claims": len(allowed_claims),
        "output_key_claims": len(key_claims),
        "evidence_traceability": traceable,
        "claims_fit_context": claims_fit_context,
        "contradiction_preserved": bool(contradictions),
        "missing_evidence_preserved": bool(missing),
        "noise_control_present": bool(context.get("excluded_evidence_summary")),
    }


def evaluate_context_policy(context: dict[str, Any]) -> dict[str, Any]:
    policy = context.get("context_policy", {})
    included = context.get("included_evidence", [])
    must_preserve = set(policy.get("must_preserve", []))
    harness_checks = set(policy.get("harness_checks", []))
    matched_tags = {tag for item in included for tag in item.get("policy_matched_tags", [])}
    preferred_tags = set(policy.get("preferred_context_tags", []))
    max_items = int(policy.get("max_context_items", 0) or 0)
    source_policy_match = bool(policy.get("available", True)) and bool(policy.get("source_path"))
    budget_respected = not max_items or len(included) <= max_items
    must_preserve_satisfied = {"evidence_ids", "claim_ids", "contradictions", "missing_evidence"} <= must_preserve and bool(context.get("contradiction_table")) and bool(context.get("missing_evidence"))
    role_focus_alignment = not included or bool(matched_tags & preferred_tags) or bool(policy.get("evidence_selection", {}).get("include_governance_agents_all_claims"))
    no_real_trade_action = policy.get("real_trade_allowed") is False and policy.get("broker_integration") is False
    score = 30
    if source_policy_match:
        score += 15
    if budget_respected:
        score += 15
    if must_preserve_satisfied:
        score += 20
    if role_focus_alignment:
        score += 10
    if no_real_trade_action:
        score += 10
    return {
        "score": min(100, score),
        "policy_available": bool(policy.get("available", True)),
        "source_policy_match": source_policy_match,
        "context_budget_respected": budget_respected,
        "must_preserve_satisfied": must_preserve_satisfied,
        "role_focus_alignment": role_focus_alignment,
        "no_real_trade_action": no_real_trade_action,
        "harness_checks_present": sorted(harness_checks),
        "preferred_context_tags": sorted(preferred_tags),
        "matched_context_tags": sorted(matched_tags),
        "max_context_items": max_items,
        "included_evidence": len(included),
    }


def evaluate_skill_invocation(context: dict[str, Any], output: dict[str, Any]) -> dict[str, Any]:
    skill = context.get("skill_contract", {})
    runtime = output.get("agent_runtime", {})
    sections = set(skill.get("sections", []))
    runtime_sections = set(runtime.get("skill_sections", []))
    required_present = REQUIRED_SKILL_SECTIONS <= sections
    runtime_matches = bool(runtime.get("skill_path")) and runtime.get("skill_path") == skill.get("source_path")
    checklist_count = len(output.get("role_checklist_applied", []))
    evidence_rule_count = len(output.get("skill_evidence_rules", []))
    score = 30
    if skill.get("available"):
        score += 15
    if required_present:
        score += 20
    if runtime_matches and runtime_sections == sections:
        score += 15
    if checklist_count:
        score += 10
    if evidence_rule_count:
        score += 10
    return {
        "score": min(100, score),
        "skill_available": bool(skill.get("available")),
        "required_sections_present": required_present,
        "runtime_matches_context": runtime_matches,
        "role_checklist_items": checklist_count,
        "evidence_rule_items": evidence_rule_count,
        "missing_required_sections": sorted(REQUIRED_SKILL_SECTIONS - sections),
    }


def evaluate_tool_policy(context: dict[str, Any], output: dict[str, Any]) -> dict[str, Any]:
    policy = context.get("tool_policy", {})
    allowed = set(policy.get("allowed_tools", []))
    required = set(policy.get("required_tools", []))
    forbidden = set(policy.get("forbidden_tools", []))
    declared = set(context.get("agent_card", {}).get("declared_tools", [])) or set(output.get("agent_declared_tools", []))
    output_allowed = set(output.get("allowed_tools", []))
    output_required = set(output.get("required_tools", []))
    missing_tools = {row.get("tool") for row in output.get("missing_tool_calls", []) if row.get("tool")}
    forbidden_actions = output.get("forbidden_tool_actions", [])
    checks = output.get("tool_permission_checks", {})
    tool_policy_available = bool(policy.get("available")) and bool(policy.get("source_path"))
    allowed_tools_declared = bool(allowed) and declared <= allowed and output_allowed == allowed
    required_tools_reported = required <= output_required and (not required or required <= missing_tools)
    forbidden_tools_respected = not bool((allowed | output_allowed) & forbidden) and not forbidden_actions and checks.get("forbidden_tools_respected", True)
    real_trade_disabled = policy.get("real_trade_allowed") is False and checks.get("real_trade_allowed") is False
    broker_integration_disabled = policy.get("broker_integration") is False and checks.get("broker_integration") is False
    score = 20
    if tool_policy_available:
        score += 15
    if allowed_tools_declared:
        score += 20
    if required_tools_reported:
        score += 15
    if forbidden_tools_respected:
        score += 15
    if real_trade_disabled:
        score += 8
    if broker_integration_disabled:
        score += 7
    return {
        "score": min(100, score),
        "tool_policy_available": tool_policy_available,
        "allowed_tools_declared": allowed_tools_declared,
        "required_tools_reported": required_tools_reported,
        "forbidden_tools_respected": forbidden_tools_respected,
        "real_trade_disabled": real_trade_disabled,
        "broker_integration_disabled": broker_integration_disabled,
        "harness_checks_present": sorted(policy.get("harness_checks", [])),
        "allowed_tools": sorted(allowed),
        "required_tools": sorted(required),
        "missing_required_tools": sorted(required - missing_tools),
        "forbidden_tools": sorted(forbidden),
    }


def evaluate_memory_policy(context: dict[str, Any], output: dict[str, Any]) -> dict[str, Any]:
    policy = context.get("memory_policy", {})
    retrieval = policy.get("retrieval_contract", {})
    writeback = policy.get("writeback_rules", {})
    forbidden = set(policy.get("forbidden_memory_writes", []))
    output_policy = output.get("memory_policy", {})
    output_namespaces = output.get("memory_namespaces", {})
    output_retrieval = output.get("memory_retrieval_contract", {})
    output_writeback = output.get("memory_writeback_rules", {})
    output_forbidden = set(output.get("forbidden_memory_writes", []))
    checks = output.get("memory_permission_checks", {})
    memory_policy_available = bool(policy.get("available")) and output_policy.get("source_path") == policy.get("source_path")
    retrieval_contract_declared = bool(retrieval.get("max_memory_items")) and output_retrieval.get("max_memory_items") == retrieval.get("max_memory_items")
    namespaces_aligned = set(policy.get("read_namespaces", [])) <= set(output_namespaces.get("read", [])) and set(policy.get("write_namespaces", [])) <= set(output_namespaces.get("write", []))
    evolution_gate_required = writeback.get("requires_evolution_gate") is True and output_writeback.get("requires_evolution_gate") is True and checks.get("evolution_gate_required") is True
    reversible_ledger_required = writeback.get("requires_reversible_ledger") is True and output_writeback.get("requires_reversible_ledger") is True
    forbidden_memory_writes_respected = {"core_profile", "tool_permissions", "risk_limits"} <= forbidden and forbidden <= output_forbidden
    real_trade_disabled = policy.get("real_trade_allowed") is False and checks.get("real_trade_allowed") is False
    broker_integration_disabled = policy.get("broker_integration") is False and checks.get("broker_integration") is False
    score = 20
    if memory_policy_available:
        score += 15
    if retrieval_contract_declared:
        score += 15
    if namespaces_aligned:
        score += 10
    if evolution_gate_required:
        score += 15
    if reversible_ledger_required:
        score += 8
    if forbidden_memory_writes_respected:
        score += 12
    if real_trade_disabled:
        score += 5
    if broker_integration_disabled:
        score += 5
    return {
        "score": min(100, score),
        "memory_policy_available": memory_policy_available,
        "retrieval_contract_declared": retrieval_contract_declared,
        "namespaces_aligned": namespaces_aligned,
        "evolution_gate_required": evolution_gate_required,
        "reversible_ledger_required": reversible_ledger_required,
        "forbidden_memory_writes_respected": forbidden_memory_writes_respected,
        "real_trade_disabled": real_trade_disabled,
        "broker_integration_disabled": broker_integration_disabled,
        "harness_checks_present": sorted(policy.get("harness_checks", [])),
        "read_namespaces": sorted(policy.get("read_namespaces", [])),
        "write_namespaces": sorted(policy.get("write_namespaces", [])),
        "max_memory_items": retrieval.get("max_memory_items", 0),
    }


def evaluate_role_consistency(agent_id: str, context: dict[str, Any], output: dict[str, Any]) -> dict[str, Any]:
    card = context.get("agent_card", {})
    runtime = output.get("agent_runtime", {})
    declared_skills = set(card.get("declared_skills", []))
    output_skills = set(output.get("agent_declared_skills", []))
    role_match = output.get("agent_id") == agent_id and output.get("role") == context.get("role")
    card_loaded = bool(card.get("available")) and runtime.get("agent_card_path") == card.get("source_path")
    boundaries_checked = bool(output.get("forbidden_actions_checked"))
    disclaimer_present = "不构成投资建议" in output.get("disclaimer", "")
    skill_alignment = bool(declared_skills) and output_skills == declared_skills
    score = 30
    if role_match:
        score += 20
    if card_loaded:
        score += 20
    if skill_alignment:
        score += 10
    if boundaries_checked:
        score += 10
    if disclaimer_present:
        score += 10
    return {
        "score": min(100, score),
        "role_match": role_match,
        "agent_card_loaded": card_loaded,
        "declared_skills_aligned": skill_alignment,
        "boundaries_checked": boundaries_checked,
        "disclaimer_present": disclaimer_present,
    }


def aggregate_scores(agent_results: list[dict[str, Any]]) -> dict[str, float]:
    if not agent_results:
        return {"context_compression": 0, "context_policy": 0, "context_management_quality": 0, "thread_memory_summary": 0, "memory_lesson_traceability": 0, "reasoning_layer_separation": 0, "memory_policy": 0, "tool_policy": 0, "skill_invocation": 0, "role_consistency": 0, "overall": 0}
    context_score = avg(row["context_compression_quality"]["score"] for row in agent_results)
    policy_score = avg(row["context_policy_quality"]["score"] for row in agent_results)
    context_management_score = avg(row["context_management_quality"]["score"] for row in agent_results)
    thread_summary_score = avg(row["thread_memory_summary_quality"]["score"] for row in agent_results)
    memory_lesson_score = avg(row["memory_lesson_traceability_quality"]["score"] for row in agent_results)
    reasoning_layer_score = avg(row["reasoning_layer_separation_quality"]["score"] for row in agent_results)
    memory_score = avg(row["memory_policy_quality"]["score"] for row in agent_results)
    tool_score = avg(row["tool_policy_quality"]["score"] for row in agent_results)
    skill_score = avg(row["skill_invocation_quality"]["score"] for row in agent_results)
    role_score = avg(row["role_consistency_quality"]["score"] for row in agent_results)
    return {
        "context_compression": context_score,
        "context_policy": policy_score,
        "context_management_quality": context_management_score,
        "thread_memory_summary": thread_summary_score,
        "memory_lesson_traceability": memory_lesson_score,
        "reasoning_layer_separation": reasoning_layer_score,
        "memory_policy": memory_score,
        "tool_policy": tool_score,
        "skill_invocation": skill_score,
        "role_consistency": role_score,
        "overall": round((context_score + policy_score + context_management_score + thread_summary_score + memory_lesson_score + reasoning_layer_score + memory_score + tool_score + skill_score + role_score) / 10, 1),
    }


def avg(values: Any) -> float:
    rows = list(values)
    if not rows:
        return 0
    return round(sum(rows) / len(rows), 1)


def blocking_issues(*quality_docs: dict[str, Any]) -> list[str]:
    issues = []
    for doc in quality_docs:
        if doc.get("score", 0) < 60:
            issues.append("agent_harness_score_below_60")
            break
    return issues


def infer_run_id(run_path: Path, agent_results: list[dict[str, Any]]) -> str:
    run_doc = run_path / "run.yaml"
    if run_doc.exists():
        return (read_yaml(run_doc) or {}).get("run_id", run_path.name)
    return run_path.name if run_path.name else "unknown"


def read_optional_yaml(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    return read_yaml(path) or default
