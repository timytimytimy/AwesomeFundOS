from __future__ import annotations

from pathlib import Path
from typing import Any

from fundos.agent_harness import load_agent_harness
from fundos.case_replay import load_case_replay
from fundos.outcomes import load_outcome_tracking
from fundos.portfolio import load_portfolio_state
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
    tool_harness = load_tool_harness(run_path)
    outcome_tracking = load_outcome_tracking(run_path)
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
    if portfolio_review.get("reviewed_actions", 0):
        accepted_outputs.append("portfolio_review")
    if agent_harness.get("agent_count", 0):
        accepted_outputs.append("agent_harness")
    if tool_harness.get("high_confidence_allowed"):
        accepted_outputs.append("tool_harness")
    if outcome_tracking.get("actions_evaluated", 0) > 0:
        accepted_outputs.append("outcome_tracking")
    for issue in tool_harness.get("blocking_issues", []):
        if issue not in blocking:
            blocking.append(issue)
    agent_harness_scores = agent_harness.get("aggregate_scores", {})
    tool_harness_adapter = tool_harness.get("adapter_coverage", {})
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
            "skill_invocation": agent_harness_scores.get("skill_invocation", 0),
            "role_consistency": agent_harness_scores.get("role_consistency", 0),
            "overall": agent_harness_scores.get("overall", 0),
        },
        "tool_harness_quality": {
            "overall_score": tool_harness.get("overall_score", 0),
            "public_research_items": tool_harness_adapter.get("public_research_items", 0),
            "primary_public_items": tool_harness_adapter.get("primary_public_items", 0),
            "low_tier_public_items": tool_harness_adapter.get("low_tier_public_items", 0),
            "high_confidence_allowed": tool_harness.get("high_confidence_allowed", False),
            "blocking_issues": tool_harness.get("blocking_issues", []),
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
