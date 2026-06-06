from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fundos.io import read_yaml, write_yaml

APPROVAL_MODE = "evolution_gate_v1_auto_controlled"
SUMMARY_DEFAULT = {
    "memory_writes": 0,
    "agent_writes": {},
    "skipped_non_accepted": 0,
    "skipped_unsafe": 0,
    "skipped_existing": 0,
    "approval_mode": APPROVAL_MODE,
    "written_paths": [],
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def load_agent_memory_summary(root: Path, agent_id: str) -> dict[str, Any]:
    memory_dir = root / "memory" / "agents" / agent_id
    semantic_path = memory_dir / "semantic_memory.md"
    ledger_path = memory_dir / "evolution-ledger.jsonl"
    if not semantic_path.exists() and not ledger_path.exists():
        raise FileNotFoundError(f"memory_not_found: {agent_id}")
    semantic_text = semantic_path.read_text(encoding="utf-8") if semantic_path.exists() else ""
    ledger_rows = read_jsonl(ledger_path)
    latest = ledger_rows[-1] if ledger_rows else {}
    return {
        "agent_id": agent_id,
        "semantic_memory_path": semantic_path,
        "ledger_path": ledger_path,
        "semantic_memory_exists": semantic_path.exists(),
        "ledger_exists": ledger_path.exists(),
        "accepted_lessons": semantic_text.count("## Accepted Evolution Lesson:"),
        "ledger_entries": len(ledger_rows),
        "latest_candidate": latest.get("candidate_id", "none"),
        "latest_run_id": latest.get("run_id", "none"),
        "latest_candidate_type": latest.get("candidate_type", "none"),
        "approval_mode": latest.get("approval_mode", "none"),
        "reversible": latest.get("reversible", "none"),
        "real_trade_allowed": latest.get("real_trade_allowed", False),
        "broker_integration": latest.get("broker_integration", "disabled"),
        "latest_proposal": latest.get("proposal", ""),
        "semantic_preview": semantic_preview(semantic_text),
    }


def semantic_preview(text: str, max_lines: int = 12) -> str:
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return "none"
    return "\n".join(lines[:max_lines])


def load_memory_writeback_summary(run_path: Path) -> dict[str, Any]:
    path = run_path / "evolution" / "memory-writeback-summary.yaml"
    if not path.exists():
        return dict(SUMMARY_DEFAULT)
    loaded = read_yaml(path) or {}
    summary = dict(SUMMARY_DEFAULT)
    summary.update(loaded)
    return summary


def apply_evolution_results(run_path: Path, results: list[dict[str, Any]], memory_root: Path | None = None) -> dict[str, Any]:
    """Write accepted EvolutionGate lessons into controlled long-term memory.

    The writeback root is the project/runtime root that owns the run directory:
    `<root>/runs/<run_id>` -> `<root>/memory/...`. This intentionally never
    mutates `agents/<id>/profile.yaml`, source-controlled agent cards, skills,
    tool permissions, risk limits, or organization structure.
    """
    root = memory_root or infer_runtime_root(run_path)
    summary: dict[str, Any] = {
        "memory_writes": 0,
        "agent_writes": {},
        "skipped_non_accepted": 0,
        "skipped_unsafe": 0,
        "skipped_existing": 0,
        "approval_mode": APPROVAL_MODE,
        "written_paths": [],
    }
    for result in results:
        if result.get("decision") != "accept":
            summary["skipped_non_accepted"] += 1
            continue
        if not is_safe_memory_write(result):
            summary["skipped_unsafe"] += 1
            result["memory_write_allowed"] = False
            controls = result.setdefault("controls", [])
            if "no_memory_write" not in controls:
                controls.append("no_memory_write")
            continue
        target_agent = result.get("target_agent") or result.get("source_agent") or "organization"
        if already_written(root, target_agent, result.get("candidate_id")):
            result["memory_write_allowed"] = True
            result["memory_write"] = {
                "target_agent": target_agent,
                "approval_mode": APPROVAL_MODE,
                "already_written": True,
                "semantic_memory_path": str(Path("memory") / "agents" / target_agent / "semantic_memory.md"),
                "agent_ledger_path": str(Path("memory") / "agents" / target_agent / "evolution-ledger.jsonl"),
                "organization_ledger_path": str(Path("memory") / "organization" / "evolution-ledger.jsonl"),
            }
            summary["skipped_existing"] += 1
            continue
        ledger_row = make_ledger_row(result, target_agent)
        write_agent_memory(root, target_agent, ledger_row)
        write_ledgers(root, target_agent, ledger_row)
        result["memory_write_allowed"] = True
        result["memory_write"] = {
            "target_agent": target_agent,
            "approval_mode": APPROVAL_MODE,
            "semantic_memory_path": str(Path("memory") / "agents" / target_agent / "semantic_memory.md"),
            "agent_ledger_path": str(Path("memory") / "agents" / target_agent / "evolution-ledger.jsonl"),
            "organization_ledger_path": str(Path("memory") / "organization" / "evolution-ledger.jsonl"),
        }
        summary["memory_writes"] += 1
        summary["agent_writes"][target_agent] = summary["agent_writes"].get(target_agent, 0) + 1
        summary["written_paths"].extend([
            str(Path("memory") / "agents" / target_agent / "semantic_memory.md"),
            str(Path("memory") / "agents" / target_agent / "evolution-ledger.jsonl"),
            str(Path("memory") / "organization" / "evolution-ledger.jsonl"),
        ])
    summary["written_paths"] = sorted(set(summary["written_paths"]))
    write_yaml(run_path / "evolution" / "memory-writeback-summary.yaml", summary)
    return summary


def infer_runtime_root(run_path: Path) -> Path:
    run_path = run_path.resolve()
    if run_path.parent.name == "runs":
        return run_path.parent.parent
    return run_path.parent


def is_safe_memory_write(result: dict[str, Any]) -> bool:
    if result.get("decision") != "accept":
        return False
    if result.get("adoption_route") in {"managed_capability_pending_human_apply", "skill_patch_pending_human_apply", "forbidden_protected_mutation"}:
        return False
    if result.get("memory_write_policy") in {"no_direct_memory_write", "blocked"}:
        return False
    target_scope = result.get("target_scope", "agent_memory")
    candidate_type = result.get("candidate_type", "unknown")
    if target_scope not in {"agent_memory", "skill", "workflow", "principle"}:
        return False
    if candidate_type in {"profile_update", "tool_permission_update", "risk_limit_update"}:
        return False
    controls = set(result.get("controls", []))
    return "no_direct_profile_mutation" in controls and "no_real_trade_action" in controls


def make_ledger_row(result: dict[str, Any], target_agent: str) -> dict[str, Any]:
    return {
        "timestamp": now_iso(),
        "candidate_id": result.get("candidate_id"),
        "run_id": result.get("run_id"),
        "source_agent": result.get("source_agent"),
        "target_agent": target_agent,
        "candidate_type": result.get("candidate_type"),
        "target_scope": result.get("target_scope", "agent_memory"),
        "proposal": result.get("proposal", ""),
        "source_basis": result.get("source_basis", []),
        "metadata": result.get("metadata", {}),
        "hypothesis_origin_quality": result.get("hypothesis_origin_quality", {}),
        "required_tests": result.get("required_tests", result.get("required_follow_up_tests", [])),
        "scores": result.get("scores", {}),
        "controls": result.get("controls", []),
        "approval_mode": APPROVAL_MODE,
        "reversible": True,
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def already_written(root: Path, target_agent: str, candidate_id: Any) -> bool:
    if not candidate_id:
        return False
    ledger_path = root / "memory" / "agents" / target_agent / "evolution-ledger.jsonl"
    if not ledger_path.exists():
        return False
    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("candidate_id") == candidate_id:
            return True
    return False


def write_agent_memory(root: Path, target_agent: str, row: dict[str, Any]) -> None:
    path = root / "memory" / "agents" / target_agent / "semantic_memory.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = path.read_text(encoding="utf-8")
    else:
        existing = f"# {target_agent} Long-term Memory\n\n"
    entry = format_memory_entry(row)
    path.write_text(existing.rstrip() + "\n\n" + entry + "\n", encoding="utf-8")


def format_memory_entry(row: dict[str, Any]) -> str:
    basis = ", ".join(
        f"{item.get('evidence_id', 'unknown')}:{item.get('source_tier', 'unknown')}"
        for item in row.get("source_basis", [])
    ) or "none"
    tests = ", ".join(row.get("required_tests", [])) or "none"
    lines = [
        f"## Accepted Evolution Lesson: {row.get('candidate_id')}",
        "",
        f"- timestamp: {row.get('timestamp')}",
        f"- run_id: {row.get('run_id')}",
        f"- source_agent: {row.get('source_agent')}",
        f"- candidate_type: {row.get('candidate_type')}",
        f"- target_scope: {row.get('target_scope')}",
        f"- proposal: {row.get('proposal')}",
        f"- source_basis: {basis}",
        f"- required_tests: {tests}",
        f"- approval_mode: {row.get('approval_mode')}",
    ]
    metadata = row.get("metadata", {}) if isinstance(row.get("metadata", {}), dict) else {}
    if metadata.get("source") == "agent_reasoning_layer":
        lines.extend([
            f"- hypothesis_source: {metadata.get('source')}",
            f"- source_agent_id: {metadata.get('source_agent_id')}",
            f"- source_evidence_id: {metadata.get('source_evidence_id')}",
            f"- source_claim_id: {metadata.get('source_claim_id')}",
            f"- validation_required: {metadata.get('validation_required')}",
            f"- real_trade_allowed: {str(row.get('real_trade_allowed', False)).lower()}",
            f"- broker_integration: {row.get('broker_integration', 'disabled')}",
        ])
    lines.extend([
        "- controls: no core profile mutation; no real trade action; reversible ledger entry",
    ])
    return "\n".join(lines)


def write_ledgers(root: Path, target_agent: str, row: dict[str, Any]) -> None:
    append_jsonl(root / "memory" / "agents" / target_agent / "evolution-ledger.jsonl", [row])
    append_jsonl(root / "memory" / "organization" / "evolution-ledger.jsonl", [row])
