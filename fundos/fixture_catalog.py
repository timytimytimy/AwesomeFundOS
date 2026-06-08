from __future__ import annotations

from pathlib import Path
from typing import Any

from fundos.io import REPO_ROOT, read_yaml

FIXTURE_CATALOG_PATH = REPO_ROOT / "examples" / "fixtures" / "fixture-catalog.yaml"


def load_fixture_catalog(path: Path | None = None) -> dict[str, Any]:
    catalog_path = path or FIXTURE_CATALOG_PATH
    doc = read_yaml(catalog_path) or {}
    fixtures = doc.get("fixtures", {}) if isinstance(doc.get("fixtures"), dict) else {}
    normalized: dict[str, Any] = {}
    for fixture_id, row in fixtures.items():
        if not isinstance(row, dict):
            continue
        normalized[str(fixture_id)] = normalize_fixture_row(str(fixture_id), row)
    return {
        "version": doc.get("version", "0.1.0"),
        "artifact_type": "public_research_fixture_catalog",
        "catalog_path": str(catalog_path.relative_to(REPO_ROOT)) if catalog_path.is_relative_to(REPO_ROOT) else str(catalog_path),
        "fixture_count": len(normalized),
        "fixtures": normalized,
        "controls": doc.get("controls", []),
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def normalize_fixture_row(fixture_id: str, row: dict[str, Any]) -> dict[str, Any]:
    research_fixture = str(row.get("research_fixture") or "")
    market_replay_fixture = str(row.get("market_replay_fixture") or "")
    return {
        "fixture_id": fixture_id,
        "topic": str(row.get("topic") or ""),
        "research_fixture": research_fixture,
        "market_replay_fixture": market_replay_fixture,
        "primary_agents": list(row.get("primary_agents", []) or []),
        "market_regime": str(row.get("market_regime") or ""),
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def list_fixture_summaries(catalog: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    doc = catalog or load_fixture_catalog()
    fixtures = doc.get("fixtures", {}) if isinstance(doc.get("fixtures"), dict) else {}
    return [fixtures[key] for key in sorted(fixtures)]


def resolve_fixture(fixture_id: str, catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    doc = catalog or load_fixture_catalog()
    fixtures = doc.get("fixtures", {}) if isinstance(doc.get("fixtures"), dict) else {}
    if fixture_id not in fixtures:
        raise KeyError(f"fixture_not_found: {fixture_id}")
    row = dict(fixtures[fixture_id])
    for field in ["research_fixture", "market_replay_fixture"]:
        if row.get(field):
            path = Path(str(row[field]))
            if not path.is_absolute():
                path = REPO_ROOT / path
            row[field] = str(path)
    return row


def fixture_catalog_missing_paths(catalog: dict[str, Any] | None = None) -> list[dict[str, str]]:
    doc = catalog or load_fixture_catalog()
    missing: list[dict[str, str]] = []
    fixtures = doc.get("fixtures", {}) if isinstance(doc.get("fixtures"), dict) else {}
    for fixture_id, row in fixtures.items():
        for field in ["research_fixture", "market_replay_fixture"]:
            value = row.get(field)
            if not value:
                continue
            path = Path(str(value))
            if not path.is_absolute():
                path = REPO_ROOT / path
            if not path.exists():
                missing.append({"fixture_id": str(fixture_id), "field": field, "path": str(path)})
    return missing
