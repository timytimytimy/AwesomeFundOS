from __future__ import annotations

import json
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
    tool_runtime = load_yaml(run_path / "tools" / "tool-runtime-report.yaml", {})
    tool_runtime_evidence = load_yaml(run_path / "evidence" / "tool-runtime-evidence.yaml", {})
    tool_call_ledger = load_jsonl(run_path / "tools" / "tool-call-ledger.jsonl")
    claim_graph = load_yaml(run_path / "harness" / "claim-graph.yaml", {})
    agent_performance = load_yaml(run_path / "harness" / "agent-performance.yaml", {})
    agent_governance = load_yaml(run_path / "harness" / "agent-governance.yaml", {})
    agent_harness_full = load_yaml(run_path / "harness" / "agent-harness.yaml", {})
    collaboration_harness = load_yaml(run_path / "harness" / "collaboration-harness.yaml", {})
    decision_readiness = load_yaml(run_path / "committee" / "decision-readiness.yaml", {})
    disagreement_register = load_yaml(run_path / "committee" / "disagreement-register.yaml", {})
    veto_table = load_yaml(run_path / "committee" / "veto-table.yaml", {})
    decision_memo = load_yaml(run_path / "decision" / "final-decision-memo.yaml", {})
    watchlist = load_yaml(run_path / "portfolio" / "watchlist.yaml", {})
    paper_portfolio = load_yaml(run_path / "portfolio" / "paper-portfolio.yaml", {})
    portfolio_review = load_yaml(run_path / "portfolio" / "portfolio-review.yaml", {})
    outcome_tracking = load_yaml(run_path / "portfolio" / "outcome-tracking.yaml", {})
    source_registry = load_yaml(run_path / "learning" / "source-registry.yaml", {})
    source_ingestion = load_yaml(run_path / "learning" / "source-ingestion-report.yaml", {})
    agent_learning = load_yaml(run_path / "learning" / "agent-learning-report.yaml", {})
    agent_learning_candidates = load_jsonl(run_path / "learning" / "agent-learning-candidates.jsonl")
    evolution_candidates = load_jsonl(run_path / "evolution" / "candidates.jsonl")
    gate_results = load_jsonl(run_path / "evolution" / "evolution-gate-results.jsonl")
    accepted_evolution = load_jsonl(run_path / "evolution" / "accepted.jsonl")
    quarantined_evolution = load_jsonl(run_path / "evolution" / "quarantine.jsonl")
    rejected_evolution = load_jsonl(run_path / "evolution" / "rejected.jsonl")
    memory_writeback = load_yaml(run_path / "evolution" / "memory-writeback-summary.yaml", {})
    capability_candidates = load_jsonl(run_path / "evolution" / "capability-candidates.jsonl")
    capability_summary = load_yaml(run_path / "evolution" / "capability-version-summary.yaml", {})
    agent_capability_ledger = load_yaml(run_path / "evolution" / "agent-capability-ledger.yaml", {})
    capability_regression = load_yaml(run_path / "harness" / "capability-regression.yaml", {})
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
    manifest_source_check = operating_system_manifest_source_provenance_check(os_manifest, source_registry, source_ingestion, evidence)
    manifest_evolution_learning_check = operating_system_manifest_evolution_learning_check(
        os_manifest,
        agent_learning,
        agent_learning_candidates,
        source_ingestion,
        evolution_candidates,
        gate_results,
        accepted_evolution,
        quarantined_evolution,
        rejected_evolution,
        memory_writeback,
        capability_candidates,
        capability_summary,
        capability_regression,
    )
    manifest_context_check = operating_system_manifest_context_management_check(os_manifest, agent_harness_full)
    manifest_tool_runtime_check = operating_system_manifest_tool_runtime_check(os_manifest, tool_runtime, tool_call_ledger, tool_runtime_evidence)
    manifest_agent_capability_ledger_check = operating_system_manifest_agent_capability_ledger_check(os_manifest, agent_capability_ledger)
    runtime_maturity_check = runtime_agent_maturity_contract_check(run_path, [row.get("agent_id", "") for row in selected])
    manifest_maturity_check = operating_system_manifest_agent_maturity_check(os_manifest, run_path, [row.get("agent_id", "") for row in selected])
    committee_check = committee_debate_risk_decision_loop_check(decision_readiness, disagreement_register, veto_table, collaboration_harness, decision_memo)
    portfolio_outcome_check = operating_system_manifest_portfolio_outcome_check(os_manifest, watchlist, paper_portfolio, portfolio_review, outcome_tracking)
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
            "runtime.agent_outputs_include_maturity_contracts",
            "runtime_agent_outputs",
            "Every selected agent ContextPack and structured output include differentiated maturity, benchmark, compression, evolution, and paper-only safety contract fields.",
            [run_path / "context", run_path / "agent_work"],
            runtime_maturity_check["ok"],
            details=runtime_maturity_check,
        ),
        requirement(
            "runtime.agent_maturity_contract_summary_matches_sources",
            "runtime_agent_outputs",
            "Operating-system manifest agent maturity summary matches ContextPack and structured output maturity contracts while preserving paper-only safety boundaries.",
            [run_path / "system" / "operating-system-manifest.yaml", run_path / "context", run_path / "agent_work"],
            manifest_maturity_check["ok"],
            details=manifest_maturity_check,
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
        requirement(
            "runtime.operating_system_manifest_source_provenance_matches_sources",
            "runtime_governance",
            "Operating-system manifest source provenance summary matches registry, ingestion, and evidence source coverage while preserving KOL methodology-only boundaries.",
            [
                run_path / "system" / "operating-system-manifest.yaml",
                run_path / "learning" / "source-registry.yaml",
                run_path / "learning" / "source-ingestion-report.yaml",
                run_path / "evidence" / "evidence-pack.yaml",
            ],
            manifest_source_check["ok"],
            details=manifest_source_check,
        ),
        requirement(
            "runtime.evolution_learning_loop_matches_manifest",
            "learning_evolution",
            "Learning candidates, source ingestion, EvolutionGate, memory writeback, capability regression, and approval summaries match the OS manifest and preserve quarantine-before-adoption boundaries.",
            [
                run_path / "system" / "operating-system-manifest.yaml",
                run_path / "learning" / "agent-learning-candidates.jsonl",
                run_path / "learning" / "agent-learning-report.yaml",
                run_path / "learning" / "source-ingestion-report.yaml",
                run_path / "evolution" / "candidates.jsonl",
                run_path / "evolution" / "evolution-gate-results.jsonl",
                run_path / "evolution" / "accepted.jsonl",
                run_path / "evolution" / "quarantine.jsonl",
                run_path / "evolution" / "rejected.jsonl",
                run_path / "evolution" / "memory-writeback-summary.yaml",
                run_path / "evolution" / "capability-candidates.jsonl",
                run_path / "evolution" / "capability-version-summary.yaml",
                run_path / "harness" / "capability-regression.yaml",
            ],
            manifest_evolution_learning_check["ok"],
            details=manifest_evolution_learning_check,
        ),
        requirement(
            "runtime.agent_capability_ledger_matches_manifest",
            "learning_evolution",
            "Per-agent capability lifecycle ledger matches the OS manifest and preserves regression plus human-approval-before-apply controls.",
            [
                run_path / "system" / "operating-system-manifest.yaml",
                run_path / "evolution" / "agent-capability-ledger.yaml",
                run_path / "evolution" / "capability-candidates.jsonl",
                run_path / "harness" / "capability-regression.yaml",
            ],
            manifest_agent_capability_ledger_check["ok"],
            details=manifest_agent_capability_ledger_check,
        ),
        requirement(
            "runtime.operating_system_manifest_context_management_matches_harness",
            "context_management",
            "Operating-system manifest context management summary matches agent harness context compression, loss accounting, and thread-memory summary quality.",
            [
                run_path / "system" / "operating-system-manifest.yaml",
                run_path / "harness" / "agent-harness.yaml",
                run_path / "context",
            ],
            manifest_context_check["ok"],
            details=manifest_context_check,
        ),
        requirement(
            "runtime.tool_runtime_ledger_matches_manifest",
            "tooling",
            "Tool Runtime report, tool-call ledger, and tool evidence match the OS manifest summary while preserving read-only no-broker boundaries.",
            [
                run_path / "system" / "operating-system-manifest.yaml",
                run_path / "tools" / "tool-runtime-report.yaml",
                run_path / "tools" / "tool-call-ledger.jsonl",
                run_path / "evidence" / "tool-runtime-evidence.yaml",
            ],
            manifest_tool_runtime_check["ok"],
            details=manifest_tool_runtime_check,
        ),
        requirement(
            "runtime.committee_debate_risk_decision_loop_complete",
            "governance",
            "Runtime committee loop preserves bear challenge, risk veto/cap, disagreements, collaboration harness, and final memo linkage under paper-only boundaries.",
            [
                run_path / "committee" / "decision-readiness.yaml",
                run_path / "committee" / "disagreement-register.yaml",
                run_path / "committee" / "veto-table.yaml",
                run_path / "harness" / "collaboration-harness.yaml",
                run_path / "decision" / "final-decision-memo.yaml",
            ],
            committee_check["ok"],
            details=committee_check,
        ),
        requirement(
            "runtime.portfolio_outcome_loop_matches_manifest",
            "portfolio_outcome",
            "Runtime watchlist, Paper Portfolio, review, and outcome tracking loop matches the OS manifest summary and preserves paper-only no-broker boundaries.",
            [
                run_path / "system" / "operating-system-manifest.yaml",
                run_path / "portfolio" / "watchlist.yaml",
                run_path / "portfolio" / "paper-portfolio.yaml",
                run_path / "portfolio" / "portfolio-review.yaml",
                run_path / "portfolio" / "outcome-tracking.yaml",
            ],
            portfolio_outcome_check["ok"],
            details=portfolio_outcome_check,
        ),
    ]


