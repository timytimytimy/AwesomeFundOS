from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fundos.io import read_yaml, write_yaml

APPLY_VERSION = "0.1.0"
MANAGED_SECTION_TITLE = "## FundOS Applied Capability Candidates"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def list_pending_capabilities(root: Path) -> list[dict[str, Any]]:
    rows = []
    base = root / "memory" / "agents"
    if not base.exists():
        return []
    for registry_path in sorted(base.glob("*/capabilities/*.jsonl")):
        registry_rel = registry_path.relative_to(root).as_posix()
        for row in read_jsonl(registry_path):
            if row.get("application_status") == "pending_human_apply":
                rows.append({**row, "registry_path": registry_rel})
    return rows


def apply_approved_capability(root: Path, candidate_id: str, approver: str) -> dict[str, Any]:
    if not approver:
        raise PermissionError("human approver is required before applying a capability candidate")
    match = find_candidate(root, candidate_id)
    if not match:
        raise FileNotFoundError(f"pending capability candidate not found: {candidate_id}")
    registry_path, rows, index, candidate = match
    if candidate.get("application_status") != "pending_human_apply":
        raise ValueError(f"capability candidate is not pending_human_apply: {candidate_id}")

    target_agent = candidate.get("target_agent") or candidate.get("source_agent") or "organization"
    capability_kind = candidate.get("capability_kind") or kind_from_path(registry_path)
    if capability_kind == "skill":
        target_path = apply_skill_candidate(root, target_agent, candidate)
    else:
        target_path = apply_policy_candidate(root, target_agent, capability_kind, candidate)

    applied_ref = {
        "version": APPLY_VERSION,
        "candidate_id": candidate_id,
        "target_agent": target_agent,
        "capability_kind": capability_kind,
        "target_path": target_path.relative_to(root).as_posix(),
        "applied_at": now_iso(),
        "approver": approver,
        "reversible": True,
        "managed_block_only": capability_kind == "skill",
        "mutated_agent_card": False,
        "mutated_runtime_skill": capability_kind == "skill",
        "mutated_core_profile": False,
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }
    rows[index] = {**candidate, "application_status": "applied", "applied_ref": applied_ref}
    write_jsonl(registry_path, rows)
    append_jsonl(root / "memory" / "organization" / "capability-apply-ledger.jsonl", [
        {
            **applied_ref,
            "run_id": candidate.get("run_id"),
            "source_agent": candidate.get("source_agent"),
            "proposal": candidate.get("proposal", ""),
            "required_tests": candidate.get("required_tests", []),
            "controls": sorted(set(candidate.get("controls", []) + ["human_approved_apply", "no_direct_profile_mutation", "no_real_trade_action"])),
        }
    ])
    return {"application_status": "applied", **applied_ref}


def find_candidate(root: Path, candidate_id: str) -> tuple[Path, list[dict[str, Any]], int, dict[str, Any]] | None:
    for registry_path in sorted((root / "memory" / "agents").glob("*/capabilities/*.jsonl")):
        rows = read_jsonl(registry_path)
        for index, row in enumerate(rows):
            if row.get("candidate_id") == candidate_id:
                return registry_path, rows, index, row
    return None


def kind_from_path(path: Path) -> str:
    return path.stem


def apply_skill_candidate(root: Path, target_agent: str, candidate: dict[str, Any]) -> Path:
    skill_path = root / "skills" / target_agent / "SKILL.md"
    skill_path.parent.mkdir(parents=True, exist_ok=True)
    if skill_path.exists():
        text = skill_path.read_text(encoding="utf-8")
    else:
        text = f"# {target_agent} Skill\n"
    marker = candidate_marker(candidate["candidate_id"])
    if marker[0] not in text:
        block = render_skill_block(candidate)
        text = text.rstrip() + "\n\n" + block + "\n"
        skill_path.write_text(text, encoding="utf-8")
    return skill_path


def candidate_marker(candidate_id: str) -> tuple[str, str]:
    return (f"<!-- FUNDOS_CAPABILITY:{candidate_id} START -->", f"<!-- FUNDOS_CAPABILITY:{candidate_id} END -->")


def render_skill_block(candidate: dict[str, Any]) -> str:
    start, end = candidate_marker(candidate["candidate_id"])
    required_tests = candidate.get("required_tests", [])
    controls = sorted(set(candidate.get("controls", []) + ["human_approved_apply", "no_real_trade_action"]))
    lines = [
        start,
        MANAGED_SECTION_TITLE,
        "",
        f"- candidate_id: `{candidate.get('candidate_id')}`",
        f"- run_id: `{candidate.get('run_id', '')}`",
        f"- proposal: {candidate.get('proposal', '')}",
        "- status: human-approved applied capability candidate",
        "- boundaries: research/watchlist/paper portfolio only; no broker integration; no real trade action.",
    ]
    if required_tests:
        lines.append("- required_tests: " + ", ".join(required_tests))
    if controls:
        lines.append("- controls: " + ", ".join(controls))
    lines.append(end)
    return "\n".join(lines)


def apply_policy_candidate(root: Path, target_agent: str, capability_kind: str, candidate: dict[str, Any]) -> Path:
    path = root / "agents" / target_agent / "applied-capabilities.yaml"
    current = read_yaml(path) if path.exists() else None
    doc = current if isinstance(current, dict) else {"version": APPLY_VERSION, "agent_id": target_agent, "applied_capabilities": []}
    doc.setdefault("version", APPLY_VERSION)
    doc.setdefault("agent_id", target_agent)
    applied = doc.setdefault("applied_capabilities", [])
    if not any(row.get("candidate_id") == candidate.get("candidate_id") for row in applied):
        applied.append(
            {
                "candidate_id": candidate.get("candidate_id"),
                "run_id": candidate.get("run_id"),
                "source_agent": candidate.get("source_agent"),
                "capability_kind": capability_kind,
                "candidate_type": candidate.get("candidate_type"),
                "target_scope": candidate.get("target_scope"),
                "proposal": candidate.get("proposal", ""),
                "required_tests": candidate.get("required_tests", []),
                "controls": sorted(set(candidate.get("controls", []) + ["human_approved_apply", "no_direct_profile_mutation", "no_real_trade_action"])),
                "mutated_core_profile": False,
                "real_trade_allowed": False,
                "broker_integration": "disabled",
            }
        )
    write_yaml(path, doc)
    return path
