from __future__ import annotations

from pathlib import Path
from typing import Any

from fundos.io import DISCLAIMER, read_yaml, write_yaml

AUDIT_VERSION = "0.1.0"


def run_system_audit(repo_root: Path, out_dir: Path | None = None, run_path: Path | None = None) -> dict[str, Any]:
    root = repo_root.resolve()
    runtime_run_path = run_path.resolve() if run_path else None
    roster = load_yaml(root / "specs" / "agents" / "default-roster.yaml", {})
    agents = roster.get("agents", []) if isinstance(roster, dict) else []
    requirements = build_requirements(root, agents)
    if runtime_run_path:
        requirements.extend(build_runtime_requirements(root, runtime_run_path))
    passed = sum(1 for row in requirements if row["status"] == "pass")
    score = round(passed / len(requirements) * 100, 1) if requirements else 0
    report = {
        "version": AUDIT_VERSION,
        "artifact_type": "system_requirement_coverage_audit",
        "repo_root": str(root),
        "agent_count": len(agents),
        "requirement_count": len(requirements),
        "passed_requirements": passed,
        "failed_requirements": len(requirements) - passed,
        "overall_coverage_score": score,
        "category_counts": count_by(requirements, "category"),
        "status_counts": count_by(requirements, "status"),
        "requirements": requirements,
        "blocking_issues": [issue for row in requirements for issue in row.get("blocking_issues", [])],
        "runtime_run_path": str(runtime_run_path) if runtime_run_path else "",
        "controls": [
            "requirement_coverage_is_evidence_based",
            "agent_assets_must_match_roster",
            "harness_and_evolution_closure_required",
            "no_real_trade_action",
            "broker_integration_disabled",
            "paper_portfolio_only",
        ],
        "disclaimer": DISCLAIMER,
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }
    if out_dir:
        write_outputs(report, out_dir)
    return report