def build_requirements(root: Path, agents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    agent_ids = [agent["id"] for agent in agents if agent.get("id")]
    prd_coverage = module_prd_coverage(root)
    return [
        requirement(
            "prd.overall_and_modules_exist",
            "prd",
            "Overall PRD and all core module PRDs exist with implementation-ready scope, artifacts, acceptance criteria, and safety boundaries.",
            [root / "docs/prd/overall-prd.md", root / "docs/prd/modules"],
            prd_coverage["ok"],
            details=prd_coverage,
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
            "agents.agent_cards_expose_machine_auditable_os_policies",
            "agent_identity",
            "Every agent card exposes explicit machine-auditable Memory Policy, Tool Policy, Evolution Contract, and Safety Boundary sections.",
            [root / "specs/agents/agent-cards"],
            all(agent_card_has_machine_auditable_policy_sections(root, aid) for aid in agent_ids),
            details={"missing_sections": missing_agent_card_machine_policy_sections(root, agent_ids)},
        ),
        requirement(
            "agents.skill_files_expose_machine_auditable_execution_policies",
            "agent_skills_tools_memory",
            "Every agent skill exposes explicit machine-auditable Tool Use Policy, Memory Policy, Evolution Policy, and Safety Boundary sections.",
            [root / "specs/skills"],
            all(agent_skill_has_machine_auditable_policy_sections(root, aid) for aid in agent_ids),
            details={"missing_sections": missing_agent_skill_machine_policy_sections(root, agent_ids)},
        ),
        requirement(
            "agents.agent_maturity_contracts_are_differentiated",
            "agent_identity",
            "Each Agent card and Skill define differentiated edge, market regimes, anti-patterns, capability benchmarks, growth roadmap, role-specific context compression, and evolution candidate rules.",
            [root / "specs/agents/agent-cards", root / "specs/skills"],
            agent_maturity_contracts_ok(root, agents),
            details=agent_maturity_contract_mismatches(root, agents),
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


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def exists(path: Path) -> bool:
    return path.exists()


def dir_has_files(path: Path, pattern: str) -> bool:
    return path.is_dir() and any(path.glob(pattern))


REQUIRED_MODULE_PRDS = {
    "agent-system": ["agent", "profile", "memory", "harness", "acceptance criteria", "real_trade_allowed=false"],
    "codex-runtime": ["codex", "cli", "run.yaml", "model_records", "acceptance criteria", "broker_integration=disabled"],
    "context-management": ["contextpack", "thread_memory_summary", "contextbudgetmanifest", "acceptance criteria", "real_trade_allowed=false"],
    "evidence-system": ["evidencepack", "source quality", "public", "acceptance criteria", "broker_integration=disabled"],
    "harness": ["evaluationreport", "agent-harness.yaml", "capability-regression.yaml", "acceptance criteria", "real_trade_allowed=false"],
    "learning-evolution": ["evolutiongate", "capability", "failure pattern", "acceptance criteria", "broker_integration=disabled"],
    "investment-committee": ["investment committee", "debate", "risk", "decision memo", "acceptance criteria", "real_trade_allowed=false"],
    "portfolio-outcome": ["watchlist", "paper portfolio", "outcome tracking", "market replay", "acceptance criteria", "broker_integration=disabled"],
    "tooling-data-adapters": ["tool adapter", "read-only", "fixture", "source", "acceptance criteria", "real_trade_allowed=false"],
    "system-governance-audit": ["operating-system-manifest", "system audit", "schema", "strict", "acceptance criteria", "broker_integration=disabled"],
}


def module_prd_coverage(root: Path) -> dict[str, Any]:
    modules_dir = root / "docs" / "prd" / "modules"
    present_modules = sorted(path.name.removesuffix("-prd.md") for path in modules_dir.glob("*-prd.md")) if modules_dir.exists() else []
    missing_modules = sorted(set(REQUIRED_MODULE_PRDS) - set(present_modules))
    weak_modules: list[dict[str, Any]] = []
    for module, needles in REQUIRED_MODULE_PRDS.items():
        path = modules_dir / f"{module}-prd.md"
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8").lower()
        missing_needles = [needle for needle in needles if needle.lower() not in text]
        if missing_needles:
            weak_modules.append({"module": module, "missing_terms": missing_needles})
    overall = root / "docs" / "prd" / "overall-prd.md"
    overall_ok = overall.exists() and all(term in overall.read_text(encoding="utf-8").lower() for term in ["v1", "agent", "harness", "evolutiongate", "不构成投资建议"])
    return {
        "ok": overall_ok and not missing_modules and not weak_modules,
        "overall_prd_present": overall.exists(),
        "overall_prd_implementation_ready": overall_ok,
        "required_modules": sorted(REQUIRED_MODULE_PRDS),
        "present_modules": present_modules,
        "missing_modules": missing_modules,
        "weak_modules": weak_modules,
    }


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


AGENT_CARD_MACHINE_POLICY_SECTIONS = [
    "## Memory Policy",
    "## Tool Policy",
    "## Evolution Contract",
    "## Safety Boundary",
]


AGENT_SKILL_MACHINE_POLICY_SECTIONS = [
    "## Tool Use Policy",
    "## Memory Policy",
    "## Evolution Policy",
    "## Safety Boundary",
]


def agent_card_has_machine_auditable_policy_sections(root: Path, agent_id: str) -> bool:
    return not missing_machine_sections(root / f"specs/agents/agent-cards/{agent_id}/agent.md", AGENT_CARD_MACHINE_POLICY_SECTIONS)


def missing_agent_card_machine_policy_sections(root: Path, agent_ids: list[str]) -> dict[str, list[str]]:
    missing = {
        aid: missing_machine_sections(root / f"specs/agents/agent-cards/{aid}/agent.md", AGENT_CARD_MACHINE_POLICY_SECTIONS)
        for aid in agent_ids
    }
    return {aid: sections for aid, sections in missing.items() if sections}


def agent_skill_has_machine_auditable_policy_sections(root: Path, agent_id: str) -> bool:
    return not missing_machine_sections(root / f"specs/skills/{agent_id}/SKILL.md", AGENT_SKILL_MACHINE_POLICY_SECTIONS)


def missing_agent_skill_machine_policy_sections(root: Path, agent_ids: list[str]) -> dict[str, list[str]]:
    missing = {
        aid: missing_machine_sections(root / f"specs/skills/{aid}/SKILL.md", AGENT_SKILL_MACHINE_POLICY_SECTIONS)
        for aid in agent_ids
    }
    return {aid: sections for aid, sections in missing.items() if sections}


def missing_machine_sections(path: Path, required_sections: list[str]) -> list[str]:
    if not path.exists():
        return [path.name]
    text = path.read_text(encoding="utf-8")
    return [section for section in required_sections if section not in text]


AGENT_MATURITY_CARD_REQUIRED = [
    "## Differentiated Edge",
    "## Preferred Market Regimes",
    "## Anti-Patterns and Failure Modes",
    "## Capability Benchmarks",
    "## Growth Roadmap",
    "## Role-Specific Context Compression",
    "edge_signature:",
    "preferred_regimes:",
    "adverse_regimes:",
    "benchmark_id:",
    "minimum_pass_score:",
    "regression_tests:",
    "context_priority_order:",
    "must_preserve_context:",
    "compression_loss_budget:",
    "growth_stage_v1:",
    "promotion_criteria:",
    "rollback_triggers:",
    "Research / watchlist / Paper Portfolio only",
    "real_trade_allowed=false",
    "broker_integration=disabled",
]


AGENT_MATURITY_SKILL_REQUIRED = [
    "## Role-Specific Benchmark",
    "## Context Compression Recipe",
    "## Evolution Candidate Rules",
    "benchmark_id:",
    "minimum_pass_score:",
    "regression_tests:",
    "context_priority_order:",
    "must_preserve_context:",
    "compression_loss_budget:",
    "Research / watchlist / Paper Portfolio only",
    "real_trade_allowed=false",
    "broker_integration=disabled",
]


def agent_maturity_contracts_ok(root: Path, agents: list[dict[str, Any]]) -> bool:
    details = agent_maturity_contract_mismatches(root, agents)
    return not details["missing_by_agent"] and details["unique_edge_signatures"] >= max(details["agent_count"] - 1, 0)


def agent_maturity_contract_mismatches(root: Path, agents: list[dict[str, Any]]) -> dict[str, Any]:
    missing_by_agent: dict[str, list[str]] = {}
    edge_signatures: list[str] = []
    for agent in agents:
        aid = agent.get("id", "")
        issues: list[str] = []
        card_path = root / f"specs/agents/agent-cards/{aid}/agent.md"
        skill_path = root / f"specs/skills/{aid}/SKILL.md"
        if not card_path.exists():
            issues.append("missing_agent_card")
            card_text = ""
        else:
            card_text = card_path.read_text(encoding="utf-8")
            issues.extend(f"agent_card_missing:{needle}" for needle in AGENT_MATURITY_CARD_REQUIRED if needle not in card_text)
            signature_lines = [line.strip() for line in card_text.splitlines() if line.strip().startswith("- edge_signature:")]
            if len(signature_lines) != 1:
                issues.append("agent_card_edge_signature_count")
            else:
                edge_signatures.append(signature_lines[0])
        if not skill_path.exists():
            issues.append("missing_skill")
            skill_text = ""
        else:
            skill_text = skill_path.read_text(encoding="utf-8")
            issues.extend(f"skill_missing:{needle}" for needle in AGENT_MATURITY_SKILL_REQUIRED if needle not in skill_text)
        combined = card_text + "\n" + skill_text
        for safety in ["Research / watchlist / Paper Portfolio only", "real_trade_allowed=false", "broker_integration=disabled"]:
            if safety not in combined:
                issues.append(f"safety_missing:{safety}")
        if issues:
            missing_by_agent[aid or "unknown"] = issues
    return {
        "agent_count": len(agents),
        "edge_signature_count": len(edge_signatures),
        "unique_edge_signatures": len(set(edge_signatures)),
        "required_unique_edge_signatures": max(len(agents) - 1, 0),
        "missing_by_agent": missing_by_agent,
    }


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


def committee_debate_risk_decision_loop_check(readiness: Any, disagreements: Any, vetoes: Any, collaboration: Any, memo: Any) -> dict[str, Any]:
    mismatches: list[str] = []
    if not all(isinstance(item, dict) for item in [readiness, disagreements, vetoes, collaboration, memo]):
        return {"ok": False, "mismatches": ["committee_or_decision_artifact_missing_or_invalid"]}
    checks = readiness.get("checks", {}) or {}
    disagreement_items = disagreements.get("items", []) or []
    veto_items = vetoes.get("items", []) or []
    active_vetoes = [item for item in veto_items if isinstance(item, dict) and item.get("status") == "active"]
    memo_collaboration = memo.get("collaboration_summary", {}) or {}
    final_decision = memo.get("final_decision", {}) or {}

    if checks.get("bear_challenge_present") is not True:
        mismatches.append(f"bear_challenge_present: expected True, got {checks.get('bear_challenge_present')!r}")
    if checks.get("risk_veto_or_cap_present") is not True:
        mismatches.append(f"risk_veto_or_cap_present: expected True, got {checks.get('risk_veto_or_cap_present')!r}")
    if checks.get("disagreement_preserved") is not True:
        mismatches.append(f"disagreement_preserved: expected True, got {checks.get('disagreement_preserved')!r}")
    if checks.get("paper_only") is not True:
        mismatches.append(f"paper_only: expected True, got {checks.get('paper_only')!r}")
    if len(disagreement_items) < 1 or disagreements.get("disagreement_count") != len(disagreement_items):
        mismatches.append(f"disagreement_count: expected >=1 and equal to items, got count={disagreements.get('disagreement_count')!r}, items={len(disagreement_items)}")
    if len(active_vetoes) < 1 or vetoes.get("veto_count") != len(veto_items):
        mismatches.append(f"active_veto_count: expected >=1 and veto_count equal to items, got active={len(active_vetoes)}, count={vetoes.get('veto_count')!r}, items={len(veto_items)}")
    if not any(isinstance(item, dict) and item.get("owner_agent") == "bear_debater" for item in disagreement_items):
        mismatches.append("bear_debater_disagreement: missing")
    if not any(isinstance(item, dict) and item.get("owner_agent") == "risk_manager" for item in active_vetoes):
        mismatches.append("risk_manager_active_veto: missing")
    compare_value(mismatches, "collaboration.disagreement_count", collaboration.get("disagreement_count"), len(disagreement_items))
    compare_value(mismatches, "collaboration.veto_count", collaboration.get("veto_count"), len(veto_items))
    compare_value(mismatches, "memo.collaboration_summary.disagreement_count", memo_collaboration.get("disagreement_count"), len(disagreement_items))
    compare_value(mismatches, "memo.collaboration_summary.veto_count", memo_collaboration.get("veto_count"), len(veto_items))
    if memo_collaboration.get("overall_score", 0) < 80:
        mismatches.append(f"memo.collaboration_summary.overall_score: expected >=80, got {memo_collaboration.get('overall_score')!r}")
    if final_decision.get("label") not in {"continue_research", "needs_more_evidence", "watchlist_only", "reject"}:
        mismatches.append(f"final_decision.label: unexpected {final_decision.get('label')!r}")
    position_range = str(final_decision.get("hypothetical_position_range", ""))
    if "0" not in position_range or ("观察" not in position_range and "Paper" not in position_range and "paper" not in position_range):
        mismatches.append(f"final_decision.hypothetical_position_range: expected paper/watchlist cap, got {position_range!r}")
    if readiness.get("real_trade_allowed") is not False:
        mismatches.append(f"readiness.real_trade_allowed: expected False, got {readiness.get('real_trade_allowed')!r}")
    if vetoes.get("real_trade_allowed") is not False:
        mismatches.append(f"veto_table.real_trade_allowed: expected False, got {vetoes.get('real_trade_allowed')!r}")
    if disagreements.get("real_trade_allowed") is not False:
        mismatches.append(f"disagreement_register.real_trade_allowed: expected False, got {disagreements.get('real_trade_allowed')!r}")
    if collaboration.get("real_trade_allowed") is not False:
        mismatches.append(f"collaboration.real_trade_allowed: expected False, got {collaboration.get('real_trade_allowed')!r}")
    if collaboration.get("broker_integration") not in {False, "disabled"}:
        mismatches.append(f"collaboration.broker_integration: expected disabled, got {collaboration.get('broker_integration')!r}")
    return {
        "ok": not mismatches,
        "mismatches": mismatches,
        "bear_challenge_present": checks.get("bear_challenge_present") is True,
        "risk_veto_or_cap_present": checks.get("risk_veto_or_cap_present") is True,
        "disagreement_count": len(disagreement_items),
        "active_veto_count": len(active_vetoes),
        "collaboration_score": collaboration.get("overall_score", 0),
        "memo_label": final_decision.get("label"),
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def operating_system_manifest_portfolio_outcome_check(manifest: Any, watchlist: Any, paper: Any, review: Any, outcome: Any) -> dict[str, Any]:
    mismatches: list[str] = []
    if not all(isinstance(item, dict) for item in [manifest, watchlist, paper, review, outcome]):
        return {"ok": False, "mismatches": ["manifest_or_portfolio_artifact_missing_or_invalid"]}
    summary = manifest.get("portfolio_outcome_summary", {}) or {}
    if not isinstance(summary, dict):
        return {"ok": False, "mismatches": ["portfolio_outcome_summary_missing_or_invalid"]}

    watch_items = watchlist.get("items", []) if isinstance(watchlist.get("items", []), list) else []
    actions = paper.get("actions", []) if isinstance(paper.get("actions", []), list) else []
    attribution_items = review.get("attribution_items", []) if isinstance(review.get("attribution_items", []), list) else []
    learning_candidates = review.get("learning_candidates", []) if isinstance(review.get("learning_candidates", []), list) else []
    outcome_results = outcome.get("results", []) if isinstance(outcome.get("results", []), list) else []
    expected_controls = sorted({
        str(control)
        for source in [review, outcome]
        for control in (source.get("controls", []) if isinstance(source.get("controls", []), list) else [])
        if control
    })

    compare_value(mismatches, "portfolio_outcome_summary.watchlist_items", summary.get("watchlist_items"), len(watch_items))
    compare_value(mismatches, "portfolio_outcome_summary.paper_actions", summary.get("paper_actions"), len(actions))
    compare_value(mismatches, "portfolio_outcome_summary.reviewed_actions", summary.get("reviewed_actions"), int(review.get("reviewed_actions", 0) or 0))
    compare_value(mismatches, "portfolio_outcome_summary.attribution_items", summary.get("attribution_items"), len(attribution_items))
    compare_value(mismatches, "portfolio_outcome_summary.learning_candidates", summary.get("learning_candidates"), len(learning_candidates))
    compare_value(mismatches, "portfolio_outcome_summary.outcome_status", summary.get("outcome_status"), str(outcome.get("outcome_status", "missing_market_replay")))
    compare_value(mismatches, "portfolio_outcome_summary.actions_evaluated", summary.get("actions_evaluated"), int(outcome.get("actions_evaluated", 0) or 0))
    compare_value(mismatches, "portfolio_outcome_summary.actions_missing_market_replay", summary.get("actions_missing_market_replay"), int(outcome.get("actions_missing_market_replay", 0) or 0))
    compare_value(mismatches, "portfolio_outcome_summary.outcome_quality_score", summary.get("outcome_quality_score"), float(outcome.get("outcome_quality_score", 0) or 0))
    compare_value(mismatches, "portfolio_outcome_summary.real_trade_violations", summary.get("real_trade_violations"), int(review.get("real_trade_violations", 0) or 0))
    compare_value(mismatches, "portfolio_outcome_summary.review_verdict", summary.get("review_verdict"), str(review.get("review_verdict", "missing_portfolio_review")))
    compare_value(mismatches, "portfolio_outcome_summary.controls", summary.get("controls"), expected_controls)

    required_controls = {
        "paper_only",
        "no_broker_integration",
        "no_real_trade_action",
        "review_before_upgrade",
        "market_replay_is_not_trade_signal",
        "outcome_tracking_requires_fixture_or_adapter",
    }
    missing_controls = sorted(required_controls - set(expected_controls))
    if missing_controls:
        mismatches.append(f"portfolio_outcome_summary.controls: missing {missing_controls!r}")
    if summary.get("real_trade_allowed") is not False:
        mismatches.append(f"portfolio_outcome_summary.real_trade_allowed: expected False, got {summary.get('real_trade_allowed')!r}")
    if summary.get("broker_integration") != "disabled":
        mismatches.append(f"portfolio_outcome_summary.broker_integration: expected 'disabled', got {summary.get('broker_integration')!r}")

    constraints = paper.get("constraints", {}) if isinstance(paper.get("constraints", {}), dict) else {}
    if constraints.get("real_trade_allowed") is not False:
        mismatches.append(f"paper_portfolio.constraints.real_trade_allowed: expected False, got {constraints.get('real_trade_allowed')!r}")
    if constraints.get("broker_integration") != "disabled":
        mismatches.append(f"paper_portfolio.constraints.broker_integration: expected 'disabled', got {constraints.get('broker_integration')!r}")
    for idx, action in enumerate(actions):
        if not isinstance(action, dict):
            mismatches.append(f"paper_portfolio.actions[{idx}]: expected object")
            continue
        if action.get("real_trade_allowed") is not False:
            mismatches.append(f"paper_portfolio.actions[{idx}].real_trade_allowed: expected False, got {action.get('real_trade_allowed')!r}")
    for idx, item in enumerate(attribution_items):
        if not isinstance(item, dict):
            mismatches.append(f"portfolio_review.attribution_items[{idx}]: expected object")
            continue
        if item.get("real_trade_violation") not in {False, None}:
            mismatches.append(f"portfolio_review.attribution_items[{idx}].real_trade_violation: expected False, got {item.get('real_trade_violation')!r}")
        if item.get("broker_integration") != "disabled":
            mismatches.append(f"portfolio_review.attribution_items[{idx}].broker_integration: expected 'disabled', got {item.get('broker_integration')!r}")
    for idx, result in enumerate(outcome_results):
        if not isinstance(result, dict):
            mismatches.append(f"outcome_tracking.results[{idx}]: expected object")
            continue
        if result.get("real_trade_allowed") is not False:
            mismatches.append(f"outcome_tracking.results[{idx}].real_trade_allowed: expected False, got {result.get('real_trade_allowed')!r}")
        if result.get("broker_integration") != "disabled":
            mismatches.append(f"outcome_tracking.results[{idx}].broker_integration: expected 'disabled', got {result.get('broker_integration')!r}")
    if int(review.get("real_trade_violations", 0) or 0) != 0:
        mismatches.append(f"portfolio_review.real_trade_violations: expected 0, got {review.get('real_trade_violations')!r}")

    return {
        "ok": not mismatches,
        "mismatches": mismatches,
        "watchlist_items": len(watch_items),
        "paper_actions": len(actions),
        "reviewed_actions": int(review.get("reviewed_actions", 0) or 0),
        "attribution_items": len(attribution_items),
        "learning_candidates": len(learning_candidates),
        "outcome_status": str(outcome.get("outcome_status", "missing_market_replay")),
        "actions_evaluated": int(outcome.get("actions_evaluated", 0) or 0),
        "actions_missing_market_replay": int(outcome.get("actions_missing_market_replay", 0) or 0),
        "outcome_quality_score": float(outcome.get("outcome_quality_score", 0) or 0),
        "real_trade_violations": int(review.get("real_trade_violations", 0) or 0),
        "review_verdict": str(review.get("review_verdict", "missing_portfolio_review")),
        "controls": expected_controls,
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


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


def runtime_agent_maturity_contract_check(run_path: Path, agent_ids: list[str]) -> dict[str, Any]:
    missing_by_agent: dict[str, list[str]] = {}
    edge_signatures: list[str] = []
    required_output_fields = [
        "edge_signature",
        "capability_benchmark_id",
        "skill_benchmark_id",
        "minimum_pass_score",
        "context_priority_order",
        "must_preserve_context",
        "compression_loss_budget",
        "evolution_approval_route",
    ]
    for agent_id in agent_ids:
        if not agent_id:
            continue
        issues: list[str] = []
        context = load_yaml(run_path / "context" / f"{agent_id}.context-pack.yaml", {})
        output = load_yaml(run_path / "agent_work" / f"{agent_id}.structured.yaml", {})
        card_contract = (((context.get("agent_card") or {}).get("maturity_contract") or {}) if isinstance(context, dict) else {})
        skill_contract = ((context.get("skill_contract") or {}) if isinstance(context, dict) else {})
        output_contract = ((output.get("maturity_contract") or {}) if isinstance(output, dict) else {})
        if not card_contract.get("differentiated_edge", {}).get("edge_signature"):
            issues.append("context_agent_card_missing_edge_signature")
        if not card_contract.get("capability_benchmarks", {}).get("benchmark_id"):
            issues.append("context_agent_card_missing_capability_benchmark")
        if not card_contract.get("context_compression", {}).get("context_priority_order"):
            issues.append("context_agent_card_missing_context_priority_order")
        if not skill_contract.get("role_specific_benchmark", {}).get("benchmark_id"):
            issues.append("context_skill_missing_role_specific_benchmark")
        if not skill_contract.get("context_compression_recipe", {}).get("must_preserve_context"):
            issues.append("context_skill_missing_compression_recipe")
        if not skill_contract.get("evolution_candidate_rules", {}).get("approval_route"):
            issues.append("context_skill_missing_evolution_rules")
        for field in required_output_fields:
            if not output_contract.get(field):
                issues.append(f"structured_output_missing:{field}")
        if output_contract.get("real_trade_allowed") is not False:
            issues.append("structured_output_real_trade_not_disabled")
        if output_contract.get("broker_integration") != "disabled":
            issues.append("structured_output_broker_not_disabled")
        if output_contract.get("edge_signature"):
            edge_signatures.append(str(output_contract["edge_signature"]))
        if issues:
            missing_by_agent[agent_id] = issues
    return {
        "ok": not missing_by_agent and len(set(edge_signatures)) >= max(len([aid for aid in agent_ids if aid]) - 1, 0),
        "checked_agents": len([aid for aid in agent_ids if aid]),
        "edge_signature_count": len(edge_signatures),
        "unique_edge_signatures": len(set(edge_signatures)),
        "required_unique_edge_signatures": max(len([aid for aid in agent_ids if aid]) - 1, 0),
        "missing_by_agent": missing_by_agent,
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def expected_agent_maturity_summary(run_path: Path, agent_ids: list[str]) -> dict[str, Any]:
    clean_agent_ids = [aid for aid in agent_ids if aid]
    missing_by_agent: dict[str, list[str]] = {}
    edge_signatures: list[str] = []
    maturity_contracts_present = 0
    capability_benchmarks_present = 0
    skill_benchmarks_present = 0
    context_compression_contracts_present = 0
    evolution_candidate_rules_present = 0
    minimum_scores: list[int] = []
    for agent_id in clean_agent_ids:
        issues: list[str] = []
        context = load_yaml(run_path / "context" / f"{agent_id}.context-pack.yaml", {})
        output = load_yaml(run_path / "agent_work" / f"{agent_id}.structured.yaml", {})
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
        "agents_evaluated": len(clean_agent_ids),
        "maturity_contracts_present": maturity_contracts_present,
        "edge_signature_count": len(edge_signatures),
        "unique_edge_signatures": len(set(edge_signatures)),
        "required_unique_edge_signatures": max(len(clean_agent_ids) - 1, 0),
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


def operating_system_manifest_agent_maturity_check(manifest: Any, run_path: Path, agent_ids: list[str]) -> dict[str, Any]:
    mismatches: list[str] = []
    if not isinstance(manifest, dict):
        return {"ok": False, "mismatches": ["manifest_missing_or_invalid"]}
    summary = manifest.get("agent_maturity_contract_summary", {}) or {}
    if not isinstance(summary, dict) or not summary:
        return {"ok": False, "mismatches": ["agent_maturity_contract_summary_missing_or_invalid"]}
    expected = expected_agent_maturity_summary(run_path, agent_ids)
    for field, expected_value in expected.items():
        compare_value(mismatches, f"agent_maturity_contract_summary.{field}", summary.get(field), expected_value)
    if summary.get("unique_edge_signatures", 0) < summary.get("required_unique_edge_signatures", 0):
        mismatches.append(
            "agent_maturity_contract_summary.unique_edge_signatures: "
            f"expected >= required_unique_edge_signatures, got {summary.get('unique_edge_signatures')!r} < {summary.get('required_unique_edge_signatures')!r}"
        )
    if summary.get("minimum_pass_score_floor", 0) < 80:
        mismatches.append(f"agent_maturity_contract_summary.minimum_pass_score_floor: expected >=80, got {summary.get('minimum_pass_score_floor')!r}")
    controls = set(summary.get("controls", []) or [])
    for required_control in ["differentiated_agent_edge_required", "role_specific_benchmark_required", "role_specific_context_compression_required", "evolution_candidate_rules_required"]:
        if required_control not in controls:
            mismatches.append(f"agent_maturity_contract_summary.controls: missing {required_control}")
    if summary.get("real_trade_allowed") is not False:
        mismatches.append(f"agent_maturity_contract_summary.real_trade_allowed: expected False, got {summary.get('real_trade_allowed')!r}")
    if summary.get("broker_integration") != "disabled":
        mismatches.append(f"agent_maturity_contract_summary.broker_integration: expected 'disabled', got {summary.get('broker_integration')!r}")
    return {"ok": not mismatches, "mismatches": mismatches, **expected}


def parse_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


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
        "evolution_learning_summary": manifest.get("evolution_learning_summary", {}),
        "source_provenance_summary": manifest.get("source_provenance_summary", {}),
        "context_management_summary": manifest.get("context_management_summary", {}),
        "tool_runtime_summary": manifest.get("tool_runtime_summary", {}),
        "portfolio_outcome_summary": manifest.get("portfolio_outcome_summary", {}),
        "agent_performance_summary": manifest.get("agent_performance_summary", {}),
        "agent_governance_summary": manifest.get("agent_governance_summary", {}),
        "evaluation_summary": manifest.get("evaluation_summary", {}),
        "real_trade_allowed": manifest.get("real_trade_allowed"),
        "broker_integration": manifest.get("broker_integration"),
    }


def operating_system_manifest_context_management_check(manifest: Any, agent_harness: Any) -> dict[str, Any]:
    mismatches: list[str] = []
    if not all(isinstance(item, dict) for item in [manifest, agent_harness]):
        return {"ok": False, "mismatches": ["manifest_or_agent_harness_missing_or_invalid"]}
    summary = manifest.get("context_management_summary", {}) or {}
    results = agent_harness.get("agent_results", []) or []
    context_docs = [row.get("context_management_quality", {}) for row in results if isinstance(row, dict) and isinstance(row.get("context_management_quality", {}), dict)]
    thread_docs = [row.get("thread_memory_summary_quality", {}) for row in results if isinstance(row, dict) and isinstance(row.get("thread_memory_summary_quality", {}), dict)]
    aggregate = agent_harness.get("aggregate_scores", {}) or {}
    compare_value(mismatches, "context_management_summary.overall", summary.get("overall"), aggregate.get("context_management_quality", 0))
    compare_value(mismatches, "context_management_summary.agents_evaluated", summary.get("agents_evaluated"), len(context_docs))
    compare_value(mismatches, "context_management_summary.budget_manifest_present", summary.get("budget_manifest_present"), sum(1 for item in context_docs if item.get("budget_manifest_present")))
    compare_value(mismatches, "context_management_summary.token_budget_respected", summary.get("token_budget_respected"), sum(1 for item in context_docs if item.get("token_budget_respected")))
    compare_value(mismatches, "context_management_summary.loss_accounting_present", summary.get("loss_accounting_present"), sum(1 for item in context_docs if item.get("loss_accounting_present")))
    compare_value(mismatches, "context_management_summary.role_specific_compression_present", summary.get("role_specific_compression_present"), sum(1 for item in context_docs if item.get("role_specific_compression_present")))
    compare_value(mismatches, "context_management_summary.evidence_loss_auditable", summary.get("evidence_loss_auditable"), sum(1 for item in context_docs if item.get("evidence_loss_auditable")))
    compare_value(mismatches, "context_management_summary.excluded_items", summary.get("excluded_items"), sum(int(item.get("excluded_items", 0) or 0) for item in context_docs))
    compare_value(mismatches, "context_management_summary.estimated_tokens_before", summary.get("estimated_tokens_before"), sum(int(item.get("estimated_tokens_before", 0) or 0) for item in context_docs))
    compare_value(mismatches, "context_management_summary.estimated_tokens_after", summary.get("estimated_tokens_after"), sum(int(item.get("estimated_tokens_after", 0) or 0) for item in context_docs))
    compare_value(mismatches, "context_management_summary.drop_reasons", summary.get("drop_reasons"), sorted({reason for item in context_docs for reason in item.get("drop_reasons", []) if reason}))
    compare_value(mismatches, "context_management_summary.thread_memory_summary_quality", summary.get("thread_memory_summary_quality"), aggregate.get("thread_memory_summary", 0))
    compare_value(mismatches, "context_management_summary.thread_summaries_available", summary.get("thread_summaries_available"), sum(1 for item in thread_docs if item.get("available")))
    compare_value(mismatches, "context_management_summary.thread_summary_signals_present", summary.get("thread_summary_signals_present"), sum(1 for item in thread_docs if item.get("summary_signal_present")))
    controls = set(summary.get("controls", []) or [])
    for required_control in ["role_specific_compression", "loss_accounting_required", "token_budget_respected", "thread_summary_is_retrieval_input_only"]:
        if required_control not in controls:
            mismatches.append(f"context_management_summary.controls: missing {required_control}")
    if summary.get("real_trade_allowed") is not False:
        mismatches.append(f"context_management_summary.real_trade_allowed: expected False, got {summary.get('real_trade_allowed')!r}")
    if summary.get("broker_integration") != "disabled":
        mismatches.append(f"context_management_summary.broker_integration: expected 'disabled', got {summary.get('broker_integration')!r}")
    return {"ok": not mismatches, "mismatches": mismatches}


def operating_system_manifest_tool_runtime_check(manifest: Any, runtime_report: Any, ledger_rows: list[dict[str, Any]], evidence_doc: Any) -> dict[str, Any]:
    mismatches: list[str] = []
    if not all(isinstance(item, dict) for item in [manifest, runtime_report, evidence_doc]):
        return {"ok": False, "mismatches": ["manifest_or_tool_runtime_artifact_missing_or_invalid"]}
    summary = manifest.get("tool_runtime_summary", {}) or {}
    if not isinstance(summary, dict):
        return {"ok": False, "mismatches": ["tool_runtime_summary_missing_or_invalid"]}

    evidence_items = evidence_doc.get("evidence_items", []) if isinstance(evidence_doc.get("evidence_items", []), list) else []
    succeeded_rows = [row for row in ledger_rows if isinstance(row, dict) and row.get("status") == "succeeded"]
    blocked_rows = [row for row in ledger_rows if isinstance(row, dict) and row.get("status") == "blocked"]
    adapters_called = sorted({str(row.get("adapter_id")) for row in succeeded_rows if row.get("adapter_id")})
    source_tier_counts = count_by(evidence_items, "source_tier")

    compare_value(mismatches, "tool_runtime_summary.runtime_id", summary.get("runtime_id"), str(runtime_report.get("runtime_id", "")))
    compare_value(mismatches, "tool_runtime_summary.tool_runtime_quality_score", summary.get("tool_runtime_quality_score"), float(runtime_report.get("tool_runtime_quality_score", 0) or 0))
    compare_value(mismatches, "tool_runtime_summary.tool_call_count", summary.get("tool_call_count"), int(runtime_report.get("tool_call_count", 0) or 0))
    compare_value(mismatches, "tool_runtime_summary.succeeded_tool_calls", summary.get("succeeded_tool_calls"), int(runtime_report.get("succeeded_tool_calls", 0) or 0))
    compare_value(mismatches, "tool_runtime_summary.blocked_tool_calls", summary.get("blocked_tool_calls"), int(runtime_report.get("blocked_tool_calls", 0) or 0))
    compare_value(mismatches, "tool_runtime_summary.evidence_items_created", summary.get("evidence_items_created"), int(runtime_report.get("evidence_items_created", 0) or 0))
    compare_value(mismatches, "tool_runtime_summary.adapters_called", summary.get("adapters_called"), runtime_report.get("adapters_called", []))
    compare_value(mismatches, "tool_runtime_summary.source_tier_counts", summary.get("source_tier_counts"), runtime_report.get("source_tier_counts", {}))
    compare_value(mismatches, "tool_runtime_summary.ledger_path", summary.get("ledger_path"), str(runtime_report.get("ledger_path", "")))
    compare_value(mismatches, "tool_runtime_summary.evidence_path", summary.get("evidence_path"), str(runtime_report.get("evidence_path", "")))
    compare_value(mismatches, "tool_runtime_summary.blocking_issue_count", summary.get("blocking_issue_count"), len(runtime_report.get("blocking_issues", []) or []))
    compare_value(mismatches, "tool_runtime_summary.controls", summary.get("controls"), runtime_report.get("controls", []))
    compare_value(mismatches, "tool_runtime.ledger_row_count", len(ledger_rows), int(runtime_report.get("tool_call_count", 0) or 0))
    compare_value(mismatches, "tool_runtime.succeeded_ledger_rows", len(succeeded_rows), int(runtime_report.get("succeeded_tool_calls", 0) or 0))
    compare_value(mismatches, "tool_runtime.blocked_ledger_rows", len(blocked_rows), int(runtime_report.get("blocked_tool_calls", 0) or 0))
    compare_value(mismatches, "tool_runtime.evidence_item_count", len(evidence_items), int(runtime_report.get("evidence_items_created", 0) or 0))
    compare_value(mismatches, "tool_runtime.adapters_called", adapters_called, runtime_report.get("adapters_called", []))
    compare_value(mismatches, "tool_runtime.source_tier_counts", source_tier_counts, runtime_report.get("source_tier_counts", {}))

    controls = set(runtime_report.get("controls", []) or [])
    for required_control in ["all_fixture_tools_are_read_only", "tool_call_ledger_required", "every_tool_result_maps_to_evidence_item", "no_order_or_broker_adapter"]:
        if required_control not in controls:
            mismatches.append(f"tool_runtime_summary.controls: missing {required_control}")
    linked_evidence_ids = {str(eid) for row in succeeded_rows for eid in (row.get("evidence_item_ids", []) if isinstance(row.get("evidence_item_ids", []), list) else [])}
    evidence_ids = {str(item.get("id")) for item in evidence_items if isinstance(item, dict) and item.get("id")}
    missing_evidence_links = sorted(linked_evidence_ids - evidence_ids)
    if missing_evidence_links:
        mismatches.append(f"tool_runtime.ledger_evidence_links_missing: {missing_evidence_links!r}")
    for idx, row in enumerate(ledger_rows):
        if not isinstance(row, dict):
            mismatches.append(f"tool_call_ledger[{idx}]: expected object")
            continue
        if row.get("permission_level") != "read_only_analysis":
            mismatches.append(f"tool_call_ledger[{idx}].permission_level: expected 'read_only_analysis', got {row.get('permission_level')!r}")
        if row.get("real_trade_allowed") is not False:
            mismatches.append(f"tool_call_ledger[{idx}].real_trade_allowed: expected False, got {row.get('real_trade_allowed')!r}")
        if row.get("broker_integration") != "disabled":
            mismatches.append(f"tool_call_ledger[{idx}].broker_integration: expected 'disabled', got {row.get('broker_integration')!r}")
    if summary.get("real_trade_allowed") is not False:
        mismatches.append(f"tool_runtime_summary.real_trade_allowed: expected False, got {summary.get('real_trade_allowed')!r}")
    if summary.get("broker_integration") != "disabled":
        mismatches.append(f"tool_runtime_summary.broker_integration: expected 'disabled', got {summary.get('broker_integration')!r}")
    if runtime_report.get("real_trade_allowed") is not False:
        mismatches.append(f"tool_runtime_report.real_trade_allowed: expected False, got {runtime_report.get('real_trade_allowed')!r}")
    if runtime_report.get("broker_integration") != "disabled":
        mismatches.append(f"tool_runtime_report.broker_integration: expected 'disabled', got {runtime_report.get('broker_integration')!r}")

    return {
        "ok": not mismatches,
        "mismatches": mismatches,
        "tool_call_count": int(runtime_report.get("tool_call_count", 0) or 0),
        "ledger_row_count": len(ledger_rows),
        "succeeded_tool_calls": int(runtime_report.get("succeeded_tool_calls", 0) or 0),
        "blocked_tool_calls": int(runtime_report.get("blocked_tool_calls", 0) or 0),
        "evidence_items_created": int(runtime_report.get("evidence_items_created", 0) or 0),
        "tool_runtime_evidence_items": len(evidence_items),
        "adapters_called": runtime_report.get("adapters_called", []),
        "source_tier_counts": runtime_report.get("source_tier_counts", {}),
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def operating_system_manifest_source_provenance_check(manifest: Any, registry: Any, ingestion: Any, evidence: Any) -> dict[str, Any]:
    mismatches: list[str] = []
    if not all(isinstance(item, dict) for item in [manifest, registry, ingestion, evidence]):
        return {"ok": False, "mismatches": ["manifest_or_source_provenance_report_missing_or_invalid"]}
    summary = manifest.get("source_provenance_summary", {}) or {}
    source_coverage = evidence.get("source_coverage", {}) or {}
    boundary_policy = registry.get("boundary_policy", {}) or {}
    compare_value(mismatches, "source_provenance_summary.registry_source_count", summary.get("registry_source_count"), registry.get("source_count", 0))
    compare_value(mismatches, "source_provenance_summary.registry_source_tier_counts", summary.get("registry_source_tier_counts"), registry.get("source_tier_counts", {}))
    compare_value(mismatches, "source_provenance_summary.registry_source_type_counts", summary.get("registry_source_type_counts"), registry.get("source_type_counts", {}))
    compare_value(mismatches, "source_provenance_summary.ingested_sources", summary.get("ingested_sources"), ingestion.get("ingested_sources", 0))
    compare_value(mismatches, "source_provenance_summary.quarantined_sources", summary.get("quarantined_sources"), ingestion.get("quarantined_sources", 0))
    compare_value(mismatches, "source_provenance_summary.pattern_candidates", summary.get("pattern_candidates"), ingestion.get("pattern_candidates", 0))
    compare_value(mismatches, "source_provenance_summary.evolution_candidates", summary.get("evolution_candidates"), ingestion.get("evolution_candidates", 0))
    compare_value(mismatches, "source_provenance_summary.direct_trade_signal_blocked", summary.get("direct_trade_signal_blocked"), ingestion.get("direct_trade_signal_blocked", False))
    compare_value(mismatches, "source_provenance_summary.copyright_violation_blocked", summary.get("copyright_violation_blocked"), ingestion.get("copyright_violation_blocked", False))
    compare_value(mismatches, "source_provenance_summary.all_patterns_start_quarantined", summary.get("all_patterns_start_quarantined"), ingestion.get("all_patterns_start_quarantined", False))
    compare_value(mismatches, "source_provenance_summary.evidence_item_count", summary.get("evidence_item_count"), source_coverage.get("total_items", len(evidence.get("evidence_items", []) or [])))
    compare_value(mismatches, "source_provenance_summary.evidence_tier_counts", summary.get("evidence_tier_counts"), source_coverage.get("tier_counts", {}))
    compare_value(mismatches, "source_provenance_summary.evidence_type_counts", summary.get("evidence_type_counts"), source_coverage.get("type_counts", {}))
    compare_value(mismatches, "source_provenance_summary.primary_fact_evidence_items", summary.get("primary_fact_evidence_items"), source_coverage.get("primary_fact_items", 0))
    compare_value(mismatches, "source_provenance_summary.low_tier_evidence_items", summary.get("low_tier_evidence_items"), source_coverage.get("low_tier_items", 0))
    compare_value(mismatches, "source_provenance_summary.methodology_sources_are_hypothesis_only", summary.get("methodology_sources_are_hypothesis_only"), boundary_policy.get("methodology_sources_are_hypothesis_generators", False))
    compare_value(mismatches, "source_provenance_summary.primary_evidence_required_for_company_conclusions", summary.get("primary_evidence_required_for_company_conclusions"), boundary_policy.get("primary_evidence_required_for_company_conclusions", False))
    if summary.get("real_trade_allowed") is not False:
        mismatches.append(f"source_provenance_summary.real_trade_allowed: expected False, got {summary.get('real_trade_allowed')!r}")
    if summary.get("broker_integration") != "disabled":
        mismatches.append(f"source_provenance_summary.broker_integration: expected 'disabled', got {summary.get('broker_integration')!r}")
    if boundary_policy.get("methodology_sources_are_hypothesis_generators") is not True:
        mismatches.append("source_registry.boundary_policy.methodology_sources_are_hypothesis_generators: expected True")
    if boundary_policy.get("primary_evidence_required_for_company_conclusions") is not True:
        mismatches.append("source_registry.boundary_policy.primary_evidence_required_for_company_conclusions: expected True")
    return {"ok": not mismatches, "mismatches": mismatches}


def operating_system_manifest_evolution_learning_check(
    manifest: Any,
    agent_learning: Any,
    agent_learning_rows: list[dict[str, Any]],
    source_ingestion: Any,
    evolution_rows: list[dict[str, Any]],
    gate_rows: list[dict[str, Any]],
    accepted_rows: list[dict[str, Any]],
    quarantine_rows: list[dict[str, Any]],
    rejected_rows: list[dict[str, Any]],
    memory_writeback: Any,
    capability_rows: list[dict[str, Any]],
    capability_summary: Any,
    capability_regression: Any,
) -> dict[str, Any]:
    mismatches: list[str] = []
    if not isinstance(manifest, dict):
        return {"ok": False, "mismatches": ["manifest_missing_or_invalid"]}
    summary = manifest.get("evolution_learning_summary", {}) or {}
    if not isinstance(summary, dict):
        return {"ok": False, "mismatches": ["evolution_learning_summary_missing_or_invalid"]}
    agent_learning = agent_learning if isinstance(agent_learning, dict) else {}
    source_ingestion = source_ingestion if isinstance(source_ingestion, dict) else {}
    memory_writeback = memory_writeback if isinstance(memory_writeback, dict) else {}
    capability_summary = capability_summary if isinstance(capability_summary, dict) else {}
    capability_regression = capability_regression if isinstance(capability_regression, dict) else {}

    expected_accepted = len(accepted_rows) if accepted_rows else sum(1 for row in gate_rows if row.get("decision") == "accept")
    expected_quarantined = len(quarantine_rows) if quarantine_rows else sum(1 for row in gate_rows if row.get("decision") == "quarantine")
    expected_rejected = len(rejected_rows) if rejected_rows else sum(1 for row in gate_rows if row.get("decision") == "reject")
    expected_controls = set(summary.get("controls", []) or [])

    compare_value(mismatches, "evolution_learning_summary.agent_learning_candidates", summary.get("agent_learning_candidates"), int(agent_learning.get("candidate_count", len(agent_learning_rows)) or 0))
    compare_value(mismatches, "evolution_learning_summary.new_agent_learning_candidates", summary.get("new_agent_learning_candidates"), int(agent_learning.get("new_candidates", 0) or 0))
    compare_value(mismatches, "evolution_learning_summary.merged_to_evolution", summary.get("merged_to_evolution"), int(agent_learning.get("merged_to_evolution", 0) or 0))
    compare_value(mismatches, "evolution_learning_summary.agent_learning_route_counts", summary.get("agent_learning_route_counts"), agent_learning.get("route_counts", {}))
    compare_value(mismatches, "evolution_learning_summary.source_ingestion_candidates", summary.get("source_ingestion_candidates"), int(source_ingestion.get("evolution_candidates", 0) or 0))
    compare_value(mismatches, "evolution_learning_summary.source_quarantined", summary.get("source_quarantined"), int(source_ingestion.get("quarantined_sources", 0) or 0))
    compare_value(mismatches, "evolution_learning_summary.evolution_candidates", summary.get("evolution_candidates"), len(evolution_rows))
    compare_value(mismatches, "evolution_learning_summary.gate_results", summary.get("gate_results"), len(gate_rows))
    compare_value(mismatches, "evolution_learning_summary.accepted", summary.get("accepted"), expected_accepted)
    compare_value(mismatches, "evolution_learning_summary.quarantined", summary.get("quarantined"), expected_quarantined)
    compare_value(mismatches, "evolution_learning_summary.rejected", summary.get("rejected"), expected_rejected)
    compare_value(mismatches, "evolution_learning_summary.memory_writes", summary.get("memory_writes"), int(memory_writeback.get("memory_writes", 0) or 0))
    compare_value(mismatches, "evolution_learning_summary.memory_agent_writes", summary.get("memory_agent_writes"), memory_writeback.get("agent_writes", {}))
    compare_value(mismatches, "evolution_learning_summary.capability_candidates", summary.get("capability_candidates"), len(capability_rows))
    compare_value(mismatches, "evolution_learning_summary.approved_candidates", summary.get("approved_candidates"), int(capability_summary.get("approved_candidates", 0) or 0))
    compare_value(mismatches, "evolution_learning_summary.pending_human_apply", summary.get("pending_human_apply"), int(capability_summary.get("pending_human_apply", 0) or 0))
    compare_value(mismatches, "evolution_learning_summary.regression_status", summary.get("regression_status"), str(capability_regression.get("regression_status", "missing")))
    compare_value(mismatches, "evolution_learning_summary.regression_candidates_total", summary.get("regression_candidates_total"), int(capability_regression.get("candidates_total", 0) or 0))
    compare_value(mismatches, "evolution_learning_summary.regression_passed_candidates", summary.get("regression_passed_candidates"), int(capability_regression.get("passed_candidates", 0) or 0))
    compare_value(mismatches, "evolution_learning_summary.regression_blocked_candidates", summary.get("regression_blocked_candidates"), int(capability_regression.get("blocked_candidates", 0) or 0))

    required_controls = {
        "quarantine_before_adoption",
        "evolution_gate_required",
        "capability_regression_required",
        "human_approval_before_apply",
        "no_direct_profile_mutation",
        "no_direct_skill_mutation",
        "no_direct_tool_mutation",
        "no_real_trade_action",
        "broker_integration_disabled",
    }
    missing_controls = sorted(required_controls - expected_controls)
    if missing_controls:
        mismatches.append(f"evolution_learning_summary.controls: missing {missing_controls!r}")
    if summary.get("direct_profile_mutation_allowed") is not False:
        mismatches.append(f"evolution_learning_summary.direct_profile_mutation_allowed: expected False, got {summary.get('direct_profile_mutation_allowed')!r}")
    if summary.get("direct_skill_mutation_allowed") is not False:
        mismatches.append(f"evolution_learning_summary.direct_skill_mutation_allowed: expected False, got {summary.get('direct_skill_mutation_allowed')!r}")
    if summary.get("direct_tool_mutation_allowed") is not False:
        mismatches.append(f"evolution_learning_summary.direct_tool_mutation_allowed: expected False, got {summary.get('direct_tool_mutation_allowed')!r}")
    if summary.get("real_trade_allowed") is not False:
        mismatches.append(f"evolution_learning_summary.real_trade_allowed: expected False, got {summary.get('real_trade_allowed')!r}")
    if summary.get("broker_integration") != "disabled":
        mismatches.append(f"evolution_learning_summary.broker_integration: expected 'disabled', got {summary.get('broker_integration')!r}")

    for idx, row in enumerate(gate_rows):
        controls = set(row.get("controls", []) or []) if isinstance(row, dict) else set()
        if "no_direct_profile_mutation" not in controls:
            mismatches.append(f"evolution_gate_results[{idx}].controls: missing no_direct_profile_mutation")
        if "no_real_trade_action" not in controls:
            mismatches.append(f"evolution_gate_results[{idx}].controls: missing no_real_trade_action")
        if isinstance(row, dict) and row.get("adoption_route") in {"managed_capability_pending_human_apply", "skill_patch_pending_human_apply"} and row.get("memory_write_allowed") is True:
            mismatches.append(f"evolution_gate_results[{idx}].memory_write_allowed: capability candidate must wait for human apply")
    for idx, row in enumerate(capability_rows):
        if not isinstance(row, dict):
            mismatches.append(f"capability_candidates[{idx}]: expected object")
            continue
        if row.get("application_status") == "applied":
            mismatches.append(f"capability_candidates[{idx}].application_status: expected pending/blocked before human apply, got 'applied'")

    return {
        "ok": not mismatches,
        "mismatches": mismatches,
        "agent_learning_candidates": int(agent_learning.get("candidate_count", len(agent_learning_rows)) or 0),
        "evolution_candidates": len(evolution_rows),
        "gate_results": len(gate_rows),
        "accepted": expected_accepted,
        "quarantined": expected_quarantined,
        "rejected": expected_rejected,
        "memory_writes": int(memory_writeback.get("memory_writes", 0) or 0),
        "capability_candidates": len(capability_rows),
        "pending_human_apply": int(capability_summary.get("pending_human_apply", 0) or 0),
        "regression_candidates_total": int(capability_regression.get("candidates_total", 0) or 0),
        "controls": sorted(expected_controls),
        "direct_profile_mutation_allowed": False,
        "direct_skill_mutation_allowed": False,
        "direct_tool_mutation_allowed": False,
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def operating_system_manifest_agent_capability_ledger_check(manifest: Any, ledger: Any) -> dict[str, Any]:
    mismatches: list[str] = []
    if not isinstance(manifest, dict) or not isinstance(ledger, dict):
        return {"ok": False, "mismatches": ["manifest_or_agent_capability_ledger_missing_or_invalid"]}
    summary = manifest.get("agent_capability_ledger_summary", {}) or {}
    if not isinstance(summary, dict) or not summary:
        return {"ok": False, "mismatches": ["agent_capability_ledger_summary_missing_or_invalid"]}
    expected = expected_agent_capability_ledger_summary(ledger)
    for field, expected_value in expected.items():
        compare_value(mismatches, f"agent_capability_ledger_summary.{field}", summary.get(field), expected_value)
    controls = set(summary.get("controls", []) or [])
    for required_control in [
        "capability_lifecycle_per_agent_required",
        "capability_regression_before_apply",
        "human_approval_before_apply",
        "no_real_trade_action",
        "broker_integration_disabled",
    ]:
        if required_control not in controls:
            mismatches.append(f"agent_capability_ledger_summary.controls: missing {required_control}")
    if summary.get("candidate_count", 0) != len(ledger_candidate_ids(ledger)):
        mismatches.append(
            "agent_capability_ledger_summary.candidate_count: "
            f"expected unique ledger candidate count {len(ledger_candidate_ids(ledger))!r}, got {summary.get('candidate_count')!r}"
        )
    for agent_id, agent in (ledger.get("agents", {}) or {}).items():
        if not isinstance(agent, dict):
            mismatches.append(f"agent_capability_ledger.agents.{agent_id}: expected object")
            continue
        if agent.get("real_trade_allowed") is not False:
            mismatches.append(f"agent_capability_ledger.agents.{agent_id}.real_trade_allowed: expected False, got {agent.get('real_trade_allowed')!r}")
        if agent.get("broker_integration") != "disabled":
            mismatches.append(f"agent_capability_ledger.agents.{agent_id}.broker_integration: expected 'disabled', got {agent.get('broker_integration')!r}")
        if agent.get("candidate_count", 0) > 0 and not agent.get("candidate_ids"):
            mismatches.append(f"agent_capability_ledger.agents.{agent_id}.candidate_ids: missing")
    if ledger.get("real_trade_allowed") is not False:
        mismatches.append(f"agent_capability_ledger.real_trade_allowed: expected False, got {ledger.get('real_trade_allowed')!r}")
    if ledger.get("broker_integration") != "disabled":
        mismatches.append(f"agent_capability_ledger.broker_integration: expected 'disabled', got {ledger.get('broker_integration')!r}")
    if summary.get("real_trade_allowed") is not False:
        mismatches.append(f"agent_capability_ledger_summary.real_trade_allowed: expected False, got {summary.get('real_trade_allowed')!r}")
    if summary.get("broker_integration") != "disabled":
        mismatches.append(f"agent_capability_ledger_summary.broker_integration: expected 'disabled', got {summary.get('broker_integration')!r}")
    return {"ok": not mismatches, "mismatches": mismatches, **expected}


def expected_agent_capability_ledger_summary(ledger: dict[str, Any]) -> dict[str, Any]:
    agents = ledger.get("agents", {}) if isinstance(ledger.get("agents", {}), dict) else {}
    return {
        "candidate_count": int(ledger.get("candidate_count", 0) or 0),
        "agent_count": int(ledger.get("agent_count", 0) or 0),
        "pending_human_apply": int(ledger.get("pending_human_apply", 0) or 0),
        "applied": int(ledger.get("applied", 0) or 0),
        "blocked_regression": int(ledger.get("blocked_regression", 0) or 0),
        "needs_more_evidence": int(ledger.get("needs_more_evidence", 0) or 0),
        "not_applicable": int(ledger.get("not_applicable", 0) or 0),
        "agents": sorted(str(agent_id) for agent_id in agents),
        "controls": ledger.get("controls", []) if isinstance(ledger.get("controls", []), list) else [],
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def ledger_candidate_ids(ledger: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    agents = ledger.get("agents", {}) if isinstance(ledger.get("agents", {}), dict) else {}
    for agent in agents.values():
        if not isinstance(agent, dict):
            continue
        for candidate_id in agent.get("candidate_ids", []) or []:
            if candidate_id:
                ids.add(str(candidate_id))
    return ids


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
