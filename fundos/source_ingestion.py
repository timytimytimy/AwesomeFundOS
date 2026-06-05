from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from fundos.io import read_yaml, write_yaml

FORBIDDEN_OUTPUTS = {
    "direct_buy_signal",
    "direct_sell_signal",
    "direct_a_share_buy_signal",
    "portfolio_action",
    "real_order",
    "broker_instruction",
}
DIRECT_TRADE_TERMS = [
    "直接买",
    "直接买入",
    "直接卖",
    "直接卖出",
    "买入信号",
    "卖出信号",
    "下单",
    "满仓",
    "加仓到",
    "broker",
    "real order",
    "buy now",
    "sell now",
]
PAID_TEXT_TERMS = ["付费课程原文", "课程逐字稿", "整章", "全文复制", "copied paid", "chapter text", "transcript dump"]
BASE_REQUIRED_GATES = [
    "historical_case_replay",
    "primary_evidence_check",
    "role_drift_check",
    "evidence_quality_check",
    "copyright_boundary_check",
]
PRACTITIONER_GATES = ["target_market_adaptation", "bear_case_review"]
SOCIAL_GATES = ["source_corroboration", "no_trade_signal_check"]


def ingest_source_candidates(run_path: Path, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    learning_dir = run_path / "learning"
    evolution_dir = run_path / "evolution"
    learning_dir.mkdir(parents=True, exist_ok=True)
    evolution_dir.mkdir(parents=True, exist_ok=True)

    normalized = [normalize_candidate(candidate) for candidate in candidates]
    quarantine_rows = [row for row in normalized if row.get("violations")]
    pattern_rows = [make_pattern_candidate(row) for row in normalized if not row.get("violations")]
    evolution_rows = [make_evolution_candidate(row, pattern) for row, pattern in zip([r for r in normalized if not r.get("violations")], pattern_rows)]

    write_jsonl(learning_dir / "source-candidates.jsonl", normalized)
    write_jsonl(learning_dir / "source-quarantine.jsonl", quarantine_rows)
    write_jsonl(learning_dir / "pattern-candidates.jsonl", pattern_rows)
    write_jsonl(evolution_dir / "candidates.jsonl", evolution_rows)

    report = {
        "version": "0.1.0",
        "artifact_type": "source_ingestion_report",
        "purpose": "Track external learning source intake, quarantine, pattern generation, and proposed evolution candidates.",
        "ingested_sources": len(normalized),
        "quarantined_sources": len(quarantine_rows),
        "pattern_candidates": len(pattern_rows),
        "evolution_candidates": len(evolution_rows),
        "direct_trade_signal_blocked": any("direct_trade_signal" in row.get("violations", []) for row in quarantine_rows),
        "copyright_violation_blocked": any("copied_paid_text" in row.get("violations", []) for row in quarantine_rows),
        "all_patterns_start_quarantined": all(row.get("status") == "quarantine" for row in pattern_rows),
        "real_trade_allowed": False,
        "broker_integration": "disabled",
        "controls": [
            "no_direct_trade_signal",
            "no_copied_paid_text",
            "primary_evidence_validation_required",
            "historical_case_replay_required",
            "social_or_kol_cannot_direct_buy_sell",
            "evolution_candidate_is_proposed_not_applied",
        ],
        "artifacts": {
            "source_candidates": "learning/source-candidates.jsonl",
            "source_quarantine": "learning/source-quarantine.jsonl",
            "pattern_candidates": "learning/pattern-candidates.jsonl",
            "evolution_candidates": "evolution/candidates.jsonl",
        },
    }
    write_yaml(learning_dir / "source-ingestion-report.yaml", report)
    return report


def load_ingestion_report(run_path: Path | None) -> dict[str, Any]:
    if not run_path:
        return missing_report()
    path = run_path / "learning" / "source-ingestion-report.yaml"
    if not path.exists():
        return missing_report()
    doc = read_yaml(path)
    doc["report_path"] = "learning/source-ingestion-report.yaml"
    return doc


def missing_report() -> dict[str, Any]:
    return {
        "artifact_type": "source_ingestion_report",
        "status": "missing",
        "ingested_sources": 0,
        "quarantined_sources": 0,
        "pattern_candidates": 0,
        "evolution_candidates": 0,
        "direct_trade_signal_blocked": False,
        "copyright_violation_blocked": False,
        "real_trade_allowed": False,
        "broker_integration": "disabled",
        "controls": [],
    }


def normalize_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    source_id = candidate.get("source_id") or stable_id(candidate)
    source_type = classify_source_type(candidate)
    source_tier = assign_source_tier(candidate, source_type)
    requested_outputs = list(candidate.get("requested_outputs", []))
    allowed = allowed_outputs(source_type, requested_outputs)
    not_allowed = sorted(FORBIDDEN_OUTPUTS | set(candidate.get("not_allowed_outputs", [])))
    violations = boundary_violations(candidate, requested_outputs)
    return {
        "source_id": source_id,
        "display_name": candidate.get("display_name") or source_id,
        "source_type": source_type,
        "source_tier": source_tier,
        "url": candidate.get("url", candidate.get("source_url", "")),
        "author": candidate.get("author", ""),
        "summary": candidate.get("summary", ""),
        "claims": candidate.get("claims", []),
        "requested_outputs": requested_outputs,
        "allowed_learning_outputs": allowed,
        "not_allowed_outputs": not_allowed,
        "target_agents": candidate.get("target_agents", []),
        "required_gates": required_gates_for(source_type, source_tier),
        "classification_status": "quarantine",
        "violations": violations,
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def classify_source_type(candidate: dict[str, Any]) -> str:
    raw_type = str(candidate.get("source_type", "")).strip()
    if raw_type:
        return raw_type
    text = searchable_text(candidate)
    if any(name in text for name in ["serenity", "aleabitoreddit", "lihai"]):
        return "public_practitioner"
    if any(name in text for name in ["howard marks", "druckenmiller", "soros", "oneil", "minervini", "buffett", "munger", "peter lynch"]):
        return "canonical_framework"
    if "book" in text or "书" in text:
        return "book"
    if "course" in text or "课程" in text:
        return "course"
    if "case" in text or "案例" in text:
        return "historical_case"
    if "x.com" in text or "twitter" in text or "社交" in text:
        return "social_signal"
    return "unknown"


def assign_source_tier(candidate: dict[str, Any], source_type: str) -> str:
    text = searchable_text(candidate)
    if any(name in text for name in ["serenity", "aleabitoreddit", "lihai"]):
        return "tier_3_verified_public_practitioner"
    if source_type in {"canonical_framework", "book", "course"} and any(
        name in text for name in ["howard marks", "druckenmiller", "soros", "oneil", "minervini", "buffett", "munger", "peter lynch"]
    ):
        return "tier_2_canonical_framework"
    if source_type == "historical_case":
        return "tier_2_canonical_framework"
    if source_type == "public_practitioner":
        return "tier_3_verified_public_practitioner"
    if source_type == "social_signal":
        return "tier_5_social_signal"
    return "tier_6_unverified"


def allowed_outputs(source_type: str, requested_outputs: list[str]) -> list[str]:
    defaults = {
        "public_practitioner": ["research_lens", "checklist", "failure_pattern", "market_state_taxonomy"],
        "canonical_framework": ["principle_candidate", "checklist", "evaluation_rubric"],
        "book": ["framework_summary", "principle_candidate", "checklist"],
        "course": ["skill_gap", "practice_task", "rubric_candidate"],
        "historical_case": ["case_replay", "failure_pattern", "market_state_taxonomy"],
        "social_signal": ["hypothesis_seed", "source_discovery"],
    }.get(source_type, ["hypothesis_seed"])
    merged = []
    for item in defaults + requested_outputs:
        if item not in FORBIDDEN_OUTPUTS and item not in merged:
            merged.append(item)
    return merged


def boundary_violations(candidate: dict[str, Any], requested_outputs: list[str]) -> list[str]:
    text = searchable_text(candidate)
    violations: list[str] = []
    if any(term.lower() in text for term in DIRECT_TRADE_TERMS):
        violations.append("direct_trade_signal")
    if FORBIDDEN_OUTPUTS & set(requested_outputs):
        violations.append("requested_forbidden_output")
    if any(term.lower() in text for term in PAID_TEXT_TERMS):
        violations.append("copied_paid_text")
    if candidate.get("real_trade_allowed") is True:
        violations.append("real_trade_requested")
    return violations


def required_gates_for(source_type: str, source_tier: str) -> list[str]:
    gates = list(BASE_REQUIRED_GATES)
    if source_type == "public_practitioner" or source_tier == "tier_3_verified_public_practitioner":
        gates.extend(PRACTITIONER_GATES)
    if source_type == "social_signal" or source_tier in {"tier_5_social_signal", "tier_6_unverified"}:
        gates.extend(SOCIAL_GATES)
    return dedupe(gates)


def make_pattern_candidate(source: dict[str, Any]) -> dict[str, Any]:
    pattern_id = f"pattern_{source['source_id']}"
    return {
        "pattern_id": pattern_id,
        "source_id": source["source_id"],
        "source_tier": source["source_tier"],
        "source_type": source["source_type"],
        "name": f"Distilled pattern from {source.get('display_name', source['source_id'])}",
        "summary": source.get("summary", ""),
        "claims_to_validate": source.get("claims", []),
        "target_agents": source.get("target_agents", []),
        "allowed_learning_outputs": source.get("allowed_learning_outputs", []),
        "not_allowed_outputs": source.get("not_allowed_outputs", []),
        "required_gates": source.get("required_gates", []),
        "status": "quarantine",
        "memory_write_allowed": False,
        "real_trade_allowed": False,
    }


def make_evolution_candidate(source: dict[str, Any], pattern: dict[str, Any]) -> dict[str, Any]:
    candidate_type = "skill_update" if "checklist" in pattern.get("allowed_learning_outputs", []) else "principle_update"
    target_agent = first_or_default(source.get("target_agents", []), "learning_curator")
    return {
        "candidate_id": f"cand_source_{source['source_id']}",
        "source_agent": "learning_curator",
        "target_agent": target_agent,
        "candidate_type": candidate_type,
        "target_scope": "agent_memory" if target_agent != "learning_curator" else "workflow",
        "proposal": f"将外部学习源 {source.get('display_name', source['source_id'])} 提炼为可验证的研究流程候选，而不是交易信号。",
        "source_basis": [
            {
                "source_id": source["source_id"],
                "source_tier": source["source_tier"],
                "source_type": source["source_type"],
                "rationale": "source ingestion candidate; quarantined until gates pass",
            }
        ],
        "pattern_candidate_id": pattern["pattern_id"],
        "required_tests": pattern.get("required_gates", []),
        "status": "proposed",
        "memory_write_allowed": False,
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def searchable_text(candidate: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ["source_id", "display_name", "source_type", "url", "source_url", "author", "summary"]:
        value = candidate.get(key)
        if value:
            parts.append(str(value))
    for claim in candidate.get("claims", []) or []:
        parts.append(str(claim))
    return " ".join(parts).lower()


def stable_id(candidate: dict[str, Any]) -> str:
    base = candidate.get("display_name") or candidate.get("url") or candidate.get("summary") or "source"
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", str(base)).strip("_").lower()
    return slug[:80] or "source"


def first_or_default(values: list[str], default: str) -> str:
    return values[0] if values else default


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            out.append(value)
            seen.add(value)
    return out
