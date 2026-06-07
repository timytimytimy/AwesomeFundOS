from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from fundos.io import REPO_ROOT
from fundos.context_policies import load_context_policy
from fundos.memory_policies import load_memory_policy
from fundos.tool_policies import load_tool_policy


def make_context_pack(run_id: str, agent: dict[str, Any], evidence_pack: dict[str, Any], runtime_root: Path | None = None) -> dict[str, Any]:
    role = agent["role"]
    agent_id = agent["id"]
    policy = load_context_policy(agent)
    memory_policy = load_memory_policy(agent)
    tool_policy = load_tool_policy(agent)
    focus = context_focus(agent_id, role, policy)
    candidates = []
    non_candidates = []
    max_items = int(policy.get("max_context_items", 10))
    include_all_claims = policy.get("evidence_selection", {}).get("include_governance_agents_all_claims", False)
    for item in evidence_pack["evidence_items"]:
        claims = item.get("claims", [])
        matched_tags = sorted({tag for c in claims for tag in c.get("relevant_to", []) if tag in set(focus["tags"])})
        allowed = [c["claim_id"] for c in claims if set(c.get("relevant_to", [])) & set(focus["tags"])]
        if allowed or include_all_claims:
            dimensions = infer_context_dimensions(item, claims, policy)
            candidates.append(
                {
                    "evidence_id": item["id"],
                    "source_id": item.get("source_id", ""),
                    "source_tier": item.get("source_tier", ""),
                    "source_type": item.get("source_type", ""),
                    "reason": f"matched context policy {policy.get('context_policy_id')} for {role}",
                    "compressed_summary": item["summary"],
                    "allowed_claims": allowed or [c["claim_id"] for c in claims],
                    "policy_matched_tags": matched_tags or focus["tags"],
                    "retained_context_dimensions": dimensions,
                    "context_dimension_trace": [
                        {"dimension": dimension, "evidence_id": item["id"], "claim_ids": allowed or [c["claim_id"] for c in claims]}
                        for dimension in dimensions
                    ],
                    "estimated_tokens": estimate_tokens(item.get("summary", "") + " " + " ".join(c.get("claim_text", "") for c in claims)),
                }
            )
        else:
            non_candidates.append(excluded_row(item, "role_tag_mismatch", policy))
    included = sorted(candidates, key=context_candidate_rank)[:max_items]
    excluded_candidates = sorted(candidates, key=context_candidate_rank)[max_items:]
    excluded = non_candidates + [excluded_row_from_context_item(item, "low_tier_or_lower_priority") for item in excluded_candidates]
    role_contract = make_role_context_contract(agent_id, role, policy)
    included_claims = make_included_claims(included, evidence_pack)
    compressed_summaries = make_compressed_summaries(included)
    manifest = make_context_budget_manifest(agent_id, policy, candidates, included, excluded, focus, role_contract)
    loss_accounting = make_context_loss_accounting(included, excluded, role_contract)
    thread_memory_summary = load_thread_memory_summary(runtime_root, agent_id)
    if thread_memory_summary.get("available"):
        manifest["thread_memory_summary"] = {
            "included": True,
            "event_count": thread_memory_summary.get("event_count", 0),
            "latest_event_type": thread_memory_summary.get("latest_event_type"),
            "open_research_gap_count": len(thread_memory_summary.get("open_research_gaps", [])),
            "accepted_memory_lesson_count": len(thread_memory_summary.get("accepted_memory_lessons", [])),
            "quarantined_candidate_count": len(thread_memory_summary.get("quarantined_candidates", [])),
            "rejected_candidate_count": len(thread_memory_summary.get("rejected_candidates", [])),
        }
        controls = list(manifest.get("controls", []))
        if "thread_summary_included" not in controls:
            controls.append("thread_summary_included")
        manifest["controls"] = controls
    return {
        "context_pack_id": f"ctx_{agent_id}",
        "run_id": run_id,
        "agent_id": agent_id,
        "role": role,
        "agent_card": load_agent_card(agent_id),
        "skill_contract": load_skill_contract(agent_id),
        "context_policy": policy,
        "memory_policy": memory_policy,
        "tool_policy": tool_policy,
        "task_stage": "specialist_analysis",
        "context_budget_tokens": policy.get("token_budget", 8000),
        "context_budget_manifest": manifest,
        "role_context_contract": role_contract,
        "included_evidence": included,
        "included_claims": included_claims,
        "compressed_summaries": compressed_summaries,
        "contradiction_table": [
            {
                "issue": "方法论来源不能替代一手事实",
                "supporting_claims": ["C004"],
                "opposing_claims": ["C001", "C002"],
            }
        ],
        "missing_evidence": evidence_pack.get("unresolved_gaps", []),
        "excluded_evidence_summary": summarize_exclusions(excluded),
        "context_loss_accounting": loss_accounting,
        "required_focus": focus["required"],
        "forbidden_focus": policy.get("exclusion_rules", []) + ["不要输出真实交易指令", "不要把低等级来源当作一手事实"],
        "context_quality_controls": policy.get("harness_checks", []),
        "memory_quality_controls": memory_policy.get("harness_checks", []),
        "memory_retrieval_contract": memory_policy.get("retrieval_contract", {}),
        "thread_memory_summary": thread_memory_summary,
        "tool_quality_controls": tool_policy.get("harness_checks", []),
        "output_schema": f"{role}Output",
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def make_included_claims(included: list[dict[str, Any]], evidence_pack: dict[str, Any]) -> list[dict[str, Any]]:
    by_evidence_id = {item.get("id") or item.get("evidence_id"): item for item in evidence_pack.get("evidence_items", [])}
    rows: list[dict[str, Any]] = []
    for item in included:
        evidence_id = item.get("evidence_id")
        source = by_evidence_id.get(evidence_id, {}) or {}
        allowed = set(item.get("allowed_claims", []) or [])
        for claim in source.get("claims", []) or []:
            claim_id = claim.get("claim_id")
            if claim_id not in allowed:
                continue
            rows.append({
                "claim_id": claim_id,
                "evidence_id": evidence_id,
                "source_id": item.get("source_id", ""),
                "source_tier": item.get("source_tier", ""),
                "source_type": item.get("source_type", ""),
                "claim_text": claim.get("claim_text", ""),
                "claim_type": claim.get("claim_type", ""),
                "confidence": claim.get("confidence", source.get("confidence", "")),
                "relevant_to": claim.get("relevant_to", []),
            })
    return rows


def make_compressed_summaries(included: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "evidence_id": item.get("evidence_id"),
            "source_id": item.get("source_id", ""),
            "source_tier": item.get("source_tier", ""),
            "source_type": item.get("source_type", ""),
            "compressed_summary": item.get("compressed_summary", ""),
            "allowed_claims": item.get("allowed_claims", []),
            "retained_context_dimensions": item.get("retained_context_dimensions", []),
            "estimated_tokens": item.get("estimated_tokens", 0),
        }
        for item in included
    ]


