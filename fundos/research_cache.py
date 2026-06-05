from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fundos.io import read_yaml, write_yaml

RESEARCH_CACHE_VERSION = "0.1.0"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def cache_key(query: str, adapter_name: str, limit: int) -> str:
    return stable_hash(json.dumps({"query": query, "adapter_name": adapter_name, "limit": limit}, ensure_ascii=False, sort_keys=True))


def source_hash(result: dict[str, Any]) -> str:
    payload = json.dumps({"title": result.get("title"), "url": result.get("url"), "snippet": result.get("snippet")}, ensure_ascii=False, sort_keys=True)
    return stable_hash(payload)


def add_retrieval_metadata(results: list[dict[str, Any]], query: str, adapter_name: str, cache_status: str) -> list[dict[str, Any]]:
    rows = []
    for index, row in enumerate(results, start=1):
        h = source_hash(row)
        rows.append(
            {
                **row,
                "retrieval_id": row.get("retrieval_id") or f"pr_{stable_hash(query + adapter_name + h)[:10]}_{index:03d}",
                "source_hash": row.get("source_hash") or h,
                "adapter_name": row.get("adapter_name") or adapter_name,
                "cache_status": cache_status,
            }
        )
    return rows


def read_cached_results(cache_root: Path | None, query: str, adapter_name: str, limit: int) -> list[dict[str, Any]] | None:
    if not cache_root:
        return None
    path = cache_path(cache_root, query, adapter_name, limit)
    if not path.exists():
        return None
    doc = json.loads(path.read_text(encoding="utf-8"))
    return add_retrieval_metadata(doc.get("results", []), query, adapter_name, "hit")


def write_cached_results(cache_root: Path | None, query: str, adapter_name: str, limit: int, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = add_retrieval_metadata(results, query, adapter_name, "stored")
    if cache_root:
        path = cache_path(cache_root, query, adapter_name, limit)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "version": RESEARCH_CACHE_VERSION,
                    "artifact_type": "public_research_cache_entry",
                    "query": query,
                    "adapter_name": adapter_name,
                    "limit": limit,
                    "cache_status": "stored",
                    "created_at": now_iso(),
                    "results": rows,
                    "boundary_controls": default_boundary_controls(),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    return add_retrieval_metadata(results, query, adapter_name, "hit" if cache_root else "uncached")


def cache_path(cache_root: Path, query: str, adapter_name: str, limit: int) -> Path:
    return cache_root / f"{cache_key(query, adapter_name, limit)}.json"


def write_run_research_manifest(run_path: Path, query: str, results: list[dict[str, Any]], adapter_name: str, cache_root: Path | None = None, research_plan: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    manifest = build_research_manifest(query, results, adapter_name, cache_root, research_plan=research_plan)
    write_yaml(run_path / "evidence" / "public-research-manifest.yaml", manifest)
    return manifest


def build_research_manifest(query: str, results: list[dict[str, Any]], adapter_name: str, cache_root: Path | None = None, research_plan: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    plan_categories = {row.get("category") for row in research_plan or [] if row.get("category")}
    covered_categories = {row.get("research_category") for row in results if row.get("research_category")}
    return {
        "version": RESEARCH_CACHE_VERSION,
        "artifact_type": "public_research_manifest",
        "query": query,
        "adapter_name": adapter_name,
        "cache_root": str(cache_root) if cache_root else "disabled",
        "result_count": len(results),
        "cache_status_counts": count_by(results, "cache_status"),
        "source_tier_counts": count_by(results, "source_tier"),
        "source_type_counts": count_by(results, "source_type"),
        "research_plan_coverage": {
            "planned_categories": len(plan_categories),
            "categories_covered": len(covered_categories),
            "missing_categories": sorted(plan_categories - covered_categories),
            "category_counts": count_by([row for row in results if row.get("research_category")], "research_category"),
            "plan_step_count": len(research_plan or []) or len({row.get("research_plan_id") for row in results if row.get("research_plan_id")}),
        },
        "research_plan": research_plan or [],
        "results": [
            {
                "retrieval_id": row.get("retrieval_id"),
                "title": row.get("title"),
                "url": row.get("url"),
                "source_type": row.get("source_type"),
                "source_tier": row.get("source_tier"),
                "source_hash": row.get("source_hash"),
                "cache_status": row.get("cache_status", "uncached"),
                "research_plan_id": row.get("research_plan_id"),
                "research_category": row.get("research_category"),
                "research_query": row.get("research_query"),
            }
            for row in results
        ],
        "boundary_controls": default_boundary_controls(),
    }


def load_research_manifest(run_path: Path | None) -> dict[str, Any]:
    if not run_path:
        return default_manifest()
    path = run_path / "evidence" / "public-research-manifest.yaml"
    if not path.exists():
        return default_manifest()
    loaded = read_yaml(path) or {}
    default = default_manifest()
    default.update(loaded)
    return default


def default_manifest() -> dict[str, Any]:
    return {
        "version": RESEARCH_CACHE_VERSION,
        "artifact_type": "public_research_manifest",
        "query": "",
        "adapter_name": "unknown",
        "cache_root": "disabled",
        "result_count": 0,
        "cache_status_counts": {},
        "source_tier_counts": {},
        "source_type_counts": {},
        "research_plan_coverage": {"categories_covered": 0, "category_counts": {}, "plan_step_count": 0},
        "results": [],
        "boundary_controls": default_boundary_controls(),
    }


def default_boundary_controls() -> list[str]:
    return [
        "primary_source_required_for_high_confidence",
        "kol_is_hypothesis_not_trade_signal",
        "book_and_case_are_methodology_only",
        "social_signal_never_direct_buy",
        "cache_is_audit_trail_not_truth_source",
    ]


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return counts
