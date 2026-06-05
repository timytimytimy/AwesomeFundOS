from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fundos.io import read_yaml, write_yaml

AGENT_THREAD_VERSION = "0.1.0"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def materialize_agent_threads(root: Path, roster: dict[str, Any]) -> dict[str, Any]:
    agents = roster.get("agents", [])
    count = 0
    for agent in agents:
        ensure_agent_thread(root, agent)
        count += 1
    summary = {
        "version": AGENT_THREAD_VERSION,
        "artifact_type": "agent_thread_materialization_summary",
        "agent_count": len(agents),
        "created_or_existing_threads": count,
        "thread_root": "memory/agents",
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }
    write_yaml(root / "memory" / "organization" / "agent-thread-summary.yaml", summary)
    return summary


def ensure_agent_thread(root: Path, agent: dict[str, Any]) -> dict[str, Any]:
    agent_id = agent["id"]
    memory_dir = root / "memory" / "agents" / agent_id
    memory_dir.mkdir(parents=True, exist_ok=True)
    thread_path = memory_dir / "thread.yaml"
    events_path = memory_dir / "thread-events.jsonl"
    if not thread_path.exists():
        doc = {
            "version": AGENT_THREAD_VERSION,
            "artifact_type": "agent_thread",
            "thread_id": f"thread_{agent_id}",
            "agent_id": agent_id,
            "agent_name": agent.get("name"),
            "role": agent.get("role"),
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "continuity_scope": ["profile", "skills", "tools", "memory", "harness", "evolution", "performance", "failure_patterns"],
            "event_log_path": str(Path("memory") / "agents" / agent_id / "thread-events.jsonl"),
            "semantic_memory_path": str(Path("memory") / "agents" / agent_id / "semantic_memory.md"),
            "evolution_ledger_path": str(Path("memory") / "agents" / agent_id / "evolution-ledger.jsonl"),
            "controls": [
                "persistent_agent_identity",
                "append_only_event_log",
                "evolution_gate_required_for_memory_write",
                "no_core_profile_mutation",
                "no_real_trade_action",
            ],
            "real_trade_allowed": False,
            "broker_integration": "disabled",
        }
        write_yaml(thread_path, doc)
    if not events_path.exists():
        append_event(events_path, {
            "event_type": "thread_created",
            "agent_id": agent_id,
            "role": agent.get("role"),
            "run_id": "none",
            "payload": {"source": "fundos init/materialize"},
        })
    return read_yaml(thread_path)


