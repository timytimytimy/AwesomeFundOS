from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fundos.io import DISCLAIMER, REPO_ROOT, read_yaml, write_yaml
from fundos.system_audit import cross_reference_mismatches_for_agent


ASSET_PATHS = {
    "agent_card": "specs/agents/agent-cards/{agent_id}/agent.md",
    "skill": "specs/skills/{agent_id}/SKILL.md",
    "context_policy": "specs/agents/context-policies/{agent_id}.yaml",
    "tool_policy": "specs/agents/tool-policies/{agent_id}.yaml",
    "memory_policy": "specs/agents/memory-policies/{agent_id}.yaml",
}

HARNESS_ARTIFACTS = [
    "harness/agent-harness.yaml",
    "harness/tool-harness.yaml",
    "harness/agent-tool-use.yaml",
    "harness/skill-benchmark.yaml",
    "harness/market-state.yaml",
    "harness/historical-case-replay.yaml",
    "harness/claim-graph.yaml",
    "harness/capability-regression.yaml",
    "harness/agent-performance.yaml",
    "harness/agent-governance.yaml",
]

EVOLUTION_ARTIFACTS = [
    "evolution/candidates.jsonl",
    "evolution/evolution-gate-results.jsonl",
    "evolution/accepted.jsonl",
    "evolution/quarantine.jsonl",
    "evolution/rejected.jsonl",
    "evolution/memory-writeback-summary.yaml",
    "evolution/capability-candidates.jsonl",
    "evolution/capability-version-summary.yaml",
    "learning/agent-learning-candidates.jsonl",
    "learning/failure-patterns.yaml",
]

MEMORY_THREAD_ARTIFACTS = [
    "memory/agent-thread-manifest.yaml",
]


def write_operating_system_manifest(run_path: Path, repo_root: Path | None = None) -> dict[str, Any]:
    repo_root = repo_root or REPO_ROOT
    run_doc = read_yaml(run_path / "run.yaml")
    selected = run_doc.get("selected_agents", []) or []
    roster_agents = selected_agents_with_roster_details(repo_root, selected)
    model_records = run_doc.get("model_records", []) or []
    agent_assets = [agent_asset_row(repo_root, row) for row in roster_agents]
    loaded_counts = {
        key: sum(1 for row in agent_assets if row.get("assets", {}).get(key, {}).get("exists"))
        for key in ASSET_PATHS
    }
    expected_count = len(selected)
    missing_assets = [
        {"agent_id": row["agent_id"], "asset_kind": kind, "path": asset["path"]}
        for row in agent_assets
        for kind, asset in row["assets"].items()
        if not asset["exists"]
    ]
    contract_summary = agent_os_contract_summary(agent_assets)
    manifest = {
        "version": "0.1.0",
        "artifact_type": "operating_system_manifest",
        "run_id": run_doc.get("run_id"),
        "input": run_doc.get("input", {}),
        "market": run_doc.get("market"),
        "runtime_mode": common_value(model_records, "runtime_mode", "local_file_protocol"),
        "selected_agent_count": expected_count,
        "model_record_count": len(model_records),
        "loaded_asset_counts": loaded_counts,
        "all_selected_agents_have_runtime_assets": not missing_assets and all(count == expected_count for count in loaded_counts.values()),
        "missing_agent_assets": missing_assets,
        "all_agent_os_contracts_valid": contract_summary["invalid_contracts"] == 0,
        "agent_os_contract_summary": contract_summary,
        "agents": agent_assets,
        "model_records": model_records,
        "harness_artifacts": existing_relative_paths(run_path, HARNESS_ARTIFACTS),
        "memory_thread_artifacts": existing_relative_paths(run_path, MEMORY_THREAD_ARTIFACTS),
        "evolution_artifacts": existing_relative_paths(run_path, EVOLUTION_ARTIFACTS),
        "evolution_summary": evolution_summary(run_path),
        "safety_invariants": {
            "research_watchlist_paper_only": True,
            "paper_portfolio_only": True,
            "no_personalized_investment_advice": True,
            "no_real_trade": True,
            "broker_integration_disabled": True,
            "kol_is_hypothesis_only": True,
            "durable_learning_requires_harness_and_evolution_gate": True,
        },
        "real_trade_allowed": False,
        "broker_integration": "disabled",
        "controls": [
            "profile_skill_tool_memory_thread_harness_evolution_boundaries",
            "agent_os_asset_cross_reference_contract",
            "context_pack_scoped_agent_execution",
            "strict_runtime_policy_records",
            "human_approval_required_for_capability_apply",
            "no_broker_or_order_placement",
        ],
        "disclaimer": DISCLAIMER,
    }
    write_yaml(run_path / "system" / "operating-system-manifest.yaml", manifest)
    write_operating_system_manifest_markdown(run_path, manifest)
    return manifest


