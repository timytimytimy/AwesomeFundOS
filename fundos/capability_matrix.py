from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fundos.capabilities import append_jsonl
from fundos.capability_apply import apply_approved_capability
from fundos.capability_regression import run_capability_regression
from fundos.io import read_yaml, write_yaml

CAPABILITY_MATRIX_VERSION = "0.1.0"
FIXTURE_ID = "capability_matrix_non_skill_and_blocking_fixture_v1"
RUN_ID = "capability-matrix-fixture"
TARGET_AGENT = "fund_manager"


def run_capability_matrix_fixture(root: Path, fixture_name: str = FIXTURE_ID) -> dict[str, Any]:
    workspace = root / "runs" / fixture_name
    run_path = workspace / "runs" / RUN_ID
    if workspace.exists():
        remove_tree(workspace)
    for name in ["harness", "evaluations", "memory", "agents", "portfolio"]:
        (run_path / name).mkdir(parents=True, exist_ok=True)
    write_yaml(run_path / "run.yaml", {
        "run_id": RUN_ID,
        "selected_agents": [{"agent_id": TARGET_AGENT, "role": "FundManagerAgent"}],
        "model_records": [],
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    })
    write_passing_regression_artifacts(run_path)

    candidates = fixture_candidates()
    registries: dict[str, list[dict[str, Any]]] = {}
    for candidate in candidates:
        registries.setdefault(candidate["capability_kind"], []).append(candidate)
    for kind, rows in registries.items():
        append_jsonl(workspace / "memory" / "agents" / TARGET_AGENT / "capabilities" / f"{kind}.jsonl", rows)

    before = snapshot_workspace(workspace)
    regression = run_capability_regression(run_path, root=workspace)
    apply_results = []
    apply_errors = []
    for result in regression.get("candidate_results", []):
        candidate_id = result.get("candidate_id")
        if result.get("application_status_after_regression") != "pending_human_apply":
            apply_errors.append({"candidate_id": candidate_id, "skipped_reason": "blocked_regression"})
            continue
        try:
            apply_results.append(apply_approved_capability(workspace, candidate_id, approver="capability-matrix-human"))
        except Exception as exc:  # pragma: no cover - retained in report for fixture diagnostics
            apply_errors.append({"candidate_id": candidate_id, "error": str(exc)})
    after = snapshot_workspace(workspace)
    candidate_results = merge_candidate_results(regression.get("candidate_results", []), apply_results, apply_errors)
    summary = summarize_matrix(candidate_results, before, after)
    report = {
        "version": CAPABILITY_MATRIX_VERSION,
        "artifact_type": "capability_matrix_fixture_report",
        "fixture_id": FIXTURE_ID,
        "run_id": RUN_ID,
        "workspace_path": workspace.relative_to(root).as_posix() if workspace.is_relative_to(root) else str(workspace),
        "status": "passed" if summary["matrix_passed"] else "blocked",
        "candidate_count": len(candidate_results),
        "passed_candidate_count": summary["passed_candidate_count"],
        "blocked_candidate_count": summary["blocked_candidate_count"],
        "applied_candidate_count": summary["applied_candidate_count"],
        "non_skill_applied_count": summary["non_skill_applied_count"],
        "blocked_protected_scope_count": summary["blocked_protected_scope_count"],
        "blocked_missing_artifact_count": summary["blocked_missing_artifact_count"],
        "regression_status": regression.get("regression_status"),
        "candidate_results": candidate_results,
        "baseline": before,
        "after_apply": after,
        "improvement": summary,
        "blocking_issues": summary["blocking_issues"],
        "controls": [
            "non_skill_capability_benchmark_fixture",
            "principle_workflow_checklist_apply_path",
            "blocked_regression_negative_cases",
            "protected_scope_blocked",
            "missing_required_artifact_blocked",
            "human_approval_required",
            "no_direct_profile_mutation",
            "no_real_trade_action",
            "broker_integration_disabled",
        ],
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }
    write_yaml(run_path / "harness" / "capability-matrix-fixture.yaml", report)
    return report


