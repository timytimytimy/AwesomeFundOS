from __future__ import annotations

from pathlib import Path
from typing import Any

from fundos.io import read_yaml, write_yaml

CASE_REPLAY_VERSION = "0.1.0"

DEFAULT_CASES: list[dict[str, Any]] = [
    {
        "case_id": "a_share_theme_diffusion_policy_to_leader_to_laggard",
        "case_type": "theme_diffusion",
        "market": "CN_A_SHARE",
        "tags": ["industry", "trading", "risk", "bear_case"],
        "pattern_ids": ["a_share_theme_diffusion_case", "serenity_scheme_first_chokepoint"],
        "market_state": "policy_ignition_to_late_stage_diffusion",
        "known_lessons": [
            "政策点火不等于所有映射标的都有基本面兑现。",
            "越到后期越要降低低质量跟风标的权重。",
            "案例只能提供 falsifiable checklist，不能直接映射买卖。",
        ],
        "failure_modes": ["one_case_direct_mapping", "late_stage_chasing", "evidence_quality_decay"],
    },
    {
        "case_id": "a_share_market_state_drawdown_discipline",
        "case_type": "market_state",
        "market": "CN_A_SHARE",
        "tags": ["trading", "risk", "bear_case"],
        "pattern_ids": ["lihai_a_share_market_state", "a_share_theme_diffusion_case"],
        "market_state": "weak_or_retreating_theme",
        "known_lessons": [
            "市场状态和账户回撤优先于单票叙事。",
            "没有退出条件的买点判断不可接受。",
        ],
        "failure_modes": ["drawdown_blindness", "no_exit_plan", "sentiment_reversal"],
    },
    {
        "case_id": "governance_blowup_primary_evidence_gap",
        "case_type": "fraud_blowup",
        "market": "CN_A_SHARE",
        "tags": ["company", "risk", "bear_case"],
        "pattern_ids": ["fraud_blowup_case", "howard_marks_cycle_risk"],
        "market_state": "confidence_break",
        "known_lessons": [
            "财务和治理疑点不能被主题强度抵消。",
            "缺少一手证据时必须降低置信度和模拟仓位。",
        ],
        "failure_modes": ["governance_blindness", "source_tier_inflation"],
    },
]


def load_case_library(case_library_path: Path | None = None) -> list[dict[str, Any]]:
    if case_library_path and case_library_path.exists():
        doc = read_yaml(case_library_path) or {}
        return doc.get("cases", [])
    return DEFAULT_CASES


def load_run_patterns(run_path: Path) -> list[dict[str, Any]]:
    path = run_path / "learning" / "patterns.yaml"
    if not path.exists():
        return []
    doc = read_yaml(path) or {}
    return doc.get("patterns", [])


def needs_case_replay(pattern: dict[str, Any]) -> bool:
    gates = set(pattern.get("validation_gates", []))
    return bool({"historical_case_replay", "A_share_case_replay"} & gates)


def run_case_replay(run_path: Path, case_library_path: Path | None = None) -> dict[str, Any]:
    patterns = [pattern for pattern in load_run_patterns(run_path) if needs_case_replay(pattern)]
    cases = load_case_library(case_library_path)
    results: list[dict[str, Any]] = []
    for pattern in patterns:
        matched = match_cases(pattern, cases)
        if not matched:
            results.append(no_match_result(pattern))
            continue
        for case in matched:
            results.append(evaluate_pattern_against_case(pattern, case))
    replay = build_replay_summary(patterns, cases, results)
    write_yaml(run_path / "harness" / "historical-case-replay.yaml", replay)
    return replay


def match_cases(pattern: dict[str, Any], cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pattern_id = pattern.get("id")
    pattern_tags = set(pattern.get("tags", []))
    matched = []
    for case in cases:
        case_tags = set(case.get("tags", []))
        if pattern_id in case.get("pattern_ids", []) or pattern_tags & case_tags:
            matched.append(case)
    return matched[:3]


def no_match_result(pattern: dict[str, Any]) -> dict[str, Any]:
    return {
        "pattern_id": pattern.get("id"),
        "case_id": "none",
        "case_type": "none",
        "fit_score": 0,
        "overfit_risk": 95,
        "verdict": "needs_more_cases",
        "lessons_checked": [],
        "failure_modes_checked": [],
        "allowed_use": "quarantine_until_cases_exist",
    }


def evaluate_pattern_against_case(pattern: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    pattern_tags = set(pattern.get("tags", []))
    case_tags = set(case.get("tags", []))
    direct_match = pattern.get("id") in case.get("pattern_ids", [])
    overlap = len(pattern_tags & case_tags)
    fit_score = min(95, 45 + overlap * 10 + (25 if direct_match else 0))
    overfit_risk = max(10, 65 - overlap * 8 - (15 if direct_match else 0))
    verdict = "usable_as_pattern_check" if fit_score >= 65 and overfit_risk <= 55 else "needs_more_cases"
    return {
        "pattern_id": pattern.get("id"),
        "case_id": case.get("case_id"),
        "case_type": case.get("case_type"),
        "fit_score": fit_score,
        "overfit_risk": overfit_risk,
        "verdict": verdict,
        "lessons_checked": case.get("known_lessons", []),
        "failure_modes_checked": case.get("failure_modes", []),
        "allowed_use": "hypothesis_and_checklist_only_not_direct_mapping",
    }


def build_replay_summary(patterns: list[dict[str, Any]], cases: list[dict[str, Any]], results: list[dict[str, Any]]) -> dict[str, Any]:
    passed = [row for row in results if row.get("verdict") == "usable_as_pattern_check"]
    risky = [row for row in results if row.get("overfit_risk", 100) > 55]
    avg_fit = round(sum(row.get("fit_score", 0) for row in results) / len(results), 1) if results else 0
    avg_overfit = round(sum(row.get("overfit_risk", 0) for row in results) / len(results), 1) if results else 0
    score = round(max(0, min(100, avg_fit - max(0, avg_overfit - 45) - len(risky) * 3)), 1) if results else 0
    return {
        "case_replay_version": CASE_REPLAY_VERSION,
        "purpose": "Validate learning patterns against small historical case library without allowing direct analogy-to-trade mapping.",
        "patterns_replayed": len(patterns),
        "cases_available": len(cases),
        "case_results_total": len(results),
        "passed_results": len(passed),
        "high_overfit_results": len(risky),
        "average_fit_score": avg_fit,
        "average_overfit_risk": avg_overfit,
        "case_replay_score": score,
        "controls": [
            "case_replay_is_not_trade_signal",
            "direct_case_mapping_forbidden",
            "primary_evidence_still_required",
        ],
        "case_results": results,
    }


def load_case_replay(run_path: Path) -> dict[str, Any]:
    path = run_path / "harness" / "historical-case-replay.yaml"
    if not path.exists():
        return {
            "case_replay_version": CASE_REPLAY_VERSION,
            "patterns_replayed": 0,
            "cases_available": 0,
            "case_results_total": 0,
            "passed_results": 0,
            "high_overfit_results": 0,
            "case_replay_score": 0,
            "controls": [],
            "case_results": [],
        }
    return read_yaml(path)
