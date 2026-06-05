from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fundos.agent_performance import load_agent_performance
from fundos.io import REPO_ROOT, read_yaml, write_yaml

GOVERNANCE_VERSION = "0.1.0"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def infer_runtime_root(run_path: Path) -> Path:
    if run_path.parent.name == "runs":
        return run_path.parent.parent
    return run_path.parent


def load_roster_categories() -> dict[str, dict[str, Any]]:
    path = REPO_ROOT / "specs" / "agents" / "default-roster.yaml"
    roster = read_yaml(path) or {"agents": []}
    return {agent["id"]: agent for agent in roster.get("agents", [])}


def evaluate_agent_governance(run_path: Path) -> dict[str, Any]:
    performance = load_agent_performance(run_path)
    roster = load_roster_categories()
    reviews = []
    for row in performance.get("agent_results", []):
        reviews.append(review_agent(row, roster.get(row.get("agent_id"), {})))
    seat_groups = group_reviews(reviews)
    seat_competitions = {seat: summarize_seat(seat, rows) for seat, rows in seat_groups.items()}
    action_counts = count_by(reviews, "governance_action")
    return {
        "version": GOVERNANCE_VERSION,
        "artifact_type": "agent_governance_report",
        "run_id": performance.get("run_id", run_path.name),
        "agent_count": len(reviews),
        "governance_action_counts": action_counts,
        "seat_groups": {seat: [row["agent_id"] for row in rows] for seat, rows in seat_groups.items()},
        "seat_competitions": seat_competitions,
        "agent_reviews": reviews,
        "controls": [
            "promotion_does_not_change_capital_authority",
            "downgrade_does_not_delete_memory",
            "seat_competition_is_review_signal_only",
            "human_approval_required_for_role_change",
            "no_real_trade_action",
            "broker_integration_disabled",
        ],
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def review_agent(performance_row: dict[str, Any], roster_row: dict[str, Any]) -> dict[str, Any]:
    score = float(performance_row.get("final_score", 0) or 0)
    perf_action = performance_row.get("recommended_action", "needs_more_observations")
    blocking = performance_row.get("blocking_issues", []) or []
    if perf_action == "promote_watch" and score >= 88 and not blocking:
        action = "promotion_watch"
        rationale = "High score and clean harness record; observe for broader mandate or lead-seat eligibility."
    elif perf_action == "retrain_or_downgrade_watch" or score < 60 or blocking:
        action = "retrain_and_downgrade_watch"
        rationale = "Low score or blocking issues; route to retraining and reduce seat confidence until recovery."
    elif perf_action == "needs_more_observations":
        action = "needs_more_observations"
        rationale = "Insufficient performance history for governance action."
    else:
        action = "maintain_seat"
        rationale = "Adequate performance; maintain current role and continue observation."
    return {
        "agent_id": performance_row.get("agent_id"),
        "role": performance_row.get("role") or roster_row.get("role"),
        "seat_group": roster_row.get("category", infer_seat_group(performance_row.get("role", ""))),
        "final_score": score,
        "performance_action": perf_action,
        "governance_action": action,
        "rationale": rationale,
        "blocking_issues": blocking,
        "requires_human_approval_for_role_change": True,
        "risk_limit_changed": False,
        "profile_mutated": False,
        "memory_deleted": False,
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def infer_seat_group(role: str) -> str:
    if "Trader" in role:
        return "trading"
    if "Analyst" in role:
        return "research"
    return "core_operating"


def group_reviews(reviews: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in reviews:
        seat = row.get("seat_group", "unknown")
        groups.setdefault(seat, []).append(row)
    return groups


def summarize_seat(seat: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    ranked = sorted(rows, key=lambda row: row.get("final_score", 0), reverse=True)
    leader = ranked[0] if ranked else {}
    return {
        "seat_group": seat,
        "agent_count": len(rows),
        "leader_agent_id": leader.get("agent_id", "none"),
        "leader_score": leader.get("final_score", 0),
        "promotion_watch_agents": [row["agent_id"] for row in rows if row.get("governance_action") == "promotion_watch"],
        "retrain_watch_agents": [row["agent_id"] for row in rows if row.get("governance_action") == "retrain_and_downgrade_watch"],
        "maintain_agents": [row["agent_id"] for row in rows if row.get("governance_action") == "maintain_seat"],
        "seat_competition_status": "competitive" if len(rows) > 1 else "single_agent_observation",
        "requires_human_approval_for_role_change": True,
        "real_trade_allowed": False,
    }


def write_agent_governance(run_path: Path, root: Path | None = None) -> dict[str, Any]:
    runtime_root = root or infer_runtime_root(run_path)
    report = evaluate_agent_governance(run_path)
    write_yaml(run_path / "harness" / "agent-governance.yaml", report)
    rows = [ledger_row(report, row) for row in report.get("agent_reviews", [])]
    append_jsonl(runtime_root / "memory" / "organization" / "agent-governance-ledger.jsonl", rows)
    for row in rows:
        append_jsonl(runtime_root / "agents" / row["agent_id"] / "governance" / "seat-history.jsonl", [row])
    return report


def ledger_row(report: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": GOVERNANCE_VERSION,
        "timestamp": now_iso(),
        "run_id": report.get("run_id"),
        "agent_id": review.get("agent_id"),
        "role": review.get("role"),
        "seat_group": review.get("seat_group"),
        "final_score": review.get("final_score"),
        "governance_action": review.get("governance_action"),
        "performance_action": review.get("performance_action"),
        "blocking_issues": review.get("blocking_issues", []),
        "requires_human_approval_for_role_change": True,
        "risk_limit_changed": False,
        "profile_mutated": False,
        "memory_deleted": False,
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def load_governance_summary(run_path: Path | None) -> dict[str, Any]:
    if not run_path:
        return default_report()
    path = run_path / "harness" / "agent-governance.yaml"
    if not path.exists():
        return default_report()
    loaded = read_yaml(path) or {}
    report = default_report()
    report.update(loaded)
    return report


def default_report() -> dict[str, Any]:
    return {
        "version": GOVERNANCE_VERSION,
        "artifact_type": "agent_governance_report",
        "agent_count": 0,
        "governance_action_counts": {},
        "seat_groups": {},
        "seat_competitions": {},
        "agent_reviews": [],
        "controls": [],
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key, "unknown"))
        counts[value] = counts.get(value, 0) + 1
    return counts
