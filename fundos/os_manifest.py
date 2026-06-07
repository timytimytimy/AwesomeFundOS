from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fundos.capabilities import write_agent_capability_ledger
from fundos.io import DISCLAIMER, REPO_ROOT, read_yaml, write_yaml
from fundos.system_audit import cross_reference_mismatches_for_agent, expected_runtime_policy_contract_summary


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
    "evolution/agent-capability-ledger.yaml",
    "learning/agent-learning-candidates.jsonl",
    "learning/failure-patterns.yaml",
]

MEMORY_THREAD_ARTIFACTS = [
    "memory/agent-thread-manifest.yaml",
]


def write_operating_system_manifest(run_path: Path, repo_root: Path | None = None) -> dict[str, Any]:
    repo_root = repo_root or REPO_ROOT
    write_agent_capability_ledger(run_path)
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
        "agent_maturity_contract_summary": agent_maturity_contract_summary(run_path, selected),
        "runtime_policy_contract_summary": expected_runtime_policy_contract_summary(run_path, [row.get("agent_id", "") for row in selected]),
        "agents": agent_assets,
        "model_records": model_records,
        "harness_artifacts": existing_relative_paths(run_path, HARNESS_ARTIFACTS),
        "memory_thread_artifacts": existing_relative_paths(run_path, MEMORY_THREAD_ARTIFACTS),
        "evolution_artifacts": existing_relative_paths(run_path, EVOLUTION_ARTIFACTS),
        "evolution_summary": evolution_summary(run_path),
        "evolution_learning_summary": evolution_learning_summary(run_path),
        "agent_capability_ledger_summary": agent_capability_ledger_summary(run_path),
        "source_provenance_summary": source_provenance_summary(run_path),
        "context_management_summary": context_management_summary(run_path),
        "tool_runtime_summary": tool_runtime_summary(run_path),
        "portfolio_outcome_summary": portfolio_outcome_summary(run_path),
        "agent_performance_summary": agent_performance_summary(run_path),
        "agent_governance_summary": agent_governance_summary(run_path),
        "evaluation_summary": evaluation_summary(run_path),
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
    evolution_learning = manifest.get("evolution_learning_summary", {}) or {}
    capability_ledger = manifest.get("agent_capability_ledger_summary", {}) or {}
    performance = manifest.get("agent_performance_summary", {}) or {}
    governance = manifest.get("agent_governance_summary", {}) or {}
    evaluation = manifest.get("evaluation_summary", {}) or {}
    provenance = manifest.get("source_provenance_summary", {}) or {}
    context_management = manifest.get("context_management_summary", {}) or {}
    tool_runtime = manifest.get("tool_runtime_summary", {}) or {}
    portfolio_outcome = manifest.get("portfolio_outcome_summary", {}) or {}
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
    maturity_summary = manifest.get("agent_maturity_contract_summary", {}) or {}
    policy_summary = manifest.get("runtime_policy_contract_summary", {}) or {}
    lines.extend([
        "",
        "## Agent OS Contract Checks",
        "",
        f"- all_agent_os_contracts_valid: {manifest.get('all_agent_os_contracts_valid')}",
        f"- valid_contracts: {contract_summary.get('valid_contracts', 0)}",
        f"- invalid_contracts: {contract_summary.get('invalid_contracts', 0)}",
        f"- checked_agents: {contract_summary.get('checked_agents', 0)}",
        f"- agent_maturity_contracts: {maturity_summary.get('maturity_contracts_present', 0)}",
        f"- agent_maturity_unique_edges: {maturity_summary.get('unique_edge_signatures', 0)}",
        f"- agent_maturity_skill_benchmarks: {maturity_summary.get('skill_benchmarks_present', 0)}",
        f"- runtime_policy_contracts_loaded: {'runtime_policy_contracts_loaded' in (policy_summary.get('controls', []) or [])}",
        f"- runtime_policy_agent_contracts: {policy_summary.get('context_agent_policy_contracts_present', 0)}",
        f"- runtime_policy_skill_contracts: {policy_summary.get('context_skill_execution_policy_contracts_present', 0)}",
        f"- runtime_policy_output_contracts: {policy_summary.get('structured_output_policy_contracts_present', 0)}",
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
        f"- evolution_learning_candidates: {evolution_learning.get('agent_learning_candidates', 0)}",
        f"- evolution_candidates: {evolution_learning.get('evolution_candidates', 0)}",
        f"- evolution_quarantined: {evolution_learning.get('quarantined', 0)}",
        f"- evolution_capability_candidates: {evolution_learning.get('capability_candidates', 0)}",
        f"- evolution_regression_candidates_total: {evolution_learning.get('regression_candidates_total', 0)}",
        f"- evolution_pending_human_apply: {evolution_learning.get('pending_human_apply', 0)}",
        f"- agent_capability_ledger_candidates: {capability_ledger.get('candidate_count', 0)}",
        f"- agent_capability_ledger_agents: {capability_ledger.get('agent_count', 0)}",
        f"- agent_capability_pending_human_apply: {capability_ledger.get('pending_human_apply', 0)}",
        f"- registry_source_count: {provenance.get('registry_source_count', 0)}",
        f"- ingested_sources: {provenance.get('ingested_sources', 0)}",
        f"- quarantined_sources: {provenance.get('quarantined_sources', 0)}",
        f"- evidence_item_count: {provenance.get('evidence_item_count', 0)}",
        f"- methodology_sources_are_hypothesis_only: {provenance.get('methodology_sources_are_hypothesis_only')}",
        f"- context_management_score: {context_management.get('overall', 0)}",
        f"- context_agents_evaluated: {context_management.get('agents_evaluated', 0)}",
        f"- context_token_budget_respected: {context_management.get('token_budget_respected', 0)}",
        f"- context_loss_accounting_present: {context_management.get('loss_accounting_present', 0)}",
        f"- tool_runtime_calls: {tool_runtime.get('tool_call_count', 0)}",
        f"- tool_runtime_succeeded_calls: {tool_runtime.get('succeeded_tool_calls', 0)}",
        f"- tool_runtime_blocked_calls: {tool_runtime.get('blocked_tool_calls', 0)}",
        f"- tool_runtime_evidence_items: {tool_runtime.get('evidence_items_created', 0)}",
        f"- portfolio_watchlist_items: {portfolio_outcome.get('watchlist_items', 0)}",
        f"- portfolio_paper_actions: {portfolio_outcome.get('paper_actions', 0)}",
        f"- portfolio_reviewed_actions: {portfolio_outcome.get('reviewed_actions', 0)}",
        f"- outcome_status: {portfolio_outcome.get('outcome_status', 'missing_market_replay')}",
        f"- agent_performance_score: {performance.get('average_final_score', 0)}",
        f"- agent_governance_score: {governance.get('governance_quality_score', 0)}",
        f"- evaluation_overall_score: {evaluation.get('overall_score', 0)}",
        f"- evaluation_blocking_issues: {evaluation.get('blocking_issue_count', 0)}",
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


def agent_maturity_contract_summary(run_path: Path, selected_agents: list[dict[str, Any]]) -> dict[str, Any]:
    agent_ids = [row.get("agent_id", "") for row in selected_agents if row.get("agent_id")]
    missing_by_agent: dict[str, list[str]] = {}
    edge_signatures: list[str] = []
    maturity_contracts_present = 0
    capability_benchmarks_present = 0
    skill_benchmarks_present = 0
    context_compression_contracts_present = 0
    evolution_candidate_rules_present = 0
    minimum_scores: list[int] = []
    for agent_id in agent_ids:
        issues: list[str] = []
        context = read_optional_yaml(run_path / "context" / f"{agent_id}.context-pack.yaml", {})
        output = read_optional_yaml(run_path / "agent_work" / f"{agent_id}.structured.yaml", {})
        card_contract = (((context.get("agent_card") or {}).get("maturity_contract") or {}) if isinstance(context, dict) else {})
        skill_contract = ((context.get("skill_contract") or {}) if isinstance(context, dict) else {})
        output_contract = ((output.get("maturity_contract") or {}) if isinstance(output, dict) else {})
        edge = card_contract.get("differentiated_edge", {}) or {}
        capability = card_contract.get("capability_benchmarks", {}) or {}
        card_compression = card_contract.get("context_compression", {}) or {}
        skill_benchmark = skill_contract.get("role_specific_benchmark", {}) or {}
        skill_compression = skill_contract.get("context_compression_recipe", {}) or {}
        evolution_rules = skill_contract.get("evolution_candidate_rules", {}) or {}
        if edge.get("edge_signature") and output_contract.get("edge_signature"):
            maturity_contracts_present += 1
            edge_signatures.append(str(output_contract.get("edge_signature")))
        else:
            issues.append("maturity_contract_edge_signature_missing")
        if capability.get("benchmark_id") and output_contract.get("capability_benchmark_id"):
            capability_benchmarks_present += 1
        else:
            issues.append("capability_benchmark_missing")
        if skill_benchmark.get("benchmark_id") and output_contract.get("skill_benchmark_id"):
            skill_benchmarks_present += 1
        else:
            issues.append("skill_benchmark_missing")
        if (card_compression.get("context_priority_order") or skill_compression.get("context_priority_order")) and output_contract.get("context_priority_order") and output_contract.get("must_preserve_context"):
            context_compression_contracts_present += 1
        else:
            issues.append("context_compression_contract_missing")
        if evolution_rules.get("approval_route") and output_contract.get("evolution_approval_route"):
            evolution_candidate_rules_present += 1
        else:
            issues.append("evolution_candidate_rules_missing")
        score = parse_int(output_contract.get("minimum_pass_score") or capability.get("minimum_pass_score") or skill_benchmark.get("minimum_pass_score"))
        if score is not None:
            minimum_scores.append(score)
        else:
            issues.append("minimum_pass_score_missing")
        if output_contract.get("real_trade_allowed") is not False:
            issues.append("real_trade_not_disabled")
        if output_contract.get("broker_integration") != "disabled":
            issues.append("broker_integration_not_disabled")
        if issues:
            missing_by_agent[agent_id] = issues
    return {
        "agents_evaluated": len(agent_ids),
        "maturity_contracts_present": maturity_contracts_present,
        "edge_signature_count": len(edge_signatures),
        "unique_edge_signatures": len(set(edge_signatures)),
        "required_unique_edge_signatures": max(len(agent_ids) - 1, 0),
        "capability_benchmarks_present": capability_benchmarks_present,
        "skill_benchmarks_present": skill_benchmarks_present,
        "context_compression_contracts_present": context_compression_contracts_present,
        "evolution_candidate_rules_present": evolution_candidate_rules_present,
        "minimum_pass_score_floor": min(minimum_scores) if minimum_scores else 0,
        "missing_by_agent": missing_by_agent,
        "controls": [
            "differentiated_agent_edge_required",
            "role_specific_benchmark_required",
            "role_specific_context_compression_required",
            "evolution_candidate_rules_required",
            "no_real_trade_action",
            "broker_integration_disabled",
        ],
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def parse_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


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


def evolution_learning_summary(run_path: Path) -> dict[str, Any]:
    agent_learning = read_optional_yaml(run_path / "learning" / "agent-learning-report.yaml", {})
    source_ingestion = read_optional_yaml(run_path / "learning" / "source-ingestion-report.yaml", {})
    memory_writeback = read_optional_yaml(run_path / "evolution" / "memory-writeback-summary.yaml", {})
    capability_summary = read_optional_yaml(run_path / "evolution" / "capability-version-summary.yaml", {})
    capability_regression = read_optional_yaml(run_path / "harness" / "capability-regression.yaml", {})
    agent_learning_rows = read_jsonl(run_path / "learning" / "agent-learning-candidates.jsonl")
    evolution_rows = read_jsonl(run_path / "evolution" / "candidates.jsonl")
    gate_rows = read_jsonl(run_path / "evolution" / "evolution-gate-results.jsonl")
    accepted_rows = read_jsonl(run_path / "evolution" / "accepted.jsonl")
    quarantine_rows = read_jsonl(run_path / "evolution" / "quarantine.jsonl")
    rejected_rows = read_jsonl(run_path / "evolution" / "rejected.jsonl")
    capability_rows = read_jsonl(run_path / "evolution" / "capability-candidates.jsonl")
    controls = sorted({
        "quarantine_before_adoption",
        "evolution_gate_required",
        "capability_regression_required",
        "human_approval_before_apply",
        "no_direct_profile_mutation",
        "no_direct_skill_mutation",
        "no_direct_tool_mutation",
        "no_real_trade_action",
        "broker_integration_disabled",
    } | set(str(item) for source in [agent_learning, capability_regression] if isinstance(source, dict) for item in source.get("controls", []) if item))
    return {
        "agent_learning_candidates": int(agent_learning.get("candidate_count", len(agent_learning_rows)) or 0) if isinstance(agent_learning, dict) else len(agent_learning_rows),
        "new_agent_learning_candidates": int(agent_learning.get("new_candidates", 0) or 0) if isinstance(agent_learning, dict) else 0,
        "merged_to_evolution": int(agent_learning.get("merged_to_evolution", 0) or 0) if isinstance(agent_learning, dict) else 0,
        "agent_learning_route_counts": agent_learning.get("route_counts", {}) if isinstance(agent_learning, dict) and isinstance(agent_learning.get("route_counts", {}), dict) else {},
        "source_ingestion_candidates": int(source_ingestion.get("evolution_candidates", 0) or 0) if isinstance(source_ingestion, dict) else 0,
        "source_quarantined": int(source_ingestion.get("quarantined_sources", 0) or 0) if isinstance(source_ingestion, dict) else 0,
        "evolution_candidates": len(evolution_rows),
        "gate_results": len(gate_rows),
        "accepted": len(accepted_rows) if accepted_rows else sum(1 for row in gate_rows if row.get("decision") == "accept"),
        "quarantined": len(quarantine_rows) if quarantine_rows else sum(1 for row in gate_rows if row.get("decision") == "quarantine"),
        "rejected": len(rejected_rows) if rejected_rows else sum(1 for row in gate_rows if row.get("decision") == "reject"),
        "memory_writes": int(memory_writeback.get("memory_writes", 0) or 0) if isinstance(memory_writeback, dict) else 0,
        "memory_agent_writes": memory_writeback.get("agent_writes", {}) if isinstance(memory_writeback, dict) and isinstance(memory_writeback.get("agent_writes", {}), dict) else {},
        "capability_candidates": len(capability_rows),
        "approved_candidates": int(capability_summary.get("approved_candidates", 0) or 0) if isinstance(capability_summary, dict) else 0,
        "pending_human_apply": int(capability_summary.get("pending_human_apply", 0) or 0) if isinstance(capability_summary, dict) else 0,
        "regression_status": str(capability_regression.get("regression_status", "missing")) if isinstance(capability_regression, dict) else "missing",
        "regression_candidates_total": int(capability_regression.get("candidates_total", 0) or 0) if isinstance(capability_regression, dict) else 0,
        "regression_passed_candidates": int(capability_regression.get("passed_candidates", 0) or 0) if isinstance(capability_regression, dict) else 0,
        "regression_blocked_candidates": int(capability_regression.get("blocked_candidates", 0) or 0) if isinstance(capability_regression, dict) else 0,
        "direct_profile_mutation_allowed": False,
        "direct_skill_mutation_allowed": False,
        "direct_tool_mutation_allowed": False,
        "controls": controls,
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def agent_capability_ledger_summary(run_path: Path) -> dict[str, Any]:
    ledger = read_optional_yaml(run_path / "evolution" / "agent-capability-ledger.yaml", {})
    agents = ledger.get("agents", {}) if isinstance(ledger.get("agents", {}), dict) else {}
    controls = ledger.get("controls", []) if isinstance(ledger.get("controls", []), list) else default_agent_capability_ledger_controls()
    return {
        "candidate_count": int(ledger.get("candidate_count", 0) or 0) if isinstance(ledger, dict) else 0,
        "agent_count": int(ledger.get("agent_count", 0) or 0) if isinstance(ledger, dict) else 0,
        "pending_human_apply": int(ledger.get("pending_human_apply", 0) or 0) if isinstance(ledger, dict) else 0,
        "applied": int(ledger.get("applied", 0) or 0) if isinstance(ledger, dict) else 0,
        "blocked_regression": int(ledger.get("blocked_regression", 0) or 0) if isinstance(ledger, dict) else 0,
        "needs_more_evidence": int(ledger.get("needs_more_evidence", 0) or 0) if isinstance(ledger, dict) else 0,
        "not_applicable": int(ledger.get("not_applicable", 0) or 0) if isinstance(ledger, dict) else 0,
        "agents": sorted(str(agent_id) for agent_id in agents),
        "controls": controls,
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def default_agent_capability_ledger_controls() -> list[str]:
    return [
        "capability_lifecycle_per_agent_required",
        "evolution_gate_before_capability_registry",
        "capability_regression_before_apply",
        "human_approval_before_apply",
        "no_direct_profile_mutation",
        "no_real_trade_action",
        "broker_integration_disabled",
    ]


def source_provenance_summary(run_path: Path) -> dict[str, Any]:
    registry = read_optional_yaml(run_path / "learning" / "source-registry.yaml", {})
    ingestion = read_optional_yaml(run_path / "learning" / "source-ingestion-report.yaml", {})
    evidence = read_optional_yaml(run_path / "evidence" / "evidence-pack.yaml", {})
    source_coverage = evidence.get("source_coverage", {}) if isinstance(evidence, dict) else {}
    boundary_policy = registry.get("boundary_policy", {}) if isinstance(registry, dict) else {}
    return {
        "registry_source_count": int(registry.get("source_count", 0) or 0) if isinstance(registry, dict) else 0,
        "registry_source_tier_counts": registry.get("source_tier_counts", {}) if isinstance(registry, dict) and isinstance(registry.get("source_tier_counts", {}), dict) else {},
        "registry_source_type_counts": registry.get("source_type_counts", {}) if isinstance(registry, dict) and isinstance(registry.get("source_type_counts", {}), dict) else {},
        "ingested_sources": int(ingestion.get("ingested_sources", 0) or 0) if isinstance(ingestion, dict) else 0,
        "quarantined_sources": int(ingestion.get("quarantined_sources", 0) or 0) if isinstance(ingestion, dict) else 0,
        "pattern_candidates": int(ingestion.get("pattern_candidates", 0) or 0) if isinstance(ingestion, dict) else 0,
        "evolution_candidates": int(ingestion.get("evolution_candidates", 0) or 0) if isinstance(ingestion, dict) else 0,
        "direct_trade_signal_blocked": bool(ingestion.get("direct_trade_signal_blocked", False)) if isinstance(ingestion, dict) else False,
        "copyright_violation_blocked": bool(ingestion.get("copyright_violation_blocked", False)) if isinstance(ingestion, dict) else False,
        "all_patterns_start_quarantined": bool(ingestion.get("all_patterns_start_quarantined", False)) if isinstance(ingestion, dict) else False,
        "evidence_item_count": int(source_coverage.get("total_items", 0) or len(evidence.get("evidence_items", []) or [])) if isinstance(evidence, dict) and isinstance(source_coverage, dict) else 0,
        "evidence_tier_counts": source_coverage.get("tier_counts", {}) if isinstance(source_coverage, dict) and isinstance(source_coverage.get("tier_counts", {}), dict) else {},
        "evidence_type_counts": source_coverage.get("type_counts", {}) if isinstance(source_coverage, dict) and isinstance(source_coverage.get("type_counts", {}), dict) else {},
        "primary_fact_evidence_items": int(source_coverage.get("primary_fact_items", 0) or 0) if isinstance(source_coverage, dict) else 0,
        "low_tier_evidence_items": int(source_coverage.get("low_tier_items", 0) or 0) if isinstance(source_coverage, dict) else 0,
        "methodology_sources_are_hypothesis_only": bool(boundary_policy.get("methodology_sources_are_hypothesis_generators", False)) if isinstance(boundary_policy, dict) else False,
        "primary_evidence_required_for_company_conclusions": bool(boundary_policy.get("primary_evidence_required_for_company_conclusions", False)) if isinstance(boundary_policy, dict) else False,
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def context_management_summary(run_path: Path) -> dict[str, Any]:
    agent_harness = read_optional_yaml(run_path / "harness" / "agent-harness.yaml", {})
    results = agent_harness.get("agent_results", []) if isinstance(agent_harness, dict) else []
    context_docs = [row.get("context_management_quality", {}) for row in results if isinstance(row, dict) and isinstance(row.get("context_management_quality", {}), dict)]
    thread_docs = [row.get("thread_memory_summary_quality", {}) for row in results if isinstance(row, dict) and isinstance(row.get("thread_memory_summary_quality", {}), dict)]
    aggregate = agent_harness.get("aggregate_scores", {}) if isinstance(agent_harness, dict) else {}
    return {
        "overall": float(aggregate.get("context_management_quality", 0) or 0) if isinstance(aggregate, dict) else 0,
        "agents_evaluated": len(context_docs),
        "budget_manifest_present": sum(1 for item in context_docs if item.get("budget_manifest_present")),
        "token_budget_respected": sum(1 for item in context_docs if item.get("token_budget_respected")),
        "loss_accounting_present": sum(1 for item in context_docs if item.get("loss_accounting_present")),
        "role_specific_compression_present": sum(1 for item in context_docs if item.get("role_specific_compression_present")),
        "evidence_loss_auditable": sum(1 for item in context_docs if item.get("evidence_loss_auditable")),
        "role_context_contract_present": sum(1 for item in context_docs if item.get("role_context_contract_present")),
        "required_context_dimensions_covered": sum(1 for item in context_docs if item.get("required_context_dimensions_covered")),
        "forbidden_drop_list_respected": sum(1 for item in context_docs if item.get("forbidden_drop_list_respected")),
        "retained_omitted_dimensions_traced": sum(1 for item in context_docs if item.get("retained_omitted_dimensions_traced")),
        "missing_required_context_dimensions": sorted({dimension for item in context_docs for dimension in item.get("missing_required_context_dimensions", []) if dimension}),
        "forbidden_drop_violations": sorted({dimension for item in context_docs for dimension in item.get("forbidden_drop_violations", []) if dimension}),
        "excluded_items": sum(int(item.get("excluded_items", 0) or 0) for item in context_docs),
        "estimated_tokens_before": sum(int(item.get("estimated_tokens_before", 0) or 0) for item in context_docs),
        "estimated_tokens_after": sum(int(item.get("estimated_tokens_after", 0) or 0) for item in context_docs),
        "drop_reasons": sorted({reason for item in context_docs for reason in item.get("drop_reasons", []) if reason}),
        "thread_memory_summary_quality": float(aggregate.get("thread_memory_summary", 0) or 0) if isinstance(aggregate, dict) else 0,
        "thread_summaries_available": sum(1 for item in thread_docs if item.get("available")),
        "thread_summary_signals_present": sum(1 for item in thread_docs if item.get("summary_signal_present")),
        "controls": [
            "role_specific_compression",
            "loss_accounting_required",
            "role_context_contract_loaded",
            "vertical_required_dimensions_traced",
            "forbidden_drop_list_checked",
            "token_budget_respected",
            "thread_summary_is_retrieval_input_only",
            "no_real_trade_action",
            "broker_integration_disabled",
        ],
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def portfolio_outcome_summary(run_path: Path) -> dict[str, Any]:
    watchlist = read_optional_yaml(run_path / "portfolio" / "watchlist.yaml", {})
    paper = read_optional_yaml(run_path / "portfolio" / "paper-portfolio.yaml", {})
    review = read_optional_yaml(run_path / "portfolio" / "portfolio-review.yaml", {})
    outcome = read_optional_yaml(run_path / "portfolio" / "outcome-tracking.yaml", {})
    actions = paper.get("actions", []) if isinstance(paper, dict) and isinstance(paper.get("actions", []), list) else []
    watch_items = watchlist.get("items", []) if isinstance(watchlist, dict) and isinstance(watchlist.get("items", []), list) else []
    attribution_items = review.get("attribution_items", []) if isinstance(review, dict) and isinstance(review.get("attribution_items", []), list) else []
    controls = sorted({str(control) for source in [review, outcome] if isinstance(source, dict) for control in source.get("controls", []) if control})
    return {
        "watchlist_items": len(watch_items),
        "paper_actions": len(actions),
        "reviewed_actions": int(review.get("reviewed_actions", 0) or 0) if isinstance(review, dict) else 0,
        "attribution_items": len(attribution_items),
        "learning_candidates": len(review.get("learning_candidates", []) or []) if isinstance(review, dict) and isinstance(review.get("learning_candidates", []), list) else 0,
        "outcome_status": str(outcome.get("outcome_status", "missing_market_replay")) if isinstance(outcome, dict) else "missing_market_replay",
        "actions_evaluated": int(outcome.get("actions_evaluated", 0) or 0) if isinstance(outcome, dict) else 0,
        "actions_missing_market_replay": int(outcome.get("actions_missing_market_replay", 0) or 0) if isinstance(outcome, dict) else 0,
        "outcome_quality_score": float(outcome.get("outcome_quality_score", 0) or 0) if isinstance(outcome, dict) else 0,
        "real_trade_violations": int(review.get("real_trade_violations", 0) or 0) if isinstance(review, dict) else 0,
        "review_verdict": str(review.get("review_verdict", "missing_portfolio_review")) if isinstance(review, dict) else "missing_portfolio_review",
        "controls": controls,
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def tool_runtime_summary(run_path: Path) -> dict[str, Any]:
    report = read_optional_yaml(run_path / "tools" / "tool-runtime-report.yaml", {})
    controls = report.get("controls", []) if isinstance(report, dict) and isinstance(report.get("controls", []), list) else []
    adapters = report.get("adapters_called", []) if isinstance(report, dict) and isinstance(report.get("adapters_called", []), list) else []
    source_tier_counts = report.get("source_tier_counts", {}) if isinstance(report, dict) and isinstance(report.get("source_tier_counts", {}), dict) else {}
    return {
        "runtime_id": str(report.get("runtime_id", "")) if isinstance(report, dict) else "",
        "tool_runtime_quality_score": float(report.get("tool_runtime_quality_score", 0) or 0) if isinstance(report, dict) else 0,
        "tool_call_count": int(report.get("tool_call_count", 0) or 0) if isinstance(report, dict) else 0,
        "succeeded_tool_calls": int(report.get("succeeded_tool_calls", 0) or 0) if isinstance(report, dict) else 0,
        "blocked_tool_calls": int(report.get("blocked_tool_calls", 0) or 0) if isinstance(report, dict) else 0,
        "evidence_items_created": int(report.get("evidence_items_created", 0) or 0) if isinstance(report, dict) else 0,
        "adapters_called": adapters,
        "source_tier_counts": source_tier_counts,
        "ledger_path": str(report.get("ledger_path", "")) if isinstance(report, dict) else "",
        "evidence_path": str(report.get("evidence_path", "")) if isinstance(report, dict) else "",
        "blocking_issue_count": len(report.get("blocking_issues", []) or []) if isinstance(report, dict) and isinstance(report.get("blocking_issues", []), list) else 0,
        "controls": controls,
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def agent_performance_summary(run_path: Path) -> dict[str, Any]:
    report = read_optional_yaml(run_path / "harness" / "agent-performance.yaml", {})
    counts = report.get("recommended_action_counts", {}) if isinstance(report, dict) else {}
    return {
        "agent_count": int(report.get("agent_count", 0) or 0) if isinstance(report, dict) else 0,
        "average_final_score": float(report.get("average_final_score", 0) or 0) if isinstance(report, dict) else 0,
        "recommended_action_counts": counts if isinstance(counts, dict) else {},
        "ledger_entries_written": int(report.get("ledger_entries_written", 0) or 0) if isinstance(report, dict) else 0,
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def agent_governance_summary(run_path: Path) -> dict[str, Any]:
    report = read_optional_yaml(run_path / "harness" / "agent-governance.yaml", {})
    counts = report.get("governance_action_counts", {}) if isinstance(report, dict) else {}
    return {
        "agent_count": int(report.get("agent_count", 0) or 0) if isinstance(report, dict) else 0,
        "governance_quality_score": float(report.get("governance_quality_score", 0) or 0) if isinstance(report, dict) else 0,
        "governance_action_counts": counts if isinstance(counts, dict) else {},
        "seat_competition_count": len(report.get("seat_competitions", {}) or {}) if isinstance(report, dict) else 0,
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def evaluation_summary(run_path: Path) -> dict[str, Any]:
    report = read_optional_yaml(run_path / "evaluations" / "evaluation-report.yaml", {})
    dimensions = report.get("dimension_scores", {}) if isinstance(report, dict) else {}
    blocking = report.get("blocking_issues", []) if isinstance(report, dict) else []
    accepted = report.get("accepted_outputs", []) if isinstance(report, dict) else []
    return {
        "overall_score": float(report.get("overall_score", 0) or 0) if isinstance(report, dict) else 0,
        "agent_performance_score": float(dimensions.get("agent_performance", 0) or 0) if isinstance(dimensions, dict) else 0,
        "agent_governance_score": float(dimensions.get("agent_governance", 0) or 0) if isinstance(dimensions, dict) else 0,
        "agent_os_contract_score": float(dimensions.get("agent_os_contract", 0) or 0) if isinstance(dimensions, dict) else 0,
        "blocking_issue_count": len(blocking) if isinstance(blocking, list) else 0,
        "accepted_output_count": len(accepted) if isinstance(accepted, list) else 0,
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
