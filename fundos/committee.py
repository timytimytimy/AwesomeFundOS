from __future__ import annotations

from pathlib import Path
from typing import Any

from fundos.io import DISCLAIMER, REPO_ROOT, read_yaml, write_yaml

PROTOCOL_REL = "specs/protocols/investment-committee-protocol.yaml"
DEBATE_REL = "specs/protocols/debate-protocol.yaml"
HANDOFF_REL = "specs/protocols/handoff-contract.yaml"


def load_committee_protocol() -> dict[str, Any]:
    protocol = read_yaml(REPO_ROOT / PROTOCOL_REL)
    protocol["source_path"] = PROTOCOL_REL
    protocol["debate_protocol_doc"] = read_yaml(REPO_ROOT / DEBATE_REL)
    protocol["handoff_contract_doc"] = read_yaml(REPO_ROOT / HANDOFF_REL)
    return protocol


def load_collaboration_harness(run_path: Path | None) -> dict[str, Any]:
    if not run_path:
        return default_collaboration_harness()
    path = run_path / "harness" / "collaboration-harness.yaml"
    if not path.exists():
        return default_collaboration_harness()
    loaded = read_yaml(path) or {}
    report = default_collaboration_harness()
    report.update(loaded)
    return report


def default_collaboration_harness() -> dict[str, Any]:
    return {
        "artifact_type": "collaboration_harness_report",
        "overall_score": 0,
        "checks": {},
        "blocking_issues": ["missing_collaboration_harness"],
        "disagreement_count": 0,
        "handoff_count": 0,
        "veto_count": 0,
    }


def write_committee_artifacts(
    run_path: Path,
    run_id: str,
    query: str,
    selected: list[dict[str, str]],
    agent_outputs: list[dict[str, Any]],
    evidence_pack: dict[str, Any],
) -> dict[str, Any]:
    protocol = load_committee_protocol()
    committee_dir = run_path / "committee"
    debate_dir = run_path / "debate"
    committee_dir.mkdir(parents=True, exist_ok=True)
    debate_dir.mkdir(parents=True, exist_ok=True)

    selected_ids = [row["agent_id"] for row in selected]
    output_by_agent = {row["agent_id"]: row for row in agent_outputs}
    handoffs = build_handoffs(selected_ids, output_by_agent)
    disagreements = build_disagreements(output_by_agent, evidence_pack)
    vetoes = build_vetoes(output_by_agent, evidence_pack)
    readiness = build_decision_readiness(protocol, selected_ids, handoffs, disagreements, vetoes)
    issue_table = build_issue_table(disagreements, vetoes)
    bear_case_text = build_bear_case_markdown(query, disagreements, vetoes)
    report = evaluate_collaboration(protocol, selected_ids, handoffs, disagreements, vetoes, readiness)

    write_yaml(committee_dir / "committee-protocol.yaml", compact_protocol(protocol))
    write_yaml(committee_dir / "handoffs.yaml", {"artifact_type": "committee_handoffs", "run_id": run_id, "handoff_count": len(handoffs), "items": handoffs, "real_trade_allowed": False})
    write_yaml(committee_dir / "disagreement-register.yaml", {"artifact_type": "disagreement_register", "run_id": run_id, "disagreement_count": len(disagreements), "items": disagreements, "real_trade_allowed": False})
    write_yaml(committee_dir / "veto-table.yaml", {"artifact_type": "risk_veto_table", "run_id": run_id, "veto_count": len(vetoes), "items": vetoes, "real_trade_allowed": False})
    write_yaml(committee_dir / "decision-readiness.yaml", readiness)
    write_yaml(debate_dir / "issue-table.yaml", issue_table)
    (debate_dir / "bear-case.md").write_text(bear_case_text, encoding="utf-8")
    write_yaml(run_path / "harness" / "collaboration-harness.yaml", report)
    return report


def compact_protocol(protocol: dict[str, Any]) -> dict[str, Any]:
    return {
        "protocol_id": protocol.get("protocol_id"),
        "source_path": protocol.get("source_path"),
        "required_roles": protocol.get("required_roles", []),
        "decision_gates": protocol.get("decision_gates", []),
        "handoff_contract": protocol.get("handoff_contract"),
        "debate_protocol": protocol.get("debate_protocol"),
        "safety_controls": protocol.get("safety_controls", []),
    }