def write_operating_system_manifest_markdown(run_path: Path, manifest: dict[str, Any]) -> Path:
    path = run_path / "system" / "operating-system-manifest.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_operating_system_manifest_markdown(manifest), encoding="utf-8")
    return path


def render_operating_system_manifest_markdown(manifest: dict[str, Any]) -> str:
    loaded = manifest.get("loaded_asset_counts", {}) or {}
    evolution = manifest.get("evolution_summary", {}) or {}
    safety = manifest.get("safety_invariants", {}) or {}
    lines = [
        "# Operating System Manifest",
        "",
        f"run_id: {manifest.get('run_id')}",
        f"runtime_mode: {manifest.get('runtime_mode')}",
        f"selected_agent_count: {manifest.get('selected_agent_count')}",
        f"model_record_count: {manifest.get('model_record_count')}",
        f"all_selected_agents_have_runtime_assets: {manifest.get('all_selected_agents_have_runtime_assets')}",
        "",
        "## Agent Runtime Assets",
        "",
    ]
    for key in ["agent_card", "skill", "context_policy", "tool_policy", "memory_policy"]:
        lines.append(f"- {key}: {loaded.get(key, 0)}")
    lines.extend(["", "### Selected Agents", ""])
    for row in manifest.get("agents", []) or []:
        lines.append(f"- {row.get('agent_id')}: {row.get('agent_card_path')} | {row.get('skill_path')}")
    contract_summary = manifest.get("agent_os_contract_summary", {}) or {}
    lines.extend([
        "",
        "## Agent OS Contract Checks",
        "",
        f"- all_agent_os_contracts_valid: {manifest.get('all_agent_os_contracts_valid')}",
        f"- valid_contracts: {contract_summary.get('valid_contracts', 0)}",
        f"- invalid_contracts: {contract_summary.get('invalid_contracts', 0)}",
        f"- checked_agents: {contract_summary.get('checked_agents', 0)}",
        "",
    ])
    for row in manifest.get("agents", []) or []:
        checks = row.get("os_contract_checks", {}) or {}
        lines.append(f"- {row.get('agent_id')}: valid={checks.get('valid')} mismatches={len(checks.get('mismatches', []) or [])}")
    lines.extend([
        "",
        "## Harness, Memory, Evolution",
        "",
        f"- harness_artifacts: {len(manifest.get('harness_artifacts', []) or [])}",
        f"- memory_thread_artifacts: {len(manifest.get('memory_thread_artifacts', []) or [])}",
        f"- evolution_artifacts: {len(manifest.get('evolution_artifacts', []) or [])}",
        f"- evolution_gate_results: {evolution.get('gate_results', 0)}",
        f"- memory_writes: {evolution.get('memory_writes', 0)}",
        f"- pending_human_apply: {evolution.get('pending_human_apply', 0)}",
        "",
        "## Safety Boundaries",
        "",
        f"- research_watchlist_paper_only: {safety.get('research_watchlist_paper_only')}",
        f"- paper_portfolio_only: {safety.get('paper_portfolio_only')}",
        f"- kol_is_hypothesis_only: {safety.get('kol_is_hypothesis_only')}",
        f"- durable_learning_requires_harness_and_evolution_gate: {safety.get('durable_learning_requires_harness_and_evolution_gate')}",
        f"- real_trade_allowed: {manifest.get('real_trade_allowed')}",
        f"- broker_integration: {manifest.get('broker_integration')}",
        "",
        manifest.get("disclaimer", DISCLAIMER),
        "",
    ])
    return "\n".join(lines)


