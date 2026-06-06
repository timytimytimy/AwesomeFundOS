from __future__ import annotations

from typing import Any

RESEARCH_GAP_PRIORITY_MAP = {
    "market_data": "high",
    "case_library": "medium",
    "announcement": "high",
    "policy": "high",
    "news": "medium",
    "social_signal": "low",
}

RESEARCH_GAP_OWNER_MAP = {
    "market_data": "position_trend_trader",
    "case_library": "review_archivist",
    "announcement": "quality_growth_company_analyst",
    "policy": "policy_event_analyst",
    "news": "tech_growth_analyst",
    "social_signal": "bear_debater",
}


def build_next_research_tasks(coverage: dict[str, Any], run_id: str) -> list[dict[str, Any]]:
    tasks = []
    for index, category in enumerate(coverage.get("missing_categories", []) or [], start=1):
        owner = RESEARCH_GAP_OWNER_MAP.get(category, "chief_of_staff")
        tasks.append(
            {
                "task_id": f"{run_id}:research_gap:{index:03d}",
                "category": category,
                "owner_agent": owner,
                "owner_agent_id": owner,
                "priority": RESEARCH_GAP_PRIORITY_MAP.get(category, "medium"),
                "reason": f"research plan category {category} had no accepted public research evidence",
                "real_trade_allowed": False,
                "broker_integration": "disabled",
            }
        )
    return tasks