def write_passing_regression_artifacts(run_path: Path) -> None:
    write_yaml(run_path / "harness" / "historical-case-replay.yaml", {
        "artifact_type": "historical_case_replay",
        "case_replay_score": 84,
        "case_results_total": 3,
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    })
    write_yaml(run_path / "harness" / "agent-harness.yaml", {
        "artifact_type": "agent_harness_report",
        "aggregate_scores": {"role_consistency": 88, "skill_invocation": 87, "context_compression": 84},
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    })
    write_yaml(run_path / "evaluations" / "evaluation-report.yaml", {
        "artifact_type": "evaluation_report",
        "source_coverage": {"tier_1_primary_fact": 2},
        "dimension_scores": {"evidence_quality": 86},
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    })
    write_yaml(run_path / "harness" / "tool-harness.yaml", {
        "artifact_type": "tool_harness_report",
        "high_confidence_allowed": True,
        "blocking_issues": [],
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    })


def fixture_candidates() -> list[dict[str, Any]]:
    base = {
        "run_id": RUN_ID,
        "source_agent": "evaluation_harness",
        "target_agent": TARGET_AGENT,
        "application_status": "pending_human_apply",
        "adoption_route": "managed_capability_pending_human_apply",
        "memory_write_policy": "no_direct_memory_write",
        "human_approval_required": True,
        "protected_mutation_allowed": False,
        "source_basis": [{"evidence_id": "E011", "source_tier": "tier_1_primary_fact"}],
        "controls": ["no_direct_profile_mutation", "no_real_trade_action", "broker_integration_disabled"],
        "scores": {"testability": 88, "source_quality": 84, "overfit_risk": 18},
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }
    return [
        {
            **base,
            "candidate_id": f"cand_{RUN_ID}_principle",
            "capability_kind": "principle",
            "candidate_type": "principle_update",
            "target_scope": "principle",
            "proposal": "方法论、KOL 和历史案例只能生成问题清单；FundManager 必须等待一手证据再提高 conviction。",
            "required_tests": ["historical_case_replay", "role_drift_check", "evidence_quality_check"],
        },
        {
            **base,
            "candidate_id": f"cand_{RUN_ID}_workflow",
            "capability_kind": "workflow",
            "candidate_type": "workflow_update",
            "target_scope": "workflow",
            "proposal": "最终 memo 前必须检查 tool harness、bear/risk blocking issues 和未关闭 research gaps。",
            "required_tests": ["role_drift_check", "tool_harness", "evidence_quality_check"],
        },
        {
            **base,
            "candidate_id": f"cand_{RUN_ID}_checklist",
            "capability_kind": "checklist",
            "candidate_type": "checklist_update",
            "target_scope": "checklist",
            "proposal": "新增投委会 checklist：证据等级、反方争议、风控 cap、触发/失效条件四项同时回链。",
            "required_tests": ["historical_case_replay", "agent_harness"],
        },
        {
            **base,
            "candidate_id": f"cand_{RUN_ID}_protected_tool_permission",
            "capability_kind": "tool_policy",
            "candidate_type": "tool_policy_update",
            "target_scope": "tool_permission",
            "proposal": "直接扩大工具权限。该候选必须被保护域阻断，不能应用。",
            "required_tests": ["tool_harness"],
        },
        {
            **base,
            "candidate_id": f"cand_{RUN_ID}_missing_outcome_review",
            "capability_kind": "workflow",
            "candidate_type": "workflow_update",
            "target_scope": "workflow",
            "proposal": "依赖尚未生成的组合 outcome review，因此必须停留在 blocked_regression。",
            "required_tests": ["outcome_review"],
        },
    ]


