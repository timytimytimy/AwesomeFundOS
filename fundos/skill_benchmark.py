from __future__ import annotations

from pathlib import Path
from typing import Any

from fundos.capability_regression import load_capability_regression
from fundos.io import REPO_ROOT, read_yaml, write_yaml

BENCHMARK_REL = "specs/skills/regression-benchmarks.yaml"
BENCHMARK_VERSION = "0.1.0"


def load_skill_regression_benchmarks() -> dict[str, Any]:
    spec = read_yaml(REPO_ROOT / BENCHMARK_REL)
    spec["source_path"] = BENCHMARK_REL
    return spec


def default_skill_benchmark_report() -> dict[str, Any]:
    return {
        "version": BENCHMARK_VERSION,
        "artifact_type": "skill_benchmark_report",
        "overall_score": 0,
        "agents_evaluated": 0,
        "passed_agents": 0,
        "blocked_agents": 0,
        "skill_candidates_evaluated": 0,
        "blocked_skill_candidates": 0,
        "agent_skill_results": [],
        "capability_candidate_results": [],
        "blocking_issues": ["missing_skill_benchmark"],
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def load_skill_benchmark_report(run_path: Path | None) -> dict[str, Any]:
    if not run_path:
        return default_skill_benchmark_report()
    path = run_path / "harness" / "skill-benchmark.yaml"
    if not path.exists():
        return default_skill_benchmark_report()
    loaded = read_yaml(path) or {}
    report = default_skill_benchmark_report()
    report.update(loaded)
    return report


def run_skill_benchmark(run_path: Path) -> dict[str, Any]:
    spec = load_skill_regression_benchmarks()
    agent_harness = read_yaml(run_path / "harness" / "agent-harness.yaml") if (run_path / "harness" / "agent-harness.yaml").exists() else {"agent_results": []}
    agent_results = [evaluate_agent_skill(row, spec) for row in agent_harness.get("agent_results", [])]
    capability_results = evaluate_skill_candidates(run_path, agent_results)
    passed_agents = [row for row in agent_results if row.get("benchmark_status") == "passed"]
    blocked_agents = [row for row in agent_results if row.get("benchmark_status") == "blocked"]
    blocked_candidates = [row for row in capability_results if row.get("skill_benchmark_status") == "blocked"]
    scores = [row.get("overall_skill_score", 0) for row in agent_results]
    overall = round(sum(scores) / len(scores), 1) if scores else 0
    blocking = sorted({issue for row in agent_results for issue in row.get("blocking_issues", [])} | {issue for row in blocked_candidates for issue in row.get("blocking_issues", [])})
    report = {
        "version": BENCHMARK_VERSION,
        "artifact_type": "skill_benchmark_report",
        "benchmark_id": spec.get("benchmark_id"),
        "source_path": spec.get("source_path"),
        "run_id": run_path.name,
        "overall_score": overall,
        "agents_evaluated": len(agent_results),
        "passed_agents": len(passed_agents),
        "blocked_agents": len(blocked_agents),
        "skill_candidates_evaluated": len(capability_results),
        "blocked_skill_candidates": len(blocked_candidates),
        "agent_skill_results": agent_results,
        "capability_candidate_results": capability_results,
        "blocking_issues": blocking,
        "controls": spec.get("controls", []),
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }
    write_yaml(run_path / "harness" / "skill-benchmark.yaml", report)
    return report


def evaluate_agent_skill(agent_result: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    gate_scores: dict[str, Any] = {}
    blocking: list[str] = []
    for gate in spec.get("global_gates", []):
        gate_id = gate["gate_id"]
        value = metric_value(agent_result, gate.get("source_metric", ""))
        passed = gate_passed(value, gate)
        gate_scores[gate_id] = {"value": value, "passed": passed}
        if not passed:
            blocking.append(gate.get("blocking_issue", f"{gate_id}_failed"))
    numeric_scores = [score_value(row["value"]) for row in gate_scores.values()]
    overall = round(sum(numeric_scores) / len(numeric_scores), 1) if numeric_scores else 0
    status = "passed" if not blocking else "blocked"
    return {
        "agent_id": agent_result.get("agent_id"),
        "role": agent_result.get("role"),
        "role_family": infer_role_family(agent_result),
        "overall_skill_score": overall,
        "benchmark_status": status,
        "gate_scores": gate_scores,
        "blocking_issues": sorted(set(blocking)),
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def metric_value(row: dict[str, Any], dotted: str) -> Any:
    cur: Any = row
    for part in dotted.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def gate_passed(value: Any, gate: dict[str, Any]) -> bool:
    if "required_value" in gate:
        return value is gate["required_value"] or value == gate["required_value"]
    if "min_score" in gate:
        try:
            return float(value or 0) >= float(gate["min_score"])
        except (TypeError, ValueError):
            return False
    return bool(value)


def score_value(value: Any) -> float:
    if isinstance(value, bool):
        return 100.0 if value else 0.0
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def infer_role_family(agent_result: dict[str, Any]) -> str:
    agent_id = agent_result.get("agent_id", "") or ""
    role = agent_result.get("role", "") or ""
    if any(key in agent_id for key in ["trader"]):
        return "trading"
    if "Analyst" in role and any(key in agent_id for key in ["company", "governance", "turnaround"]):
        return "company"
    if "Analyst" in role:
        return "research"
    return "core_operating"


def evaluate_skill_candidates(run_path: Path, agent_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    regression = load_capability_regression(run_path)
    by_agent = {row.get("agent_id"): row for row in agent_results}
    results: list[dict[str, Any]] = []
    for candidate in regression.get("candidate_results", []):
        if candidate.get("capability_kind") != "skill" and candidate.get("target_scope") != "skill" and candidate.get("candidate_type") != "skill_update":
            continue
        target_agent = candidate.get("target_agent")
        agent_status = by_agent.get(target_agent, {}).get("benchmark_status", "missing_agent_benchmark")
        candidate_passed = candidate.get("regression_status") == "passed" and agent_status == "passed"
        blocking = list(candidate.get("blocking_issues", []))
        if agent_status != "passed":
            blocking.append(f"agent_skill_benchmark_not_passed:{agent_status}")
        results.append({
            "candidate_id": candidate.get("candidate_id"),
            "target_agent": target_agent,
            "capability_kind": candidate.get("capability_kind") or candidate.get("target_scope"),
            "regression_status": candidate.get("regression_status"),
            "agent_benchmark_status": agent_status,
            "skill_benchmark_status": "passed" if candidate_passed else "blocked",
            "application_status_after_skill_benchmark": "pending_human_apply" if candidate_passed else "blocked_skill_benchmark",
            "blocking_issues": sorted(set(blocking)),
            "real_trade_allowed": False,
            "broker_integration": "disabled",
        })
    return results
