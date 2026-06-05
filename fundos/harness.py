from __future__ import annotations

from typing import Any


def make_evaluation(run_id: str, selected: list[dict[str, str]], evidence_pack: dict[str, Any]) -> dict[str, Any]:
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
        },
        "context_quality_scores": {
            "relevance": 82,
            "compression_fidelity": 78,
            "evidence_traceability": 86,
            "role_specificity": 82,
            "information_sufficiency": 70 if public_items else 60,
            "noise_control": 84,
            "leakage_control": 85,
            "contradiction_preservation": 80,
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
        "accepted_outputs": ["final-decision-memo"],
        "rejected_outputs": [],
    }
