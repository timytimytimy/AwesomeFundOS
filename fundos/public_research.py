from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        if self.fixture_path:
            return self._read_fixture(limit)
        if self.enable_network or os.environ.get("FUNDOS_ENABLE_NETWORK") == "1":
            try:
                return self._search_duckduckgo(query, limit)
            except Exception:
                return []
        return []

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


def normalize_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": str(result.get("title") or "Untitled public research result"),
        "url": str(result.get("url") or ""),
        "snippet": str(result.get("snippet") or result.get("summary") or ""),
        "source_type": str(result.get("source_type") or "web"),
        "source_tier": str(result.get("source_tier") or "tier_4_expert_opinion"),
        "published_at": str(result.get("published_at") or ""),
    }


def tool_result_to_evidence(evidence_id: str, result: dict[str, Any], retrieved_at: str, relevant_to: list[str]) -> dict[str, Any]:
    normalized = normalize_result(result)
    tier = normalized["source_tier"]
    claim_type = "fact" if tier == "tier_1_primary_fact" else "hypothesis"
    confidence = "high" if tier == "tier_1_primary_fact" else "medium" if tier in {"tier_2_canonical_framework", "tier_3_verified_public_practitioner"} else "low"
    return {
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