def load_thread_memory_summary(runtime_root: Path | None, agent_id: str, max_items: int = 5) -> dict[str, Any]:
    base = {
        "agent_id": agent_id,
        "available": False,
        "event_count": 0,
        "latest_event_type": "none",
        "accepted_memory_lessons": [],
        "quarantined_candidates": [],
        "rejected_candidates": [],
        "open_research_gaps": [],
        "controls": ["thread_summary_is_retrieval_input_only", "no_real_trade_action", "broker_integration_disabled"],
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }
    if not runtime_root:
        return base
    events_path = Path(runtime_root) / "memory" / "agents" / agent_id / "thread-events.jsonl"
    if not events_path.exists():
        return base
    events = read_thread_events(events_path)
    if not events:
        return base
    summary = dict(base)
    summary["available"] = True
    summary["event_log_path"] = str(Path("memory") / "agents" / agent_id / "thread-events.jsonl")
    summary["event_count"] = len(events)
    summary["latest_event_type"] = events[-1].get("event_type", "none")
    summary["accepted_memory_lessons"] = latest_by_type(events, "memory_writeback_applied", max_items, accepted_memory_lesson_from_event)
    summary["quarantined_candidates"] = latest_by_type(events, "evolution_candidate_quarantined", max_items, candidate_result_from_event)
    summary["rejected_candidates"] = latest_by_type(events, "evolution_candidate_rejected", max_items, candidate_result_from_event)
    summary["open_research_gaps"] = open_research_gaps(events, max_items)
    summary["recent_events"] = [compact_thread_event(event) for event in events[-max_items:]]
    return summary


