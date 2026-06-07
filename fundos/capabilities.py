from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fundos.io import read_yaml, write_yaml
from fundos.memory import infer_runtime_root

CAPABILITY_VERSION = "0.1.0"
APPROVAL_MODE = "evolution_gate_v1_capability_candidate"
CAPABILITY_TYPES = {
    "principle_update": "principle",
    "skill_update": "skill",
    "checklist_update": "checklist",
    "workflow_update": "workflow",
    "tool_policy_update": "tool_policy",
}
SUMMARY_DEFAULT = {
    "version": CAPABILITY_VERSION,
    "artifact_type": "capability_version_summary",
    "approved_candidates": 0,
    "quarantined_candidates": 0,
    "rejected_candidates": 0,
    "pending_human_apply": 0,
    "skipped_existing": 0,
    "agent_versions": {},
    "written_paths": [],
    "approval_mode": APPROVAL_MODE,
    "controls": [
        "evolution_gate_before_capability_registry",
        "capability_regression_required",
        "human_approval_before_apply",
        "no_direct_profile_mutation",
        "no_real_trade_action",
        "broker_integration_disabled",
    ],
    "direct_profile_mutation_allowed": False,
    "direct_skill_mutation_allowed": False,
    "direct_tool_mutation_allowed": False,
    "real_trade_allowed": False,
    "broker_integration": "disabled",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def load_capability_summary(run_path: Path) -> dict[str, Any]:
    path = run_path / "evolution" / "capability-version-summary.yaml"
    if not path.exists():
        return dict(SUMMARY_DEFAULT)
    loaded = read_yaml(path) or {}
    summary = dict(SUMMARY_DEFAULT)
    summary.update(loaded)
    return summary


def apply_capability_versions(run_path: Path, results: list[dict[str, Any]], root: Path | None = None) -> dict[str, Any]:
    runtime_root = root or infer_runtime_root(run_path)
    queue_rows: list[dict[str, Any]] = []
    summary: dict[str, Any] = dict(SUMMARY_DEFAULT)
    summary["agent_versions"] = {}
    summary["written_paths"] = []
    summary["controls"] = list(SUMMARY_DEFAULT["controls"])

    for result in results:
        if not is_capability_candidate(result):
            continue
        queue_row = make_queue_row(result)
        if result.get("decision") == "accept" and is_safe_capability_candidate(result):
            target_agent = result.get("target_agent") or result.get("source_agent") or "organization"
            capability_kind = capability_kind_for(result)
            if capability_already_written(runtime_root, target_agent, capability_kind, result.get("candidate_id")):
                summary["skipped_existing"] += 1
                queue_row["status"] = "approved_candidate"
                queue_row["application_status"] = "already_pending_or_recorded"
                result["capability_version"] = capability_ref(target_agent, capability_kind, result.get("candidate_id"), already_written=True)
            else:
                version_row = make_version_row(result, target_agent, capability_kind)
                write_capability_version(runtime_root, target_agent, capability_kind, version_row)
                result["capability_version"] = capability_ref(target_agent, capability_kind, result.get("candidate_id"), already_written=False)
                summary["approved_candidates"] += 1
                summary["pending_human_apply"] += 1
                summary["agent_versions"][target_agent] = summary["agent_versions"].get(target_agent, 0) + 1
                summary["written_paths"].extend([
                    str(Path("memory") / "agents" / target_agent / "capabilities" / f"{capability_kind}.jsonl"),
                    str(Path("memory") / "organization" / "capability-ledger.jsonl"),
                ])
            queue_row["status"] = "approved_candidate"
            queue_row["application_status"] = result["capability_version"]["application_status"]
        elif result.get("decision") == "quarantine":
            summary["quarantined_candidates"] += 1
            queue_row["status"] = "quarantine"
            queue_row["application_status"] = "needs_more_evidence"
        else:
            summary["rejected_candidates"] += 1
            queue_row["status"] = "reject"
            queue_row["application_status"] = "not_applicable"
        queue_rows.append(queue_row)

    summary["written_paths"] = sorted(set(summary["written_paths"]))
    write_jsonl(run_path / "evolution" / "capability-candidates.jsonl", queue_rows)
    write_yaml(run_path / "evolution" / "capability-version-summary.yaml", summary)
    return summary


def is_capability_candidate(result: dict[str, Any]) -> bool:
    if result.get("adoption_route") in {"managed_capability_pending_human_apply", "skill_patch_pending_human_apply"}:
        return True
    return result.get("candidate_type") in CAPABILITY_TYPES or result.get("target_scope") in {"skill", "workflow", "principle", "checklist", "tool_policy"}


def is_safe_capability_candidate(result: dict[str, Any]) -> bool:
    if result.get("decision") != "accept":
        return False
    controls = set(result.get("controls", []))
    if "no_direct_profile_mutation" not in controls or "no_real_trade_action" not in controls:
        return False
    if result.get("target_scope") in {"core_profile", "org_structure", "risk_limit", "tool_permission"}:
        return False
    if result.get("adoption_route") == "forbidden_protected_mutation":
        return False
    return result.get("candidate_type") in CAPABILITY_TYPES


def capability_kind_for(result: dict[str, Any]) -> str:
    return CAPABILITY_TYPES.get(result.get("candidate_type"), result.get("target_scope", "capability"))


def make_queue_row(result: dict[str, Any]) -> dict[str, Any]:
    requires_human_apply = is_capability_candidate(result)
    return {
        "version": CAPABILITY_VERSION,
        "candidate_id": result.get("candidate_id"),
        "run_id": result.get("run_id"),
        "source_agent": result.get("source_agent"),
        "target_agent": result.get("target_agent") or result.get("source_agent"),
        "candidate_type": result.get("candidate_type"),
        "target_scope": result.get("target_scope"),
        "status": result.get("decision"),
        "proposal": result.get("proposal", ""),
        "scores": result.get("scores", {}),
        "reasons": result.get("reasons", []),
        "source_basis": result.get("source_basis", []),
        "required_tests": result.get("required_tests", []),
        "required_follow_up_tests": result.get("required_follow_up_tests", []),
        "controls": result.get("controls", []),
        "approval_mode": APPROVAL_MODE,
        "adoption_route": result.get("adoption_route"),
        "memory_write_policy": result.get("memory_write_policy"),
        "human_approval_required": True if requires_human_apply else bool(result.get("human_approval_required", True)),
        "protected_mutation_allowed": bool(result.get("protected_mutation_allowed", False)),
        "application_status": "pending_review",
        "mutated_agent_card": False,
        "mutated_runtime_skill": False,
        "mutated_core_profile": False,
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def make_version_row(result: dict[str, Any], target_agent: str, capability_kind: str) -> dict[str, Any]:
    return {
        "version": CAPABILITY_VERSION,
        "timestamp": now_iso(),
        "candidate_id": result.get("candidate_id"),
        "run_id": result.get("run_id"),
        "source_agent": result.get("source_agent"),
        "target_agent": target_agent,
        "capability_kind": capability_kind,
        "candidate_type": result.get("candidate_type"),
        "target_scope": result.get("target_scope"),
        "status": "approved_candidate",
        "application_status": "pending_human_apply",
        "proposal": result.get("proposal", ""),
        "source_basis": result.get("source_basis", []),
        "required_tests": result.get("required_tests", []),
        "scores": result.get("scores", {}),
        "controls": result.get("controls", []),
        "approval_mode": APPROVAL_MODE,
        "adoption_route": result.get("adoption_route"),
        "memory_write_policy": result.get("memory_write_policy"),
        "human_approval_required": True,
        "protected_mutation_allowed": bool(result.get("protected_mutation_allowed", False)),
        "reversible": True,
        "mutated_agent_card": False,
        "mutated_runtime_skill": False,
        "mutated_core_profile": False,
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def write_capability_version(root: Path, target_agent: str, capability_kind: str, row: dict[str, Any]) -> None:
    append_jsonl(root / "memory" / "agents" / target_agent / "capabilities" / f"{capability_kind}.jsonl", [row])
    append_jsonl(root / "memory" / "organization" / "capability-ledger.jsonl", [row])


def capability_already_written(root: Path, target_agent: str, capability_kind: str, candidate_id: Any) -> bool:
    if not candidate_id:
        return False
    path = root / "memory" / "agents" / target_agent / "capabilities" / f"{capability_kind}.jsonl"
    for row in read_jsonl(path):
        if row.get("candidate_id") == candidate_id:
            return True
    return False


def capability_ref(target_agent: str, capability_kind: str, candidate_id: Any, already_written: bool) -> dict[str, Any]:
    return {
        "target_agent": target_agent,
        "capability_kind": capability_kind,
        "candidate_id": candidate_id,
        "approval_mode": APPROVAL_MODE,
        "application_status": "already_pending_or_recorded" if already_written else "pending_human_apply",
        "registry_path": str(Path("memory") / "agents" / target_agent / "capabilities" / f"{capability_kind}.jsonl"),
        "organization_ledger_path": str(Path("memory") / "organization" / "capability-ledger.jsonl"),
        "already_written": already_written,
        "mutated_agent_card": False,
        "mutated_runtime_skill": False,
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def write_agent_capability_ledger(run_path: Path, root: Path | None = None) -> dict[str, Any]:
    runtime_root = root or infer_runtime_root(run_path)
    run_id = infer_run_id(run_path)
    candidate_rows = read_jsonl(run_path / "evolution" / "capability-candidates.jsonl")
    registry_rows = capability_registry_rows_for_run(runtime_root, run_path, run_id)
    rows = merge_capability_rows(candidate_rows, registry_rows)
    agents: dict[str, dict[str, Any]] = {}
    for row in rows:
        target_agent = str(row.get("target_agent") or row.get("source_agent") or "organization")
        agent = agents.setdefault(target_agent, empty_agent_capability_summary())
        update_agent_capability_summary(agent, row)
    for agent in agents.values():
        finalize_agent_capability_summary(agent)
    statuses = [str(row.get("application_status") or "") for row in rows]
    ledger = {
        "version": CAPABILITY_VERSION,
        "artifact_type": "agent_capability_ledger",
        "run_id": run_id,
        "candidate_count": len(rows),
        "agent_count": len(agents),
        "pending_human_apply": statuses.count("pending_human_apply"),
        "applied": statuses.count("applied"),
        "blocked_regression": statuses.count("blocked_regression"),
        "needs_more_evidence": statuses.count("needs_more_evidence"),
        "not_applicable": statuses.count("not_applicable"),
        "agents": dict(sorted(agents.items())),
        "controls": agent_capability_ledger_controls(),
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }
    write_yaml(run_path / "evolution" / "agent-capability-ledger.yaml", ledger)
    return ledger


def infer_run_id(run_path: Path) -> str:
    run_doc = run_path / "run.yaml"
    if run_doc.exists():
        loaded = read_yaml(run_doc) or {}
        if isinstance(loaded, dict) and loaded.get("run_id"):
            return str(loaded["run_id"])
    return run_path.name


def capability_registry_rows_for_run(root: Path, run_path: Path, run_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    base = root / "memory" / "agents"
    if not base.exists():
        return rows
    for registry in sorted(base.glob("*/capabilities/*.jsonl")):
        try:
            rel = registry.relative_to(root).as_posix()
            agent_id = registry.relative_to(base).parts[0]
        except ValueError:
            rel = registry.as_posix()
            agent_id = registry.parent.parent.name
        capability_kind = registry.stem
        for row in read_jsonl(registry):
            if row.get("run_id") in {run_path.name, run_id}:
                rows.append({
                    **row,
                    "target_agent": row.get("target_agent") or agent_id,
                    "capability_kind": row.get("capability_kind") or capability_kind,
                    "registry_path": rel,
                })
    return rows


def merge_capability_rows(candidate_rows: list[dict[str, Any]], registry_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for row in candidate_rows:
        candidate_id = row.get("candidate_id")
        if not candidate_id:
            continue
        merged[str(candidate_id)] = dict(row)
    for row in registry_rows:
        candidate_id = row.get("candidate_id")
        if not candidate_id:
            continue
        existing = merged.get(str(candidate_id), {})
        merged[str(candidate_id)] = {**existing, **row}
    return [merged[key] for key in sorted(merged)]


def empty_agent_capability_summary() -> dict[str, Any]:
    return {
        "candidate_count": 0,
        "approved_candidates": 0,
        "pending_human_apply": 0,
        "applied": 0,
        "blocked_regression": 0,
        "needs_more_evidence": 0,
        "not_applicable": 0,
        "capability_kinds": [],
        "candidate_ids": [],
        "latest_candidate_id": "",
        "latest_application_status": "none",
        "latest_regression_status": "missing",
        "registry_paths": [],
        "approval_routes": [],
        "required_tests": [],
        "controls": [],
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def update_agent_capability_summary(agent: dict[str, Any], row: dict[str, Any]) -> None:
    candidate_id = str(row.get("candidate_id") or "")
    application_status = str(row.get("application_status") or "pending_review")
    regression_status = str(row.get("regression_status") or "missing")
    agent["candidate_count"] += 1
    if row.get("status") == "approved_candidate":
        agent["approved_candidates"] += 1
    for status_field in ["pending_human_apply", "applied", "blocked_regression", "needs_more_evidence", "not_applicable"]:
        if application_status == status_field:
            agent[status_field] += 1
    append_unique(agent["capability_kinds"], row.get("capability_kind") or capability_kind_for(row))
    append_unique(agent["candidate_ids"], candidate_id)
    append_unique(agent["registry_paths"], row.get("registry_path"))
    append_unique(agent["approval_routes"], row.get("adoption_route") or row.get("approval_mode"))
    for test in row.get("required_tests", []) or []:
        append_unique(agent["required_tests"], test)
    for control in row.get("controls", []) or []:
        append_unique(agent["controls"], control)
    agent["latest_candidate_id"] = candidate_id
    agent["latest_application_status"] = application_status
    agent["latest_regression_status"] = regression_status


def finalize_agent_capability_summary(agent: dict[str, Any]) -> None:
    for key in ["capability_kinds", "candidate_ids", "registry_paths", "approval_routes", "required_tests", "controls"]:
        agent[key] = sorted(str(item) for item in agent.get(key, []) if item)
    for control in agent_capability_ledger_controls():
        append_unique(agent["controls"], control)
    agent["controls"] = sorted(agent["controls"])
    agent["real_trade_allowed"] = False
    agent["broker_integration"] = "disabled"


def append_unique(values: list[Any], value: Any) -> None:
    if value and value not in values:
        values.append(value)


def agent_capability_ledger_controls() -> list[str]:
    return [
        "capability_lifecycle_per_agent_required",
        "evolution_gate_before_capability_registry",
        "capability_regression_before_apply",
        "human_approval_before_apply",
        "no_direct_profile_mutation",
        "no_real_trade_action",
        "broker_integration_disabled",
    ]