def build_handoffs(selected_ids: list[str], outputs: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    handoffs: list[dict[str, Any]] = []
    if "bear_debater" in selected_ids and "fund_manager" in selected_ids:
        handoffs.append({
            "from_agent": "bear_debater",
            "to_agent": "fund_manager",
            "handoff_type": "bear_to_fund_manager_dispute",
            "reason": "反方阻断项必须进入最终备忘录，而不是被平均掉。",
            "artifact": "committee/disagreement-register.yaml",
            "required_response": "逐条处理未解决争议或降低 conviction。",
            "blocking_if_missing": True,
        })
    if "risk_manager" in selected_ids and "fund_manager" in selected_ids:
        handoffs.append({
            "from_agent": "risk_manager",
            "to_agent": "fund_manager",
            "handoff_type": "risk_to_fund_manager_position_cap",
            "reason": "风控必须决定模拟仓位上限、veto 或 kill criteria。",
            "artifact": "committee/veto-table.yaml",
            "required_response": "接受 position cap / veto 或保留阻断项。",
            "blocking_if_missing": True,
        })
    trader_ids = [aid for aid in selected_ids if "trader" in aid]
    analyst_ids = [aid for aid in selected_ids if "analyst" in aid]
    for analyst_id in analyst_ids[:2]:
        for trader_id in trader_ids[:1]:
            handoffs.append({
                "from_agent": analyst_id,
                "to_agent": trader_id,
                "handoff_type": "analyst_to_trader_trigger_check",
                "reason": "研究假设需要量价、触发和失效条件检验。",
                "artifact": f"agent_work/{analyst_id}.structured.yaml",
                "required_response": "输出等待/观察/触发/失效条件，不输出真实交易指令。",
                "blocking_if_missing": False,
            })
    if "evaluation_harness" in selected_ids and "review_archivist" in selected_ids:
        handoffs.append({
            "from_agent": "evaluation_harness",
            "to_agent": "review_archivist",
            "handoff_type": "evaluation_to_archivist_review_task",
            "reason": "Harness 阻断项和失败模式需要归档为复盘任务。",
            "artifact": "harness/collaboration-harness.yaml",
            "required_response": "生成 review task 和 evolution candidate。",
            "blocking_if_missing": False,
        })
    return handoffs


def build_disagreements(outputs: dict[str, dict[str, Any]], evidence_pack: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    bear = outputs.get("bear_debater")
    if bear:
        items.append({
            "issue_id": "D001",
            "owner_agent": "bear_debater",
            "issue": "核心假设仍可能被方法论源或社媒热度污染，缺少订单、收入、客户和价格序列确认。",
            "opposes": "premature_conviction_upgrade",
            "evidence_refs": refs_from_output(bear),
            "status": "unresolved",
            "required_resolution": "补充一手公告/财报/行情或保持观察队列。",
        })
    risk = outputs.get("risk_manager")
    if risk:
        items.append({
            "issue_id": "D002",
            "owner_agent": "risk_manager",
            "issue": "证据链不完整时必须限制模拟仓位，不能因叙事强而提高风险暴露。",
            "opposes": "position_without_evidence",
            "evidence_refs": refs_from_output(risk),
            "status": "unresolved",
            "required_resolution": "明确 position cap、kill criteria 和 review date。",
        })
    low_count = sum(1 for item in evidence_pack.get("evidence_items", []) if item.get("source_tier") in {"tier_5_social_signal", "tier_6_unverified"})
    if low_count:
        items.append({
            "issue_id": "D003",
            "owner_agent": "evaluation_harness",
            "issue": "低等级公开信号只能作为线索，不能进入高置信决策。",
            "opposes": "low_tier_signal_upgrade",
            "evidence_refs": [],
            "status": "unresolved",
            "required_resolution": "Source boundary gate must stay closed until primary evidence appears.",
        })
    return items


def build_vetoes(outputs: dict[str, dict[str, Any]], evidence_pack: dict[str, Any]) -> list[dict[str, Any]]:
    primary_count = sum(1 for item in evidence_pack.get("evidence_items", []) if item.get("source_tier") == "tier_1_primary_fact")
    items = [{
        "veto_id": "V001",
        "owner_agent": "risk_manager",
        "veto_type": "position_cap",
        "condition": "真实公告、财报、行情或关键一手事实不足以支持高置信升级。",
        "effect": "hypothetical_position_range_capped_at_0_to_1_percent_paper_only" if primary_count else "hypothetical_position_range_capped_at_0_percent",
        "status": "active",
        "real_trade_allowed": False,
    }]
    items.append({
        "veto_id": "V002",
        "owner_agent": "bear_debater",
        "veto_type": "conviction_blocker",
        "condition": "反方核心争议未解决。",
        "effect": "final_memo_must_preserve_disagreement_and_cap_confidence",
        "status": "active",
        "real_trade_allowed": False,
    })
    return items


def build_decision_readiness(protocol: dict[str, Any], selected_ids: list[str], handoffs: list[dict[str, Any]], disagreements: list[dict[str, Any]], vetoes: list[dict[str, Any]]) -> dict[str, Any]:
    required = set(protocol.get("required_roles", []))
    selected = set(selected_ids)
    checks = {
        "mandatory_roles_present": required <= selected,
        "bear_challenge_present": any(row.get("owner_agent") == "bear_debater" for row in disagreements),
        "risk_veto_or_cap_present": any(row.get("owner_agent") == "risk_manager" for row in vetoes),
        "disagreement_preserved": bool(disagreements),
        "blocking_handoffs_present": any(row.get("blocking_if_missing") for row in handoffs),
        "paper_only": True,
    }
    blocking = [name for name, ok in checks.items() if not ok]
    return {
        "artifact_type": "committee_decision_readiness",
        "checks": checks,
        "ready_for_final_memo": not blocking,
        "blocking_issues": blocking,
        "real_trade_allowed": False,
    }


def build_issue_table(disagreements: list[dict[str, Any]], vetoes: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "artifact_type": "committee_issue_table",
        "issues": [
            {"issue": row["issue"], "owner_agent": row["owner_agent"], "status": row["status"], "required_resolution": row["required_resolution"]}
            for row in disagreements
        ],
        "vetoes": vetoes,
        "real_trade_allowed": False,
    }


def build_bear_case_markdown(query: str, disagreements: list[dict[str, Any]], vetoes: list[dict[str, Any]]) -> str:
    lines = ["# Bear Case", "", DISCLAIMER, "", f"任务：{query}", "", "## 未解决争议"]
    lines.extend(f"- {row['issue_id']} / {row['owner_agent']}: {row['issue']}" for row in disagreements)
    lines.append("")
    lines.append("## Veto / Position Cap")
    lines.extend(f"- {row['veto_id']} / {row['owner_agent']}: {row['effect']}" for row in vetoes)
    return "\n".join(lines) + "\n"


def evaluate_collaboration(protocol: dict[str, Any], selected_ids: list[str], handoffs: list[dict[str, Any]], disagreements: list[dict[str, Any]], vetoes: list[dict[str, Any]], readiness: dict[str, Any]) -> dict[str, Any]:
    checks = readiness.get("checks", {})
    score = 30
    score += 15 if checks.get("mandatory_roles_present") else 0
    score += 15 if checks.get("bear_challenge_present") else 0
    score += 15 if checks.get("risk_veto_or_cap_present") else 0
    score += 10 if checks.get("disagreement_preserved") else 0
    score += 10 if checks.get("blocking_handoffs_present") else 0
    score += 5 if checks.get("paper_only") else 0
    blocking = readiness.get("blocking_issues", [])
    return {
        "artifact_type": "collaboration_harness_report",
        "protocol_id": protocol.get("protocol_id"),
        "overall_score": min(100, score),
        "selected_roles": selected_ids,
        "handoff_count": len(handoffs),
        "disagreement_count": len(disagreements),
        "veto_count": len(vetoes),
        "checks": checks,
        "blocking_issues": blocking,
        "accepted_outputs": ["committee-protocol", "handoffs", "disagreement-register", "veto-table", "decision-readiness"],
        "real_trade_allowed": False,
        "broker_integration": False,
    }


def refs_from_output(output: dict[str, Any]) -> list[str]:
    return [f"{row.get('evidence_id')}:{row.get('claim_id')}" for row in output.get("key_claims", [])[:3] if row.get("evidence_id") and row.get("claim_id")]
