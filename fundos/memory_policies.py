from __future__ import annotations

from pathlib import Path
from typing import Any

from fundos.io import REPO_ROOT, read_yaml, write_yaml

MEMORY_POLICY_VERSION = "0.1.0"
FORBIDDEN_MEMORY_WRITES = [
    "core_profile",
    "tool_permissions",
    "risk_limits",
    "broker_credentials",
    "personal_financial_advice",
    "unverified_facts_as_memory",
]
HARNESS_CHECKS = [
    "memory_policy_loaded",
    "retrieval_contract_declared",
    "evolution_gate_required",
    "reversible_ledger_required",
    "forbidden_memory_writes_respected",
    "no_real_trade_action",
    "broker_integration_disabled",
]
PERSONALITY_STABILITY_GUARDS = [
    "Do not change name, role, mandate, investment style, or risk preference through memory writes.",
    "Use memory to add lessons, failure patterns, and retrieval hints; never mutate profile identity.",
    "Contradictory lessons must be preserved and routed to review instead of overwritten.",
]


def role_family(role: str, category: str = "") -> str:
    if "Trader" in role:
        return "trader"
    if "Risk" in role:
        return "risk"
    if "Bear" in role:
        return "bear"
    if "Evaluation" in role:
        return "evaluation"
    if "Learning" in role:
        return "learning"
    if "Archivist" in role:
        return "archivist"
    if "FundManager" in role:
        return "fund_manager"
    if "Company" in role or "Governance" in role or category == "company":
        return "company"
    if "Analyst" in role or category == "research":
        return "industry"
    return "operator"


def family_spec(family: str) -> dict[str, Any]:
    specs = {
        "trader": {"max_memory_items": 5, "max_age_days": 120, "retrieval_tags": ["market_state", "entry_exit", "position_sizing", "drawdown", "failure_pattern"], "compression": "trigger_failure_table"},
        "risk": {"max_memory_items": 7, "max_age_days": 240, "retrieval_tags": ["risk", "drawdown", "liquidity", "kill_criteria", "evidence_inflation"], "compression": "risk_lesson_matrix"},
        "bear": {"max_memory_items": 7, "max_age_days": 240, "retrieval_tags": ["bear_case", "contradiction", "failed_thesis", "crowding", "missing_evidence"], "compression": "assumption_failure_table"},
        "evaluation": {"max_memory_items": 8, "max_age_days": 365, "retrieval_tags": ["harness", "regression", "role_drift", "tool_quality", "context_quality"], "compression": "scorecard_delta_table"},
        "learning": {"max_memory_items": 8, "max_age_days": 365, "retrieval_tags": ["source_tier", "pattern", "evolution_gate", "case_replay", "anti_overfit"], "compression": "pattern_validation_card"},
        "archivist": {"max_memory_items": 8, "max_age_days": 365, "retrieval_tags": ["run_lineage", "case_card", "review_task", "failure_pattern", "artifact"], "compression": "case_lineage_table"},
        "fund_manager": {"max_memory_items": 8, "max_age_days": 365, "retrieval_tags": ["committee", "decision_quality", "risk_reward", "weakest_link", "kill_criteria"], "compression": "committee_lesson_brief"},
        "company": {"max_memory_items": 6, "max_age_days": 240, "retrieval_tags": ["filing", "financial_quality", "governance", "valuation", "company_failure"], "compression": "company_lesson_table"},
        "industry": {"max_memory_items": 6, "max_age_days": 240, "retrieval_tags": ["industry", "chokepoint", "policy_to_demand", "research_gap", "adoption_curve"], "compression": "chokepoint_lesson_table"},
        "operator": {"max_memory_items": 6, "max_age_days": 365, "retrieval_tags": ["workflow", "routing", "handoff", "artifact", "blocking_issue"], "compression": "workflow_lesson_table"},
    }
    return specs[family]


def policy_template(agent: dict[str, Any]) -> dict[str, Any]:
    family = role_family(agent.get("role", ""), agent.get("category", ""))
    spec = family_spec(family)
    agent_ns = f"memory/agents/{agent['id']}"
    read_namespaces = [agent_ns, "memory/organization/failure-pattern-library", "memory/organization/evolution-ledger"]
    if family in {"fund_manager", "evaluation", "learning", "archivist", "operator"}:
        read_namespaces.append("memory/organization")
    return {
        "version": MEMORY_POLICY_VERSION,
        "agent_id": agent["id"],
        "role": agent["role"],
        "memory_policy_id": f"{agent['id']}_memory_policy",
        "role_family": family,
        "read_namespaces": read_namespaces,
        "write_namespaces": [agent_ns],
        "retrieval_contract": {
            "max_memory_items": spec["max_memory_items"],
            "max_age_days": spec["max_age_days"],
            "retrieval_tags": spec["retrieval_tags"],
            "require_source_basis": True,
            "require_evidence_or_candidate_id": True,
            "stale_memory_action": "mark_stale_and_route_to_review",
            "contradiction_action": "preserve_both_and_create_review_task",
        },
        "writeback_rules": {
            "requires_evolution_gate": True,
            "requires_reversible_ledger": True,
            "requires_source_basis": True,
            "requires_regression_or_replay": True,
            "allow_direct_profile_mutation": False,
            "allow_direct_skill_mutation": False,
            "allow_direct_tool_permission_mutation": False,
        },
        "forbidden_memory_writes": FORBIDDEN_MEMORY_WRITES,
        "staleness_policy": {
            "default_max_age_days": spec["max_age_days"],
            "market_state_memory_max_age_days": min(60, spec["max_age_days"]),
            "requires_refresh_when_regime_changes": True,
            "stale_label": "stale_requires_revalidation",
        },
        "context_compression": {
            "style": spec["compression"],
            "must_preserve": ["candidate_id", "run_id", "source_basis", "decision", "failure_pattern", "contradictions"],
            "drop_rules": ["drop_prose_without_evidence_id", "drop_duplicate_low_value_lessons"],
        },
        "personality_stability_guards": PERSONALITY_STABILITY_GUARDS,
        "harness_checks": HARNESS_CHECKS,
        "real_trade_allowed": False,
        "broker_integration": False,
    }


def load_memory_policy(agent: dict[str, Any]) -> dict[str, Any]:
    agent_id = agent["id"]
    rel = f"specs/agents/memory-policies/{agent_id}.yaml"
    path = REPO_ROOT / rel
    if path.exists():
        loaded = read_yaml(path) or {}
        policy = policy_template(agent)
        policy.update(loaded)
        policy["source_path"] = rel
        policy["available"] = True
        return policy
    policy = policy_template(agent)
    policy["source_path"] = rel
    policy["available"] = False
    return policy


def write_default_memory_policies(root: Path | None = None) -> int:
    base = root or REPO_ROOT
    roster = read_yaml(base / "specs" / "agents" / "default-roster.yaml")
    out_dir = base / "specs" / "agents" / "memory-policies"
    out_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for agent in roster["agents"]:
        path = out_dir / f"{agent['id']}.yaml"
        if not path.exists():
            write_yaml(path, policy_template(agent))
            count += 1
    return count
