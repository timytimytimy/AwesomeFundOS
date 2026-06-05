from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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
    reasons = detect_reasons(tiers, tests, proposal, target_scope, candidate_type)

    decision = decide(source_quality, testability, overfitting_risk, role_drift_risk, reasons)
    controls = ["approval_required", "no_direct_profile_mutation", "no_real_trade_action"]
    if decision != "accept":
        controls.append("no_memory_write")
    return {
        "candidate_id": candidate["candidate_id"],
        "candidate_type": candidate_type,
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
        "required_follow_up_tests": tests if decision in {"quarantine", "reject"} else [],
        "source_basis": candidate.get("source_basis", []),
        "proposal": candidate.get("proposal", ""),
        "rationale": rationale_for(decision, reasons),
    }


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
    candidates = read_jsonl(evo_dir / "candidates.jsonl")
    results = [evaluate_candidate(candidate) for candidate in candidates]
    accepted = [row for row in results if row["decision"] == "accept"]
    quarantined = [row for row in results if row["decision"] == "quarantine"]
    rejected = [row for row in results if row["decision"] == "reject"]
    write_jsonl(evo_dir / "evolution-gate-results.jsonl", results)
    write_jsonl(evo_dir / "accepted.jsonl", accepted)
    write_jsonl(evo_dir / "quarantine.jsonl", quarantined)
    write_jsonl(evo_dir / "rejected.jsonl", rejected)
    return results
