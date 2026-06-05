from __future__ import annotations

from pathlib import Path
from typing import Any

from fundos.io import REPO_ROOT, read_yaml, write_yaml

PATTERN_DIR = REPO_ROOT / "specs" / "learning" / "patterns"
SEED_LIBRARY_PATH = REPO_ROOT / "specs" / "learning" / "seed-library.yaml"
LEARNING_SOURCE_REGISTRY_VERSION = "0.1.0"
DEFAULT_REQUIRED_GATES = ["historical_case_replay", "evidence_quality_check", "role_drift_check"]
NON_ADOPTION_GATES = {"source_trace"}
METHODOLOGY_TIERS = {"tier_3_verified_public_practitioner", "tier_4_expert_opinion"}


def load_learning_patterns(pattern_dir: Path | None = None) -> list[dict[str, Any]]:
    import yaml

    root = pattern_dir or PATTERN_DIR
    patterns = []
    for path in sorted(root.glob("*.yaml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        doc["pattern_path"] = str(path.relative_to(REPO_ROOT))
        patterns.append(doc)
    return patterns


def load_seed_library() -> dict[str, Any]:
    return read_yaml(SEED_LIBRARY_PATH)


def build_learning_source_registry(seed_library: dict[str, Any] | None = None) -> dict[str, Any]:
    seed = seed_library or load_seed_library()
    sources = [normalize_learning_source(source) for source in seed.get("sources", [])]
    return {
        "version": LEARNING_SOURCE_REGISTRY_VERSION,
        "artifact_type": "learning_source_registry",
        "purpose": "Govern external trader, KOL, book, course, and case learning sources before they can become agent memory or capability upgrades.",
        "source_count": len(sources),
        "source_tier_counts": count_by(sources, "source_tier"),
        "source_type_counts": count_by(sources, "source_type"),
        "required_default_gates": DEFAULT_REQUIRED_GATES,
        "boundary_policy": {
            "real_trade_allowed": False,
            "broker_integration": "disabled",
            "primary_evidence_required_for_company_conclusions": True,
            "methodology_sources_are_hypothesis_generators": True,
            "copyright_boundary": seed.get("source_policy", {}).get("copyright_boundary", "metadata_and_distilled_patterns_only"),
            "investment_boundary": seed.get("source_policy", {}).get("investment_boundary", "learning_only_not_investment_advice"),
            "controls": [
                "no_direct_trade_signal",
                "no_unverified_company_fact",
                "no_copied_paid_course_or_book_text",
                "primary_evidence_check_before_adoption",
                "historical_case_replay_before_memory_write",
            ],
        },
        "sources": sources,
        "case_types": seed.get("case_types", []),
    }


def normalize_learning_source(source: dict[str, Any]) -> dict[str, Any]:
    validation_required = source.get("validation_required", [])
    required_gates = [gate for gate in validation_required if gate not in NON_ADOPTION_GATES]
    tier = source.get("source_tier", "tier_6_unverified")
    requires_primary = tier in METHODOLOGY_TIERS or source.get("source_type") == "public_practitioner"
    if requires_primary and "primary_evidence_check" not in required_gates:
        required_gates.append("primary_evidence_check")
    adoption_policy = "methodology_only_until_validated" if requires_primary else "canonical_framework_until_context_validated"
    return {
        "id": source.get("id"),
        "display_name": source.get("display_name"),
        "source_url": source.get("source_url", ""),
        "source_tier": tier,
        "source_type": source.get("source_type", "unknown"),
        "public_handles": source.get("public_handles", []),
        "primary_value": source.get("primary_value", []),
        "target_agents": source.get("target_agents", []),
        "allowed_learning_outputs": source.get("allowed_learning_outputs", []),
        "not_allowed_outputs": source.get("not_allowed_outputs", []),
        "validation_required": validation_required,
        "required_gates_for_evolution": required_gates,
        "requires_primary_validation": requires_primary,
        "adoption_policy": adoption_policy,
        "distilled_patterns": source.get("distilled_patterns", []),
    }


def write_run_learning_source_registry(run_path: Path) -> dict[str, Any]:
    registry = build_learning_source_registry()
    write_yaml(run_path / "learning" / "source-registry.yaml", registry)
    return registry


def source_registry_by_id(seed_library: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    registry = build_learning_source_registry(seed_library)
    return {source["id"]: source for source in registry.get("sources", []) if source.get("id")}


def patterns_for_agent(agent_id: str, focus_tags: list[str] | None = None, limit: int = 5) -> list[dict[str, Any]]:
    focus = set(focus_tags or [])
    selected = []
    for pattern in load_learning_patterns():
        targets = set(pattern.get("target_agents", []))
        tags = set(pattern.get("tags", []))
        if agent_id not in targets:
            continue
        if focus and not (focus & tags):
            continue
        selected.append(pattern)
    return selected[:limit]


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key, "unknown"))
        counts[value] = counts.get(value, 0) + 1
    return counts


def compact_pattern(pattern: dict[str, Any]) -> dict[str, Any]:
    return {
        "pattern_id": pattern["id"],
        "name": pattern.get("name"),
        "source_id": pattern.get("source_id"),
        "source_tier": pattern.get("source_tier"),
        "pattern_type": pattern.get("pattern_type"),
        "tags": pattern.get("tags", []),
        "summary": pattern.get("summary"),
        "checklist": pattern.get("checklist", [])[:5],
        "validation_gates": pattern.get("validation_gates", []),
        "not_allowed_outputs": pattern.get("not_allowed_outputs", []),
    }


def write_run_learning_patterns(run_path: Path, agent_ids: list[str]) -> list[dict[str, Any]]:
    by_id = {}
    for agent_id in agent_ids:
        for pattern in patterns_for_agent(agent_id):
            by_id[pattern["id"]] = pattern
    patterns = list(by_id.values())
    write_yaml(
        run_path / "learning" / "patterns.yaml",
        {
            "version": "0.1.0",
            "purpose": "Run-scoped distilled learning patterns available to selected agents.",
            "patterns": patterns,
        },
    )
    return patterns
