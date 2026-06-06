from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fundos.io import read_yaml, write_yaml

PERFORMANCE_VERSION = "0.1.0"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def infer_runtime_root(run_path: Path) -> Path:
    if run_path.parent.name == "runs":
        return run_path.parent.parent
    return run_path.parent


def load_optional_yaml(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    return read_yaml(path) or default


def evaluate_agent_performance(run_path: Path) -> dict[str, Any]:
    run_doc = load_optional_yaml(run_path / "run.yaml", {"run_id": run_path.name, "selected_agents": []})
    selected = run_doc.get("selected_agents", [])
    harness = load_optional_yaml(run_path / "harness" / "agent-harness.yaml", {"agent_results": []})
    evaluation = load_optional_yaml(run_path / "evaluations" / "evaluation-report.yaml", {"agent_scores": []})
    harness_by_agent = {row.get("agent_id"): row for row in harness.get("agent_results", [])}
    eval_by_agent = {row.get("agent_id"): row for row in evaluation.get("agent_scores", [])}
    results = [evaluate_single_agent(run_doc.get("run_id", run_path.name), item, harness_by_agent.get(item.get("agent_id")), eval_by_agent.get(item.get("agent_id"))) for item in selected]
    counts = count_by(results, "recommended_action")
    scored = [float(row.get("final_score", 0) or 0) for row in results if float(row.get("final_score", 0) or 0) > 0]
    return {
        "version": PERFORMANCE_VERSION,
        "artifact_type": "agent_performance_report",
        "run_id": run_doc.get("run_id", run_path.name),
        "agent_count": len(results),
        "average_final_score": round(sum(scored) / len(scored), 1) if scored else 0,
        "recommended_action_counts": counts,
        "ledger_entries_written": len(results),
        "agent_results": results,
        "controls": [
            "performance_review_is_not_capital_authority",
            "promotion_does_not_change_risk_limits",
            "downgrade_does_not_delete_memory",
            "no_real_trade_action",
        ],
    }


def evaluate_single_agent(run_id: str, selected: dict[str, Any], harness_row: dict[str, Any] | None, eval_row: dict[str, Any] | None) -> dict[str, Any]:
    agent_id = selected.get("agent_id")
    role = selected.get("role")
    blocking: list[str] = []
    if harness_row is None:
        blocking.append("missing_agent_harness")
        harness_row = {}
    if eval_row is None:
        blocking.append("missing_evaluation_agent_score")
        eval_row = {}
    context_score = float((harness_row.get("context_compression_quality") or {}).get("score", 0) or 0)
    skill_score = float((harness_row.get("skill_invocation_quality") or {}).get("score", 0) or 0)
    role_score = float((harness_row.get("role_consistency_quality") or {}).get("score", eval_row.get("role_consistency", 0)) or 0)
    contribution = float(eval_row.get("contribution_quality", 0) or 0)
    context_fit = float(eval_row.get("context_fit", 0) or 0)
    harness_overall = float(harness_row.get("overall_score", 0) or 0)
    if harness_row.get("blocking_issues"):
        blocking.extend(harness_row.get("blocking_issues", []))
    component_values = [value for value in [context_score, skill_score, role_score, contribution, context_fit, harness_overall] if value > 0]
    final_score = round(sum(component_values) / len(component_values), 1) if component_values else 0
    action = recommend_action(final_score, blocking, bool(component_values))
    return {
        "version": PERFORMANCE_VERSION,
        "run_id": run_id,
        "agent_id": agent_id,
        "role": role,
        "final_score": final_score,
        "component_scores": {
            "context_compression": context_score,
            "skill_invocation": skill_score,
            "role_consistency": role_score,
            "contribution_quality": contribution,
            "context_fit": context_fit,
            "harness_overall": harness_overall,
        },
        "recommended_action": action,
        "blocking_issues": sorted(set(blocking)),
        "real_trade_allowed": False,
        "risk_limit_changed": False,
        "profile_mutated": False,
        "memory_deleted": False,
    }


def recommend_action(final_score: float, blocking: list[str], has_scores: bool) -> str:
    if not has_scores:
        return "needs_more_observations"
    if final_score >= 88 and not blocking:
        return "promote_watch"
    if final_score < 60 or blocking:
        return "retrain_or_downgrade_watch"
    return "maintain"


def write_agent_performance(run_path: Path, root: Path | None = None) -> dict[str, Any]:
    runtime_root = root or infer_runtime_root(run_path)
    report = evaluate_agent_performance(run_path)
    write_yaml(run_path / "harness" / "agent-performance.yaml", report)
    for row in report.get("agent_results", []):
        write_agent_performance_rows(runtime_root, row)
    return report


def write_agent_performance_rows(root: Path, row: dict[str, Any]) -> None:
    agent_id = row.get("agent_id")
    if not agent_id:
        return
    perf_dir = root / "agents" / agent_id / "performance"
    ledger_row = dict(row)
    append_jsonl(perf_dir / "performance_ledger.jsonl", [ledger_row])
    append_jsonl(perf_dir / "evaluation_history.jsonl", [ledger_row])
    append_jsonl(perf_dir / "promotion_history.jsonl", [{
        "version": PERFORMANCE_VERSION,
        "run_id": row.get("run_id"),
        "agent_id": agent_id,
        "recommended_action": row.get("recommended_action"),
        "final_score": row.get("final_score"),
        "blocking_issues": row.get("blocking_issues", []),
        "risk_limit_changed": False,
        "profile_mutated": False,
        "real_trade_allowed": False,
    }])


def load_performance_summary(root: Path, agent_id: str) -> dict[str, Any]:
    ledger_path = root / "agents" / agent_id / "performance" / "performance_ledger.jsonl"
    rows = read_jsonl(ledger_path)
    if not rows:
        return {
            "agent_id": agent_id,
            "ledger_path": str(ledger_path),
            "runs_evaluated": 0,
            "average_score": 0,
            "latest_action": "none",
            "promote_watch_count": 0,
            "downgrade_watch_count": 0,
            "latest_score": 0,
        }
    scores = [float(row.get("final_score", 0) or 0) for row in rows]
    latest = rows[-1]
    return {
        "agent_id": agent_id,
        "ledger_path": str(ledger_path),
        "runs_evaluated": len(rows),
        "average_score": round(sum(scores) / len(scores), 1),
        "latest_action": latest.get("recommended_action", "none"),
        "promote_watch_count": sum(1 for row in rows if row.get("recommended_action") == "promote_watch"),
        "downgrade_watch_count": sum(1 for row in rows if row.get("recommended_action") == "retrain_or_downgrade_watch"),
        "latest_score": latest.get("final_score", 0),
    }


def load_agent_performance(run_path: Path | None) -> dict[str, Any]:
    if not run_path:
        return default_report()
    path = run_path / "harness" / "agent-performance.yaml"
    if not path.exists():
        return default_report()
    loaded = read_yaml(path) or {}
    report = default_report()
    report.update(loaded)
    return report


def default_report() -> dict[str, Any]:
    return {
        "version": PERFORMANCE_VERSION,
        "artifact_type": "agent_performance_report",
        "agent_count": 0,
        "recommended_action_counts": {},
        "agent_results": [],
        "controls": [],
    }


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key, "unknown"))
        counts[value] = counts.get(value, 0) + 1
    return counts
