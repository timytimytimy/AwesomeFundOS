import json
import tempfile
import unittest
from pathlib import Path

import yaml

from fundos.public_research import PublicResearchClient, tool_result_to_evidence
from fundos.cli import make_evidence_pack


class PublicResearchTests(unittest.TestCase):
    def test_tool_result_to_evidence_preserves_url_source_tier_and_claim(self):
        result = {
            "title": "工业机器人政策新闻",
            "url": "https://example.com/robotics-policy",
            "snippet": "政策支持机器人产业链发展，产业链国产替代加速。",
            "source_type": "news",
            "source_tier": "tier_4_expert_opinion",
            "published_at": "2026-06-01",
        }
        evidence = tool_result_to_evidence("E900", result, "2026-06-05T00:00:00+00:00", ["industry", "policy"])
        self.assertEqual(evidence["id"], "E900")
        self.assertEqual(evidence["url"], "https://example.com/robotics-policy")
        self.assertEqual(evidence["source_tier"], "tier_4_expert_opinion")
        self.assertEqual(evidence["claims"][0]["claim_type"], "hypothesis")
        self.assertIn("industry", evidence["claims"][0]["relevant_to"])

    def test_public_research_client_reads_local_fixture_without_network(self):
        with tempfile.TemporaryDirectory() as d:
            fixture = Path(d) / "fixture.json"
            fixture.write_text(json.dumps([
                {"title": "公告", "url": "https://example.com/ann", "snippet": "公司公告显示机器人业务进展。", "source_type": "announcement", "source_tier": "tier_1_primary_fact"},
                {"title": "新闻", "url": "https://example.com/news", "snippet": "市场关注机器人主题。", "source_type": "news", "source_tier": "tier_4_expert_opinion"},
            ], ensure_ascii=False))
            client = PublicResearchClient(fixture_path=fixture)
            results = client.search("机器人产业链")
            self.assertEqual(len(results), 2)
            self.assertEqual(results[0]["source_type"], "announcement")

    def test_public_research_client_network_failure_degrades_to_empty_results(self):
        class FailingClient(PublicResearchClient):
            def _search_duckduckgo(self, query, limit):
                raise TimeoutError("simulated timeout")

        client = FailingClient(enable_network=True)
        self.assertEqual(client.search("机器人"), [])

    def test_make_evidence_pack_can_include_public_research_results(self):
        results = [
            {"title": "机器人公告", "url": "https://example.com/ann", "snippet": "公告验证机器人订单。", "source_type": "announcement", "source_tier": "tier_1_primary_fact"}
        ]
        pack = make_evidence_pack("run1", "topic", "机器人产业链", public_results=results)
        urls = {item.get("url") for item in pack["evidence_items"]}
        self.assertIn("https://example.com/ann", urls)
        self.assertIn("public_research", pack["retrieval_plan"])
        item = next(item for item in pack["evidence_items"] if item.get("url") == "https://example.com/ann")
        self.assertEqual(item["source_type"], "announcement")
        self.assertEqual(item["claims"][0]["confidence"], "high")


if __name__ == "__main__":
    unittest.main()
