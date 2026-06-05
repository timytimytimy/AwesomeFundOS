from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fundos.io import DISCLAIMER, read_yaml, write_yaml


def review_date(days: int = 30) -> str:
    return (datetime.now(timezone.utc).date() + timedelta(days=days)).isoformat()


def build_portfolio_artifacts(memo: dict[str, Any], evidence_pack: dict[str, Any]) -> dict[str, Any]:
    final = memo["final_decision"]
    run_id = memo["run_id"]
    query = evidence_pack.get("query", "unknown")
    if isinstance(query, dict):
        query = query.get("value", "unknown")
    evidence_refs = memo.get("evidence_references", [])[:8]
    label = final.get("label", "needs_more_evidence")
    target_weight = target_weight_for(final)
    action_type = action_type_for(final, target_weight)
    item = {
        "watchlist_id": f"wl_{run_id}",
        "run_id": run_id,
        "subject": query,
        "market": evidence_pack.get("market", "CN_A_SHARE"),
        "status": "active_research" if label in {"continue_research", "watchlist", "upgrade_research_priority", "simulated_long_candidate"} else "needs_more_evidence",
        "source_decision_label": label,
        "stance": final.get("stance"),
        "conviction": final.get("conviction"),
        "priority": priority_for(final),
        "review_date": review_date(),
        "triggers": memo.get("trading_plan", {}).get("entry_conditions", []),
        "add_conditions": memo.get("trading_plan", {}).get("add_conditions", []),
        "reduce_conditions": memo.get("trading_plan", {}).get("reduce_conditions", []),
        "exit_conditions": memo.get("trading_plan", {}).get("exit_conditions", []),
        "kill_criteria": memo.get("kill_criteria", []),
        "evidence_references": evidence_refs,
        "notes": [
            "Generated from simulated investment committee memo.",
            "Requires future outcome review; no real trade is allowed.",
        ],
        "disclaimer": DISCLAIMER,
    }
    action = {
        "action_id": f"ppa_{run_id}_001",
        "run_id": run_id,
        "watchlist_id": item["watchlist_id"],
        "subject": query,
        "market": item["market"],
        "action_type": action_type,
        "target_weight": target_weight,
        "max_weight": max(target_weight, 0.0),
        "real_trade_allowed": False,
        "rationale": final.get("hypothetical_position_range", "Paper Portfolio only"),
        "required_before_upgrade": item["triggers"],
        "risk_controls": item["kill_criteria"] + item["exit_conditions"],
        "review_date": item["review_date"],
        "evidence_references": evidence_refs,
        "disclaimer": DISCLAIMER,
    }
    return {
        "watchlist": {
            "version": "0.1.0",
            "artifact_type": "watchlist",
            "run_id": run_id,
            "items": [item],
            "disclaimer": DISCLAIMER,
        },
        "paper_portfolio": {
            "version": "0.1.0",
            "artifact_type": "paper_portfolio",
            "run_id": run_id,
            "actions": [action],
            "constraints": {
                "real_trade_allowed": False,
                "broker_integration": "disabled",
                "max_real_capital": 0,
            },
            "disclaimer": DISCLAIMER,
        },
    }


def target_weight_for(final: dict[str, Any]) -> float:
    label = final.get("label")
    conviction = final.get("conviction")
    if label == "simulated_long_candidate" and conviction == "high":
        return 0.02
    if label in {"watchlist", "upgrade_research_priority"} and conviction in {"medium", "high"}:
        return 0.01
    return 0.0


def action_type_for(final: dict[str, Any], target_weight: float) -> str:
    label = final.get("label")
    if label in {"reject", "simulated_reduce_or_avoid"}:
        return "avoid"
    if target_weight > 0:
        return "paper_add"
    return "watchlist_only"


def priority_for(final: dict[str, Any]) -> str:
    if final.get("conviction") == "high":
        return "high"
    if final.get("conviction") == "medium":
        return "medium"
    return "low"


def write_portfolio_artifacts(run_path: Path, memo: dict[str, Any], evidence_pack: dict[str, Any]) -> dict[str, Path]:
    artifacts = build_portfolio_artifacts(memo, evidence_pack)
    portfolio_dir = run_path / "portfolio"
    portfolio_dir.mkdir(parents=True, exist_ok=True)
    watchlist_path = portfolio_dir / "watchlist.yaml"
    paper_path = portfolio_dir / "paper-portfolio.yaml"
    actions_path = portfolio_dir / "portfolio-actions.jsonl"
    write_yaml(watchlist_path, artifacts["watchlist"])
    write_yaml(paper_path, artifacts["paper_portfolio"])
    actions = artifacts["paper_portfolio"].get("actions", [])
    actions_path.write_text("".join(json.dumps(action, ensure_ascii=False) + "\n" for action in actions), encoding="utf-8")
    return {"watchlist": watchlist_path, "paper_portfolio": paper_path, "actions": actions_path}


