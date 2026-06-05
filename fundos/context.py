from __future__ import annotations

from typing import Any


def make_context_pack(run_id: str, agent: dict[str, Any], evidence_pack: dict[str, Any]) -> dict[str, Any]:
    role = agent["role"]
    agent_id = agent["id"]
    focus = context_focus(agent_id, role)
    included = []
    for item in evidence_pack["evidence_items"]:
        claims = item.get("claims", [])
        allowed = [c["claim_id"] for c in claims if set(c.get("relevant_to", [])) & set(focus["tags"])]
        if allowed or agent_id in {"chief_of_staff", "fund_manager", "evaluation_harness", "review_archivist"}:
            included.append(
                {
                    "evidence_id": item["id"],
                    "reason": f"relevant to {role}",
                    "compressed_summary": item["summary"],
                    "allowed_claims": allowed or [c["claim_id"] for c in claims],
                }
            )
    return {
        "context_pack_id": f"ctx_{agent_id}",
        "run_id": run_id,
        "agent_id": agent_id,
        "role": role,
        "task_stage": "specialist_analysis",
        "context_budget_tokens": 8000,
        "included_evidence": included,
        "contradiction_table": [
            {
                "issue": "方法论来源不能替代一手事实",
                "supporting_claims": ["C004"],
                "opposing_claims": ["C001", "C002"],
            }
        ],
        "missing_evidence": evidence_pack.get("unresolved_gaps", []),
        "excluded_evidence_summary": [
            {"category": "irrelevant noise", "reason": "V1 context router excludes non-role evidence by relevance tags"}
        ],
        "required_focus": focus["required"],
        "forbidden_focus": ["不要输出真实交易指令", "不要把低等级来源当作一手事实"],
        "output_schema": f"{role}Output",
    }


def context_focus(agent_id: str, role: str) -> dict[str, Any]:
    if "Trader" in role:
        return {"tags": ["trading", "risk"], "required": ["量价结构", "买卖触发条件", "仓位纪律"]}
    if "Risk" in role:
        return {"tags": ["risk", "company", "trading"], "required": ["下行风险", "证据等级", "仓位上限"]}
    if "Bear" in role:
        return {"tags": ["bear_case", "risk", "company"], "required": ["攻击核心假设", "替代解释", "证据缺口"]}
    if "Company" in role or "Governance" in role:
        return {"tags": ["company", "risk"], "required": ["财报公告", "产品和订单", "治理风险"]}
    if "Analyst" in role:
        return {"tags": ["industry", "company"], "required": ["产业链", "chokepoint", "需求验证"]}
    return {"tags": ["industry", "company", "trading", "risk", "bear_case"], "required": ["综合判断", "证据追溯", "流程完整性"]}
