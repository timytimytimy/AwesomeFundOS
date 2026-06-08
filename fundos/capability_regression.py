from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fundos.io import read_yaml, write_yaml

REGRESSION_VERSION = "0.1.0"
CAPABILITY_KINDS = {"principle", "skill", "checklist", "workflow", "tool_policy"}
TEST_ARTIFACTS = {
    "historical_case_replay": "harness/historical-case-replay.yaml",
    "role_drift_check": "harness/agent-harness.yaml",
    "evidence_quality_check": "evaluations/evaluation-report.yaml",
    "tool_harness": "harness/tool-harness.yaml",
    "agent_harness": "harness/agent-harness.yaml",
    "outcome_review": "portfolio/portfolio-review.yaml",
    "risk_limit_guard": "risk/risk-limits.yaml",
    "capability_dependency_chain": "agent_work/dependency-attestations.yaml",
    "missing_dependency_attestation": "agent_work/dependency-attestations.yaml",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def infer_runtime_root(run_path: Path) -> Path:
    if run_path.parent.name == "runs":
        return run_path.parent.parent
    return run_path.parent


def load_capability_regression(run_path: Path | None) -> dict[str, Any]:
    if not run_path:
        return default_report()
    path = run_path / "harness" / "capability-regression.yaml"
    if not path.exists():
        return default_report()
    loaded = read_yaml(path) or {}
    report = default_report()
    report.update(loaded)
    return report


def default_report() -> dict[str, Any]:
    return {
        "version": REGRESSION_VERSION,
        "artifact_type": "capability_regression_report",
        "regression_status": "missing",
        "candidates_total": 0,
        "passed_candidates": 0,
        "blocked_candidates": 0,
        "candidate_results": [],
        "controls": [],
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def run_capability_regression(run_path: Path, root: Path | None = None) -> dict[str, Any]:
    runtime_root = root or infer_runtime_root(run_path)
    candidates = collect_pending_capability_candidates(run_path, runtime_root)
    results = [evaluate_capability_candidate(run_path, candidate) for candidate in candidates]
    passed = [row for row in results if row.get("regression_status") == "passed"]
    blocked = [row for row in results if row.get("regression_status") == "blocked"]
    report = {
        "version": REGRESSION_VERSION,
        "artifact_type": "capability_regression_report",
        "run_id": run_path.name,
        "regression_status": "passed" if candidates and not blocked else ("blocked" if blocked else "no_pending_capabilities"),
        "candidates_total": len(candidates),
        "passed_candidates": len(passed),
        "blocked_candidates": len(blocked),
        "candidate_results": results,
        "controls": [
            "capability_regression_required_before_apply",
            "no_direct_profile_mutation",
            "no_real_trade_action",
            "artifact_backed_required_tests",
            "capability_regression_required",
            "human_approval_before_apply",
            "broker_integration_disabled",
        ],
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }
    write_yaml(run_path / "harness" / "capability-regression.yaml", report)
    update_capability_registries(runtime_root, results)
    return report


def collect_pending_capability_candidates(run_path: Path, root: Path) -> list[dict[str, Any]]:
    run_rows = read_jsonl(run_path / "evolution" / "capability-candidates.jsonl")
    candidates: dict[str, dict[str, Any]] = {}
    for row in run_rows:
        if row.get("application_status") in {"pending_human_apply", "already_pending_or_recorded"} or row.get("status") == "approved_candidate":
            candidate_id = row.get("candidate_id")
            if candidate_id:
                candidates[candidate_id] = {**row, "registry_path": row.get("registry_path")}
    base = root / "memory" / "agents"
    if base.exists():
        for registry in sorted(base.glob("*/capabilities/*.jsonl")):
            for row in read_jsonl(registry):
                if row.get("application_status") == "pending_human_apply" and row.get("run_id") in {None, run_path.name, infer_run_id(run_path)}:
                    candidate_id = row.get("candidate_id")
                    if candidate_id:
                        candidates[candidate_id] = {**row, "registry_path": registry.relative_to(root).as_posix()}
    return list(candidates.values())


def infer_run_id(run_path: Path) -> str:
    run_doc = run_path / "run.yaml"
    if run_doc.exists():
        return (read_yaml(run_doc) or {}).get("run_id", run_path.name)
    return run_path.name


def evaluate_capability_candidate(run_path: Path, candidate: dict[str, Any]) -> dict[str, Any]:
    required_tests = candidate.get("required_tests", [])
    checks = [evaluate_required_test(run_path, test_name) for test_name in required_tests]
    blocking = [issue for check in checks for issue in check.get("blocking_issues", [])]
    unsafe = unsafe_candidate_issues(candidate)
    blocking.extend(unsafe)
    status = "passed" if not blocking and required_tests else "blocked"
    if not required_tests:
        blocking.append("missing_required_tests")
        status = "blocked"
    return {
        "candidate_id": candidate.get("candidate_id"),
        "run_id": candidate.get("run_id"),
        "target_agent": candidate.get("target_agent"),
        "capability_kind": candidate.get("capability_kind") or kind_for(candidate),
        "candidate_type": candidate.get("candidate_type"),
        "target_scope": candidate.get("target_scope"),
        "regression_status": status,
        "required_tests": required_tests,
        "test_results": checks,
        "blocking_issues": sorted(set(blocking)),
        "application_status_after_regression": "pending_human_apply" if status == "passed" else "blocked_regression",
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def evaluate_required_test(run_path: Path, test_name: str) -> dict[str, Any]:
    rel = TEST_ARTIFACTS.get(test_name)
    if not rel:
        return {"test_name": test_name, "status": "manual_required", "blocking_issues": [f"unknown_required_test:{test_name}"]}
    path = run_path / rel
    if not path.exists():
        return {"test_name": test_name, "status": "missing_artifact", "artifact": rel, "blocking_issues": [f"missing_artifact:{rel}"]}
    doc = read_yaml(path) or {}
    issues = score_based_issues(test_name, doc)
    return {"test_name": test_name, "status": "passed" if not issues else "failed", "artifact": rel, "blocking_issues": issues}


def score_based_issues(test_name: str, doc: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if test_name == "historical_case_replay":
        if int(doc.get("case_results_total", 0) or 0) <= 0:
            issues.append("case_replay_has_no_results")
        if int(doc.get("case_replay_score", 0) or 0) < 60:
            issues.append("case_replay_score_below_60")
    if test_name in {"role_drift_check", "agent_harness"}:
        scores = doc.get("aggregate_scores", {})
        if float(scores.get("role_consistency", 0) or 0) < 70:
            issues.append("role_consistency_below_70")
        if float(scores.get("skill_invocation", 0) or 0) < 70:
            issues.append("skill_invocation_below_70")
    if test_name == "evidence_quality_check":
        coverage = doc.get("source_coverage", {})
        dimensions = doc.get("dimension_scores", {})
        if int(coverage.get("tier_1_primary_fact", 0) or 0) <= 0:
            issues.append("missing_tier_1_primary_fact")
        if float(dimensions.get("evidence_quality", 0) or 0) < 60:
            issues.append("evidence_quality_below_60")
    if test_name == "tool_harness" and doc.get("high_confidence_allowed") is False:
        issues.append("tool_harness_blocks_high_confidence")
    if test_name == "risk_limit_guard":
        if doc.get("real_trade_allowed") is not False:
            issues.append("risk_limit_real_trade_allowed_forbidden")
        if doc.get("broker_integration") != "disabled":
            issues.append("risk_limit_broker_integration_not_disabled")
        if doc.get("risk_manager_veto_required") is not True:
            issues.append("risk_manager_veto_required_missing")
    if test_name == "capability_dependency_chain":
        if doc.get("dependencies_ready") is not True:
            issues.append("capability_dependency_chain_not_ready")
        missing = [row.get("agent_id") for row in doc.get("attestations", []) if row.get("status") != "ready"]
        if missing:
            issues.append("capability_dependency_attestations_missing:" + ",".join(str(item) for item in sorted(missing)))
    if test_name == "missing_dependency_attestation":
        issues.append("capability_dependency_attestation_required")
    return issues


def unsafe_candidate_issues(candidate: dict[str, Any]) -> list[str]:
    issues = []
    if candidate.get("target_scope") in {"core_profile", "org_structure", "tool_permission", "risk_limit"}:
        issues.append("protected_scope_requires_separate_governance")
    if candidate.get("candidate_type") in {"profile_update", "tool_permission_update", "risk_limit_update"}:
        issues.append("protected_candidate_type_requires_separate_governance")
    if candidate.get("real_trade_allowed") is True:
        issues.append("real_trade_allowed_forbidden")
    return issues


def kind_for(candidate: dict[str, Any]) -> str:
    candidate_type = candidate.get("candidate_type", "")
    for kind in CAPABILITY_KINDS:
        if candidate_type.startswith(kind):
            return kind
    return candidate.get("target_scope", "capability")


def update_capability_registries(root: Path, results: list[dict[str, Any]]) -> None:
    by_id = {row.get("candidate_id"): row for row in results if row.get("candidate_id")}
    base = root / "memory" / "agents"
    if not base.exists():
        return
    for registry in sorted(base.glob("*/capabilities/*.jsonl")):
        rows = read_jsonl(registry)
        changed = False
        for row in rows:
            result = by_id.get(row.get("candidate_id"))
            if not result:
                continue
            row["regression_status"] = result["regression_status"]
            row["regression_report_path"] = "harness/capability-regression.yaml"
            row["regression_blocking_issues"] = result["blocking_issues"]
            row["application_status"] = result["application_status_after_regression"]
            if result["regression_status"] == "blocked":
                follow_up = set(row.get("required_follow_up_tests", []))
                follow_up.add("capability_regression_required")
                row["required_follow_up_tests"] = sorted(follow_up)
            changed = True
        if changed:
            write_jsonl(registry, rows)