def build_portfolio_review(run_path: Path) -> dict[str, Any]:
    state = load_portfolio_state(run_path)
    watch_items = state["watchlist"].get("items", [])
    actions = state["paper_portfolio"].get("actions", [])
    constraints = state["paper_portfolio"].get("constraints", {})
    attribution_items = [build_attribution_item(action, watch_items, constraints) for action in actions]
    real_trade_violations = sum(1 for item in attribution_items if item.get("real_trade_violation"))
    learning_candidates = [build_review_candidate(item) for item in attribution_items]
    return {
        "version": "0.1.0",
        "artifact_type": "portfolio_review",
        "run_id": state["paper_portfolio"].get("run_id") or state["watchlist"].get("run_id"),
        "reviewed_actions": len(actions),
        "watchlist_items": len(watch_items),
        "attribution_items": attribution_items,
        "learning_candidates": learning_candidates,
        "real_trade_violations": real_trade_violations,
        "review_verdict": "blocked_real_trade_violation" if real_trade_violations else "paper_review_recorded",
        "controls": ["paper_only", "no_broker_integration", "no_real_trade_action", "review_before_upgrade"],
        "disclaimer": DISCLAIMER,
    }


def build_attribution_item(action: dict[str, Any], watch_items: list[dict[str, Any]], constraints: dict[str, Any]) -> dict[str, Any]:
    watch = next((item for item in watch_items if item.get("watchlist_id") == action.get("watchlist_id")), {})
    evidence_refs = action.get("evidence_references", [])
    target_weight = float(action.get("target_weight", 0) or 0)
    real_trade_violation = bool(action.get("real_trade_allowed") or constraints.get("real_trade_allowed"))
    if real_trade_violation:
        status = "invalid_real_trade_leakage"
    elif target_weight == 0:
        status = "watchlist_only_pending_evidence"
    else:
        status = "paper_position_pending_outcome"
    return {
        "action_id": action.get("action_id"),
        "run_id": action.get("run_id"),
        "watchlist_id": action.get("watchlist_id"),
        "subject": action.get("subject"),
        "action_type": action.get("action_type"),
        "target_weight": target_weight,
        "review_date": action.get("review_date") or watch.get("review_date"),
        "evidence_count": len(evidence_refs),
        "trigger_count": len(watch.get("triggers", [])),
        "risk_control_count": len(action.get("risk_controls", [])),
        "outcome_status": "not_due_or_no_market_data",
        "attribution_status": status,
        "attribution_notes": [
            "No live price/outcome adapter in V1; attribution records process quality and review readiness.",
            "Paper portfolio review is not a real trading signal.",
        ],
        "real_trade_violation": real_trade_violation,
        "broker_integration": constraints.get("broker_integration", "disabled"),
    }


def build_review_candidate(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": f"portfolio_review_{item.get('action_id')}",
        "run_id": item.get("run_id"),
        "source_agent": "review_archivist",
        "target_agent": "fund_manager",
        "candidate_type": "memory_update",
        "target_scope": "agent_memory",
        "proposal": "Paper Portfolio 复盘应记录触发条件、证据数量、风控约束和是否缺少后验行情数据。",
        "source_basis": [{"evidence_id": item.get("action_id"), "source_tier": "tier_2_canonical_framework", "rationale": "paper portfolio process attribution"}],
        "required_tests": ["outcome_review", "role_drift_check", "evidence_quality_check"],
        "status": "proposed",
    }


def write_portfolio_review(run_path: Path) -> dict[str, Any]:
    review = build_portfolio_review(run_path)
    portfolio_dir = run_path / "portfolio"
    portfolio_dir.mkdir(parents=True, exist_ok=True)
    write_yaml(portfolio_dir / "portfolio-review.yaml", review)
    attribution = review.get("attribution_items", [])
    candidates = review.get("learning_candidates", [])
    (portfolio_dir / "attribution.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in attribution), encoding="utf-8")
    (portfolio_dir / "review-candidates.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in candidates), encoding="utf-8")
    return review


def load_portfolio_state(run_path: Path) -> dict[str, Any]:
    portfolio_dir = run_path / "portfolio"
    return {
        "watchlist": read_yaml(portfolio_dir / "watchlist.yaml") if (portfolio_dir / "watchlist.yaml").exists() else {"items": []},
        "paper_portfolio": read_yaml(portfolio_dir / "paper-portfolio.yaml") if (portfolio_dir / "paper-portfolio.yaml").exists() else {"actions": []},
        "actions": load_jsonl(portfolio_dir / "portfolio-actions.jsonl"),
        "portfolio_review": read_yaml(portfolio_dir / "portfolio-review.yaml") if (portfolio_dir / "portfolio-review.yaml").exists() else {"reviewed_actions": 0, "attribution_items": [], "learning_candidates": []},
        "attribution": load_jsonl(portfolio_dir / "attribution.jsonl"),
        "review_candidates": load_jsonl(portfolio_dir / "review-candidates.jsonl"),
    }


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