def build_runtime_requirements(repo_root: Path, run_path: Path) -> list[dict[str, Any]]:
    evidence = load_yaml(run_path / "evidence" / "evidence-pack.yaml", {})
    evaluation = load_yaml(run_path / "evaluations" / "evaluation-report.yaml", {})
    tool_harness = load_yaml(run_path / "harness" / "tool-harness.yaml", {})
    agent_tool_use = load_yaml(run_path / "harness" / "agent-tool-use.yaml", {})
    claim_graph = load_yaml(run_path / "harness" / "claim-graph.yaml", {})
    agent_performance = load_yaml(run_path / "harness" / "agent-performance.yaml", {})
    agent_governance = load_yaml(run_path / "harness" / "agent-governance.yaml", {})
    os_manifest = load_yaml(run_path / "system" / "operating-system-manifest.yaml", {})
    run_doc = load_yaml(run_path / "run.yaml", {})
    items = evidence.get("evidence_items", []) if isinstance(evidence, dict) else []
    public_items = [item for item in items if item.get("source_id") == "public_research"]
    primary_public_items = [item for item in public_items if item.get("source_tier") == "tier_1_primary_fact"]
    unresolved_gaps = evidence.get("unresolved_gaps", []) if isinstance(evidence, dict) else []
    blocking = evaluation.get("blocking_issues", []) if isinstance(evaluation, dict) else []
    selected = run_doc.get("selected_agents", []) if isinstance(run_doc, dict) else []
    model_record_check = runtime_model_records_check(run_doc)
    manifest_schema_check = validate_operating_system_manifest_schema(repo_root, os_manifest)
    evaluation_schema_check = validate_evaluation_report_schema(repo_root, evaluation)
    manifest_summary_check = operating_system_manifest_runtime_summary_check(os_manifest, agent_performance, agent_governance, evaluation)
    return [
        requirement(
            "runtime.run_core_artifacts_exist",
            "runtime_operability",
            "Run contains core evidence, context, agent work, decision, evaluation, harness, and portfolio artifacts.",
            [run_path / p for p in [
                "run.yaml",
                "evidence/evidence-pack.yaml",
                "decision/final-decision-memo.yaml",
                "evaluations/evaluation-report.yaml",
                "harness/tool-harness.yaml",
                "harness/agent-tool-use.yaml",
                "harness/claim-graph.yaml",
                "portfolio/paper-portfolio.yaml",
                "system/operating-system-manifest.yaml",
                "system/operating-system-manifest.md",
            ]],
            all((run_path / p).exists() for p in [
                "run.yaml",
                "evidence/evidence-pack.yaml",
                "decision/final-decision-memo.yaml",
                "evaluations/evaluation-report.yaml",
                "harness/tool-harness.yaml",
                "harness/agent-tool-use.yaml",
                "harness/claim-graph.yaml",
                "portfolio/paper-portfolio.yaml",
                "system/operating-system-manifest.yaml",
                "system/operating-system-manifest.md",
            ]),
        ),
        requirement(
            "runtime.run_has_public_research_primary_evidence",
            "runtime_evidence",
            "Run evidence contains at least one public_research item backed by tier_1_primary_fact evidence.",
            [run_path / "evidence/evidence-pack.yaml", run_path / "evidence/public-research-manifest.yaml"],
            len(public_items) >= 1 and len(primary_public_items) >= 1,
            details={"public_research_items": len(public_items), "primary_public_items": len(primary_public_items)},
        ),
        requirement(
            "runtime.run_has_no_stub_blocking_issues",
            "runtime_evidence",
            "Run evaluation and evidence gaps do not contain unresolved public retrieval stub blockers.",
            [run_path / "evidence/evidence-pack.yaml", run_path / "evaluations/evaluation-report.yaml"],
            not contains_stub_gap(unresolved_gaps + blocking),
            details={"unresolved_gaps": unresolved_gaps, "blocking_issues": blocking},
        ),
        requirement(
            "runtime.run_harness_accepts_tool_claim_agent_outputs",
            "runtime_harness",
            "Runtime harness accepts tool usage, claim graph, and public research quality without blocking issues.",
            [run_path / "harness/tool-harness.yaml", run_path / "harness/agent-tool-use.yaml", run_path / "harness/claim-graph.yaml"],
            tool_harness_ok(tool_harness) and agent_tool_use_ok(agent_tool_use) and claim_graph_ok(claim_graph),
            details={
                "tool_harness_blocking_issues": tool_harness.get("blocking_issues", []) if isinstance(tool_harness, dict) else [],
                "agent_tool_use_blocking_issues": agent_tool_use.get("blocking_issues", []) if isinstance(agent_tool_use, dict) else [],
                "claim_graph_blocking_issues": claim_graph.get("blocking_issues", []) if isinstance(claim_graph, dict) else [],
            },
        ),
        requirement(
            "runtime.selected_agents_have_context_and_outputs",
            "runtime_agent_outputs",
            "Every selected agent has a ContextPack plus markdown and structured YAML output.",
            [run_path / "selected-agents.yaml", run_path / "context", run_path / "agent_work"],
            all(selected_agent_artifacts_exist(run_path, row.get("agent_id", "")) for row in selected),
            details={"missing": missing_selected_agent_artifacts(run_path, [row.get("agent_id", "") for row in selected])},
        ),
        requirement(
            "runtime.model_records_have_concrete_policy_fields",
            "runtime_governance",
            "Every runtime model record declares concrete model/tool policy fields and preserves paper-only safety boundaries.",
            [run_path / "run.yaml"],
            model_record_check["ok"],
            details=model_record_check,
        ),
        requirement(
            "runtime.operating_system_manifest_links_agent_os_assets",
            "runtime_governance",
            "Run operating-system manifest links selected agents to Profile, Skill, Tool, Memory, Thread, Harness, Evolution, and safety boundaries.",
            [run_path / "system" / "operating-system-manifest.yaml", run_path / "system" / "operating-system-manifest.md"],
            operating_system_manifest_ok(os_manifest, run_doc),
            details=operating_system_manifest_details(os_manifest),
        ),
        requirement(
            "runtime.operating_system_manifest_matches_schema",
            "runtime_governance",
            "Run operating-system manifest satisfies the source-controlled schema for Agent OS assets, evolution summary, and safety boundaries.",
            [repo_root / "specs/schemas/operating-system-manifest.schema.yaml", run_path / "system" / "operating-system-manifest.yaml"],
            manifest_schema_check["ok"],
            details=manifest_schema_check,
        ),
        requirement(
            "runtime.evaluation_report_matches_schema",
            "runtime_harness",
            "Run evaluation report satisfies the source-controlled schema for scoring dimensions, harness quality blocks, and safety boundaries.",
            [repo_root / "specs/schemas/evaluation-report.schema.yaml", run_path / "evaluations" / "evaluation-report.yaml"],
            evaluation_schema_check["ok"],
            details=evaluation_schema_check,
        ),
        requirement(
            "runtime.operating_system_manifest_runtime_summaries_match_sources",
            "runtime_governance",
            "Operating-system manifest performance, governance, and evaluation summaries match source reports and preserve safety boundaries.",
            [
                run_path / "system" / "operating-system-manifest.yaml",
                run_path / "harness" / "agent-performance.yaml",
                run_path / "harness" / "agent-governance.yaml",
                run_path / "evaluations" / "evaluation-report.yaml",
            ],
            manifest_summary_check["ok"],
            details=manifest_summary_check,
        ),
    ]


