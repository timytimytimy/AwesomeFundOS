from __future__ import annotations

from pathlib import Path
from typing import Any

from fundos.io import REPO_ROOT, read_yaml, write_yaml

CONTEXT_POLICY_VERSION = "0.1.0"
DEFAULT_MUST_PRESERVE = ["evidence_ids", "claim_ids", "contradictions", "missing_evidence", "source_tiers", "low_confidence_claims"]
DEFAULT_EXCLUSIONS = ["real_trade_orders", "personal_financial_advice", "uncited_high_confidence_claims", "brokerage_instructions"]
DEFAULT_HARNESS_CHECKS = ["source_policy_match", "context_budget_respected", "must_preserve_satisfied", "role_focus_alignment", "no_real_trade_action"]


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


def policy_template(agent: dict[str, Any]) -> dict[str, Any]:
    family = role_family(agent.get("role", ""), agent.get("category", ""))
    spec = family_spec(family)
    return {
        "version": CONTEXT_POLICY_VERSION,
        "agent_id": agent["id"],
        "role": agent["role"],
        "context_policy_id": agent.get("context_policy_id"),
        "role_family": family,
        "token_budget": spec["token_budget"],
        "max_context_items": spec["max_context_items"],
        "preferred_context_tags": spec["preferred_context_tags"],
        "preferred_source_tiers": ["tier_1_primary_fact", "tier_2_canonical_framework", "tier_3_verified_public_practitioner"],
        "preferred_claim_types": ["fact", "inference", "hypothesis", "opinion"],
        "must_preserve": DEFAULT_MUST_PRESERVE,
        "compression_style": spec["compression_style"],
        "priority_lenses": spec["priority_lenses"],
        "required_focus": spec["required_focus"],
        "exclusion_rules": DEFAULT_EXCLUSIONS + spec.get("exclusion_rules", []),
        "evidence_selection": {
            "match_mode": "claim_relevance_tag_overlap",
            "include_governance_agents_all_claims": family in {"operator", "fund_manager", "evaluation", "archivist"},
            "prefer_primary_sources": True,
            "cap_low_tier_confidence": True,
            "kol_and_books_as_methodology_only": True,
        },
        "harness_checks": DEFAULT_HARNESS_CHECKS,
        "real_trade_allowed": False,
        "broker_integration": False,
    }


def family_spec(family: str) -> dict[str, Any]:
    specs = {
        "trader": {
            "token_budget": 6500,
            "max_context_items": 6,
            "preferred_context_tags": ["trading", "risk"],
            "compression_style": ["trigger_table", "price_volume_summary", "risk_boundary_table"],
            "priority_lenses": ["market_state", "price_volume", "trigger", "invalidation", "liquidity", "position_sizing"],
            "required_focus": ["量价结构", "买卖触发条件", "仓位纪律"],
            "exclusion_rules": ["company_list_without_trigger", "theme_story_without_price_volume"],
        },
        "risk": {
            "token_budget": 7500,
            "max_context_items": 8,
            "preferred_context_tags": ["risk", "company", "trading"],
            "compression_style": ["risk_matrix", "scenario_table", "kill_criteria_table"],
            "priority_lenses": ["downside", "liquidity", "concentration", "valuation_fragility", "tail_risk"],
            "required_focus": ["下行风险", "证据等级", "仓位上限"],
        },
        "bear": {
            "token_budget": 7500,
            "max_context_items": 8,
            "preferred_context_tags": ["bear_case", "risk", "company"],
            "compression_style": ["assumption_attack_table", "contradiction_table", "alternative_explanation_table"],
            "priority_lenses": ["core_assumptions", "contradictions", "missing_evidence", "failed_analogies", "crowding"],
            "required_focus": ["攻击核心假设", "替代解释", "证据缺口"],
        },
        "evaluation": {
            "token_budget": 8500,
            "max_context_items": 10,
            "preferred_context_tags": ["industry", "company", "trading", "risk", "bear_case"],
            "compression_style": ["scorecard", "artifact_checklist", "blocking_issue_table"],
            "priority_lenses": ["artifact_completeness", "schema_validity", "role_consistency", "source_boundaries", "regression_gates"],
            "required_focus": ["评分依据", "阻断项", "回归测试"],
        },
        "learning": {
            "token_budget": 8000,
            "max_context_items": 10,
            "preferred_context_tags": ["industry", "company", "trading", "risk", "bear_case"],
            "compression_style": ["source_registry_table", "pattern_card", "validation_gate_table"],
            "priority_lenses": ["source_tier", "allowed_learning_output", "pattern_scope", "anti_overfit", "validation_gate"],
            "required_focus": ["来源等级", "可学习模式", "验证门槛"],
        },
        "archivist": {
            "token_budget": 7000,
            "max_context_items": 10,
            "preferred_context_tags": ["industry", "company", "trading", "risk", "bear_case"],
            "compression_style": ["case_card", "lineage_table", "review_task_list"],
            "priority_lenses": ["run_lineage", "artifact_paths", "failure_patterns", "review_tasks", "case_replay"],
            "required_focus": ["归档路径", "复盘任务", "案例复现"],
        },
        "fund_manager": {
            "token_budget": 9000,
            "max_context_items": 12,
            "preferred_context_tags": ["industry", "company", "trading", "risk", "bear_case"],
            "compression_style": ["committee_memo", "decision_alternative_table", "weakest_link_table"],
            "priority_lenses": ["committee_disagreement", "weakest_evidence_link", "risk_reward", "position_range", "kill_criteria"],
            "required_focus": ["综合判断", "证据追溯", "流程完整性"],
        },
        "company": {
            "token_budget": 7600,
            "max_context_items": 8,
            "preferred_context_tags": ["company", "risk"],
            "compression_style": ["company_evidence_table", "financial_quality_table", "valuation_sensitivity_table"],
            "priority_lenses": ["filings", "financial_quality", "revenue_exposure", "customer_evidence", "governance", "valuation"],
            "required_focus": ["财报公告", "产品和订单", "治理风险"],
        },
        "industry": {
            "token_budget": 7600,
            "max_context_items": 8,
            "preferred_context_tags": ["industry", "company"],
            "compression_style": ["supply_chain_map", "chokepoint_table", "research_gap_table"],
            "priority_lenses": ["industry_structure", "supply_chain_chokepoint", "policy_to_demand", "adoption_stage", "primary_validation"],
            "required_focus": ["产业链", "chokepoint", "需求验证"],
        },
        "operator": {
            "token_budget": 7000,
            "max_context_items": 10,
            "preferred_context_tags": ["industry", "company", "trading", "risk", "bear_case"],
            "compression_style": ["routing_table", "dag_state", "artifact_checklist"],
            "priority_lenses": ["task_intent", "agent_staffing", "artifact_routing", "dag_state", "handoff_blockers"],
            "required_focus": ["综合判断", "证据追溯", "流程完整性"],
        },
    }
    return specs[family]


def load_context_policy(agent: dict[str, Any]) -> dict[str, Any]:
    agent_id = agent["id"]
    rel = f"specs/agents/context-policies/{agent_id}.yaml"
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


def write_default_context_policies(root: Path | None = None) -> int:
    base = root or REPO_ROOT
    roster = read_yaml(base / "specs" / "agents" / "default-roster.yaml")
    out_dir = base / "specs" / "agents" / "context-policies"
    out_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for agent in roster["agents"]:
        path = out_dir / f"{agent['id']}.yaml"
        if not path.exists():
            write_yaml(path, policy_template(agent))
            count += 1
    return count
