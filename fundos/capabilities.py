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
    "approved_candidates": 0,
    "quarantined_candidates": 0,
    "rejected_candidates": 0,
    "pending_human_apply": 0,
    "skipped_existing": 0,
    "agent_versions": {},
    "written_paths": [],
    "approval_mode": APPROVAL_MODE,
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
        "human_approval_required": bool(result.get("human_approval_required", True)),
        "protected_mutation_allowed": bool(result.get("protected_mutation_allowed", False)),
        "application_status": "pending_review",
        "mutated_agent_card": False,
        "mutated_runtime_skill": False,
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
        "human_approval_required": bool(result.get("human_approval_required", True)),
        "protected_mutation_allowed": bool(result.get("protected_mutation_allowed", False)),
        "reversible": True,
        "mutated_agent_card": False,
        "mutated_runtime_skill": False,
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