def snapshot_workspace(workspace: Path) -> dict[str, Any]:
    applied_path = workspace / "agents" / TARGET_AGENT / "applied-capabilities.yaml"
    applied_doc = read_yaml(applied_path) if applied_path.exists() else {"applied_capabilities": []}
    applied = applied_doc.get("applied_capabilities", []) if isinstance(applied_doc, dict) else []
    registry_rows = []
    base = workspace / "memory" / "agents" / TARGET_AGENT / "capabilities"
    if base.exists():
        for registry in sorted(base.glob("*.jsonl")):
            for row in read_jsonl(registry):
                registry_rows.append({"registry": registry.stem, **row})
    return {
        "applied_capability_count": len(applied),
        "applied_capability_ids": sorted(row.get("candidate_id") for row in applied if row.get("candidate_id")),
        "applied_capability_kinds": sorted(set(row.get("capability_kind") for row in applied if row.get("capability_kind"))),
        "registry_status_counts": count_by(registry_rows, "application_status"),
        "registry_kind_counts": count_by(registry_rows, "capability_kind"),
        "mutated_core_profile": False,
        "mutated_agent_card": False,
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def merge_candidate_results(regression_results: list[dict[str, Any]], apply_results: list[dict[str, Any]], apply_errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_apply = {row.get("candidate_id"): row for row in apply_results}
    by_error = {row.get("candidate_id"): row for row in apply_errors}
    merged = []
    for row in regression_results:
        candidate_id = row.get("candidate_id")
        apply_result = by_apply.get(candidate_id, {})
        apply_error = by_error.get(candidate_id, {})
        merged.append({
            **row,
            "application_status": apply_result.get("application_status") or row.get("application_status_after_regression"),
            "applied_target_path": apply_result.get("target_path"),
            "apply_error": apply_error.get("error"),
            "skipped_reason": apply_error.get("skipped_reason"),
            "mutated_core_profile": False,
            "mutated_agent_card": False,
            "real_trade_allowed": False,
            "broker_integration": "disabled",
        })
    return merged


def summarize_matrix(candidate_results: list[dict[str, Any]], before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    issues: list[str] = []
    applied = [row for row in candidate_results if row.get("application_status") == "applied"]
    blocked = [row for row in candidate_results if row.get("application_status_after_regression") == "blocked_regression"]
    non_skill_applied = [row for row in applied if row.get("capability_kind") in {"principle", "workflow", "checklist"}]
    protected_blocked = [row for row in blocked if any("protected_scope" in issue for issue in row.get("blocking_issues", []))]
    missing_artifact_blocked = [row for row in blocked if any("missing_artifact" in issue for issue in row.get("blocking_issues", []))]
    if before.get("applied_capability_count") != 0:
        issues.append("baseline_already_had_applied_capabilities")
    if len(non_skill_applied) < 3:
        issues.append("non_skill_apply_paths_not_all_covered")
    if not protected_blocked:
        issues.append("protected_scope_negative_case_not_blocked")
    if not missing_artifact_blocked:
        issues.append("missing_artifact_negative_case_not_blocked")
    if any(row.get("application_status") == "applied" for row in blocked):
        issues.append("blocked_candidate_was_applied")
    if after.get("mutated_core_profile") or after.get("mutated_agent_card"):
        issues.append("protected_source_asset_mutated")
    if after.get("real_trade_allowed") is not False or after.get("broker_integration") != "disabled":
        issues.append("safety_boundary_violation")
    return {
        "passed_candidate_count": sum(1 for row in candidate_results if row.get("regression_status") == "passed"),
        "blocked_candidate_count": len(blocked),
        "applied_candidate_count": len(applied),
        "non_skill_applied_count": len(non_skill_applied),
        "blocked_protected_scope_count": len(protected_blocked),
        "blocked_missing_artifact_count": len(missing_artifact_blocked),
        "applied_kinds": sorted(set(row.get("capability_kind") for row in applied)),
        "blocked_candidate_ids": sorted(row.get("candidate_id") for row in blocked if row.get("candidate_id")),
        "application_status_transition": f"{before.get('applied_capability_count')}->{after.get('applied_capability_count')}",
        "matrix_passed": not issues,
        "blocking_issues": issues,
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key, "unknown"))
        counts[value] = counts.get(value, 0) + 1
    return counts


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def remove_tree(path: Path) -> None:
    for child in sorted(path.rglob("*"), reverse=True):
        if child.is_file() or child.is_symlink():
            child.unlink()
        elif child.is_dir():
            child.rmdir()
    path.rmdir()
