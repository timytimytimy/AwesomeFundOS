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


def load_portfolio_state(run_path: Path) -> dict[str, Any]:
    portfolio_dir = run_path / "portfolio"
    return {
        "watchlist": read_yaml(portfolio_dir / "watchlist.yaml") if (portfolio_dir / "watchlist.yaml").exists() else {"items": []},
        "paper_portfolio": read_yaml(portfolio_dir / "paper-portfolio.yaml") if (portfolio_dir / "paper-portfolio.yaml").exists() else {"actions": []},
        "actions": load_jsonl(portfolio_dir / "portfolio-actions.jsonl"),
    }


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
