from __future__ import annotations

from pathlib import Path
from typing import Any

from fundos.io import REPO_ROOT, DISCLAIMER, read_yaml, write_yaml
from fundos.outcomes import load_market_replay, max_drawdown_pct

MARKET_STATE_VERSION = "0.1.0"
TAXONOMY_REL = "specs/market/market-state-taxonomy.yaml"


def load_market_state_taxonomy() -> dict[str, Any]:
    taxonomy = read_yaml(REPO_ROOT / TAXONOMY_REL)
    taxonomy["source_path"] = TAXONOMY_REL
    return taxonomy


def default_market_state_report() -> dict[str, Any]:
    return {
        "version": MARKET_STATE_VERSION,
        "artifact_type": "market_state_report",
        "market_state_quality_score": 0,
        "subjects_evaluated": 0,
        "subjects_missing_data": 0,
        "subject_states": [],
        "blocking_issues": ["missing_market_state_report"],
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def load_market_state_report(run_path: Path | None) -> dict[str, Any]:
    if not run_path:
        return default_market_state_report()
    path = run_path / "harness" / "market-state.yaml"
    if not path.exists():
        return default_market_state_report()
    loaded = read_yaml(path) or {}
    report = default_market_state_report()
    report.update(loaded)
    return report


def write_market_state_report(run_path: Path, evidence_pack: dict[str, Any], market_replay_path: Path | None = None) -> dict[str, Any]:
    taxonomy = load_market_state_taxonomy()
    replay = load_market_replay(market_replay_path)
    subjects = subjects_for(evidence_pack, replay)
    states = [classify_market_series(subject, replay.get(subject, [])) for subject in subjects]
    evaluated = [row for row in states if row.get("state_id") != "insufficient_data"]
    missing = [row for row in states if row.get("state_id") == "insufficient_data"]
    blocking = []
    if not evaluated:
        blocking.append("missing_market_replay_for_market_state")
    score = quality_score(states)
    report = {
        "version": MARKET_STATE_VERSION,
        "artifact_type": "market_state_report",
        "taxonomy_id": taxonomy.get("taxonomy_id"),
        "source_path": taxonomy.get("source_path"),
        "run_id": evidence_pack.get("run_id"),
        "market": evidence_pack.get("market", "CN_A_SHARE"),
        "market_state_quality_score": score,
        "subjects_evaluated": len(evaluated),
        "subjects_missing_data": len(missing),
        "subject_states": states,
        "blocking_issues": blocking,
        "controls": taxonomy.get("controls", []),
        "disclaimer": DISCLAIMER,
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }
    write_yaml(run_path / "harness" / "market-state.yaml", report)
    return report


def subjects_for(evidence_pack: dict[str, Any], replay: dict[str, list[dict[str, Any]]]) -> list[str]:
    subjects = []
    query = evidence_pack.get("query")
    if isinstance(query, str) and query:
        subjects.append(query)
    for key in replay:
        if key not in subjects:
            subjects.append(key)
    return subjects or ["market"]


def classify_market_series(subject: str, series: list[dict[str, Any]]) -> dict[str, Any]:
    closes = [float(row["close"]) for row in series if row.get("close") is not None]
    volumes = [float(row["volume"]) for row in series if row.get("volume") is not None]
    base = {
        "subject": subject,
        "bars": len(closes),
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }
    if len(closes) < 2:
        return {**base, "state_id": "insufficient_data", "trend_direction": "unknown", "return_pct": None, "max_drawdown_pct": None, "volume_expansion": False, "confidence": "low"}
    start = closes[0]
    end = closes[-1]
    ret = round((end / start - 1) * 100, 2) if start else 0.0
    drawdown = max_drawdown_pct(closes)
    volume_expansion = bool(len(volumes) >= 2 and volumes[-1] > volumes[0] * 1.2)
    trend = "up" if ret > 3 else "down" if ret < -3 else "flat"
    state = state_for(ret, drawdown, volume_expansion)
    return {
        **base,
        "state_id": state,
        "trend_direction": trend,
        "return_pct": ret,
        "max_drawdown_pct": drawdown,
        "volume_expansion": volume_expansion,
        "start_date": first_value(series, "date"),
        "end_date": last_value(series, "date"),
        "confidence": "medium" if len(closes) >= 4 else "low",
        "interpretation": interpretation_for(state),
    }


def state_for(return_pct: float, drawdown_pct: float, volume_expansion: bool) -> str:
    if return_pct <= -15:
        return "panic_capitulation"
    if return_pct <= -5:
        return "downtrend_risk_off"
    if return_pct >= 10 and volume_expansion and drawdown_pct > -8:
        return "bull_breakout"
    if return_pct >= 4 and drawdown_pct > -10:
        return "uptrend_accumulation"
    if return_pct >= 0 and drawdown_pct <= -10:
        return "distribution_top"
    return "range_bound_rotation"


def interpretation_for(state_id: str) -> str:
    mapping = {
        "bull_breakout": "Constructive market state, but requires invalidation and paper-only risk boundary.",
        "uptrend_accumulation": "Constructive accumulation context; confirm with primary evidence and trend persistence.",
        "range_bound_rotation": "Mixed market context; wait for confirmation and avoid conviction upgrade.",
        "distribution_top": "Unstable leadership; preserve bear case and reduce confidence.",
        "downtrend_risk_off": "Risk-off context; risk manager and defensive trader dominate stance.",
        "panic_capitulation": "Capitulation context; avoid upgrade until stabilization evidence appears.",
        "insufficient_data": "Market state cannot be verified without replay or market-data adapter.",
    }
    return mapping.get(state_id, "Unknown state.")


def quality_score(states: list[dict[str, Any]]) -> int:
    if not states:
        return 0
    evaluated = [row for row in states if row.get("state_id") != "insufficient_data"]
    if not evaluated:
        return 0
    coverage = len(evaluated) / len(states)
    avg_bars = sum(row.get("bars", 0) or 0 for row in evaluated) / len(evaluated)
    confidence_bonus = sum(1 for row in evaluated if row.get("confidence") == "medium") * 5
    return int(round(min(100, 45 + coverage * 35 + min(15, avg_bars * 2) + confidence_bonus)))


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
