from __future__ import annotations

from pathlib import Path
from typing import Any

from fundos.io import REPO_ROOT, read_yaml, write_yaml

SPEC_REL = "specs/committee/pm-style-competition.yaml"
STANCE_ORDER = {"avoid": 0, "needs_research": 1, "watchlist": 2, "paper_candidate": 3}


def load_pm_competition_spec() -> dict[str, Any]:
    spec = read_yaml(REPO_ROOT / SPEC_REL)
    spec["source_path"] = SPEC_REL
    return spec


def default_pm_competition() -> dict[str, Any]:
    return {
        "artifact_type": "pm_style_competition_report",
        "overall_score": 0,
        "style_count": 0,
        "disagreement_count": 0,
        "style_views": [],
        "disagreement_register": [],
        "winner": {"style_id": "none", "authority": "simulation_only"},
        "checks": {},
        "blocking_issues": ["missing_pm_competition"],
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def default_pm_harness() -> dict[str, Any]:
    return {
        "artifact_type": "pm_style_competition_harness",
        "overall_score": 0,
        "style_count": 0,
        "disagreement_count": 0,
        "risk_boundary_present": False,
        "no_real_trade_action": True,
        "checks": {},
        "blocking_issues": ["missing_pm_competition_harness"],
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def load_pm_competition(run_path: Path | None) -> dict[str, Any]:
    if not run_path:
        return default_pm_competition()
    path = run_path / "committee" / "pm-competition.yaml"
    if not path.exists():
        return default_pm_competition()
    loaded = read_yaml(path) or {}
    base = default_pm_competition()
    base.update(loaded)
    return base


def load_pm_competition_harness(run_path: Path | None) -> dict[str, Any]:
    if not run_path:
        return default_pm_harness()
    path = run_path / "harness" / "pm-competition-harness.yaml"
    if not path.exists():
        return default_pm_harness()
    loaded = read_yaml(path) or {}
    base = default_pm_harness()
    base.update(loaded)
    return base


def write_pm_competition(
    run_path: Path,
    run_id: str,
    topic: str,
    evidence_pack: dict[str, Any],
    selected_agents: list[dict[str, str]],
    agent_outputs: list[dict[str, Any]],
) -> dict[str, Any]:
    spec = load_pm_competition_spec()
    selected_ids = {row["agent_id"] for row in selected_agents}
    output_by_agent = {row["agent_id"]: row for row in agent_outputs}
    evidence_summary = summarize_evidence(evidence_pack)
    style_views = [
        build_style_view(style, topic, selected_ids, output_by_agent, evidence_summary)
        for style in spec.get("styles", [])
    ]
    disagreements = build_style_disagreements(style_views)
    winner = choose_winner(style_views)
    checks = build_checks(style_views, disagreements)
    blocking = [name for name, ok in checks.items() if not ok]
    score = score_pm_competition(checks, len(disagreements), len(style_views))
    report = {
        "artifact_type": "pm_style_competition_report",
        "competition_id": spec.get("competition_id"),
        "source_path": spec.get("source_path"),
        "run_id": run_id,
        "topic": topic,
        "overall_score": score,
        "style_count": len(style_views),
        "disagreement_count": len(disagreements),
        "style_views": style_views,
        "disagreement_register": disagreements,
        "winner": winner,
        "checks": checks,
        "blocking_issues": blocking,
        "controls": spec.get("decision_controls", []) + spec.get("safety_controls", []),
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }
    harness = {
        "artifact_type": "pm_style_competition_harness",
        "competition_id": spec.get("competition_id"),
        "overall_score": score,
        "style_count": len(style_views),
        "disagreement_count": len(disagreements),
        "risk_boundary_present": checks.get("risk_boundary_present", False),
        "no_real_trade_action": True,
        "checks": checks,
        "blocking_issues": blocking,
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }
    write_yaml(run_path / "committee" / "pm-competition.yaml", report)
    write_yaml(run_path / "harness" / "pm-competition-harness.yaml", harness)
    return report


def summarize_evidence(evidence_pack: dict[str, Any]) -> dict[str, Any]:
    items = evidence_pack.get("evidence_items", [])
    primary = [item for item in items if item.get("source_tier") == "tier_1_primary_fact"]
    public = [item for item in items if item.get("source_id") == "public_research"]
    low = [item for item in items if item.get("source_tier") in {"tier_5_social_signal", "tier_6_unverified"}]
    trading = [item for item in items if any("trading" == tag for claim in item.get("claims", []) for tag in claim.get("relevant_to", []))]
    risk = [item for item in items if any("risk" == tag for claim in item.get("claims", []) for tag in claim.get("relevant_to", []))]
    return {
        "primary_count": len(primary),
        "public_count": len(public),
        "low_count": len(low),
        "trading_count": len(trading),
        "risk_count": len(risk),
    }


def build_style_view(
    style: dict[str, Any],
    topic: str,
    selected_ids: set[str],
    output_by_agent: dict[str, dict[str, Any]],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    style_id = style["style_id"]
    contributors = [agent_id for agent_id in style.get("preferred_agents", []) if agent_id in selected_ids]
    contributor_outputs = [output_by_agent[agent_id] for agent_id in contributors if agent_id in output_by_agent]
    primary_refs = sum(row.get("evidence_coverage", {}).get("tier_1_primary_fact", 0) for row in contributor_outputs)
    has_trader = any("trader" in agent_id for agent_id in contributors)
    has_risk_voice = any(agent_id in {"risk_manager", "bear_debater", "defensive_execution_trader", "fraud_governance_analyst"} for agent_id in contributors)
    stance = style_stance(style_id, evidence, primary_refs, has_trader, has_risk_voice)
    confidence = style_confidence(stance, evidence, primary_refs)
    risk_boundary = risk_boundary_for(stance, style_id, evidence)
    return {
        "style_id": style_id,
        "display_name": style.get("display_name"),
        "mandate": style.get("mandate"),
        "stance": stance,
        "confidence": confidence,
        "time_horizon": style.get("time_horizon"),
        "risk_posture": style.get("default_risk_posture"),
        "contributors": contributors,
        "matched_agent_count": len(contributors),
        "evidence_summary": {
            "primary_refs_from_contributors": primary_refs,
            "primary_count": evidence["primary_count"],
            "public_count": evidence["public_count"],
            "low_tier_count": evidence["low_count"],
        },
        "thesis_fragment": thesis_fragment_for(style_id, topic, stance),
        "risk_boundary": risk_boundary,
        "required_followups": followups_for(style_id, stance),
        "real_trade_allowed": False,
        "authority": "simulation_only",
    }


def style_stance(style_id: str, evidence: dict[str, Any], primary_refs: int, has_trader: bool, has_risk_voice: bool) -> str:
    primary = evidence["primary_count"] + primary_refs
    low = evidence["low_count"]
    if style_id == "defensive_risk_pm":
        return "avoid" if primary <= low + 3 else "needs_research"
    if style_id == "trend_following_pm":
        return "paper_candidate" if has_trader and evidence["trading_count"] > 0 and primary >= 3 else "needs_research"
    if style_id == "quality_growth_pm":
        return "watchlist" if primary >= 2 else "needs_research"
    if style_id == "cycle_value_pm":
        return "needs_research" if primary >= 1 else "avoid"
    return "needs_research"


def style_confidence(stance: str, evidence: dict[str, Any], primary_refs: int) -> str:
    if stance == "avoid":
        return "medium" if evidence["risk_count"] else "low"
    if evidence["primary_count"] + primary_refs >= 5 and evidence["low_count"] == 0:
        return "medium"
    return "low"


def risk_boundary_for(stance: str, style_id: str, evidence: dict[str, Any]) -> dict[str, Any]:
    cap = "0% paper" if stance == "avoid" else "0-1% paper" if stance == "paper_candidate" else "watchlist only"
    return {
        "hypothetical_position_cap": cap,
        "kill_criteria": [
            "primary evidence disappears or contradicts thesis",
            "low-tier signal becomes dominant evidence",
            "risk manager or bear debater veto remains unresolved",
        ],
        "requires_review_before_any_change": True,
        "real_trade_allowed": False,
        "style_id": style_id,
        "evidence_primary_count": evidence["primary_count"],
    }


def thesis_fragment_for(style_id: str, topic: str, stance: str) -> str:
    if style_id == "quality_growth_pm":
        return f"{topic} can remain on a quality-growth research list only if company quality and primary evidence improve; current stance={stance}."
    if style_id == "cycle_value_pm":
        return f"{topic} needs cycle-position and supply-demand confirmation before style capital would be simulated; current stance={stance}."
    if style_id == "trend_following_pm":
        return f"{topic} requires price-volume confirmation and invalidation discipline; current stance={stance}."
    return f"{topic} must pass downside, liquidity, evidence-gap, and bear-case checks before any upgrade; current stance={stance}."


def followups_for(style_id: str, stance: str) -> list[str]:
    common = ["retrieve primary announcements/filings", "preserve bear-case disagreement", "document review date"]
    style_specific = {
        "quality_growth_pm": ["verify moat and financial quality claims"],
        "cycle_value_pm": ["verify cycle position and inventory/price signal"],
        "trend_following_pm": ["verify trend, volume, relative strength, and invalidation line"],
        "defensive_risk_pm": ["verify liquidity, crowding, fraud/governance, and tail risk"],
    }
    if stance == "avoid":
        return ["do not upgrade without new primary evidence"] + style_specific.get(style_id, []) + common
    return style_specific.get(style_id, []) + common


def build_style_disagreements(style_views: list[dict[str, Any]]) -> list[dict[str, Any]]:
    disagreements: list[dict[str, Any]] = []
    for left in style_views:
        for right in style_views:
            if left["style_id"] >= right["style_id"]:
                continue
            gap = abs(STANCE_ORDER[left["stance"]] - STANCE_ORDER[right["stance"]])
            if gap >= 1:
                disagreements.append({
                    "issue_id": f"PMD{len(disagreements)+1:03d}",
                    "left_style": left["style_id"],
                    "right_style": right["style_id"],
                    "left_stance": left["stance"],
                    "right_stance": right["stance"],
                    "status": "preserved",
                    "required_resolution": "FundManager must synthesize without averaging away style-specific risk boundaries.",
                })
    return disagreements


def choose_winner(style_views: list[dict[str, Any]]) -> dict[str, Any]:
    if not style_views:
        return {"style_id": "none", "stance": "needs_research", "authority": "simulation_only"}
    ranked = sorted(style_views, key=lambda row: (STANCE_ORDER[row["stance"]], row["matched_agent_count"]), reverse=True)
    winner = ranked[0]
    return {
        "style_id": winner["style_id"],
        "stance": winner["stance"],
        "reason": "highest constructive simulated stance after preserving risk boundaries",
        "authority": "simulation_only",
        "capital_authority_changed": False,
        "real_trade_allowed": False,
    }


def build_checks(style_views: list[dict[str, Any]], disagreements: list[dict[str, Any]]) -> dict[str, bool]:
    return {
        "minimum_style_count": len(style_views) >= 4,
        "disagreement_preserved": len(disagreements) > 0,
        "risk_boundary_present": all(bool(row.get("risk_boundary")) and row["risk_boundary"].get("real_trade_allowed") is False for row in style_views),
        "paper_only": all(row.get("real_trade_allowed") is False for row in style_views),
        "style_winner_has_no_capital_authority": True,
    }


def score_pm_competition(checks: dict[str, bool], disagreement_count: int, style_count: int) -> int:
    score = 25
    score += 20 if checks.get("minimum_style_count") else 0
    score += 20 if checks.get("disagreement_preserved") else 0
    score += 20 if checks.get("risk_boundary_present") else 0
    score += 10 if checks.get("paper_only") else 0
    score += 5 if checks.get("style_winner_has_no_capital_authority") else 0
    if disagreement_count >= 2 and style_count >= 4:
        score += 5
    return min(100, score)
