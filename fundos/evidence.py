from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fundos.io import REPO_ROOT, read_yaml
from fundos.learning import load_learning_patterns
from fundos.public_research import tool_result_to_evidence


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_seed_library() -> dict[str, Any]:
    return read_yaml(REPO_ROOT / "specs" / "learning" / "seed-library.yaml")


def source_by_id(source_id: str) -> dict[str, Any]:
    for source in load_seed_library().get("sources", []):
        if source.get("id") == source_id:
            return source
    raise KeyError(source_id)


def make_evidence_pack(run_id: str, input_type: str, value: str, public_results: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    retrieved_at = now_iso()
    base_relevance = ["industry", "company", "trading", "risk", "bear_case"]
    items = [
        evidence_item("E001", "policy", "tier_1_primary_fact", "A股公开政策与监管材料检索占位", "公开政策和交易所材料应作为事实验证的一手来源。", "政策和监管口径必须优先于市场传言。", "fact", retrieved_at, ["industry", "risk"]),
        evidence_item("E002", "financial_report", "tier_1_primary_fact", "公司公告与财报检索占位", "公司公告、定期报告、互动记录用于验证产品、订单、收入和治理。", "公司层面判断必须回到公告和财报。", "fact", retrieved_at, ["company", "risk"]),
        evidence_item("E003", "market_data", "tier_1_primary_fact", "行情与量价摘要占位", "价格、成交额、相对强弱和波动用于交易结构判断。", "交易判断必须和量价结构绑定。", "fact", retrieved_at, ["trading", "risk"]),
    ]
    seed_claims = [
        ("E004", "serenity_aleabitoreddit", "practitioner_source", "学习 secular trend、supply-chain chokepoint、research gap、anti-consensus 和 falsification。", "Serenity 可用于方法论蒸馏，不能直接作为 A 股买卖依据。", "opinion", ["industry", "bear_case"]),
        ("E005", "lihai_a_share", "practitioner_source", "学习市场状态、情绪周期、买卖点、仓位和复盘纪律。", "交易计划需要市场状态和仓位纪律约束。", "opinion", ["trading", "risk"]),
        ("E006", "howard_marks", "book_summary", "学习 second-level thinking、周期和风险控制。", "风险评估必须关注赔率、周期位置和下行情景。", "opinion", ["risk", "bear_case"]),
        ("E007", "william_oneil_canslim", "book_summary", "学习成长股基本面和量价确认结合。", "成长股观察需要基本面增长和市场方向共同确认。", "opinion", ["company", "trading"]),
        ("E008", "mark_minervini", "book_summary", "学习 trend template、VCP 和风险纪律。", "趋势交易必须有明确止损和结构确认。", "opinion", ["trading", "risk"]),
        ("E009", "buffett_munger", "book_summary", "学习商业质量、护城河、能力圈和管理层激励。", "公司研究必须评估质量、激励和可理解性。", "opinion", ["company", "risk"]),
        ("E010", "peter_lynch", "book_summary", "学习 scuttlebutt、公司故事和增长分类。", "公司故事需要渠道和经营事实验证。", "opinion", ["company", "industry"]),
    ]
    for eid, source_id, source_type, summary, claim, claim_type, relevant_to in seed_claims:
        items.append(seed_evidence_item(eid, source_id, source_type, summary, claim, claim_type, retrieved_at, relevant_to))
    next_id = 11
    for pattern in load_learning_patterns():
        items.append(learning_pattern_evidence_item(f"E{next_id:03d}", pattern, retrieved_at))
        next_id += 1
    for result in public_results or []:
        items.append(tool_result_to_evidence(f"E{next_id:03d}", result, retrieved_at, base_relevance))
        next_id += 1
    items.append(evidence_item(f"E{next_id:03d}", "case", "tier_2_canonical_framework", "经典历史案例库种子", "包含大牛股早期识别、主题扩散、产业链瓶颈、泡沫破裂、财务爆雷和政策驱动案例类型。", "历史案例用于形成可测试模式，不可单案过拟合。", "inference", retrieved_at, base_relevance))
    return {
        "run_id": run_id,
        "market": "CN_A_SHARE",
        "query": value,
        "retrieved_at": retrieved_at,
        "retrieval_plan": [
            "search primary announcements and filings",
            "search policy and news sources",
            "query market data summary",
            "load seed practitioner and historical case library",
        ] + (["public_research"] if public_results else []),
        "evidence_items": items,
        "unresolved_gaps": [
            "V1 当前为 public retrieval interface stub，后续需接入真实公告、行情、新闻和网页检索工具。"
        ],
    }


def seed_evidence_item(eid: str, source_id: str, source_type: str, summary: str, claim: str, claim_type: str, retrieved_at: str, relevant_to: list[str]) -> dict[str, Any]:
    source = source_by_id(source_id)
    item = evidence_item(
        eid,
        source_type,
        source["source_tier"],
        f"{source['display_name']} 学习源",
        summary,
        claim,
        claim_type,
        retrieved_at,
        relevant_to,
    )
    item["source_id"] = source_id
    item["source_url"] = source.get("source_url", "")
    item["primary_value"] = source.get("primary_value", [])
    item["allowed_learning_outputs"] = source.get("allowed_learning_outputs", [])
    item["not_allowed_outputs"] = source.get("not_allowed_outputs", [])
    item["validation_required"] = source.get("validation_required", [])
    return item


def evidence_item(eid: str, source_type: str, tier: str, title: str, summary: str, claim: str, claim_type: str, retrieved_at: str, relevant_to: list[str]) -> dict[str, Any]:
    return {
        "id": eid,
        "source_type": source_type,
        "source_tier": tier,
        "title": title,
        "url": "",
        "published_at": "",
        "retrieved_at": retrieved_at,
        "raw_excerpt": summary,
        "summary": summary,
        "confidence": "medium" if tier != "tier_1_primary_fact" else "high",
        "claims": [
            {
                "claim_id": f"C{eid[1:]}",
                "claim_text": claim,
                "claim_type": claim_type,
                "confidence": "medium" if tier != "tier_1_primary_fact" else "high",
                "relevant_to": relevant_to,
                "supports": [],
                "contradicts": [],
            }
        ],
    }


def learning_pattern_evidence_item(eid: str, pattern: dict[str, Any], retrieved_at: str) -> dict[str, Any]:
    item = evidence_item(
        eid,
        "learning_pattern",
        pattern.get("source_tier", "tier_3_verified_public_practitioner"),
        f"{pattern.get('name', pattern['id'])} 蒸馏模式",
        pattern.get("summary", ""),
        f"可复用方法论模式：{pattern.get('summary', '')}",
        "methodology_pattern",
        retrieved_at,
        pattern.get("tags", []),
    )
    item["source_id"] = pattern.get("source_id")
    item["pattern_id"] = pattern["id"]
    item["pattern_type"] = pattern.get("pattern_type")
    item["checklist"] = pattern.get("checklist", [])
    item["validation_gates"] = pattern.get("validation_gates", [])
    item["not_allowed_outputs"] = pattern.get("not_allowed_outputs", [])
    item["target_agents"] = pattern.get("target_agents", [])
    item["claims"][0]["relevant_to"] = pattern.get("tags", [])
    return item
