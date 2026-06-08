from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from fundos.case_library import load_case_library
from fundos.case_replay import run_case_replay
from fundos.io import write_yaml

CASE_REPLAY_STRESS_VERSION = "0.1.0"
FIXTURE_ID = "case_replay_coverage_fixture_v1"
RUN_ID = "case-replay-stress-fixture"
CRITICAL_CASE_TYPES = ["fraud_blowup", "policy_driven_cycle", "failed_breakout", "kol_thesis_failure"]


PATTERN_FIXTURES: list[dict[str, Any]] = [
    {
        "id": "fraud_blowup_case",
        "tags": ["company", "risk", "bear_case", "governance", "primary_validation"],
        "target_agents": ["fraud_governance_analyst", "risk_manager", "bear_debater", "fund_manager"],
        "validation_gates": ["historical_case_replay"],
        "allowed_use": "hypothesis_and_checklist_only_not_direct_mapping",
    },
    {
        "id": "a_share_theme_diffusion_case",
        "tags": ["policy", "industry", "macro", "risk", "trading"],
        "target_agents": ["policy_event_analyst", "cyclical_macro_analyst", "risk_manager", "fund_manager"],
        "validation_gates": ["historical_case_replay"],
        "allowed_use": "hypothesis_and_checklist_only_not_direct_mapping",
    },
    {
        "id": "minervini_trend_template",
        "tags": ["trading", "risk", "failed_breakout", "market_state"],
        "target_agents": ["position_trend_trader", "swing_trader", "defensive_execution_trader", "risk_manager"],
        "validation_gates": ["historical_case_replay"],
        "allowed_use": "hypothesis_and_checklist_only_not_direct_mapping",
    },
    {
        "id": "serenity_scheme_first_chokepoint",
        "tags": ["kol", "social_signal", "bear_case", "evidence_quality", "risk"],
        "target_agents": ["learning_curator", "bear_debater", "evaluation_harness", "risk_manager"],
        "validation_gates": ["historical_case_replay"],
        "allowed_use": "hypothesis_and_checklist_only_not_direct_mapping",
    },
    {
        "id": "oneil_canslim_growth",
        "tags": ["company", "industry", "quality_growth", "primary_validation"],
        "target_agents": ["quality_growth_company_analyst", "tech_growth_analyst", "fund_manager"],
        "validation_gates": ["historical_case_replay"],
        "allowed_use": "hypothesis_and_checklist_only_not_direct_mapping",
    },
    {
        "id": "soros_reflexivity",
        "tags": ["trading", "risk", "macro", "bear_case", "liquidity"],
        "target_agents": ["cyclical_macro_analyst", "position_trend_trader", "defensive_execution_trader", "risk_manager"],
        "validation_gates": ["historical_case_replay"],
        "allowed_use": "hypothesis_and_checklist_only_not_direct_mapping",
    },
    {
        "id": "peter_lynch_scuttlebutt",
        "tags": ["company", "value", "risk", "bear_case"],
        "target_agents": ["turnaround_value_company_analyst", "fraud_governance_analyst", "risk_manager", "bear_debater"],
        "validation_gates": ["historical_case_replay"],
        "allowed_use": "hypothesis_and_checklist_only_not_direct_mapping",
    },
    {
        "id": "howard_marks_cycle_risk",
        "tags": ["methodology", "transfer", "evidence_quality", "risk", "learning"],
        "target_agents": ["learning_curator", "evaluation_harness", "fund_manager", "risk_manager"],
        "validation_gates": ["historical_case_replay"],
        "allowed_use": "hypothesis_and_checklist_only_not_direct_mapping",
    },
]


def run_case_replay_stress_fixture(root: Path, fixture_name: str = FIXTURE_ID) -> dict[str, Any]:
    workspace = root / "runs" / fixture_name
    run_path = workspace / "runs" / RUN_ID
    if workspace.exists():
        remove_tree(workspace)
    for name in ["harness", "learning", "evaluations"]:
        (run_path / name).mkdir(parents=True, exist_ok=True)

    write_yaml(run_path / "run.yaml", {
        "run_id": RUN_ID,
        "selected_agents": stress_selected_agents(),
        "model_records": [],
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    })
    write_yaml(run_path / "learning" / "patterns.yaml", {
        "artifact_type": "case_replay_stress_patterns",
        "purpose": "Force historical case replay coverage over minimum and critical failure case types without direct analogy-to-trade mapping.",
        "patterns": PATTERN_FIXTURES,
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    })

    library = load_case_library()
    replay = run_case_replay(run_path)
    report = build_stress_report(root, workspace, run_path, library, replay)
    write_yaml(run_path / "harness" / "case-replay-stress.yaml", report)
    return report


def stress_selected_agents() -> list[dict[str, str]]:
    agent_ids = sorted({agent for pattern in PATTERN_FIXTURES for agent in pattern.get("target_agents", [])})
    return [{"agent_id": agent_id, "role": agent_id} for agent_id in agent_ids]


