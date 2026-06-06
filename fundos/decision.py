from __future__ import annotations

from pathlib import Path
from typing import Any

from fundos.agent_outputs import summarize_agent_outputs
from fundos.committee import load_committee_protocol
from fundos.io import DISCLAIMER


def make_decision_memo(run_id: str, query: str, evidence_pack: dict[str, Any], agent_outputs: list[dict[str, Any]] | None = None, collaboration_report: dict[str, Any] | None = None) -> dict[str, Any]:
    refs = []
    for item in evidence_pack["evidence_items"]:
        if item.get("source_tier") in {"tier_1_primary_fact", "tier_3_verified_public_practitioner"}:
            claim = item["claims"][0]
            refs.append({"evidence_id": item["id"], "claim_id": claim["claim_id"], "usage": "supports simulated committee memo"})
        if len(refs) >= 6:
            break
    public_items = [item for item in evidence_pack["evidence_items"] if item.get("source_id") == "public_research"]
    primary_public = [item for item in public_items if item.get("source_tier") == "tier_1_primary_fact"]
    social_items = [item for item in public_items if item.get("source_tier") == "tier_5_social_signal"]
    has_public_primary = bool(primary_public)
    label = "continue_research" if has_public_primary else "needs_more_evidence"
    stance = "constructive" if has_public_primary else "neutral"
    conviction = "medium" if has_public_primary and not social_items else "low"
    thesis = f"{query} 已有 {len(primary_public)} 条 fixture/public 一手证据线索和 {len(public_items)} 条公开检索结果进入 EvidencePack；仍需真实公告、财报、行情和案例回放继续验证。"
    if not public_items:
        thesis = f"{query} 当前主要依赖 seed library 和占位事实源，需要接入真实公开资料后再判断。"
    protocol = load_committee_protocol()
    collaboration = collaboration_report or {}
    return {
        "run_id": run_id,
        "memo_type": "simulated_investment_committee_memo",
        "disclaimer": DISCLAIMER,
        "final_decision": {
            "label": label,
            "stance": stance,
            "conviction": conviction,
            "hypothetical_position_range": "0%，仅进入观察和研究队列" if conviction == "low" else "0-1%，仅限 Paper Portfolio 观察仓",
        },
        "thesis": thesis,
        "bull_case": "若一手公告、政策和产业证据继续确认需求、订单、核心零部件瓶颈和公司映射，研究优先级可提升。",
        "bear_case": "社媒热度和方法论源不能替代订单、收入、客户和价格行为验证；若只有叙事则不得升级。",
        "risk_review": "主要风险是证据链不完整、低等级信号污染、产业链映射过度推断、价格序列缺失。",
        "trading_plan": {
            "entry_conditions": ["真实行情趋势确认", "公告/财报验证订单或收入", "风控确认模拟仓位上限"],
            "add_conditions": ["核心假设被多源验证", "价格强度和板块扩散同步"],
            "reduce_conditions": ["证据等级下降", "量价结构恶化", "主题拥挤且基本面未兑现"],
            "exit_conditions": ["核心假设被证伪", "公告/财报不支持产业链映射", "风控触发退出"],
        },
        "kill_criteria": ["缺少一手证据", "关键假设被公告或财报证伪", "反方和风控提出未解决阻断项", "社媒热度成为主要依据"],
        "committee_protocol": {
            "protocol_id": protocol.get("protocol_id"),
            "source_path": protocol.get("source_path"),
            "required_roles": protocol.get("required_roles", []),
            "decision_gates": protocol.get("decision_gates", []),
        },
        "collaboration_summary": {
            "overall_score": collaboration.get("overall_score", 0),
            "handoff_count": collaboration.get("handoff_count", 0),
            "disagreement_count": collaboration.get("disagreement_count", 0),
            "veto_count": collaboration.get("veto_count", 0),
            "blocking_issues": collaboration.get("blocking_issues", []),
        },
        "agent_output_summary": summarize_agent_outputs(agent_outputs or []),
        "evidence_references": refs,
        "real_trade_allowed": False,
        "broker_integration": "disabled",
    }


def write_decision_markdown(path: Path, memo: dict[str, Any]) -> None:
    fd = memo["final_decision"]
    text = f"""# 模拟投委会研究决策备忘录

{memo['disclaimer']}

## 最终标签

- label: {fd['label']}
- stance: {fd['stance']}
- conviction: {fd['conviction']}
- hypothetical_position_range: {fd['hypothetical_position_range']}

## Thesis

{memo['thesis']}

## Bull Case

{memo['bull_case']}

## Bear Case

{memo['bear_case']}

## Risk Review

{memo['risk_review']}

## Committee Protocol

- protocol_id: {memo.get('committee_protocol', {}).get('protocol_id')}
- required_roles: {', '.join(memo.get('committee_protocol', {}).get('required_roles', []))}
- collaboration_score: {memo.get('collaboration_summary', {}).get('overall_score', 0)}
- disagreements: {memo.get('collaboration_summary', {}).get('disagreement_count', 0)}
- vetoes: {memo.get('collaboration_summary', {}).get('veto_count', 0)}

## Agent Output Summary

"""
    text += "\n".join(f"- {item['agent_id']}: {item['stance']} / {item['confidence']} / primary={item['primary_evidence_count']}" for item in memo.get("agent_output_summary", []))
    text += "\n\n## Kill Criteria\n\n"
    text += "\n".join(f"- {item}" for item in memo["kill_criteria"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + "\n", encoding="utf-8")