def build_requirements(root: Path, agents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    agent_ids = [agent["id"] for agent in agents if agent.get("id")]
    return [
        requirement(
            "prd.overall_and_modules_exist",
            "prd",
            "Overall PRD and module PRDs exist for direct Codex implementation.",
            [root / "docs/prd/overall-prd.md", root / "docs/prd/modules"],
            exists(root / "docs/prd/overall-prd.md") and dir_has_files(root / "docs/prd/modules", "*.md"),
        ),
        requirement(
            "agents.default_roster_has_diverse_roles",
            "agent_identity",
            "Default roster contains PM, risk, bear, evaluators, researchers, and traders.",
            [root / "specs/agents/default-roster.yaml"],
            len(agent_ids) >= 15 and roles_include(agents, ["FundManager", "Risk", "Bear", "Analyst", "Trader", "Evaluation"]),
            details={"agent_ids": agent_ids},
        ),
        requirement(
            "agents.all_roster_agents_have_cards_and_skills",
            "agent_identity",
            "Every roster agent has an independent agent.md and SKILL.md.",
            agent_asset_paths(root, agent_ids, ["agent_card", "skill"]),
            all((root / f"specs/agents/agent-cards/{aid}/agent.md").exists() and (root / f"specs/skills/{aid}/SKILL.md").exists() for aid in agent_ids),
            details={"missing": missing_agent_assets(root, agent_ids, ["agent_card", "skill"])},
        ),
        requirement(
            "agents.all_roster_agents_have_context_tool_memory_policies",
            "agent_skills_tools_memory",
            "Every agent has context, tool, and memory policies.",
            agent_asset_paths(root, agent_ids, ["context_policy", "tool_policy", "memory_policy"]),
            all((root / f"specs/agents/context-policies/{aid}.yaml").exists() and (root / f"specs/agents/tool-policies/{aid}.yaml").exists() and (root / f"specs/agents/memory-policies/{aid}.yaml").exists() for aid in agent_ids),
            details={"missing": missing_agent_assets(root, agent_ids, ["context_policy", "tool_policy", "memory_policy"])},
        ),
        requirement(
            "agents.agent_os_assets_cross_reference_roster_contract",
            "agent_skills_tools_memory",
            "Agent Card, Skill, ContextPolicy, ToolPolicy, and MemoryPolicy are mutually consistent with the default roster contract.",
            agent_asset_paths(root, agent_ids, ["agent_card", "skill", "context_policy", "tool_policy", "memory_policy"]),
            agent_os_asset_cross_references_ok(root, agents),
            details={"mismatches": agent_os_asset_cross_reference_mismatches(root, agents)},
        ),
        requirement(
            "agents.agent_cards_expose_profile_harness_memory_evolution",
            "agent_identity",
            "Agent cards define Profile, Skills, Tools, Harness, Context, Thread, Memory, and Evolution.",
            [root / "specs/agents/agent-cards"],
            all(agent_card_has_sections(root, aid) for aid in agent_ids),
            details={"missing_sections": missing_agent_card_sections(root, agent_ids)},
        ),
        requirement(
            "agents.skill_files_expose_purpose_workflow_context_safety",
            "agent_skills_tools_memory",
            "Every agent skill exposes Purpose, usage trigger, inputs, workflow, context management, output schema, harness hooks, and safety boundaries.",
            [root / "specs/skills"],
            all(agent_skill_has_sections(root, aid) for aid in agent_ids),
            details={"missing_sections": missing_agent_skill_sections(root, agent_ids)},
        ),
        requirement(
            "memory.persistent_threads_and_memory_policies",
            "agent_skills_tools_memory",
            "Persistent agent threads and controlled memory writeback exist.",
            [root / "fundos/agent_threads.py", root / "fundos/memory.py", root / "tests/test_agent_threads.py", root / "tests/test_memory_writeback.py"],
            all_exists(root, ["fundos/agent_threads.py", "fundos/memory.py", "tests/test_agent_threads.py", "tests/test_memory_writeback.py"]),
        ),
        requirement(
            "context.vertical_context_management_harness",
            "context_management",
            "Context compression, loss accounting, and role-specific policies are implemented.",
            [root / "fundos/context.py", root / "fundos/agent_harness.py", root / "tests/test_context_management_harness.py"],
            all_exists(root, ["fundos/context.py", "fundos/agent_harness.py", "tests/test_context_management_harness.py"]),
        ),
        requirement(
            "harness.agent_tool_context_skill_market_case_claim_evaluations",
            "harness_evaluation",
            "Harness covers agent, tool, context, skill, market-state, case replay, and claim graph quality.",
            [root / p for p in [
                "fundos/agent_harness.py", "fundos/agent_tool_use.py", "fundos/tool_harness.py",
                "fundos/skill_benchmark.py", "fundos/market_state.py", "fundos/case_replay.py", "fundos/claim_graph.py",
            ]],
            all_exists(root, [
                "fundos/agent_harness.py", "fundos/agent_tool_use.py", "fundos/tool_harness.py",
                "fundos/skill_benchmark.py", "fundos/market_state.py", "fundos/case_replay.py", "fundos/claim_graph.py",
            ]),
        ),
        requirement(
            "learning.source_ingestion_agent_learning_evolution_gate",
            "learning_evolution",
            "Learning source ingestion, agent learning candidates, EvolutionGate, and approval routing exist.",
            [root / p for p in ["fundos/source_ingestion.py", "fundos/agent_learning.py", "fundos/evolution.py", "fundos/capability_apply.py"]],
            all_exists(root, ["fundos/source_ingestion.py", "fundos/agent_learning.py", "fundos/evolution.py", "fundos/capability_apply.py"]),
        ),
        requirement(
            "evolution.human_approval_capability_apply_guarded",
            "learning_evolution",
            "Capability upgrades require EvolutionGate, regression, and human approval before apply.",
            [root / "fundos/capability_apply.py", root / "fundos/capability_regression.py", root / "tests/test_capability_apply.py"],
            file_contains(root / "fundos/capability_apply.py", ["regression_status must be passed", "adoption route is not applyable", "human approver is required"]),
        ),
        requirement(
            "cases.historical_case_failure_market_state_libraries",
            "case_library",
            "Historical cases, failure patterns, and market-state taxonomy are represented.",
            [root / "specs/cases/historical-case-library.yaml", root / "specs/cases/cases", root / "fundos/failure_patterns.py", root / "specs/market/market-state-taxonomy.yaml"],
            exists(root / "specs/cases/historical-case-library.yaml") and len(list((root / "specs/cases/cases").glob("*.yaml"))) >= 8 and all_exists(root, ["fundos/failure_patterns.py", "specs/market/market-state-taxonomy.yaml"]),
            details={"case_count": len(list((root / "specs/cases/cases").glob("*.yaml"))) if (root / "specs/cases/cases").exists() else 0},
        ),
        requirement(
            "tools.read_only_adapter_contracts_and_runtime",
            "tooling",
            "Read-only tool adapter contracts and deterministic fixture runtime exist.",
            [root / "specs/tools/tool-adapter-contracts.yaml", root / "specs/tools/fixture-adapter-runtime.yaml", root / "fundos/tool_runtime.py"],
            all_exists(root, ["specs/tools/tool-adapter-contracts.yaml", "specs/tools/fixture-adapter-runtime.yaml", "fundos/tool_runtime.py"]),
        ),
        requirement(
            "governance.committee_debate_pm_competition_seat_governance",
            "governance",
            "Committee protocols, debate, PM style competition, and seat governance exist.",
            [root / p for p in ["specs/protocols/investment-committee-protocol.yaml", "specs/protocols/debate-protocol.yaml", "fundos/pm_competition.py", "fundos/agent_governance.py"]],
            all_exists(root, ["specs/protocols/investment-committee-protocol.yaml", "specs/protocols/debate-protocol.yaml", "fundos/pm_competition.py", "fundos/agent_governance.py"]),
        ),
        requirement(
            "safety.no_real_trade_or_broker_integration",
            "safety_boundaries",
            "System enforces research/watchlist/paper-only boundaries and disables broker integration.",
            [root / "fundos", root / "specs"],
            safety_boundary_present(root),
        ),
        requirement(
            "cli.run_eval_evolve_operability",
            "cli_operability",
            "CLI exposes run, eval, evolve, report, memory, capabilities, sources, cases, threads, and governance workflows.",
            [root / "fundos/cli.py", root / "tests/test_cli_unittest.py"],
            file_contains(root / "fundos/cli.py", ["command_run", "command_eval", "command_evolve", "command_capabilities_apply", "command_sources_ingest", "command_threads_show", "command_governance_summary"]),
        ),
        requirement(
            "runtime.operating_system_manifest_schema_exists",
            "cli_operability",
            "Operating-system manifest has a schema governing Agent OS assets, evolution summary, and safety boundaries.",
            [root / "specs/schemas/operating-system-manifest.schema.yaml"],
            file_contains(root / "specs/schemas/operating-system-manifest.schema.yaml", ["operating_system_manifest", "evolution_summary", "safety_invariants", "broker_integration"]),
        ),
        requirement(
            "runtime.evaluation_report_schema_exists",
            "harness_evaluation",
            "Evaluation report has a schema governing scoring dimensions, harness quality blocks, governance signals, and safety boundaries.",
            [root / "specs/schemas/evaluation-report.schema.yaml"],
            file_contains(root / "specs/schemas/evaluation-report.schema.yaml", [
                "dimension_scores",
                "agent_governance",
                "agent_performance",
                "agent_os_contract",
                "real_trade_allowed",
                "broker_integration",
            ]),
        ),
    ]


def requirement(requirement_id: str, category: str, description: str, evidence_paths: list[Path], ok: bool, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "requirement_id": requirement_id,
        "category": category,
        "description": description,
        "status": "pass" if ok else "fail",
        "evidence": [str(path) for path in evidence_paths],
        "details": details or {},
        "blocking_issues": [] if ok else [f"requirement_not_satisfied:{requirement_id}"],
    }


def load_yaml(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return read_yaml(path) or default


def exists(path: Path) -> bool:
    return path.exists()


def dir_has_files(path: Path, pattern: str) -> bool:
    return path.is_dir() and any(path.glob(pattern))


def all_exists(root: Path, rels: list[str]) -> bool:
    return all((root / rel).exists() for rel in rels)


def file_contains(path: Path, needles: list[str]) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    return all(needle in text for needle in needles)


def roles_include(agents: list[dict[str, Any]], role_fragments: list[str]) -> bool:
    roles = "\n".join(str(agent.get("role", "")) for agent in agents)
    return all(fragment in roles for fragment in role_fragments)


def agent_asset_paths(root: Path, agent_ids: list[str], kinds: list[str]) -> list[Path]:
    paths: list[Path] = []
    for aid in agent_ids:
        for kind in kinds:
            paths.append(agent_asset_path(root, aid, kind))
    return paths


def agent_asset_path(root: Path, agent_id: str, kind: str) -> Path:
    mapping = {
        "agent_card": root / f"specs/agents/agent-cards/{agent_id}/agent.md",
        "skill": root / f"specs/skills/{agent_id}/SKILL.md",
        "context_policy": root / f"specs/agents/context-policies/{agent_id}.yaml",
        "tool_policy": root / f"specs/agents/tool-policies/{agent_id}.yaml",
        "memory_policy": root / f"specs/agents/memory-policies/{agent_id}.yaml",
    }
    return mapping[kind]


def missing_agent_assets(root: Path, agent_ids: list[str], kinds: list[str]) -> list[str]:
    missing = []
    for aid in agent_ids:
        for kind in kinds:
            path = agent_asset_path(root, aid, kind)
            if not path.exists():
                missing.append(str(path))
    return missing


def agent_os_asset_cross_references_ok(root: Path, agents: list[dict[str, Any]]) -> bool:
    return not agent_os_asset_cross_reference_mismatches(root, agents)


def agent_os_asset_cross_reference_mismatches(root: Path, agents: list[dict[str, Any]]) -> dict[str, list[str]]:
    mismatches = {agent.get("id", "unknown"): cross_reference_mismatches_for_agent(root, agent) for agent in agents}
    return {aid: rows for aid, rows in mismatches.items() if rows}


def cross_reference_mismatches_for_agent(root: Path, agent: dict[str, Any]) -> list[str]:
    aid = agent.get("id", "")
    role = agent.get("role", "")
    skills = set(agent.get("skills", []) or [])
    tools = set(agent.get("tools", []) or [])
    issues: list[str] = []
    agent_card = root / f"specs/agents/agent-cards/{aid}/agent.md"
    skill = root / f"specs/skills/{aid}/SKILL.md"
    context_policy = root / f"specs/agents/context-policies/{aid}.yaml"
    tool_policy = root / f"specs/agents/tool-policies/{aid}.yaml"
    memory_policy = root / f"specs/agents/memory-policies/{aid}.yaml"
    if not all(path.exists() for path in [agent_card, skill, context_policy, tool_policy, memory_policy]):
        return ["missing_agent_os_asset"]
    card_text = agent_card.read_text(encoding="utf-8")
    skill_text = skill.read_text(encoding="utf-8")
    context_doc = load_yaml(context_policy, {})
    tool_doc = load_yaml(tool_policy, {})
    memory_doc = load_yaml(memory_policy, {})
    if f"canonical_agent_id: `{aid}`" not in card_text:
        issues.append("agent_card_identity_mismatch")
    if f"organization_role: {role}" not in card_text:
        issues.append("agent_card_role_mismatch")
    if f"persistent_thread_manifest: `memory/agents/{aid}/thread.yaml`" not in card_text or f"long_term_namespace: `memory/agents/{aid}`" not in card_text:
        issues.append("agent_card_memory_thread_namespace_mismatch")
    for declared_skill in skills:
        if f"`{declared_skill}`" not in card_text:
            issues.append(f"agent_card_missing_skill:{declared_skill}")
    for declared_tool in tools:
        if f"`{declared_tool}`" not in card_text:
            issues.append(f"agent_card_missing_tool:{declared_tool}")
    if f"Agent card: `specs/agents/agent-cards/{aid}/agent.md`" not in skill_text:
        issues.append("skill_agent_card_reference_mismatch")
    if f"Relevant long-term memory summary from `memory/agents/{aid}`" not in skill_text:
        issues.append("skill_memory_namespace_reference_mismatch")
    for kind, doc in [("context", context_doc), ("tool", tool_doc), ("memory", memory_doc)]:
        if doc.get("agent_id") != aid:
            issues.append(f"{kind}_policy_agent_id_mismatch")
        if doc.get("role") != role:
            issues.append(f"{kind}_policy_role_mismatch")
        if doc.get("real_trade_allowed") is not False:
            issues.append(f"{kind}_policy_real_trade_not_disabled")
        if doc.get("broker_integration") is not False:
            issues.append(f"{kind}_policy_broker_not_disabled")
    if set(tool_doc.get("allowed_tools", []) or []) != tools:
        issues.append("tool_policy_allowed_tools_mismatch")
    if not set(tool_doc.get("required_tools", []) or []).issubset(tools):
        issues.append("tool_policy_required_tools_outside_roster")
    if f"memory/agents/{aid}" not in set(memory_doc.get("read_namespaces", []) or []):
        issues.append("memory_policy_missing_agent_read_namespace")
    if memory_doc.get("write_namespaces") != [f"memory/agents/{aid}"]:
        issues.append("memory_policy_write_namespace_mismatch")
    writeback = memory_doc.get("writeback_rules", {}) if isinstance(memory_doc, dict) else {}
    if writeback.get("requires_evolution_gate") is not True or writeback.get("allow_direct_profile_mutation") is not False:
        issues.append("memory_policy_evolution_or_profile_guard_mismatch")
    evidence_selection = context_doc.get("evidence_selection", {}) if isinstance(context_doc, dict) else {}
    if evidence_selection.get("kol_and_books_as_methodology_only") is not True:
        issues.append("context_policy_kol_methodology_boundary_missing")
    return issues


def agent_card_has_sections(root: Path, agent_id: str) -> bool:
    return not missing_sections_for_agent(root, agent_id)


def missing_agent_card_sections(root: Path, agent_ids: list[str]) -> dict[str, list[str]]:
    missing = {aid: missing_sections_for_agent(root, aid) for aid in agent_ids}
    return {aid: sections for aid, sections in missing.items() if sections}


def missing_sections_for_agent(root: Path, agent_id: str) -> list[str]:
    path = root / f"specs/agents/agent-cards/{agent_id}/agent.md"
    if not path.exists():
        return ["agent.md"]
    text = path.read_text(encoding="utf-8").lower()
    required = [
        "profile",
        "identity",
        "role mandate",
        "investment style",
        "risk preference",
        "decision principles",
        "personality",
        "skills",
        "tools",
        "learning patterns",
        "ability boundaries",
        "biases and weaknesses",
        "track record and growth",
        "memory and thread",
        "harness and evaluation",
        "context management policy",
        "evolution path",
        "output contract",
    ]
    return [section for section in required if section not in text]


def agent_skill_has_sections(root: Path, agent_id: str) -> bool:
    return not missing_skill_sections_for_agent(root, agent_id)


def missing_agent_skill_sections(root: Path, agent_ids: list[str]) -> dict[str, list[str]]:
    missing = {aid: missing_skill_sections_for_agent(root, aid) for aid in agent_ids}
    return {aid: sections for aid, sections in missing.items() if sections}


def missing_skill_sections_for_agent(root: Path, agent_id: str) -> list[str]:
    path = root / f"specs/skills/{agent_id}/SKILL.md"
    if not path.exists():
        return ["SKILL.md"]
    text = path.read_text(encoding="utf-8").lower()
    required = [
        "purpose",
        "when to use",
        "inputs",
        "workflow",
        "procedure",
        "context management",
        "output schema",
        "harness hooks",
        "quality gates",
        "guardrails",
        "safety",
        "boundaries",
    ]
    return [section for section in required if section not in text]


def safety_boundary_present(root: Path) -> bool:
    files = [root / "fundos/io.py", root / "fundos/tool_runtime.py", root / "fundos/capability_apply.py", root / "README.md"]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in files if path.exists())
    return all(term in combined for term in ["不构成投资建议", "no_real_trade", "broker"])


def contains_stub_gap(rows: list[Any]) -> bool:
    text = "\n".join(str(row) for row in rows)
    return "public retrieval interface stub" in text or "EvidencePack stub" in text or "真实公开数据检索工具尚未接入" in text


def tool_harness_ok(report: Any) -> bool:
    if not isinstance(report, dict):
        return False
    adapter = report.get("adapter_coverage", {})
    return (
        report.get("overall_score", 0) >= 80
        and adapter.get("public_research_items", 0) >= 1
        and adapter.get("primary_public_items", 0) >= 1
        and not report.get("blocking_issues", [])
        and not report.get("real_trade_allowed", False)
    )


def agent_tool_use_ok(report: Any) -> bool:
    if not isinstance(report, dict):
        return False
    return report.get("overall_score", 0) >= 80 and not report.get("blocking_issues", []) and not report.get("real_trade_allowed", False)


def claim_graph_ok(report: Any) -> bool:
    if not isinstance(report, dict):
        return False
    blocking = [issue for issue in report.get("blocking_issues", []) if issue != "missing_claim_graph_report"]
    return report.get("traceability_score", 0) >= 80 and not blocking and not report.get("real_trade_allowed", False)


def selected_agent_artifacts_exist(run_path: Path, agent_id: str) -> bool:
    if not agent_id:
        return False
    return all(
        (run_path / rel).exists()
        for rel in [
            f"context/{agent_id}.context-pack.yaml",
            f"agent_work/{agent_id}.md",
            f"agent_work/{agent_id}.structured.yaml",
        ]
    )


def missing_selected_agent_artifacts(run_path: Path, agent_ids: list[str]) -> list[str]:
    missing: list[str] = []
    for agent_id in agent_ids:
        for rel in [
            f"context/{agent_id}.context-pack.yaml",
            f"agent_work/{agent_id}.md",
            f"agent_work/{agent_id}.structured.yaml",
        ]:
            path = run_path / rel
            if not path.exists():
                missing.append(str(path))
    return missing


def runtime_model_records_check(run_doc: Any) -> dict[str, Any]:
    required = [
        "agent_id",
        "model",
        "model_policy_id",
        "reasoning_effort",
        "skill_versions",
        "tool_versions",
        "tool_contract_id",
        "runtime_mode",
        "real_trade_allowed",
        "broker_integration",
    ]
    records = run_doc.get("model_records", []) if isinstance(run_doc, dict) else []
    selected = run_doc.get("selected_agents", []) if isinstance(run_doc, dict) else []
    missing_fields: list[dict[str, Any]] = []
    safety_violations: list[dict[str, Any]] = []
    stub_values: list[dict[str, Any]] = []
    for idx, record in enumerate(records):
        if not isinstance(record, dict):
            missing_fields.append({"index": idx, "agent_id": "", "fields": required})
            continue
        missing = [field for field in required if field not in record]
        if missing:
            missing_fields.append({"index": idx, "agent_id": record.get("agent_id", ""), "fields": missing})
        if record.get("runtime_mode") != "local_file_protocol":
            safety_violations.append({"index": idx, "agent_id": record.get("agent_id", ""), "field": "runtime_mode", "value": record.get("runtime_mode")})
        if record.get("real_trade_allowed") is not False:
            safety_violations.append({"index": idx, "agent_id": record.get("agent_id", ""), "field": "real_trade_allowed", "value": record.get("real_trade_allowed")})
        if record.get("broker_integration") != "disabled":
            safety_violations.append({"index": idx, "agent_id": record.get("agent_id", ""), "field": "broker_integration", "value": record.get("broker_integration")})
        skill_versions = record.get("skill_versions", [])
        tool_versions = record.get("tool_versions", [])
        version_values = (skill_versions if isinstance(skill_versions, list) else []) + (tool_versions if isinstance(tool_versions, list) else [])
        joined_versions = " ".join(str(item) for item in version_values)
        if "stub" in joined_versions.lower() or "stub" in str(record.get("model", "")).lower():
            stub_values.append({"index": idx, "agent_id": record.get("agent_id", ""), "model": record.get("model"), "versions": joined_versions})
    selected_count = len(selected) if isinstance(selected, list) else 0
    record_count_matches_selected_agents = bool(records) and len(records) == selected_count
    ok = record_count_matches_selected_agents and not missing_fields and not safety_violations and not stub_values
    return {
        "ok": ok,
        "model_record_count": len(records) if isinstance(records, list) else 0,
        "selected_agent_count": selected_count,
        "record_count_matches_selected_agents": record_count_matches_selected_agents,
        "missing_model_record_fields": missing_fields,
        "safety_violations": safety_violations,
        "stub_values": stub_values,
    }


def operating_system_manifest_ok(manifest: Any, run_doc: Any) -> bool:
    if not isinstance(manifest, dict) or not isinstance(run_doc, dict):
        return False
    safety = manifest.get("safety_invariants", {}) or {}
    required_assets = {"agent_card", "skill", "context_policy", "tool_policy", "memory_policy"}
    loaded = manifest.get("loaded_asset_counts", {}) or {}
    return (
        manifest.get("artifact_type") == "operating_system_manifest"
        and manifest.get("run_id") == run_doc.get("run_id")
        and manifest.get("selected_agent_count") == len(run_doc.get("selected_agents", []) or [])
        and manifest.get("model_record_count") == len(run_doc.get("model_records", []) or [])
        and manifest.get("runtime_mode") == "local_file_protocol"
        and manifest.get("all_selected_agents_have_runtime_assets") is True
        and required_assets.issubset(set(loaded.keys()))
        and "harness/agent-harness.yaml" in (manifest.get("harness_artifacts", []) or [])
        and "evolution/candidates.jsonl" in (manifest.get("evolution_artifacts", []) or [])
        and safety.get("paper_portfolio_only") is True
        and safety.get("kol_is_hypothesis_only") is True
        and manifest.get("real_trade_allowed") is False
        and manifest.get("broker_integration") == "disabled"
    )


def operating_system_manifest_details(manifest: Any) -> dict[str, Any]:
    if not isinstance(manifest, dict):
        return {"present": False}
    return {
        "present": True,
        "selected_agent_count": manifest.get("selected_agent_count", 0),
        "model_record_count": manifest.get("model_record_count", 0),
        "loaded_asset_counts": manifest.get("loaded_asset_counts", {}),
        "missing_agent_assets": manifest.get("missing_agent_assets", []),
        "harness_artifacts": manifest.get("harness_artifacts", []),
        "memory_thread_artifacts": manifest.get("memory_thread_artifacts", []),
        "evolution_artifacts": manifest.get("evolution_artifacts", []),
        "evolution_summary": manifest.get("evolution_summary", {}),
        "agent_performance_summary": manifest.get("agent_performance_summary", {}),
        "agent_governance_summary": manifest.get("agent_governance_summary", {}),
        "evaluation_summary": manifest.get("evaluation_summary", {}),
        "real_trade_allowed": manifest.get("real_trade_allowed"),
        "broker_integration": manifest.get("broker_integration"),
    }


def operating_system_manifest_runtime_summary_check(manifest: Any, performance: Any, governance: Any, evaluation: Any) -> dict[str, Any]:
    mismatches: list[str] = []
    if not all(isinstance(item, dict) for item in [manifest, performance, governance, evaluation]):
        return {"ok": False, "mismatches": ["manifest_or_source_report_missing_or_invalid"]}
    perf_summary = manifest.get("agent_performance_summary", {}) or {}
    gov_summary = manifest.get("agent_governance_summary", {}) or {}
    eval_summary = manifest.get("evaluation_summary", {}) or {}
    dimensions = evaluation.get("dimension_scores", {}) or {}
    compare_value(mismatches, "agent_performance_summary.agent_count", perf_summary.get("agent_count"), performance.get("agent_count", 0))
    compare_value(mismatches, "agent_performance_summary.average_final_score", perf_summary.get("average_final_score"), performance.get("average_final_score", 0))
    compare_value(mismatches, "agent_performance_summary.recommended_action_counts", perf_summary.get("recommended_action_counts"), performance.get("recommended_action_counts", {}))
    compare_value(mismatches, "agent_performance_summary.ledger_entries_written", perf_summary.get("ledger_entries_written"), performance.get("ledger_entries_written", 0))
    compare_value(mismatches, "agent_governance_summary.agent_count", gov_summary.get("agent_count"), governance.get("agent_count", 0))
    compare_value(mismatches, "agent_governance_summary.governance_quality_score", gov_summary.get("governance_quality_score"), governance.get("governance_quality_score", 0))
    compare_value(mismatches, "agent_governance_summary.governance_action_counts", gov_summary.get("governance_action_counts"), governance.get("governance_action_counts", {}))
    compare_value(mismatches, "agent_governance_summary.seat_competition_count", gov_summary.get("seat_competition_count"), len(governance.get("seat_competitions", {}) or {}))
    compare_value(mismatches, "evaluation_summary.overall_score", eval_summary.get("overall_score"), evaluation.get("overall_score", 0))
    compare_value(mismatches, "evaluation_summary.agent_performance_score", eval_summary.get("agent_performance_score"), dimensions.get("agent_performance", 0))
    compare_value(mismatches, "evaluation_summary.agent_governance_score", eval_summary.get("agent_governance_score"), dimensions.get("agent_governance", 0))
    compare_value(mismatches, "evaluation_summary.agent_os_contract_score", eval_summary.get("agent_os_contract_score"), dimensions.get("agent_os_contract", 0))
    compare_value(mismatches, "evaluation_summary.blocking_issue_count", eval_summary.get("blocking_issue_count"), len(evaluation.get("blocking_issues", []) or []))
    compare_value(mismatches, "evaluation_summary.accepted_output_count", eval_summary.get("accepted_output_count"), len(evaluation.get("accepted_outputs", []) or []))
    for prefix, summary in [("agent_performance_summary", perf_summary), ("agent_governance_summary", gov_summary), ("evaluation_summary", eval_summary)]:
        if summary.get("real_trade_allowed") is not False:
            mismatches.append(f"{prefix}.real_trade_allowed: expected False, got {summary.get('real_trade_allowed')!r}")
        if summary.get("broker_integration") != "disabled":
            mismatches.append(f"{prefix}.broker_integration: expected 'disabled', got {summary.get('broker_integration')!r}")
    return {"ok": not mismatches, "mismatches": mismatches}


def compare_value(mismatches: list[str], field: str, actual: Any, expected: Any) -> None:
    if normalize_comparable(actual) != normalize_comparable(expected):
        mismatches.append(f"{field}: expected {expected!r}, got {actual!r}")


def normalize_comparable(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, int) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, dict):
        return {key: normalize_comparable(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [normalize_comparable(item) for item in value]
    return value


def validate_operating_system_manifest_schema(repo_root: Path, manifest: Any) -> dict[str, Any]:
    schema_path = repo_root / "specs" / "schemas" / "operating-system-manifest.schema.yaml"
    return validate_runtime_schema(schema_path, manifest)


def validate_evaluation_report_schema(repo_root: Path, evaluation: Any) -> dict[str, Any]:
    schema_path = repo_root / "specs" / "schemas" / "evaluation-report.schema.yaml"
    return validate_runtime_schema(schema_path, evaluation)


def validate_runtime_schema(schema_path: Path, value: Any) -> dict[str, Any]:
    schema = load_yaml(schema_path, {})
    errors = validate_schema_node(schema, value, path="$")
    return {
        "ok": not errors,
        "schema_path": str(schema_path),
        "schema_errors": errors,
    }


def validate_schema_node(schema: Any, value: Any, path: str) -> list[str]:
    if not isinstance(schema, dict):
        return []
    errors: list[str] = []
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: value {value!r} not in enum {schema['enum']!r}")

    expected_type = schema.get("type")
    if expected_type and not schema_type_matches(expected_type, value):
        errors.append(f"{path}: expected type {expected_type}, got {type(value).__name__}")
        return errors

    if expected_type == "object" or "properties" in schema or "required" in schema:
        if not isinstance(value, dict):
            errors.append(f"{path}: expected object, got {type(value).__name__}")
            return errors
        for field in schema.get("required", []) or []:
            if field not in value:
                errors.append(f"{path}.{field}: missing required field")
        properties = schema.get("properties", {}) or {}
        for field, child_schema in properties.items():
            if field in value:
                errors.extend(validate_schema_node(child_schema, value[field], f"{path}.{field}"))

    if expected_type == "array" or "items" in schema:
        if not isinstance(value, list):
            errors.append(f"{path}: expected array, got {type(value).__name__}")
            return errors
        item_schema = schema.get("items", {}) or {}
        for idx, item in enumerate(value):
            errors.extend(validate_schema_node(item_schema, item, f"{path}[{idx}]"))
    return errors


def schema_type_matches(expected_type: str, value: Any) -> bool:
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    return True


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return counts


def write_outputs(report: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    yaml_path = out_dir / "system-audit.yaml"
    md_path = out_dir / "system-audit.md"
    report["output_paths"] = {"yaml": str(yaml_path), "markdown": str(md_path)}
    write_yaml(yaml_path, report)
    md_path.write_text(render_markdown(report), encoding="utf-8")


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Requirement Coverage Audit",
        "",
        f"- overall_coverage_score: {report['overall_coverage_score']}",
        f"- requirements: {report['passed_requirements']}/{report['requirement_count']} pass",
        f"- agent_count: {report['agent_count']}",
        f"- real_trade_allowed: {report['real_trade_allowed']}",
        f"- broker_integration: {report['broker_integration']}",
        "",
        "## Requirements",
        "",
    ]
    for row in report["requirements"]:
        lines.append(f"- [{row['status']}] `{row['requirement_id']}` ({row['category']}): {row['description']}")
    lines.extend(["", report.get("disclaimer", DISCLAIMER), ""])
    return "\n".join(lines)
