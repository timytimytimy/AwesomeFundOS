from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fundos.io import DISCLAIMER, read_yaml, write_yaml
from fundos.research_cache import stable_hash

FAILURE_VERSION = "0.1.0"


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


def load_optional_yaml(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    return read_yaml(path) or default


def extract_failure_patterns(run_path: Path) -> dict[str, Any]:
    run_id = infer_run_id(run_path)
    patterns: list[dict[str, Any]] = []
    for reflection_path in sorted((run_path / "reflections").glob("*.reflection.yaml")):
        reflection = load_optional_yaml(reflection_path, {})
        agent_id = reflection.get("agent_id") or reflection_path.name.split(".")[0]
        patterns.extend(patterns_from_list(run_id, agent_id, "missing_evidence", reflection.get("missed_evidence", []), "medium", "补齐一手证据、公告、财报、行情或政策来源后再提升置信度。"))
        patterns.extend(patterns_from_list(run_id, agent_id, "reasoning_error", reflection.get("reasoning_errors", []), "high", "在下一次 ContextPack 中显式加入反例、替代解释和推理检查清单。"))
        patterns.extend(patterns_from_list(run_id, agent_id, "tool_usage_error", reflection.get("tool_usage_errors", []), "medium", "将缺失工具调用写入 tool checklist，并由 Tool Harness 检查。"))
        patterns.extend(patterns_from_list(run_id, agent_id, "bias_detected", reflection.get("bias_detected", []), "medium", "在角色输出中加入 bias self-check 和反方验证。"))
    evaluation = load_optional_yaml(run_path / "evaluations" / "evaluation-report.yaml", {})
    for issue in evaluation.get("blocking_issues", []):
        patterns.append(make_pattern(run_id, "evaluation_harness", "evaluation_blocking_issue", str(issue), "high", "阻断项必须在下一次 run 的 Evidence / Tool / Context Harness 中关闭后才能升级结论。", {"source": "evaluation-report"}))
    outcome = load_optional_yaml(run_path / "portfolio" / "outcome-tracking.yaml", {})
    for row in outcome.get("results", []):
        verdict = row.get("review_verdict")
        if verdict == "missed_opportunity_review":
            patterns.append(make_pattern(run_id, "review_archivist", "missed_opportunity", f"{row.get('subject')} return_pct={row.get('return_pct')}", "medium", "复盘为何只进入观察池，检查触发条件是否过严或证据更新是否滞后。", {"action_id": row.get("action_id")}))
        if verdict == "risk_control_review":
            patterns.append(make_pattern(run_id, "risk_manager", "risk_control_failure", f"{row.get('subject')} max_drawdown_pct={row.get('max_drawdown_pct')}", "high", "复盘止损、仓位、流动性和无效化条件是否足够明确。", {"action_id": row.get("action_id")}))
    patterns = dedupe_patterns(patterns)
    return {
        "version": FAILURE_VERSION,
        "artifact_type": "failure_pattern_report",
        "run_id": run_id,
        "pattern_count": len(patterns),
        "category_counts": count_by(patterns, "category"),
        "severity_counts": count_by(patterns, "severity"),
        "patterns": patterns,
        "controls": [
            "review_before_evolution",
            "failure_patterns_are_not_trade_signals",
            "no_real_trade_action",
            "do_not_delete_historical_errors",
        ],
        "disclaimer": DISCLAIMER,
    }


def infer_run_id(run_path: Path) -> str:
    run_doc = run_path / "run.yaml"
    if run_doc.exists():
        return (read_yaml(run_doc) or {}).get("run_id", run_path.name)
    return run_path.name


def patterns_from_list(run_id: str, agent_id: str, category: str, values: list[Any], severity: str, prevention: str) -> list[dict[str, Any]]:
    return [make_pattern(run_id, agent_id, category, str(value), severity, prevention, {"source": "reflection"}) for value in values if str(value).strip()]


def make_pattern(run_id: str, agent_id: str, category: str, description: str, severity: str, prevention: str, metadata: dict[str, Any]) -> dict[str, Any]:
    key = stable_hash(json.dumps({"run_id": run_id, "agent_id": agent_id, "category": category, "description": description}, ensure_ascii=False, sort_keys=True))
    return {
        "version": FAILURE_VERSION,
        "pattern_id": f"fp_{key}",
        "run_id": run_id,
        "agent_id": agent_id,
        "category": category,
        "description": description,
        "severity": severity,
        "prevention_check": prevention,
        "metadata": metadata,
        "tags": ["failure_pattern", category],
        "review_before_evolution": True,
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def dedupe_patterns(patterns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique = []
    for pattern in patterns:
        pid = pattern.get("pattern_id")
        if pid in seen:
            continue
        seen.add(pid)
        unique.append(pattern)
    return unique


def write_failure_patterns(run_path: Path, root: Path | None = None) -> dict[str, Any]:
    runtime_root = root or infer_runtime_root(run_path)
    report = extract_failure_patterns(run_path)
    write_yaml(run_path / "learning" / "failure-patterns.yaml", report)
    library_path = runtime_root / "memory" / "organization" / "failure-pattern-library.jsonl"
    existing = {row.get("pattern_id"): row for row in read_jsonl(library_path)}
    for pattern in report.get("patterns", []):
        existing[pattern["pattern_id"]] = pattern
    write_jsonl(library_path, list(existing.values()))
    return report


def load_failure_summary(root: Path) -> dict[str, Any]:
    path = root / "memory" / "organization" / "failure-pattern-library.jsonl"
    rows = read_jsonl(path)
    return {
        "version": FAILURE_VERSION,
        "artifact_type": "failure_pattern_summary",
        "library_path": str(path),
        "pattern_count": len(rows),
        "category_counts": count_by(rows, "category"),
        "severity_counts": count_by(rows, "severity"),
        "latest_pattern_id": rows[-1].get("pattern_id") if rows else None,
        "controls": ["review_before_evolution", "no_real_trade_action", "do_not_delete_historical_errors"],
    }


def load_run_failure_patterns(run_path: Path | None) -> dict[str, Any]:
    if not run_path:
        return default_report()
    path = run_path / "learning" / "failure-patterns.yaml"
    if not path.exists():
        return default_report()
    loaded = read_yaml(path) or {}
    report = default_report()
    report.update(loaded)
    return report


def default_report() -> dict[str, Any]:
    return {
        "version": FAILURE_VERSION,
        "artifact_type": "failure_pattern_report",
        "pattern_count": 0,
        "category_counts": {},
        "severity_counts": {},
        "patterns": [],
        "controls": [],
    }


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return counts
