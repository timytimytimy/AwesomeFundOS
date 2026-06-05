from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fundos.research_cache import read_cached_results, write_cached_results


DEFAULT_TIMEOUT_SECONDS = 8


@dataclass
class PublicResearchClient:
    """Small public research adapter.

    The adapter is deliberately conservative:
    - tests can pass fully offline using fixture_path;
    - live network is opt-in via enable_network or FUNDOS_ENABLE_NETWORK=1;
    - network results are treated as leads/hypotheses unless callers classify them higher.
    """

    fixture_path: Path | None = None
    enable_network: bool = False
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    cache_root: Path | None = None
    adapter_name: str = "public_research"

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        cached = read_cached_results(self.cache_root, query, self.adapter_name, limit)
        if cached is not None:
            return cached
        if self.fixture_path:
            return write_cached_results(self.cache_root, query, self.adapter_name, limit, self._read_fixture(limit))
        if self.enable_network or os.environ.get("FUNDOS_ENABLE_NETWORK") == "1":
            try:
                return write_cached_results(self.cache_root, query, self.adapter_name, limit, self._search_duckduckgo(query, limit))
            except Exception:
                return []
        return []

    def search_plan(self, query: str, input_type: str = "topic", per_step_limit: int = 3) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        for step in build_research_plan(query, input_type):
            step_results = self.search(step["query"], limit=per_step_limit)
            if self.fixture_path:
                fixture_rows = [row for row in self._read_fixture(10_000) if fixture_matches_step(row, step["category"])]
                step_results = write_cached_results(self.cache_root, step["query"], self.adapter_name, per_step_limit, fixture_rows[:per_step_limit])
            for result in step_results:
                key = result.get("url") or f"{result.get('title')}::{result.get('snippet')}"
                if key in seen_urls:
                    continue
                seen_urls.add(key)
                rows.append(
                    normalize_result(
                        {
                            **result,
                            "research_plan_id": step["plan_id"],
                            "research_category": step["category"],
                            "research_query": step["query"],
                            "required_source_tier": step["required_source_tier"],
                        }
                    )
                )
        return rows

    def _read_fixture(self, limit: int) -> list[dict[str, Any]]:
        assert self.fixture_path is not None
        data = json.loads(Path(self.fixture_path).read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError("public research fixture must be a JSON array")
        return [normalize_result(row) for row in data[:limit]]

    def _search_duckduckgo(self, query: str, limit: int) -> list[dict[str, Any]]:
        params = urllib.parse.urlencode({"q": query, "format": "json", "no_redirect": "1", "no_html": "1"})
        url = f"https://api.duckduckgo.com/?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "AwesomeFundOS/0.1 public research adapter"})
        with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
        results: list[dict[str, Any]] = []
        abstract_url = payload.get("AbstractURL")
        if payload.get("AbstractText"):
            results.append(
                normalize_result(
                    {
                        "title": payload.get("Heading") or query,
                        "url": abstract_url or url,
                        "snippet": payload.get("AbstractText"),
                        "source_type": "web",
                        "source_tier": "tier_4_expert_opinion",
                    }
                )
            )
        for topic in payload.get("RelatedTopics", []):
            if len(results) >= limit:
                break
            if "Topics" in topic:
                for nested in topic.get("Topics", []):
                    if len(results) >= limit:
                        break
                    maybe = related_topic_to_result(nested)
                    if maybe:
                        results.append(maybe)
            else:
                maybe = related_topic_to_result(topic)
                if maybe:
                    results.append(maybe)
        return results[:limit]


def related_topic_to_result(topic: dict[str, Any]) -> dict[str, Any] | None:
    text = topic.get("Text")
    first_url = topic.get("FirstURL")
    if not text or not first_url:
        return None
    return normalize_result(
        {
            "title": text[:80],
            "url": first_url,
            "snippet": text,
            "source_type": "web",
            "source_tier": "tier_4_expert_opinion",
        }
    )


def build_research_plan(query: str, input_type: str = "topic") -> list[dict[str, str]]:
    base = query.strip()
    stock_suffix = " 股票" if input_type == "stock" else ""
    steps = [
        ("announcement", f"{base}{stock_suffix} 公告 年报 季报 交易所 cninfo", "tier_1_primary_fact", "公司公告、财报和交易所披露"),
        ("policy", f"{base} 政策 规划 通知 gov.cn 部委", "tier_1_primary_fact", "官方政策和监管口径"),
        ("news", f"{base} 新闻 行业 产业链 订单", "tier_4_expert_opinion", "新闻和行业线索"),
        ("market_data", f"{base}{stock_suffix} 行情 成交额 相对强弱 波动", "tier_1_primary_fact", "价格成交和量价摘要"),
        ("social_signal", f"{base} 大V X 雪球 讨论 情绪", "tier_5_social_signal", "社媒叙事和情绪线索"),
        ("case_library", f"{base} 历史案例 复盘 失败 案例", "tier_2_canonical_framework", "历史案例和失败模式"),
    ]
    return [
        {
            "plan_id": f"rq_{index:03d}",
            "category": category,
            "query": planned_query,
            "required_source_tier": tier,
            "purpose": purpose,
        }
        for index, (category, planned_query, tier, purpose) in enumerate(steps, start=1)
    ]


def fixture_matches_step(row: dict[str, Any], category: str) -> bool:
    explicit = row.get("fixture_category")
    if explicit:
        return explicit == category
    source_type = row.get("source_type")
    source_tier = row.get("source_tier")
    if category == "announcement":
        return source_type == "announcement"
    if category == "policy":
        return source_type == "policy"
    if category == "market_data":
        return source_type == "market_data"
    if category == "social_signal":
        return source_tier == "tier_5_social_signal"
    if category == "news":
        return source_type in {"news", "web"} and source_tier != "tier_5_social_signal"
    if category == "case_library":
        return source_type == "case"
    return False


def classify_source(title: str, url: str) -> dict[str, str]:
    text = f"{title} {url}".lower()
    if any(domain in text for domain in ["cninfo.com.cn", "sse.com.cn", "szse.cn", "bse.cn"]):
        return {"source_type": "announcement", "source_tier": "tier_1_primary_fact"}
    if any(domain in text for domain in ["gov.cn", "ndrc.gov.cn", "miit.gov.cn", "mofcom.gov.cn", "pbc.gov.cn"]):
        return {"source_type": "policy", "source_tier": "tier_1_primary_fact"}
    if any(domain in text for domain in ["x.com", "twitter.com", "weibo.com", "xueqiu.com"]):
        return {"source_type": "web", "source_tier": "tier_5_social_signal"}
    if any(word in text for word in ["公告", "年报", "季报", "招股", "disclosure", "announcement"]):
        return {"source_type": "announcement", "source_tier": "tier_1_primary_fact"}
    if any(word in text for word in ["政策", "规划", "意见", "通知"]):
        return {"source_type": "policy", "source_tier": "tier_1_primary_fact"}
    if any(word in text for word in ["研报", "研究", "analysis", "insight"]):
        return {"source_type": "web", "source_tier": "tier_4_expert_opinion"}
    return {"source_type": "web", "source_tier": "tier_4_expert_opinion"}


def normalize_result(result: dict[str, Any]) -> dict[str, Any]:
    title = str(result.get("title") or "Untitled public research result")
    url = str(result.get("url") or "")
    classified = classify_source(title, url)
    row = {
        "title": title,
        "url": url,
        "snippet": str(result.get("snippet") or result.get("summary") or ""),
        "source_type": str(result.get("source_type") or classified["source_type"]),
        "source_tier": str(result.get("source_tier") or classified["source_tier"]),
        "published_at": str(result.get("published_at") or ""),
    }
    for field in [
        "research_plan_id",
        "research_category",
        "research_query",
        "required_source_tier",
        "fixture_category",
        "retrieval_id",
        "source_hash",
        "adapter_name",
        "cache_status",
    ]:
        if result.get(field):
            row[field] = result[field]
    return row


def tool_result_to_evidence(evidence_id: str, result: dict[str, Any], retrieved_at: str, relevant_to: list[str]) -> dict[str, Any]:
    normalized = normalize_result(result)
    tier = normalized["source_tier"]
    claim_type = "fact" if tier == "tier_1_primary_fact" else "hypothesis"
    confidence = "high" if tier == "tier_1_primary_fact" else "medium" if tier in {"tier_2_canonical_framework", "tier_3_verified_public_practitioner"} else "low"
    evidence = {
        "id": evidence_id,
        "source_type": normalized["source_type"],
        "source_tier": tier,
        "source_id": "public_research",
        "title": normalized["title"],
        "url": normalized["url"],
        "source_url": normalized["url"],
        "published_at": normalized["published_at"],
        "retrieved_at": retrieved_at,
        "raw_excerpt": normalized["snippet"],
        "summary": normalized["snippet"] or normalized["title"],
        "confidence": confidence,
        "claims": [
            {
                "claim_id": f"C{evidence_id[1:]}",
                "claim_text": normalized["snippet"] or normalized["title"],
                "claim_type": claim_type,
                "confidence": confidence,
                "relevant_to": relevant_to,
                "supports": [],
                "contradicts": [],
            }
        ],
    }
    for field in ["research_plan_id", "research_category", "research_query", "required_source_tier", "retrieval_id", "source_hash", "adapter_name", "cache_status"]:
        if normalized.get(field):
            evidence[field] = normalized[field]
    return evidence
