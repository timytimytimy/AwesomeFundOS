from __future__ import annotations

from pathlib import Path
from typing import Any

from fundos.agent_harness import evaluate_context_management
from fundos.context import make_context_pack
from fundos.evidence import enrich_evidence_pack, evidence_item, now_iso
from fundos.io import REPO_ROOT, read_yaml, write_yaml

CONTEXT_STRESS_VERSION = "0.1.0"
DEFAULT_AGENT_IDS = ["tech_growth_analyst", "position_trend_trader", "risk_manager", "bear_debater"]


def load_roster_agents() -> dict[str, dict[str, Any]]:
    roster = read_yaml(REPO_ROOT / "specs" / "agents" / "default-roster.yaml")
    return {row["id"]: row for row in roster.get("agents", [])}


def make_dense_evidence_pack(run_id: str = "context-stress", item_count: int = 72) -> dict[str, Any]:
    retrieved_at = now_iso()
    tags_by_lane = [
        ["industry", "company"],
        ["trading", "risk"],
        ["risk", "bear_case"],
        ["company", "risk"],
        ["industry", "bear_case"],
        ["trading", "company"],
    ]
    source_types = ["announcement", "market_data", "policy", "news", "case", "web"]
    source_tiers = [
        "tier_1_primary_fact",
        "tier_1_primary_fact",
        "tier_1_primary_fact",
        "tier_4_expert_opinion",
        "tier_2_canonical_framework",
        "tier_5_social_signal",
    ]
    items: list[dict[str, Any]] = []
    for index in range(item_count):
        lane = index % len(tags_by_lane)
        eid = f"CTX{index + 1:03d}"
        tags = tags_by_lane[lane]
        source_type = source_types[lane]
        source_tier = source_tiers[lane]
        summary = dense_summary(index + 1, source_type, tags)
        claim_text = f"Dense context stress claim {index + 1} for {','.join(tags)} with source tier {source_tier}."
        item = evidence_item(
            eid,
            source_type,
            source_tier,
            f"Dense context stress item {index + 1}",
            summary,
            claim_text,
            "fact" if source_tier == "tier_1_primary_fact" else "hypothesis",
            retrieved_at,
            tags,
        )
        item["source_id"] = "context_stress_fixture"
        item["url"] = f"https://example.com/context-stress/{index + 1}"
        items.append(item)
    pack = {
        "run_id": run_id,
        "market": "CN_A_SHARE",
        "query": "context stress dense evidence pack",
        "retrieved_at": retrieved_at,
        "retrieval_plan": ["context_stress_dense_fixture", "role_specific_context_compression"],
        "evidence_items": items,
        "unresolved_gaps": ["Dense context stress keeps this synthetic gap so missing-evidence preservation can be evaluated."],
    }
    enrich_evidence_pack(pack)
    return pack


def dense_summary(index: int, source_type: str, tags: list[str]) -> str:
    tag_text = ", ".join(tags)
    return (
        f"Item {index} is a synthetic dense EvidencePack row for {tag_text}. "
        f"It contains source_type={source_type}, explicit source tier, evidence id, claim id, "
        "risk blocker, market state, price volume, industry structure, primary validation, "
        "invalidation, liquidity, downside scenario, core assumption, contradiction, and missing evidence notes. "
        "This row is offline fixture data for context compression tests only, not investment advice."
    )


def run_context_stress(
    run_path: Path | None = None,
    agent_ids: list[str] | None = None,
    item_count: int = 72,
    fail_under: int = 80,
) -> dict[str, Any]:
    agents_by_id = load_roster_agents()
    requested = agent_ids or DEFAULT_AGENT_IDS
    pack = make_dense_evidence_pack("context-stress", item_count=item_count)
    agent_results = []
    for agent_id in requested:
        if agent_id not in agents_by_id:
            raise KeyError(f"agent_not_found: {agent_id}")
        context = make_context_pack("context-stress", agents_by_id[agent_id], pack)
        quality = evaluate_context_management(context)
        manifest = context.get("context_budget_manifest", {}) or {}
        loss = context.get("context_loss_accounting", {}) or {}
        agent_results.append({
            "agent_id": agent_id,
            "role": agents_by_id[agent_id].get("role"),
            "context_policy_id": context.get("context_policy", {}).get("context_policy_id"),
            "role_family": manifest.get("role_family"),
            "score": quality.get("score", 0),
            "status": "passed" if int(quality.get("score", 0) or 0) >= fail_under else "blocked",
            "candidate_items": manifest.get("candidate_items", 0),
            "included_items": manifest.get("included_items", 0),
            "excluded_items": manifest.get("excluded_items", 0),
            "estimated_tokens_before": manifest.get("estimated_tokens_before", 0),
            "estimated_tokens_after": manifest.get("estimated_tokens_after", 0),
            "compression_ratio": manifest.get("compression_ratio", 0),
            "required_context_dimensions": quality.get("required_context_dimensions", []),
            "retained_context_dimensions": quality.get("retained_context_dimensions", []),
            "missing_required_context_dimensions": quality.get("missing_required_context_dimensions", []),
            "forbidden_drop_violations": quality.get("forbidden_drop_violations", []),
            "drop_reasons": quality.get("drop_reasons", []),
            "retained_evidence_ids": loss.get("retained_evidence_ids", []),
            "dropped_claim_count": len(loss.get("dropped_claim_ids", []) or []),
            "controls": [
                "dense_evidence_pack_fixture",
                "role_specific_context_compression",
                "loss_accounting_required",
                "vertical_required_dimensions_traced",
                "no_real_trade_action",
            ],
            "real_trade_allowed": False,
            "broker_integration": "disabled",
        })
    aggregate_score = round(sum(float(row["score"]) for row in agent_results) / len(agent_results), 1) if agent_results else 0
    blocked = [row["agent_id"] for row in agent_results if row["status"] != "passed"]
    report = {
        "version": CONTEXT_STRESS_VERSION,
        "artifact_type": "context_stress_report",
        "run_id": "context-stress",
        "item_count": item_count,
        "agent_count": len(agent_results),
        "fail_under": fail_under,
        "overall_score": aggregate_score,
        "status": "passed" if not blocked else "blocked",
        "blocked_agents": blocked,
        "agent_results": agent_results,
        "controls": [
            "offline_synthetic_fixture_only",
            "context_compression_stress_test",
            "loss_accounting_required",
            "no_real_trade_action",
            "broker_integration_disabled",
        ],
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }
    if run_path:
        out = run_path / "harness" / "context-stress.yaml"
        out.parent.mkdir(parents=True, exist_ok=True)
        write_yaml(out, report)
    return report
