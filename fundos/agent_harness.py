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
            "skill_invocation": 0,
            "role_consistency": 0,
            "overall": 0,
        },
        "agent_results": [],
        "controls": [],
    }


def evaluate_agent(agent_id: str, context: dict[str, Any], output: dict[str, Any]) -> dict[str, Any]:
    context_quality = evaluate_context_compression(context, output)
    skill_quality = evaluate_skill_invocation(context, output)
    role_quality = evaluate_role_consistency(agent_id, context, output)
    overall = round((context_quality["score"] + skill_quality["score"] + role_quality["score"]) / 3, 1)
    return {
        "agent_id": agent_id,
        "role": context.get("role") or output.get("role"),
        "overall_score": overall,
        "context_compression_quality": context_quality,
        "skill_invocation_quality": skill_quality,
        "role_consistency_quality": role_quality,
        "blocking_issues": blocking_issues(context_quality, skill_quality, role_quality),
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
        return {"context_compression": 0, "skill_invocation": 0, "role_consistency": 0, "overall": 0}
    context_score = avg(row["context_compression_quality"]["score"] for row in agent_results)
    skill_score = avg(row["skill_invocation_quality"]["score"] for row in agent_results)
    role_score = avg(row["role_consistency_quality"]["score"] for row in agent_results)
    return {
        "context_compression": context_score,
        "skill_invocation": skill_score,
        "role_consistency": role_score,
        "overall": round((context_score + skill_score + role_score) / 3, 1),
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