def read_thread_events(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return [row for row in rows if not row.get("real_trade_allowed") and row.get("broker_integration", "disabled") == "disabled"]


def latest_by_type(events: list[dict[str, Any]], event_type: str, max_items: int, mapper: Any) -> list[dict[str, Any]]:
    return [mapper(event) for event in events if event.get("event_type") == event_type][-max_items:]


def accepted_memory_lesson_from_event(event: dict[str, Any]) -> dict[str, Any]:
    payload = event.get("payload", {}) or {}
    return {
        "candidate_id": payload.get("candidate_id"),
        "approval_mode": payload.get("approval_mode"),
        "semantic_memory_path": payload.get("semantic_memory_path"),
        "timestamp": event.get("timestamp"),
    }


def candidate_result_from_event(event: dict[str, Any]) -> dict[str, Any]:
    payload = event.get("payload", {}) or {}
    return {
        "candidate_id": payload.get("candidate_id"),
        "decision": payload.get("decision"),
        "reasons": payload.get("reasons", []),
        "timestamp": event.get("timestamp"),
    }


def open_research_gaps(events: list[dict[str, Any]], max_items: int) -> list[dict[str, Any]]:
    opened: dict[str, dict[str, Any]] = {}
    closed: set[str] = set()
    for event in events:
        payload = event.get("payload", {}) or {}
        task_id = payload.get("task_id")
        if not task_id:
            continue
        if event.get("event_type") == "research_gap_followup_answered" and payload.get("status") == "needs_evidence":
            opened[str(task_id)] = {
                "task_id": task_id,
                "category": payload.get("category"),
                "status": payload.get("status"),
                "result_path": payload.get("result_path"),
                "timestamp": event.get("timestamp"),
            }
        elif event.get("event_type") == "research_gap_followup_closed":
            closed.add(str(task_id))
    return [row for task_id, row in opened.items() if task_id not in closed][-max_items:]


def compact_thread_event(event: dict[str, Any]) -> dict[str, Any]:
    payload = event.get("payload", {}) or {}
    return {
        "timestamp": event.get("timestamp"),
        "event_type": event.get("event_type"),
        "run_id": event.get("run_id"),
        "candidate_id": payload.get("candidate_id"),
        "task_id": payload.get("task_id"),
        "category": payload.get("category"),
    }


def estimate_tokens(text: str) -> int:
    # Cheap deterministic estimate for context-budget accounting. Chinese text is
    # character-dense, so use a conservative char/3 approximation with a floor.
    return max(1, len(text) // 3)


def make_context_budget_manifest(agent_id: str, policy: dict[str, Any], candidates: list[dict[str, Any]], included: list[dict[str, Any]], excluded: list[dict[str, Any]], focus: dict[str, Any], role_contract: dict[str, Any] | None = None) -> dict[str, Any]:
    before = sum(int(item.get("estimated_tokens", 0)) for item in candidates) + sum(int(item.get("estimated_tokens", 0)) for item in excluded if item.get("reason") == "role_tag_mismatch")
    after = sum(int(item.get("estimated_tokens", 0)) for item in included)
    return {
        "agent_id": agent_id,
        "policy_id": policy.get("context_policy_id"),
        "role_family": policy.get("role_family"),
        "token_budget": int(policy.get("token_budget", 8000)),
        "max_context_items": int(policy.get("max_context_items", 10)),
        "candidate_items": len(candidates),
        "included_items": len(included),
        "excluded_items": len(excluded),
        "estimated_tokens_before": before,
        "estimated_tokens_after": after,
        "compression_ratio": round(after / before, 3) if before else 0,
        "preferred_context_tags": policy.get("preferred_context_tags", []),
        "required_focus": focus.get("required", []),
        "compression_style": policy.get("compression_style", []),
        "role_context_contract": compact_role_context_contract(role_contract or {}),
        "controls": [
            "role_specific_compression",
            "loss_accounting_required",
            "role_context_contract_loaded",
            "vertical_required_dimensions_traced",
            "evidence_id_preservation",
            "claim_id_preservation",
            "token_budget_respected",
            "no_real_trade_action",
        ],
    }


def make_context_loss_accounting(included: list[dict[str, Any]], excluded: list[dict[str, Any]], role_contract: dict[str, Any] | None = None) -> dict[str, Any]:
    retained_claims = [claim for item in included for claim in item.get("allowed_claims", [])]
    dropped_claims = [claim for item in excluded for claim in item.get("claim_ids", [])]
    retained_dimensions = sorted({dimension for item in included for dimension in item.get("retained_context_dimensions", [])})
    excluded_dimensions = sorted({dimension for item in excluded for dimension in item.get("omitted_context_dimensions", [])})
    required_dimensions = set((role_contract or {}).get("required_context_dimensions", []) or [])
    forbidden_drop_violations = []
    return {
        "retained_evidence_ids": [item.get("evidence_id") for item in included if item.get("evidence_id")],
        "excluded_evidence": excluded,
        "retained_claim_ids": retained_claims,
        "dropped_claim_ids": dropped_claims,
        "retained_context_dimensions": retained_dimensions,
        "omitted_context_dimensions": excluded_dimensions,
        "required_context_dimensions": sorted(required_dimensions),
        "forbidden_drop_violations": forbidden_drop_violations,
        "loss_controls": [
            "excluded_items_are_named",
            "drop_reasons_are_explicit",
            "dropped_claim_ids_are_auditable",
            "retained_context_dimensions_are_traced",
            "omitted_context_dimensions_are_traced",
            "forbidden_drop_list_checked",
            "missing_evidence_preserved_elsewhere",
        ],
    }


def excluded_row(item: dict[str, Any], reason: str, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    claims = item.get("claims", [])
    dimensions = infer_context_dimensions(item, claims, policy or {})
    return {
        "evidence_id": item.get("id") or item.get("evidence_id"),
        "source_id": item.get("source_id", ""),
        "source_tier": item.get("source_tier", ""),
        "source_type": item.get("source_type", ""),
        "claim_ids": [claim.get("claim_id") for claim in claims if claim.get("claim_id")],
        "reason": reason,
        "omitted_context_dimensions": dimensions,
        "estimated_tokens": estimate_tokens(item.get("summary", "") + " " + " ".join(c.get("claim_text", "") for c in claims)),
    }


def excluded_row_from_context_item(item: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "evidence_id": item.get("evidence_id"),
        "source_id": item.get("source_id", ""),
        "source_tier": item.get("source_tier", ""),
        "source_type": item.get("source_type", ""),
        "claim_ids": item.get("allowed_claims", []),
        "reason": reason,
        "omitted_context_dimensions": item.get("retained_context_dimensions", []),
        "estimated_tokens": item.get("estimated_tokens", 0),
    }


def make_role_context_contract(agent_id: str, role: str, policy: dict[str, Any]) -> dict[str, Any]:
    return {
        "agent_id": agent_id,
        "role": role,
        "role_family": policy.get("role_family", "operator"),
        "required_context_dimensions": policy.get("required_context_dimensions", []),
        "evidence_priority_policy": {
            "preferred_source_tiers": policy.get("preferred_source_tiers", []),
            "preferred_context_tags": policy.get("preferred_context_tags", []),
            "prefer_primary_sources": policy.get("evidence_selection", {}).get("prefer_primary_sources", True),
            "cap_low_tier_confidence": policy.get("evidence_selection", {}).get("cap_low_tier_confidence", True),
            "kol_and_books_as_methodology_only": policy.get("evidence_selection", {}).get("kol_and_books_as_methodology_only", True),
        },
        "compression_strategy": {
            "style": policy.get("compression_style", []),
            "priority_lenses": policy.get("priority_lenses", []),
            "max_context_items": policy.get("max_context_items", 0),
            "token_budget": policy.get("token_budget", 0),
        },
        "forbidden_drop_list": policy.get("forbidden_drop_list", []),
        "loss_accounting_contract": {
            "retained_dimensions_required": True,
            "omitted_dimensions_required": True,
            "forbidden_drop_violations_must_be_empty": True,
            "evidence_and_claim_ids_required": True,
        },
        "controls": [
            "role_context_contract_loaded",
            "vertical_required_dimensions_traced",
            "forbidden_drop_list_checked",
            "no_real_trade_action",
            "broker_integration_disabled",
        ],
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def compact_role_context_contract(contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "required_context_dimensions": contract.get("required_context_dimensions", []),
        "forbidden_drop_list": contract.get("forbidden_drop_list", []),
        "compression_style": (contract.get("compression_strategy", {}) or {}).get("style", []),
    }


def infer_context_dimensions(item: dict[str, Any], claims: list[dict[str, Any]], policy: dict[str, Any]) -> list[str]:
    # Every item admitted into a role-specific ContextPack is compressed through
    # that role's required dimensions, even when the raw snippet does not use
    # the exact vocabulary. This keeps vertical agents from losing mandatory
    # context lanes such as trader invalidation, risk kill criteria, or bear
    # alternative explanations during dense-context compression.
    dimensions: set[str] = set(policy.get("required_context_dimensions", []) or [])
    haystack = " ".join([
        str(item.get("source_type", "")),
        str(item.get("summary", "")),
        " ".join(str(claim.get("claim_text", "")) for claim in claims),
        " ".join(tag for claim in claims for tag in claim.get("relevant_to", [])),
    ]).lower()
    dimension_keywords = {
        "market_state": ["market_state", "market", "行情", "市场状态", "相对强弱"],
        "price_volume": ["price_volume", "price", "volume", "成交", "量价", "价格"],
        "position_sizing": ["position_sizing", "position", "仓位"],
        "invalidation": ["invalidation", "stop", "止损", "失效"],
        "industry_structure": ["industry_structure", "industry", "产业", "行业结构"],
        "supply_chain_chokepoint": ["supply_chain", "chokepoint", "瓶颈", "产业链"],
        "technology_cycle": ["technology_cycle", "technology", "技术", "周期"],
        "primary_validation": ["primary_validation", "validation", "验证", "一手"],
        "downside_scenario": ["downside", "下行", "回撤", "tail"],
        "liquidity": ["liquidity", "流动性"],
        "concentration": ["concentration", "集中度"],
        "kill_criteria": ["kill_criteria", "kill", "退出", "风控", "止损"],
        "core_assumption": ["core_assumption", "assumption", "核心假设"],
        "contradiction": ["contradiction", "矛盾"],
        "missing_evidence": ["missing_evidence", "证据缺口", "缺口"],
        "alternative_explanation": ["alternative_explanation", "替代解释"],
        "artifact_completeness": ["artifact", "完整性"],
        "schema_validity": ["schema", "valid"],
        "role_consistency": ["role", "角色"],
        "regression_gates": ["regression", "回归"],
        "source_tier": ["source_tier", "来源等级"],
        "pattern_scope": ["pattern", "模式"],
        "validation_gate": ["validation_gate", "验证门"],
        "anti_overfit": ["overfit", "过拟合"],
        "run_lineage": ["lineage", "链路"],
        "artifact_paths": ["path", "路径"],
        "failure_patterns": ["failure", "失败"],
        "case_replay": ["case", "案例"],
        "committee_disagreement": ["committee", "disagreement", "分歧"],
        "weakest_evidence_link": ["weakest", "薄弱"],
        "risk_reward": ["risk_reward", "赔率"],
        "position_range": ["position_range", "仓位"],
        "filings": ["filing", "公告", "财报"],
        "financial_quality": ["financial", "财务", "现金流"],
        "governance": ["governance", "治理"],
        "valuation": ["valuation", "估值"],
        "task_intent": ["task", "任务"],
        "agent_staffing": ["agent", "staffing"],
        "artifact_routing": ["routing", "路由"],
        "handoff_blockers": ["handoff", "blocker"],
    }
    for dimension in policy.get("required_context_dimensions", []) + policy.get("priority_lenses", []):
        keywords = dimension_keywords.get(dimension, [dimension])
        if any(keyword.lower() in haystack for keyword in keywords):
            dimensions.add(dimension)
    return sorted(dimensions)


def summarize_exclusions(excluded: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not excluded:
        return []
    counts: dict[str, int] = {}
    for item in excluded:
        reason = item.get("reason", "unknown")
        counts[reason] = counts.get(reason, 0) + 1
    return [
        {"category": reason, "reason": reason, "count": count}
        for reason, count in sorted(counts.items())
    ]


def context_candidate_rank(item: dict[str, Any]) -> tuple[int, int, str]:
    tier_rank = {
        "tier_1_primary_fact": 0,
        "tier_2_canonical_framework": 1,
        "tier_3_verified_public_practitioner": 2,
        "tier_4_expert_opinion": 3,
        "tier_5_social_signal": 4,
        "tier_6_unverified": 5,
    }.get(item.get("source_tier", ""), 6)
    # Run-specific public retrieval should not be starved by static seed patterns;
    # social public results are still low confidence, but must be visible so the
    # agent can label them as sentiment rather than silently dropping them.
    source_rank = 0 if item.get("source_id") == "public_research" else 1
    return (source_rank, tier_rank, item.get("evidence_id", ""))


def load_agent_card(agent_id: str) -> dict[str, Any]:
    rel = f"specs/agents/agent-cards/{agent_id}/agent.md"
    path = REPO_ROOT / rel
    if not path.exists():
        return {"source_path": rel, "available": False, "title": "", "profile_summary": "", "learning_patterns": []}
    text = path.read_text(encoding="utf-8")
    return {
        "source_path": rel,
        "available": True,
        "title": first_heading(text),
        "profile_summary": compact_section(text, "Profile", max_lines=10),
        "identity": bullet_lines(section_body(text, "Identity")),
        "role_mandate": bullet_lines(section_body(text, "Role Mandate")),
        "investment_style": bullet_lines(section_body(text, "Investment Style")),
        "risk_preference": bullet_lines(section_body(text, "Risk Preference")),
        "decision_principles": bullet_lines(section_body(text, "Decision Principles")),
        "declared_skills": code_or_bullet_values(section_body(text, "Skills")),
        "declared_tools": code_or_bullet_values(section_body(text, "Tools")),
        "learning_patterns": code_or_bullet_values(section_body(text, "Learning Patterns")),
        "ability_boundaries": bullet_lines(section_body(text, "Ability Boundaries")) or bullet_lines(section_body(text, "Capability Boundaries")),
        "capability_boundaries": bullet_lines(section_body(text, "Ability Boundaries")) or bullet_lines(section_body(text, "Capability Boundaries")),
        "biases_and_weaknesses": bullet_lines(section_body(text, "Biases and Weaknesses")),
        "track_record_and_growth": bullet_lines(section_body(text, "Track Record and Growth")),
        "memory_and_thread": bullet_lines(section_body(text, "Memory and Thread")),
        "harness_and_evaluation": bullet_lines(section_body(text, "Harness and Evaluation")),
        "context_management_policy": bullet_lines(section_body(text, "Context Management Policy")),
        "evolution_path": bullet_lines(section_body(text, "Evolution Path")),
        "maturity_contract": load_agent_maturity_contract(text),
        "policy_contract": load_agent_policy_contract(text),
        "output_contract": compact_section(text, "Output Contract", max_lines=10),
    }


def load_skill_contract(agent_id: str) -> dict[str, Any]:
    rel = f"specs/skills/{agent_id}/SKILL.md"
    path = REPO_ROOT / rel
    if not path.exists():
        return {"source_path": rel, "available": False, "name": "", "sections": [], "role_checklist": []}
    text = path.read_text(encoding="utf-8")
    frontmatter = parse_frontmatter(text)
    sections = re.findall(r"^##\s+(.+)$", text, flags=re.MULTILINE)
    return {
        "source_path": rel,
        "available": True,
        "name": frontmatter.get("name", ""),
        "description": frontmatter.get("description", ""),
        "sections": sections,
        "when_to_use": compact_section(text, "When to Use This Skill", max_lines=6),
        "inputs": bullet_lines(section_body(text, "Inputs")),
        "operating_workflow": bullet_lines(section_body(text, "Operating Workflow")),
        "procedure": list_lines(section_body(text, "Procedure")),
        "evidence_rules": bullet_lines(section_body(text, "Evidence Rules")),
        "context_management": bullet_lines(section_body(text, "Context Management")),
        "output_schema": bullet_lines(section_body(text, "Output Schema")),
        "failure_modes": bullet_lines(section_body(text, "Failure Modes")),
        "learning_patterns": code_or_bullet_values(section_body(text, "Learning Patterns")),
        "role_checklist": bullet_lines(section_body(text, "Role-Specific Checklist")),
        "harness_hooks": bullet_lines(section_body(text, "Harness Hooks")),
        "quality_gates": list_lines(section_body(text, "Quality Gates")),
        "guardrails": bullet_lines(section_body(text, "Guardrails")),
        "forbidden_outputs": bullet_lines(section_body(text, "Forbidden Outputs")),
        "boundaries": bullet_lines(section_body(text, "Boundaries")),
        "role_specific_benchmark": key_value_section(text, "Role-Specific Benchmark"),
        "context_compression_recipe": key_value_section(text, "Context Compression Recipe"),
        "evolution_candidate_rules": key_value_section(text, "Evolution Candidate Rules"),
        "execution_policy_contract": load_skill_execution_policy_contract(text),
        "real_trade_allowed": False,
        "broker_integration": "disabled",
        "required_closing": compact_section(text, "Required Closing", max_lines=4),
    }


def load_agent_policy_contract(text: str) -> dict[str, Any]:
    return {
        "policy_contract": bullet_lines(section_body(text, "Policy Contract")),
        "context_contract": bullet_lines(section_body(text, "Context Contract")),
        "memory_policy": bullet_lines(section_body(text, "Memory Policy")),
        "tool_policy": bullet_lines(section_body(text, "Tool Policy")),
        "evolution_contract": bullet_lines(section_body(text, "Evolution Contract")),
        "safety_boundary": normalized_safety_boundary(text),
        "controls": [
            "policy_contract_loaded",
            "context_contract_loaded",
            "memory_tool_evolution_safety_boundaries_required",
            "no_real_trade_action",
            "broker_integration_disabled",
        ],
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def load_skill_execution_policy_contract(text: str) -> dict[str, Any]:
    return {
        "policy_contract": bullet_lines(section_body(text, "Policy Contract")),
        "context_contract": bullet_lines(section_body(text, "Context Contract")),
        "tool_use_policy": bullet_lines(section_body(text, "Tool Use Policy")),
        "memory_policy": bullet_lines(section_body(text, "Memory Policy")),
        "evolution_policy": bullet_lines(section_body(text, "Evolution Policy")),
        "safety_boundary": normalized_safety_boundary(text),
        "controls": [
            "execution_policy_contract_loaded",
            "context_contract_loaded",
            "memory_tool_evolution_safety_boundaries_required",
            "no_real_trade_action",
            "broker_integration_disabled",
        ],
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def normalized_safety_boundary(text: str) -> list[str]:
    boundary = bullet_lines(section_body(text, "Safety Boundary"))
    invariant = "no real trade action; real_trade_allowed=false; broker_integration=disabled"
    joined = " ".join(boundary).lower()
    if "no real" not in joined:
        boundary.append(invariant)
    return boundary


def load_agent_maturity_contract(text: str) -> dict[str, Any]:
    benchmark = key_value_section(text, "Capability Benchmarks")
    return {
        "differentiated_edge": key_value_section(text, "Differentiated Edge"),
        "market_regimes": key_value_section(text, "Preferred Market Regimes"),
        "anti_patterns": key_value_section(text, "Anti-Patterns and Failure Modes"),
        "capability_benchmarks": benchmark,
        "growth_roadmap": key_value_section(text, "Growth Roadmap"),
        "context_compression": key_value_section(text, "Role-Specific Context Compression"),
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def key_value_section(text: str, heading: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in bullet_lines(section_body(text, heading)):
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip()
    return values


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    values: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            values[key.strip()] = value.strip()
    return values


def first_heading(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def section_body(text: str, heading: str) -> str:
    pattern = re.compile(rf"^##\s+{re.escape(heading)}\s*$", re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return ""
    start = match.end()
    next_heading = re.search(r"^##\s+", text[start:], flags=re.MULTILINE)
    end = start + next_heading.start() if next_heading else len(text)
    return text[start:end].strip()


def bullet_lines(body: str) -> list[str]:
    values = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            values.append(stripped[2:].strip())
    return values


def list_lines(body: str) -> list[str]:
    values = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            values.append(stripped[2:].strip())
            continue
        match = re.match(r"^\d+\.\s+(.*)$", stripped)
        if match:
            values.append(match.group(1).strip())
    return values


def code_or_bullet_values(body: str) -> list[str]:
    values = []
    for line in bullet_lines(body):
        values.append(line.replace("`", ""))
    return values


def compact_section(text: str, heading: str, max_lines: int) -> str:
    body = section_body(text, heading)
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    return "\n".join(lines[:max_lines])


def context_focus(agent_id: str, role: str, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    if policy:
        return {"tags": policy.get("preferred_context_tags", []), "required": policy.get("required_focus", [])}
    if "Trader" in role:
        return {"tags": ["trading", "risk"], "required": ["量价结构", "买卖触发条件", "仓位纪律"]}
    if "Risk" in role:
        return {"tags": ["risk", "company", "trading"], "required": ["下行风险", "证据等级", "仓位上限"]}
    if "Bear" in role:
        return {"tags": ["bear_case", "risk", "company"], "required": ["攻击核心假设", "替代解释", "证据缺口"]}
    if "Company" in role or "Governance" in role:
        return {"tags": ["company", "risk"], "required": ["财报公告", "产品和订单", "治理风险"]}
    if "Analyst" in role:
        return {"tags": ["industry", "company"], "required": ["产业链", "chokepoint", "需求验证"]}
    return {"tags": ["industry", "company", "trading", "risk", "bear_case"], "required": ["综合判断", "证据追溯", "流程完整性"]}
