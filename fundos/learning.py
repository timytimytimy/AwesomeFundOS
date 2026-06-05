from __future__ import annotations

from pathlib import Path
from typing import Any

from fundos.io import REPO_ROOT, write_yaml

PATTERN_DIR = REPO_ROOT / "specs" / "learning" / "patterns"


def load_learning_patterns(pattern_dir: Path | None = None) -> list[dict[str, Any]]:
    import yaml

    root = pattern_dir or PATTERN_DIR
    patterns = []
    for path in sorted(root.glob("*.yaml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        doc["pattern_path"] = str(path.relative_to(REPO_ROOT))
        patterns.append(doc)
    return patterns


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
