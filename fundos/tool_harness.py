from __future__ import annotations

from pathlib import Path
from typing import Any

from fundos.io import read_yaml, write_yaml

TOOL_HARNESS_VERSION = "0.1.0"
LOW_TIERS = {"tier_5_social_signal", "tier_6_unverified"}
PRIMARY_SOURCE_TYPES = {"announcement", "financial_report", "market_data", "policy"}
METHODOLOGY_SOURCE_TYPES = {"practitioner_source", "book_summary", "learning_pattern", "case"}


def evaluate_tool_harness(evidence_pack: dict[str, Any]) -> dict[str, Any]:
    items = evidence_pack.get("evidence_items", [])
    public_items = [item for item in items if item.get("source_id") == "public_research"]
    primary_public = [item for item in public_items if item.get("source_tier") == "tier_1_primary_fact"]
    low_public = [item for item in public_items if item.get("source_tier") in LOW_TIERS]
    source_tier_counts = count_by(items, "source_tier")
    source_type_counts = count_by(items, "source_type")
    adapter_coverage = {
        "retrieval_plan_steps": len(evidence_pack.get("retrieval_plan", [])),
        "public_research_items": len(public_items),
        "primary_public_items": len(primary_public),
        "low_tier_public_items": len(low_public),
        "announcement_items": source_type_counts.get("announcement", 0),
        "policy_items": source_type_counts.get("policy", 0),
        "market_data_items": source_type_counts.get("market_data", 0),
    }
    research_plan = evidence_pack.get("research_plan_coverage") or infer_research_plan_coverage(public_items)
    boundary = source_boundary_quality(items)
    blocking = blocking_issues(adapter_coverage, boundary, research_plan)
    adapter_score = score_adapter_coverage(adapter_coverage, research_plan)
    boundary_score = boundary["score"]
    overall = round((adapter_score + boundary_score) / 2, 1)
    return {
        "version": TOOL_HARNESS_VERSION,
        "artifact_type": "tool_harness_report",
        "run_id": evidence_pack.get("run_id"),
        "overall_score": overall,
        "adapter_coverage_score": adapter_score,
        "adapter_coverage": adapter_coverage,
        "research_plan_coverage": research_plan,
        "source_tier_counts": source_tier_counts,
        "source_type_counts": source_type_counts,
        "source_boundary_quality": boundary,
        "blocking_issues": blocking,
        "high_confidence_allowed": not blocking,
        "controls": [
            "primary_source_required_for_high_confidence",
            "kol_is_hypothesis_not_trade_signal",
            "book_and_case_are_methodology_only",
            "social_signal_never_direct_buy",
            "real_trade_action_forbidden",
        ],
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def write_tool_harness(run_path: Path, evidence_pack: dict[str, Any]) -> dict[str, Any]:
    report = evaluate_tool_harness(evidence_pack)
    path = run_path / "harness" / "tool-harness.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    write_yaml(path, report)
    return report


def load_tool_harness(run_path: Path | None) -> dict[str, Any]:
    if not run_path:
        return default_report()
    path = run_path / "harness" / "tool-harness.yaml"
    if not path.exists():
        return default_report()
    return read_yaml(path) or default_report()


def default_report() -> dict[str, Any]:
    return {
        "version": TOOL_HARNESS_VERSION,
        "artifact_type": "tool_harness_report",
        "overall_score": 0,
        "adapter_coverage": {"public_research_items": 0, "primary_public_items": 0, "low_tier_public_items": 0},
        "research_plan_coverage": {"planned_categories": 0, "categories_covered": 0, "missing_categories": [], "category_counts": {}, "plan_step_count": 0},
        "source_tier_counts": {},
        "source_type_counts": {},
        "source_boundary_quality": {"score": 0, "kol_sources_downgraded": False, "controls": []},
        "blocking_issues": [],
        "high_confidence_allowed": False,
        "controls": [],
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def source_boundary_quality(items: list[dict[str, Any]]) -> dict[str, Any]:
    methodology_items = [item for item in items if item.get("source_type") in METHODOLOGY_SOURCE_TYPES or item.get("source_tier") in {"tier_2_canonical_framework", "tier_3_verified_public_practitioner"}]
    social_items = [item for item in items if item.get("source_tier") in LOW_TIERS]
    kol_items = [item for item in methodology_items if item.get("source_tier") in {"tier_3_verified_public_practitioner", "tier_4_expert_opinion"}]
    not_allowed_present = all(item.get("not_allowed_outputs") is not None for item in methodology_items if item.get("source_type") in {"practitioner_source", "learning_pattern"})
    social_claims_low = all(claim.get("confidence") != "high" for item in social_items for claim in item.get("claims", []))
    kol_downgraded = all(item.get("source_tier") != "tier_1_primary_fact" for item in kol_items)
    score = 55
    if methodology_items:
        score += 10
    if not_allowed_present:
        score += 10
    if social_claims_low:
        score += 10
    if kol_downgraded:
        score += 10
    return {
        "score": min(100, score),
        "methodology_items": len(methodology_items),
        "kol_items": len(kol_items),
        "social_items": len(social_items),
        "kol_sources_downgraded": kol_downgraded,
        "methodology_not_allowed_outputs_present": not_allowed_present,
        "social_claims_low_confidence": social_claims_low,
        "controls": ["direct_buy_signal_forbidden", "methodology_requires_primary_validation", "social_signal_hypothesis_only"],
    }


def score_adapter_coverage(adapter: dict[str, int], research_plan: dict[str, Any] | None = None) -> int:
    score = 40
    if adapter.get("public_research_items", 0):
        score += 20
    if adapter.get("primary_public_items", 0):
        score += 20
    if adapter.get("announcement_items", 0) or adapter.get("policy_items", 0):
        score += 10
    if adapter.get("market_data_items", 0):
        score += 5
    if adapter.get("low_tier_public_items", 0) > adapter.get("primary_public_items", 0):
        score -= 20
    missing = set((research_plan or {}).get("missing_categories", []))
    if "market_data" in missing:
        score -= 10
    if "case_library" in missing:
        score -= 5
    if len(missing) >= 3:
        score -= 10
    return max(0, min(100, score))


def blocking_issues(adapter: dict[str, int], boundary: dict[str, Any], research_plan: dict[str, Any] | None = None) -> list[str]:
    issues = []
    if adapter.get("public_research_items", 0) == 0:
        issues.append("missing_public_research_adapter")
    if adapter.get("public_research_items", 0) and adapter.get("primary_public_items", 0) == 0:
        issues.append("public_research_without_primary_source")
    if adapter.get("low_tier_public_items", 0) > adapter.get("primary_public_items", 0):
        issues.append("low_tier_public_sources_dominate")
    if not boundary.get("kol_sources_downgraded", False):
        issues.append("kol_source_tier_boundary_missing")
    if not boundary.get("social_claims_low_confidence", False):
        issues.append("social_signal_confidence_too_high")
    missing = list((research_plan or {}).get("missing_categories", []))
    if missing:
        issues.append("missing_research_plan_categories:" + ",".join(missing))
    return issues


def infer_research_plan_coverage(public_items: list[dict[str, Any]]) -> dict[str, Any]:
    categories = [str(item.get("research_category")) for item in public_items if item.get("research_category")]
    return {
        "planned_categories": 0,
        "categories_covered": len(set(categories)),
        "missing_categories": [],
        "category_counts": count_values(categories),
        "plan_step_count": len({item.get("research_plan_id") for item in public_items if item.get("research_plan_id")}),
    }


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key, "unknown"))
        counts[value] = counts.get(value, 0) + 1
    return counts


def count_values(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts
