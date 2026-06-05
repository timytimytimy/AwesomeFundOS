from __future__ import annotations

from pathlib import Path
from typing import Any

from fundos.io import REPO_ROOT, read_yaml, write_yaml

CASE_LIBRARY_VERSION = "0.2.0"
CASE_LIBRARY_MANIFEST = REPO_ROOT / "specs" / "cases" / "historical-case-library.yaml"


def load_case_library(manifest_path: Path | None = None) -> dict[str, Any]:
    manifest_file = manifest_path or CASE_LIBRARY_MANIFEST
    manifest = read_yaml(manifest_file) or {}
    base = manifest_file.parent
    cases = []
    for rel in manifest.get("case_files", []):
        path = base / rel
        case = read_yaml(path) or {}
        case["source_path"] = str(path.relative_to(REPO_ROOT)) if path.is_relative_to(REPO_ROOT) else str(path)
        cases.append(normalize_case(case))
    return {
        "version": manifest.get("version", CASE_LIBRARY_VERSION),
        "artifact_type": "historical_case_library",
        "purpose": manifest.get("purpose", "Historical case library for replay and evaluation."),
        "case_count": len(cases),
        "case_type_counts": count_by(cases, "case_type"),
        "market_counts": count_by(cases, "market"),
        "agent_case_counts": count_agent_cases(cases),
        "controls": manifest.get("controls", []),
        "minimum_case_types": manifest.get("minimum_case_types", []),
        "real_trade_allowed": False,
        "broker_integration": "disabled",
        "cases": cases,
    }


def normalize_case(case: dict[str, Any]) -> dict[str, Any]:
    forbidden = list(case.get("forbidden_uses", []))
    if "direct_buy_sell_signal" not in forbidden:
        forbidden.append("direct_buy_sell_signal")
    return {
        "case_id": case.get("case_id"),
        "case_type": case.get("case_type", "unknown"),
        "market": case.get("market", "unknown"),
        "time_range": case.get("time_range", "unknown"),
        "market_state": case.get("market_state", "unknown"),
        "summary": case.get("summary", ""),
        "tags": case.get("tags", []),
        "pattern_ids": case.get("pattern_ids", []),
        "applicable_agents": case.get("applicable_agents", []),
        "evidence_requirements": case.get("evidence_requirements", []),
        "known_lessons": case.get("known_lessons", []),
        "failure_modes": case.get("failure_modes", []),
        "replay_questions": case.get("replay_questions", []),
        "forbidden_uses": forbidden,
        "real_trade_allowed": False,
        "broker_integration": "disabled",
        "source_path": case.get("source_path", ""),
    }


def build_case_library_index(library: dict[str, Any] | None = None) -> dict[str, Any]:
    doc = library or load_case_library()
    cases = doc.get("cases", [])
    return {
        "version": doc.get("version", CASE_LIBRARY_VERSION),
        "artifact_type": "historical_case_library_index",
        "case_count": len(cases),
        "case_type_counts": count_by(cases, "case_type"),
        "market_counts": count_by(cases, "market"),
        "agent_case_counts": count_agent_cases(cases),
        "pattern_case_counts": count_pattern_cases(cases),
        "controls": doc.get("controls", []),
        "case_refs": [
            {
                "case_id": case.get("case_id"),
                "case_type": case.get("case_type"),
                "market": case.get("market"),
                "tags": case.get("tags", []),
                "applicable_agents": case.get("applicable_agents", []),
                "pattern_ids": case.get("pattern_ids", []),
                "source_path": case.get("source_path", ""),
            }
            for case in cases
        ],
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def write_run_case_library(run_path: Path) -> dict[str, Any]:
    index = build_case_library_index()
    write_yaml(run_path / "learning" / "case-library-index.yaml", index)
    return index


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key, "unknown"))
        counts[value] = counts.get(value, 0) + 1
    return counts


def count_agent_cases(cases: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in cases:
        for agent in case.get("applicable_agents", []):
            counts[agent] = counts.get(agent, 0) + 1
    return counts


def count_pattern_cases(cases: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for case in cases:
        for pattern in case.get("pattern_ids", []):
            counts[pattern] = counts.get(pattern, 0) + 1
    return counts