def agent_asset_row(repo_root: Path, agent: dict[str, Any]) -> dict[str, Any]:
    agent_id = agent.get("id", "") or agent.get("agent_id", "")
    assets: dict[str, dict[str, Any]] = {}
    for kind, template in ASSET_PATHS.items():
        rel = template.format(agent_id=agent_id)
        assets[kind] = {"path": rel, "exists": (repo_root / rel).exists()}
    os_contract_checks = agent_os_contract_checks(repo_root, agent, assets)
    return {
        "agent_id": agent_id,
        "assets": assets,
        "agent_card_path": assets["agent_card"]["path"],
        "skill_path": assets["skill"]["path"],
        "context_policy_path": assets["context_policy"]["path"],
        "tool_policy_path": assets["tool_policy"]["path"],
        "memory_policy_path": assets["memory_policy"]["path"],
        "os_contract_checks": os_contract_checks,
    }


def selected_agents_with_roster_details(repo_root: Path, selected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    roster = read_yaml(repo_root / "specs/agents/default-roster.yaml") or {}
    by_id = {row.get("id"): row for row in roster.get("agents", []) or []}
    rows = []
    for item in selected:
        agent_id = item.get("agent_id", "")
        merged = dict(by_id.get(agent_id, {}))
        if not merged:
            merged = {"id": agent_id, "role": item.get("role", ""), "skills": [], "tools": []}
        rows.append(merged)
    return rows


def agent_os_contract_checks(repo_root: Path, agent: dict[str, Any], assets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    mismatches = cross_reference_mismatches_for_agent(repo_root, agent)
    asset_paths_exist = all(asset.get("exists") for asset in assets.values())
    issues = set(mismatches)
    return {
        "valid": asset_paths_exist and not mismatches,
        "asset_paths_exist": asset_paths_exist,
        "agent_card_matches_roster": not any(issue in issues or issue.startswith("agent_card_") for issue in issues),
        "skill_references_agent_card": "skill_agent_card_reference_mismatch" not in issues,
        "tool_policy_matches_roster_tools": "tool_policy_allowed_tools_mismatch" not in issues and "tool_policy_required_tools_outside_roster" not in issues,
        "memory_policy_matches_agent_namespace": "memory_policy_missing_agent_read_namespace" not in issues and "memory_policy_write_namespace_mismatch" not in issues,
        "context_policy_preserves_kol_methodology_boundary": "context_policy_kol_methodology_boundary_missing" not in issues,
        "safety_boundaries_disabled": not any(issue.endswith("_policy_real_trade_not_disabled") or issue.endswith("_policy_broker_not_disabled") for issue in issues),
        "mismatches": mismatches,
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def agent_os_contract_summary(agent_assets: list[dict[str, Any]]) -> dict[str, Any]:
    valid = sum(1 for row in agent_assets if row.get("os_contract_checks", {}).get("valid"))
    invalid = len(agent_assets) - valid
    return {
        "checked_agents": len(agent_assets),
        "valid_contracts": valid,
        "invalid_contracts": invalid,
        "mismatched_agents": [row.get("agent_id") for row in agent_assets if not row.get("os_contract_checks", {}).get("valid")],
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def existing_relative_paths(run_path: Path, rels: list[str]) -> list[str]:
    return [rel for rel in rels if (run_path / rel).exists()]


def evolution_summary(run_path: Path) -> dict[str, Any]:
    memory_writeback = read_optional_yaml(run_path / "evolution" / "memory-writeback-summary.yaml", {})
    capability_summary = read_optional_yaml(run_path / "evolution" / "capability-version-summary.yaml", {})
    gate_rows = read_jsonl(run_path / "evolution" / "evolution-gate-results.jsonl")
    return {
        "gate_results": len(gate_rows),
        "accepted": sum(1 for row in gate_rows if row.get("decision") == "accept"),
        "quarantined": sum(1 for row in gate_rows if row.get("decision") == "quarantine"),
        "rejected": sum(1 for row in gate_rows if row.get("decision") == "reject"),
        "memory_writes": int(memory_writeback.get("memory_writes", 0) or 0) if isinstance(memory_writeback, dict) else 0,
        "approved_candidates": int(capability_summary.get("approved_candidates", 0) or 0) if isinstance(capability_summary, dict) else 0,
        "pending_human_apply": int(capability_summary.get("pending_human_apply", 0) or 0) if isinstance(capability_summary, dict) else 0,
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def read_optional_yaml(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    value = read_yaml(path)
    return value if isinstance(value, dict) else default


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


def common_value(records: list[dict[str, Any]], key: str, default: Any) -> Any:
    values = {record.get(key) for record in records if isinstance(record, dict) and key in record}
    if len(values) == 1:
        return next(iter(values))
    return default
