from __future__ import annotations

from pathlib import Path
from typing import Any

from fundos.agent_harness import load_agent_harness
from fundos.agent_governance import load_governance_summary
from fundos.agent_threads import evaluate_thread_manifest
from fundos.case_replay import load_case_replay
from fundos.capability_regression import load_capability_regression
from fundos.committee import load_collaboration_harness
from fundos.outcomes import load_outcome_tracking
from fundos.pm_competition import load_pm_competition_harness
from fundos.portfolio import load_portfolio_state
from fundos.skill_benchmark import load_skill_benchmark_report
from fundos.source_ingestion import load_ingestion_report
from fundos.tool_harness import load_tool_harness


def make_evaluation(run_id: str, selected: list[dict[str, str]], evidence_pack: dict[str, Any]) -> dict[str, Any]:
    return make_evaluation_for_run(run_id, selected, evidence_pack, None)


def make_evaluation_for_run(run_id: str, selected: list[dict[str, str]], evidence_pack: dict[str, Any], run_path: Path | None = None) -> dict[str, Any]:
    items = evidence_pack["evidence_items"]
    public_items = [item for item in items if item.get("source_id") == "public_research"]
    primary_count = sum(1 for item in items if item.get("source_tier") == "tier_1_primary_fact")
    low_count = sum(1 for item in items if item.get("source_tier") in {"tier_5_social_signal", "tier_6_unverified"})
    evidence_quality = min(95, 55 + primary_count * 5 + len(public_items) * 10 - low_count * 3)
    tool_usage_quality = 70 if public_items else 50
    overall = round((evidence_quality + 70 + 82 + 72 + 75 + tool_usage_quality + 80) / 7, 1)
    blocking = []
    if not public_items:
        blocking.append("真实公开数据检索工具尚未接入，当前为 EvidencePack stub。")
    if primary_count == 0:
        blocking.append("缺少 tier_1_primary_fact，不能形成高置信结论。")
    if low_count > primary_count:
        blocking.append("低等级信号数量超过一手证据，需要降级结论。")
    portfolio = load_portfolio_state(run_path) if run_path else {
        "watchlist": {"items": []},
        "paper_portfolio": {"actions": []},
        "portfolio_review": {"reviewed_actions": 0, "real_trade_violations": 0, "attribution_items": [], "learning_candidates": []},
        "attribution": [],
        "review_candidates": [],
    }
    case_replay = load_case_replay(run_path) if run_path else {"patterns_replayed": 0, "case_results_total": 0, "case_replay_score": 0, "passed_results": 0, "high_overfit_results": 0}
    agent_harness = load_agent_harness(run_path)
    agent_governance = load_governance_summary(run_path)
    agent_thread_quality = evaluate_thread_manifest(run_path)
    collaboration_harness = load_collaboration_harness(run_path)
    pm_competition_harness = load_pm_competition_harness(run_path)
    tool_harness = load_tool_harness(run_path)
    source_ingestion = load_ingestion_report(run_path)
    outcome_tracking = load_outcome_tracking(run_path)
    capability_regression = load_capability_regression(run_path)
    skill_benchmark = load_skill_benchmark_report(run_path)
    case_replay_score = case_replay.get("case_replay_score", 0)
    outcome_score = outcome_tracking.get("outcome_quality_score", 0)
    paper_actions = portfolio["paper_portfolio"].get("actions", [])
    portfolio_review = portfolio.get("portfolio_review", {})
    attribution_items = portfolio.get("attribution", []) or portfolio_review.get("attribution_items", [])
    review_candidates = portfolio.get("review_candidates", []) or portfolio_review.get("learning_candidates", [])
    real_trade_violations = [action for action in paper_actions if action.get("real_trade_allowed")]
    review_real_trade_violations = int(portfolio_review.get("real_trade_violations", 0) or 0)
    if real_trade_violations:
        blocking.append("Paper Portfolio 出现 real_trade_allowed=true，违反 V1 边界。")
    if review_real_trade_violations:
        blocking.append("Portfolio Review 检测到真实交易泄漏，禁止进入 Evolution 或升级动作。")
    accepted_outputs = ["final-decision-memo"]
    if case_replay.get("case_results_total", 0):
        accepted_outputs.append("historical_case_replay")
    if case_replay.get("case_library_coverage", {}).get("case_count", 0):
        accepted_outputs.append("case_library")
    if portfolio_review.get("reviewed_actions", 0):
        accepted_outputs.append("portfolio_review")
    if agent_harness.get("agent_count", 0):
        accepted_outputs.append("agent_harness")
    if agent_thread_quality.get("manifest_present"):
        accepted_outputs.append("agent_threads")
    if agent_harness.get("aggregate_scores", {}).get("context_management_quality", 0) > 0:
        accepted_outputs.append("context_management")
    if collaboration_harness.get("overall_score", 0) > 0:
        accepted_outputs.append("collaboration_harness")
    if pm_competition_harness.get("overall_score", 0) > 0:
        accepted_outputs.append("pm_competition")
    if tool_harness.get("high_confidence_allowed"):
        accepted_outputs.append("tool_harness")
    if source_ingestion.get("ingested_sources", 0) > 0:
        accepted_outputs.append("source_ingestion")
    if outcome_tracking.get("actions_evaluated", 0) > 0:
        accepted_outputs.append("outcome_tracking")
    if capability_regression.get("candidates_total", 0) > 0:
        accepted_outputs.append("capability_regression")
    if skill_benchmark.get("overall_score", 0) > 0:
        accepted_outputs.append("skill_benchmark")
    if agent_governance.get("agent_count", 0) > 0:
        accepted_outputs.append("agent_governance")
    for issue in tool_harness.get("blocking_issues", []):
        if issue not in blocking:
            blocking.append(issue)
    for issue in collaboration_harness.get("blocking_issues", []):
        if issue and issue not in blocking and issue != "missing_collaboration_harness":
            blocking.append(issue)
    for issue in pm_competition_harness.get("blocking_issues", []):
        if issue and issue not in blocking and issue != "missing_pm_competition_harness":
            blocking.append(issue)
    if pm_competition_harness.get("real_trade_allowed"):
        blocking.append("PM Competition 出现 real_trade_allowed=true，违反投委会边界。")
    for issue in agent_thread_quality.get("blocking_issues", []):
        if issue and issue not in blocking and issue != "missing_agent_thread_manifest":
            blocking.append(issue)
    for issue in skill_benchmark.get("blocking_issues", []):
        if issue and issue not in blocking and issue != "missing_skill_benchmark":
            blocking.append(issue)
    if skill_benchmark.get("real_trade_allowed"):
        blocking.append("Skill Benchmark 出现 real_trade_allowed=true，违反能力评测边界。")
    if source_ingestion.get("real_trade_allowed"):
        blocking.append("Source Ingestion 出现 real_trade_allowed=true，违反学习源边界。")
    if source_ingestion.get("ingested_sources", 0) > 0 and not source_ingestion.get("all_patterns_start_quarantined", False):
        blocking.append("Source Ingestion 生成了未隔离的 pattern candidate，禁止进入 Evolution。")
    agent_harness_scores = agent_harness.get("aggregate_scores", {})
    tool_harness_adapter = tool_harness.get("adapter_coverage", {})
    context_management = summarize_context_management(agent_harness)
    return {
        "run_id": run_id,
        "overall_score": overall,
        "source_coverage": {
            "total_items": len(items),
            "public_research_items": len(public_items),
            "tier_1_primary_fact": primary_count,
            "low_tier_items": low_count,
        },
        "dimension_scores": {
            "evidence_quality": evidence_quality,
            "reasoning_quality": 70,
            "role_consistency": 82,
            "decision_quality": 72 if public_items else 68,
            "collaboration_quality": 75,
            "tool_usage_quality": tool_usage_quality,
            "context_quality": 80,
            "historical_case_replay": case_replay_score,
            "outcome_tracking": outcome_score,
        },
        "context_quality_scores": {
            "relevance": 82,
            "compression_fidelity": agent_harness_scores.get("context_compression", 78),
            "evidence_traceability": 86,
            "role_specificity": agent_harness_scores.get("role_consistency", 82),
            "information_sufficiency": 70 if public_items else 60,
            "noise_control": 84,
            "leakage_control": 85,
            "contradiction_preservation": 80,
        },
        "agent_harness_quality": {
            "agent_count": agent_harness.get("agent_count", 0),
            "context_compression": agent_harness_scores.get("context_compression", 0),
            "context_management_quality": agent_harness_scores.get("context_management_quality", 0),
            "skill_invocation": agent_harness_scores.get("skill_invocation", 0),
            "role_consistency": agent_harness_scores.get("role_consistency", 0),
            "overall": agent_harness_scores.get("overall", 0),
        },
        "agent_thread_quality": agent_thread_quality,
        "agent_governance_quality": {
            "agent_count": agent_governance.get("agent_count", 0),
            "governance_action_counts": agent_governance.get("governance_action_counts", {}),
            "seat_competitions": len(agent_governance.get("seat_competitions", {})),
            "promotion_watch": agent_governance.get("governance_action_counts", {}).get("promotion_watch", 0),
            "retrain_and_downgrade_watch": agent_governance.get("governance_action_counts", {}).get("retrain_and_downgrade_watch", 0),
            "controls": agent_governance.get("controls", []),
            "real_trade_allowed": agent_governance.get("real_trade_allowed", False),
            "broker_integration": agent_governance.get("broker_integration", "disabled"),
        },
        "context_management_quality": context_management,
        "collaboration_harness_quality": {
            "overall_score": collaboration_harness.get("overall_score", 0),
            "handoff_count": collaboration_harness.get("handoff_count", 0),
            "disagreement_count": collaboration_harness.get("disagreement_count", 0),
            "veto_count": collaboration_harness.get("veto_count", 0),
            "checks": collaboration_harness.get("checks", {}),
            "blocking_issues": collaboration_harness.get("blocking_issues", []),
        },
        "pm_competition_quality": {
            "overall_score": pm_competition_harness.get("overall_score", 0),
            "style_count": pm_competition_harness.get("style_count", 0),
            "disagreement_count": pm_competition_harness.get("disagreement_count", 0),
            "risk_boundary_present": pm_competition_harness.get("risk_boundary_present", False),
            "no_real_trade_action": pm_competition_harness.get("no_real_trade_action", True),
            "checks": pm_competition_harness.get("checks", {}),
            "blocking_issues": pm_competition_harness.get("blocking_issues", []),
            "real_trade_allowed": pm_competition_harness.get("real_trade_allowed", False),
            "broker_integration": pm_competition_harness.get("broker_integration", "disabled"),
        },
        "tool_harness_quality": {
            "overall_score": tool_harness.get("overall_score", 0),
            "public_research_items": tool_harness_adapter.get("public_research_items", 0),
            "primary_public_items": tool_harness_adapter.get("primary_public_items", 0),
            "low_tier_public_items": tool_harness_adapter.get("low_tier_public_items", 0),
            "high_confidence_allowed": tool_harness.get("high_confidence_allowed", False),
            "blocking_issues": tool_harness.get("blocking_issues", []),
        },
        "source_ingestion_quality": {
            "status": source_ingestion.get("status", "present"),
            "ingested_sources": source_ingestion.get("ingested_sources", 0),
            "quarantined_sources": source_ingestion.get("quarantined_sources", 0),
            "pattern_candidates": source_ingestion.get("pattern_candidates", 0),
            "evolution_candidates": source_ingestion.get("evolution_candidates", 0),
            "direct_trade_signal_blocked": source_ingestion.get("direct_trade_signal_blocked", False),
            "copyright_violation_blocked": source_ingestion.get("copyright_violation_blocked", False),
            "all_patterns_start_quarantined": source_ingestion.get("all_patterns_start_quarantined", False),
            "real_trade_allowed": source_ingestion.get("real_trade_allowed", False),
        },
        "portfolio_quality": {
            "watchlist_items": len(portfolio["watchlist"].get("items", [])),
            "paper_actions": len(paper_actions),
            "real_trade_violations": len(real_trade_violations),
            "review_dates_present": sum(1 for item in portfolio["watchlist"].get("items", []) if item.get("review_date")),
        },
        "portfolio_review_quality": {
            "reviewed_actions": portfolio_review.get("reviewed_actions", 0),
            "attribution_items": len(attribution_items),
            "learning_candidates": len(review_candidates),
            "real_trade_violations": review_real_trade_violations,
            "review_verdict": portfolio_review.get("review_verdict", "not_reviewed"),
        },
        "outcome_tracking_quality": {
            "outcome_status": outcome_tracking.get("outcome_status", "missing_market_replay"),
            "actions_evaluated": outcome_tracking.get("actions_evaluated", 0),
            "actions_missing_market_replay": outcome_tracking.get("actions_missing_market_replay", 0),
            "market_replay_items": outcome_tracking.get("market_replay_items", 0),
            "outcome_quality_score": outcome_score,
        },
        "case_replay_quality": {
            "patterns_replayed": case_replay.get("patterns_replayed", 0),
            "case_results_total": case_replay.get("case_results_total", 0),
            "passed_results": case_replay.get("passed_results", 0),
            "high_overfit_results": case_replay.get("high_overfit_results", 0),
            "case_replay_score": case_replay_score,
        },
        "case_library_quality": {
            "case_count": case_replay.get("case_library_coverage", {}).get("case_count", case_replay.get("cases_available", 0)),
            "matched_cases": case_replay.get("case_library_coverage", {}).get("matched_cases", 0),
            "matched_case_types": case_replay.get("case_library_coverage", {}).get("matched_case_types", 0),
            "matched_case_type_names": case_replay.get("case_library_coverage", {}).get("matched_case_type_names", []),
            "agent_coverage": case_replay.get("case_library_coverage", {}).get("agent_coverage", {}),
            "case_library_index": case_replay.get("case_library_index", ""),
            "real_trade_allowed": False,
        },
        "capability_regression_quality": {
            "regression_status": capability_regression.get("regression_status", "missing"),
            "candidates_total": capability_regression.get("candidates_total", 0),
            "passed_candidates": capability_regression.get("passed_candidates", 0),
            "blocked_candidates": capability_regression.get("blocked_candidates", 0),
        },
        "skill_benchmark_quality": {
            "overall_score": skill_benchmark.get("overall_score", 0),
            "agents_evaluated": skill_benchmark.get("agents_evaluated", 0),
            "passed_agents": skill_benchmark.get("passed_agents", 0),
            "blocked_agents": skill_benchmark.get("blocked_agents", 0),
            "skill_candidates_evaluated": skill_benchmark.get("skill_candidates_evaluated", 0),
            "blocked_skill_candidates": skill_benchmark.get("blocked_skill_candidates", 0),
            "blocking_issues": skill_benchmark.get("blocking_issues", []),
            "real_trade_allowed": skill_benchmark.get("real_trade_allowed", False),
            "broker_integration": skill_benchmark.get("broker_integration", "disabled"),
        },
        "agent_scores": [
            {
                "agent_id": item["agent_id"],
                "role_consistency": 82,
                "contribution_quality": 74 if public_items else 70,
                "context_fit": 80,
                "improvement_suggestions": ["继续提高一手证据密度", "接入真实价格序列和公告解析"],
            }
            for item in selected
        ],
        "blocking_issues": blocking,
        "accepted_outputs": accepted_outputs,
        "rejected_outputs": [],
    }