def record_run_threads(run_path: Path, selected: list[dict[str, Any]], event_type: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    root = infer_runtime_root(run_path)
    run_id = infer_run_id(run_path)
    threads = []
    for item in selected:
        agent_id = item["agent_id"]
        role = item.get("role", "")
        thread_path = root / "memory" / "agents" / agent_id / "thread.yaml"
        events_path = root / "memory" / "agents" / agent_id / "thread-events.jsonl"
        if not thread_path.exists():
            ensure_agent_thread(root, {"id": agent_id, "name": agent_id, "role": role})
        event = {
            "event_type": event_type,
            "agent_id": agent_id,
            "role": role,
            "run_id": run_id,
            "payload": payload or {},
        }
        append_event(events_path, event)
        update_thread_timestamp(thread_path)
        threads.append({
            "agent_id": agent_id,
            "thread_path": str(Path("memory") / "agents" / agent_id / "thread.yaml"),
            "event_log_path": str(Path("memory") / "agents" / agent_id / "thread-events.jsonl"),
            "latest_event_type": event_type,
        })
    manifest = {
        "version": AGENT_THREAD_VERSION,
        "artifact_type": "run_agent_thread_manifest",
        "run_id": run_id,
        "thread_count": len(threads),
        "event_type": event_type,
        "threads": threads,
        "controls": ["append_only_event_log", "agent_identity_continuity", "no_real_trade_action"],
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }
    write_yaml(run_path / "memory" / "agent-thread-manifest.yaml", manifest)
    return manifest


def load_run_thread_manifest(run_path: Path | None) -> dict[str, Any]:
    if not run_path:
        return missing_manifest()
    path = run_path / "memory" / "agent-thread-manifest.yaml"
    if not path.exists():
        return missing_manifest()
    return read_yaml(path) or missing_manifest()


def evaluate_thread_manifest(run_path: Path | None) -> dict[str, Any]:
    manifest = load_run_thread_manifest(run_path)
    if manifest.get("status") == "missing":
        return {
            "thread_count": 0,
            "manifest_present": False,
            "append_only_event_log": False,
            "agent_identity_continuity": False,
            "real_trade_allowed": False,
            "broker_integration": "disabled",
            "blocking_issues": ["missing_agent_thread_manifest"],
        }
    root = infer_runtime_root(run_path) if run_path else Path.cwd()
    missing_logs = []
    latest_types = []
    for item in manifest.get("threads", []):
        event_path = root / item.get("event_log_path", "")
        if not event_path.exists():
            missing_logs.append(item.get("agent_id"))
            continue
        rows = read_events(event_path)
        if rows:
            latest_types.append(rows[-1].get("event_type"))
    return {
        "thread_count": manifest.get("thread_count", 0),
        "manifest_present": True,
        "append_only_event_log": not missing_logs,
        "agent_identity_continuity": manifest.get("thread_count", 0) == len(manifest.get("threads", [])) and not missing_logs,
        "latest_event_types": sorted(set(latest_types)),
        "real_trade_allowed": manifest.get("real_trade_allowed", False),
        "broker_integration": manifest.get("broker_integration", "disabled"),
        "blocking_issues": ["missing_thread_event_log"] if missing_logs else [],
    }


def load_agent_thread_summary(root: Path, agent_id: str) -> dict[str, Any]:
    thread_path = root / "memory" / "agents" / agent_id / "thread.yaml"
    events_path = root / "memory" / "agents" / agent_id / "thread-events.jsonl"
    if not thread_path.exists() and not events_path.exists():
        raise FileNotFoundError(f"thread_not_found: {agent_id}")
    thread = read_yaml(thread_path) if thread_path.exists() else {}
    events = read_events(events_path)
    latest = events[-1] if events else {}
    return {
        "agent_id": agent_id,
        "thread_id": thread.get("thread_id", f"thread_{agent_id}"),
        "thread_path": thread_path,
        "event_log_path": events_path,
        "thread_exists": thread_path.exists(),
        "event_log_exists": events_path.exists(),
        "event_count": len(events),
        "latest_event_type": latest.get("event_type", "none"),
        "latest_run_id": latest.get("run_id", "none"),
        "continuity_scope": thread.get("continuity_scope", []),
        "real_trade_allowed": thread.get("real_trade_allowed", False),
        "broker_integration": thread.get("broker_integration", "disabled"),
    }


def append_event(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "timestamp": now_iso(),
        "event_type": event.get("event_type"),
        "agent_id": event.get("agent_id"),
        "role": event.get("role", ""),
        "run_id": event.get("run_id", "none"),
        "payload": event.get("payload", {}),
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def update_thread_timestamp(thread_path: Path) -> None:
    doc = read_yaml(thread_path) or {}
    doc["updated_at"] = now_iso()
    write_yaml(thread_path, doc)


def infer_runtime_root(run_path: Path) -> Path:
    resolved = run_path.resolve()
    if resolved.parent.name == "runs":
        return resolved.parent.parent
    return resolved.parent


def infer_run_id(run_path: Path) -> str:
    run_doc = run_path / "run.yaml"
    if run_doc.exists():
        return (read_yaml(run_doc) or {}).get("run_id", run_path.name)
    return run_path.name


def missing_manifest() -> dict[str, Any]:
    return {
        "version": AGENT_THREAD_VERSION,
        "artifact_type": "run_agent_thread_manifest",
        "status": "missing",
        "thread_count": 0,
        "threads": [],
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }
