from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fundos.io import DISCLAIMER, read_yaml, write_yaml
from fundos.portfolio import load_portfolio_state

OUTCOME_VERSION = "0.1.0"


def write_market_replay_fixture(path: Path, series_by_subject: dict[str, list[dict[str, Any]]]) -> None:
    write_yaml(path, {"version": OUTCOME_VERSION, "market_replay": series_by_subject})


def load_market_replay(path: Path | None) -> dict[str, list[dict[str, Any]]]:
    if not path or not path.exists():
        return {}
    doc = read_yaml(path) or {}
    if isinstance(doc, dict) and "market_replay" in doc:
        return doc.get("market_replay", {}) or {}
    return doc if isinstance(doc, dict) else {}


def run_outcome_tracking(run_path: Path, market_replay_path: Path | None = None) -> dict[str, Any]:
    existing_path = run_path / "portfolio" / "outcome-tracking.yaml"
    if market_replay_path is None and existing_path.exists():
        existing = read_yaml(existing_path) or {}
        if existing.get("actions_evaluated", 0) > 0:
            return existing
    state = load_portfolio_state(run_path)
    actions = state["paper_portfolio"].get("actions", [])
    replay = load_market_replay(market_replay_path)
    results = [evaluate_action_outcome(action, replay.get(action.get("subject", ""), [])) for action in actions]
    evaluated = [row for row in results if row.get("outcome_status") == "evaluated_with_market_replay"]
    missing = [row for row in results if row.get("outcome_status") == "missing_market_replay"]
    score = outcome_quality_score(results)
    report = {
        "version": OUTCOME_VERSION,
        "artifact_type": "portfolio_outcome_tracking",
        "run_id": state["paper_portfolio"].get("run_id") or state["watchlist"].get("run_id"),
        "outcome_status": "evaluated_with_market_replay" if evaluated else "missing_market_replay",
        "actions_evaluated": len(evaluated),
        "actions_missing_market_replay": len(missing),
        "market_replay_items": len(replay),
        "outcome_quality_score": score,
        "results": results,
        "controls": [
            "paper_only",
            "market_replay_is_not_trade_signal",
            "no_real_trade_action",
            "no_broker_integration",
            "outcome_tracking_requires_fixture_or_adapter",
        ],
        "disclaimer": DISCLAIMER,
    }
    write_yaml(run_path / "portfolio" / "outcome-tracking.yaml", report)
    write_jsonl(run_path / "portfolio" / "outcome-attribution.jsonl", results)
    return report


def evaluate_action_outcome(action: dict[str, Any], series: list[dict[str, Any]]) -> dict[str, Any]:
    base = {
        "action_id": action.get("action_id"),
        "run_id": action.get("run_id"),
        "watchlist_id": action.get("watchlist_id"),
        "subject": action.get("subject"),
        "action_type": action.get("action_type"),
        "target_weight": float(action.get("target_weight", 0) or 0),
        "real_trade_allowed": bool(action.get("real_trade_allowed", False)),
        "broker_integration": "disabled",
        "disclaimer": DISCLAIMER,
    }
    closes = [float(row["close"]) for row in series if row.get("close") is not None]
    if len(closes) < 2:
        return {
            **base,
            "outcome_status": "missing_market_replay",
            "return_pct": None,
            "max_drawdown_pct": None,
            "max_favorable_excursion_pct": None,
            "max_adverse_excursion_pct": None,
            "review_verdict": "needs_market_replay",
        }
    start = closes[0]
    end = closes[-1]
    return_pct = round((end / start - 1) * 100, 2) if start else 0.0
    max_drawdown = max_drawdown_pct(closes)
    mfe = round((max(closes) / start - 1) * 100, 2) if start else 0.0
    mae = round((min(closes) / start - 1) * 100, 2) if start else 0.0
    return {
        **base,
        "outcome_status": "evaluated_with_market_replay",
        "start_date": first_value(series, "date"),
        "end_date": last_value(series, "date"),
        "start_close": start,
        "end_close": end,
        "bars": len(closes),
        "return_pct": return_pct,
        "max_drawdown_pct": max_drawdown,
        "max_favorable_excursion_pct": mfe,
        "max_adverse_excursion_pct": mae,
        "review_verdict": verdict_for(action, return_pct, max_drawdown),
    }


def max_drawdown_pct(closes: list[float]) -> float:
    peak = closes[0]
    worst = 0.0
    for close in closes:
        peak = max(peak, close)
        if peak:
            worst = min(worst, (close / peak - 1) * 100)
    return round(worst, 2)


def verdict_for(action: dict[str, Any], return_pct: float, drawdown_pct: float) -> str:
    action_type = action.get("action_type")
    if action_type == "watchlist_only" and return_pct > 8:
        return "missed_opportunity_review"
    if drawdown_pct <= -10:
        return "risk_control_review"
    if return_pct > 0:
        return "positive_follow_through"
    return "no_follow_through_or_negative"


def outcome_quality_score(results: list[dict[str, Any]]) -> int:
    if not results:
        return 0
    evaluated = sum(1 for row in results if row.get("outcome_status") == "evaluated_with_market_replay")
    if evaluated == 0:
        return 0
    coverage = evaluated / len(results)
    avg_bars = sum(row.get("bars", 0) or 0 for row in results) / len(results)
    score = 45 + coverage * 35 + min(20, avg_bars * 2)
    return int(round(min(100, score)))


def first_value(rows: list[dict[str, Any]], key: str) -> Any:
    for row in rows:
        if row.get(key) is not None:
            return row.get(key)
    return None


def last_value(rows: list[dict[str, Any]], key: str) -> Any:
    for row in reversed(rows):
        if row.get(key) is not None:
            return row.get(key)
    return None


def load_outcome_tracking(run_path: Path | None) -> dict[str, Any]:
    if not run_path:
        return default_outcome_tracking()
    path = run_path / "portfolio" / "outcome-tracking.yaml"
    if not path.exists():
        return default_outcome_tracking()
    return read_yaml(path) or default_outcome_tracking()


def default_outcome_tracking() -> dict[str, Any]:
    return {
        "version": OUTCOME_VERSION,
        "artifact_type": "portfolio_outcome_tracking",
        "outcome_status": "missing_market_replay",
        "actions_evaluated": 0,
        "actions_missing_market_replay": 0,
        "market_replay_items": 0,
        "outcome_quality_score": 0,
        "results": [],
        "controls": [],
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