def summarize_context_management(agent_harness: dict[str, Any]) -> dict[str, Any]:
    results = agent_harness.get("agent_results", [])
    qualities = [row.get("context_management_quality", {}) for row in results if row.get("context_management_quality")]
    if not qualities:
        return {
            "overall": 0,
            "agents_evaluated": 0,
            "budget_manifest_present": 0,
            "token_budget_respected": 0,
            "loss_accounting_present": 0,
            "role_specific_compression_present": 0,
            "excluded_items": 0,
            "estimated_tokens_before": 0,
            "estimated_tokens_after": 0,
        }
    return {
        "overall": agent_harness.get("aggregate_scores", {}).get("context_management_quality", 0),
        "agents_evaluated": len(qualities),
        "budget_manifest_present": sum(1 for item in qualities if item.get("budget_manifest_present")),
        "token_budget_respected": sum(1 for item in qualities if item.get("token_budget_respected")),
        "loss_accounting_present": sum(1 for item in qualities if item.get("loss_accounting_present")),
        "role_specific_compression_present": sum(1 for item in qualities if item.get("role_specific_compression_present")),
        "excluded_items": sum(int(item.get("excluded_items", 0) or 0) for item in qualities),
        "estimated_tokens_before": sum(int(item.get("estimated_tokens_before", 0) or 0) for item in qualities),
        "estimated_tokens_after": sum(int(item.get("estimated_tokens_after", 0) or 0) for item in qualities),
        "drop_reasons": sorted({reason for item in qualities for reason in item.get("drop_reasons", [])}),
    }
