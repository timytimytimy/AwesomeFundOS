from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fundos.agent_threads import record_run_threads
from fundos.capabilities import apply_capability_versions
from fundos.capability_regression import run_capability_regression
from fundos.learning import source_registry_by_id, write_run_learning_source_registry
from fundos.memory import apply_evolution_results

PRIMARY_TIERS = {"tier_1_primary_fact", "tier_2_canonical_framework"}
METHODOLOGY_TIERS = {"tier_3_verified_public_practitioner", "tier_4_expert_opinion"}
LOW_TIERS = {"tier_5_social_signal", "tier_6_unverified"}
PROTECTED_SCOPES = {"core_profile", "org_structure", "tool_permission", "risk_limit"}
SOCIAL_BUY_TERMS = ["直接买", "直接买入", "buy", "买入信号", "放宽风控", "提高风险偏好"]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def evaluate_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    tiers = [basis.get("source_tier", "tier_6_unverified") for basis in candidate.get("source_basis", [])]
    tests = candidate.get("required_tests", [])
    proposal = candidate.get("proposal", "").lower()
    target_scope = candidate.get("target_scope", "agent_memory")
    candidate_type = candidate.get("candidate_type", "unknown")

    source_quality = score_source_quality(tiers)
    testability = score_testability(tests, candidate_type)
    overfitting_risk = score_overfitting_risk(tiers, tests, proposal)
    role_drift_risk = score_role_drift_risk(target_scope, candidate_type, proposal)
    expected_value = score_expected_value(candidate_type, proposal)
    registry_gates = required_source_registry_gates(candidate)
    missing_registry_gates = [gate for gate in registry_gates if gate not in tests]
    reasons = detect_reasons(tiers, tests, proposal, target_scope, candidate_type)
    if missing_registry_gates:
        reasons.append("missing_source_registry_required_gate")

    decision = decide(source_quality, testability, overfitting_risk, role_drift_risk, reasons)
    controls = ["approval_required", "no_direct_profile_mutation", "no_real_trade_action", "source_registry_gate_check"]
    if decision != "accept":
        controls.append("no_memory_write")
    follow_up_tests = sorted(set(tests + missing_registry_gates)) if decision in {"quarantine", "reject"} else []
    return {
        "candidate_id": candidate["candidate_id"],
        "run_id": candidate.get("run_id"),
        "source_agent": candidate.get("source_agent"),
        "target_agent": candidate.get("target_agent", candidate.get("source_agent")),
        "candidate_type": candidate_type,
        "target_scope": target_scope,
        "decision": decision,
        "scores": {
            "source_quality": source_quality,
            "testability": testability,
            "overfitting_risk": overfitting_risk,
            "role_drift_risk": role_drift_risk,
            "expected_value": expected_value,
        },
        "reasons": reasons,
        "controls": controls,
        "memory_write_allowed": False,
        "required_tests": tests,
        "source_registry_required_gates": registry_gates,
        "required_follow_up_tests": follow_up_tests,
        "source_basis": candidate.get("source_basis", []),
        "proposal": candidate.get("proposal", ""),
        "adoption_route": candidate.get("adoption_route"),
        "memory_write_policy": candidate.get("memory_write_policy"),
        "capability_kind": candidate.get("capability_kind"),
        "human_approval_required": candidate.get("human_approval_required"),
        "protected_mutation_allowed": candidate.get("protected_mutation_allowed", False),
        "auto_apply_allowed": candidate.get("auto_apply_allowed", False),
        "rationale": rationale_for(decision, reasons),
    }


def required_source_registry_gates(candidate: dict[str, Any]) -> list[str]:
    registry = source_registry_by_id()
    required: list[str] = []
    for basis in candidate.get("source_basis", []):
        source_id = basis.get("source_id")
        source = registry.get(source_id) if source_id else None
        if not source:
            continue
        for gate in source.get("required_gates_for_evolution", []):
            if gate not in required:
                required.append(gate)
    return required


def score_source_quality(tiers: list[str]) -> int:
    if not tiers:
        return 20
    score = 0
    for tier in tiers:
        if tier == "tier_1_primary_fact":
            score += 95
        elif tier == "tier_2_canonical_framework":
            score += 85
        elif tier == "tier_3_verified_public_practitioner":
            score += 75
        elif tier == "tier_4_expert_opinion":
            score += 60
        elif tier == "tier_5_social_signal":
            score += 35
        else:
            score += 20
    return round(score / len(tiers))


def score_testability(tests: list[str], candidate_type: str) -> int:
    if not tests:
        return 20
    score = min(90, 35 + len(tests) * 20)
    if "historical_case_replay" in tests:
        score += 5
    if "role_drift_check" in tests:
        score += 5
    if candidate_type in {"principle_update", "skill_update", "workflow_update"}:
        score += 5
    return min(95, score)


def score_overfitting_risk(tiers: list[str], tests: list[str], proposal: str) -> int:
    risk = 35
    if len(tiers) <= 1:
        risk += 15
    if any(tier in LOW_TIERS for tier in tiers):
        risk += 25
    if "历史案例" in proposal or "historical" in proposal:
        risk += 10
    if "historical_case_replay" in tests:
        risk -= 15
    if "evidence_quality_check" in tests:
        risk -= 10
    return max(5, min(95, risk))


def score_role_drift_risk(target_scope: str, candidate_type: str, proposal: str) -> int:
    risk = 20
    if target_scope in PROTECTED_SCOPES:
        risk += 45
    if candidate_type in {"profile_update", "tool_permission_update", "risk_limit_update"}:
        risk += 25
    if "风险偏好" in proposal or "risk preference" in proposal:
        risk += 20
    if "放宽风控" in proposal:
        risk += 20
    return max(5, min(95, risk))