def build_stress_report(root: Path, workspace: Path, run_path: Path, library: dict[str, Any], replay: dict[str, Any]) -> dict[str, Any]:
    cases = library.get("cases", []) or []
    case_results = replay.get("case_results", []) or []
    required_case_types = sorted(library.get("minimum_case_types", []) or [])
    available_case_types = sorted({case.get("case_type") for case in cases if case.get("case_type")})
    matched_case_types = sorted({row.get("case_type") for row in case_results if row.get("case_type") and row.get("case_type") != "none"})
    required_failure_modes = sorted({
        mode
        for case in cases
        if case.get("case_type") in set(CRITICAL_CASE_TYPES)
        for mode in case.get("failure_modes", [])
    })
    replay_failure_modes = sorted({mode for row in case_results for mode in row.get("failure_modes_checked", [])})
    matched_case_ids = {row.get("case_id") for row in case_results if row.get("case_id") and row.get("case_id") != "none"}
    missing_required_case_types = sorted(set(required_case_types) - set(available_case_types))
    missing_critical_replay_types = sorted(set(CRITICAL_CASE_TYPES) - set(matched_case_types))
    missing_critical_failure_modes = sorted(set(required_failure_modes) - set(replay_failure_modes))
    blocking_issues: list[str] = []

    checks = {
        "required_case_types_present": not missing_required_case_types,
        "critical_case_types_replayed": not missing_critical_replay_types,
        "failure_modes_checked": not missing_critical_failure_modes and bool(required_failure_modes),
        "methodology_only_controls_ok": methodology_only_controls_ok(cases, case_results),
        "kol_thesis_hypothesis_only_ok": kol_thesis_hypothesis_only_ok(cases, case_results),
        "no_direct_mapping_ok": no_direct_mapping_ok(cases, case_results),
        "primary_evidence_still_required_ok": primary_evidence_still_required_ok(cases, replay),
        "source_controlled_case_files_replayed": len(matched_case_ids) >= len(cases),
        "safety_ok": replay.get("real_trade_allowed") is False and replay.get("broker_integration") == "disabled" and all(row.get("real_trade_allowed") is False and row.get("broker_integration") == "disabled" for row in case_results),
    }
    for name, ok in checks.items():
        if not ok:
            blocking_issues.append(name)

    report = {
        "version": CASE_REPLAY_STRESS_VERSION,
        "artifact_type": "case_replay_stress_report",
        "fixture_id": FIXTURE_ID,
        "run_id": RUN_ID,
        "workspace_path": workspace.relative_to(root).as_posix() if workspace.is_relative_to(root) else str(workspace),
        "status": "passed" if not blocking_issues else "blocked",
        "overall_score": round(100 * sum(1 for ok in checks.values() if ok) / len(checks), 1),
        "case_count": len(cases),
        "patterns_replayed": replay.get("patterns_replayed", 0),
        "case_results_total": replay.get("case_results_total", 0),
        "required_case_types": required_case_types,
        "available_case_types": available_case_types,
        "matched_case_types": matched_case_types,
        "critical_case_types": list(CRITICAL_CASE_TYPES),
        "missing_required_case_types": missing_required_case_types,
        "missing_critical_replay_types": missing_critical_replay_types,
        "failure_modes_checked": replay_failure_modes,
        "missing_critical_failure_modes": missing_critical_failure_modes,
        "case_replay_score": replay.get("case_replay_score", 0),
        "checks": checks,
        "blocking_issues": blocking_issues,
        "controls": [
            "historical_case_replay_coverage_stress",
            "case_library_is_training_and_evaluation_not_trade_signal",
            "direct_case_mapping_forbidden",
            "kol_thesis_hypothesis_only",
            "primary_evidence_still_required",
            "source_controlled_case_files_replayed",
            "no_real_trade_action",
            "broker_integration_disabled",
        ],
        "replay_artifact": "harness/historical-case-replay.yaml",
        "case_library_index": "learning/case-library-index.yaml",
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }
    return report


def methodology_only_controls_ok(cases: list[dict[str, Any]], case_results: list[dict[str, Any]]) -> bool:
    if not cases or not case_results:
        return False
    cases_ok = all("direct_buy_sell_signal" in case.get("forbidden_uses", []) and case.get("real_trade_allowed") is False and case.get("broker_integration") == "disabled" for case in cases)
    results_ok = all(str(row.get("allowed_use", "")).endswith("not_direct_mapping") for row in case_results)
    return cases_ok and results_ok


def kol_thesis_hypothesis_only_ok(cases: list[dict[str, Any]], case_results: list[dict[str, Any]]) -> bool:
    kol_case_ids = {case.get("case_id") for case in cases if case.get("case_type") == "kol_thesis_failure" or "kol" in case.get("tags", [])}
    kol_results = [row for row in case_results if row.get("case_id") in kol_case_ids]
    return bool(kol_results) and all(row.get("allowed_use") == "hypothesis_and_checklist_only_not_direct_mapping" for row in kol_results)


def no_direct_mapping_ok(cases: list[dict[str, Any]], case_results: list[dict[str, Any]]) -> bool:
    cases_ok = all("direct_case_mapping" in case.get("forbidden_uses", []) or "direct_buy_sell_signal" in case.get("forbidden_uses", []) for case in cases)
    results_ok = all("direct" not in str(row.get("verdict", "")).lower() and "direct_mapping" not in str(row.get("allowed_use", "")).replace("not_direct_mapping", "") for row in case_results)
    return cases_ok and results_ok


def primary_evidence_still_required_ok(cases: list[dict[str, Any]], replay: dict[str, Any]) -> bool:
    case_requirements_ok = all(bool(case.get("evidence_requirements")) for case in cases)
    replay_controls = set(replay.get("controls", []) or [])
    return case_requirements_ok and "primary_evidence_still_required" in replay_controls


def remove_tree(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