def score_expected_value(candidate_type: str, proposal: str) -> int:
    score = 55
    if candidate_type in {"principle_update", "skill_update", "workflow_update"}:
        score += 15
    if any(term in proposal for term in ["证据", "复盘", "checklist", "一手", "验证"]):
        score += 10
    if any(term in proposal for term in ["直接买", "放宽风控", "提高风险偏好"]):
        score -= 30
    return max(5, min(95, score))


def detect_reasons(tiers: list[str], tests: list[str], proposal: str, target_scope: str, candidate_type: str) -> list[str]:
    reasons = []
    if not tiers:
        reasons.append("missing_source_basis")
    if any(tier in LOW_TIERS for tier in tiers):
        reasons.append("low_tier_source_basis")
    if any(tier in LOW_TIERS for tier in tiers) and any(term in proposal for term in SOCIAL_BUY_TERMS):
        reasons.append("social_signal_direct_buy")
    if not tests:
        reasons.append("missing_required_tests")
    if target_scope in PROTECTED_SCOPES or candidate_type in {"profile_update", "tool_permission_update", "risk_limit_update"}:
        reasons.append("core_profile_mutation")
    return reasons


def decide(source_quality: int, testability: int, overfitting_risk: int, role_drift_risk: int, reasons: list[str]) -> str:
    hard_reject = {"social_signal_direct_buy", "core_profile_mutation"}
    if hard_reject & set(reasons):
        return "reject"
    if "missing_source_registry_required_gate" in reasons:
        return "quarantine"
    if source_quality >= 80 and testability >= 70 and overfitting_risk <= 55 and role_drift_risk <= 45:
        return "accept"
    if source_quality < 35 or testability < 30:
        return "reject"
    return "quarantine"


def rationale_for(decision: str, reasons: list[str]) -> str:
    if decision == "accept":
        return "Candidate is evidence-backed and testable, but still requires approval before memory writes."
    if decision == "reject":
        return "Candidate violates safety/evidence boundaries: " + ", ".join(reasons)
    return "Candidate may be useful but needs more validation before adoption."


def run_evolution_gate(run_path: Path) -> list[dict[str, Any]]:
    evo_dir = run_path / "evolution"
    write_run_learning_source_registry(run_path)
    candidates = collect_evolution_candidates(run_path)
    results = [evaluate_candidate(candidate) for candidate in candidates]
    apply_evolution_results(run_path, results)
    record_evolution_thread_events(run_path, results)
    apply_capability_versions(run_path, results)
    run_capability_regression(run_path)
    accepted = [row for row in results if row["decision"] == "accept"]
    quarantined = [row for row in results if row["decision"] == "quarantine"]
    rejected = [row for row in results if row["decision"] == "reject"]
    write_jsonl(evo_dir / "evolution-gate-results.jsonl", results)
    write_jsonl(evo_dir / "accepted.jsonl", accepted)
    write_jsonl(evo_dir / "quarantine.jsonl", quarantined)
    write_jsonl(evo_dir / "rejected.jsonl", rejected)
    return results


def record_evolution_thread_events(run_path: Path, results: list[dict[str, Any]]) -> None:
    for result in results:
        target_agent = result.get("target_agent") or result.get("source_agent")
        if not target_agent:
            continue
        decision = str(result.get("decision") or "unknown")
        event_decision = {"accept": "accepted", "quarantine": "quarantined", "reject": "rejected"}.get(decision, decision)
        record_run_threads(
            run_path,
            [{"agent_id": str(target_agent), "role": "evolution_candidate_target"}],
            event_type=f"evolution_candidate_{event_decision}",
            payload={
                "candidate_id": result.get("candidate_id"),
                "decision": decision,
                "candidate_type": result.get("candidate_type"),
                "target_scope": result.get("target_scope"),
                "adoption_route": result.get("adoption_route"),
                "memory_write_policy": result.get("memory_write_policy"),
                "scores": result.get("scores", {}),
                "reasons": result.get("reasons", []),
                "memory_write_allowed": bool(result.get("memory_write_allowed")),
                "real_trade_allowed": False,
                "broker_integration": "disabled",
            },
        )
        memory_write = result.get("memory_write") or {}
        if result.get("memory_write_allowed") and memory_write:
            record_run_threads(
                run_path,
                [{"agent_id": str(target_agent), "role": "evolution_memory_target"}],
                event_type="memory_writeback_applied",
                payload={
                    "candidate_id": result.get("candidate_id"),
                    "candidate_type": result.get("candidate_type"),
                    "target_scope": result.get("target_scope"),
                    "approval_mode": memory_write.get("approval_mode"),
                    "already_written": bool(memory_write.get("already_written")),
                    "semantic_memory_path": memory_write.get("semantic_memory_path"),
                    "agent_ledger_path": memory_write.get("agent_ledger_path"),
                    "organization_ledger_path": memory_write.get("organization_ledger_path"),
                    "real_trade_allowed": False,
                    "broker_integration": "disabled",
                },
            )


def collect_evolution_candidates(run_path: Path) -> list[dict[str, Any]]:
    candidates = read_jsonl(run_path / "evolution" / "candidates.jsonl")
    candidates.extend(read_jsonl(run_path / "portfolio" / "review-candidates.jsonl"))
    return dedupe_candidates(candidates)


def dedupe_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for candidate in candidates:
        candidate_id = candidate.get("candidate_id")
        if candidate_id and candidate_id in seen:
            continue
        if candidate_id:
            seen.add(candidate_id)
        unique.append(candidate)
    return unique
