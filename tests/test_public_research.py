import json
import tempfile
import unittest
from pathlib import Path

import yaml

from fundos.public_research import PublicResearchClient, classify_source, tool_result_to_evidence
from fundos.evidence import make_evidence_pack, validate_evidence_pack


class PublicResearchTests(unittest.TestCase):
    def test_classify_source_promotes_a_share_primary_and_policy_urls(self):
        announcement = classify_source("关于机器人业务的公司公告", "https://www.cninfo.com.cn/new/disclosure/detail")
        self.assertEqual(announcement["source_type"], "announcement")
        self.assertEqual(announcement["source_tier"], "tier_1_primary_fact")

        exchange = classify_source("上市公司公告", "https://www.sse.com.cn/disclosure/listedinfo/announcement/")
        self.assertEqual(exchange["source_type"], "announcement")
        self.assertEqual(exchange["source_tier"], "tier_1_primary_fact")

        policy = classify_source("机器人产业政策", "https://www.gov.cn/zhengce/content/test.htm")
        self.assertEqual(policy["source_type"], "policy")
        self.assertEqual(policy["source_tier"], "tier_1_primary_fact")

        social = classify_source("热门大V观点", "https://x.com/example/status/1")
        self.assertEqual(social["source_type"], "web")
        self.assertEqual(social["source_tier"], "tier_5_social_signal")

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

    def test_make_evidence_pack_builds_claim_index_source_coverage_and_validates_schema(self):
        results = [
            {"title": "机器人公告", "url": "https://www.cninfo.com.cn/new/disclosure/detail", "snippet": "公告验证机器人订单。"},
            {"title": "X讨论", "url": "https://x.com/example/status/1", "snippet": "社媒显示机器人热度。"},
        ]
        pack = make_evidence_pack("run1", "topic", "机器人产业链", public_results=results)

        self.assertIn("claim_index", pack)
        self.assertIn("source_coverage", pack)
        self.assertEqual(pack["source_coverage"]["public_research_items"], 2)
        self.assertGreaterEqual(pack["source_coverage"]["tier_counts"]["tier_1_primary_fact"], 1)
        self.assertGreaterEqual(pack["source_coverage"]["tier_counts"]["tier_5_social_signal"], 1)
        first_claim = pack["evidence_items"][0]["claims"][0]
        self.assertIn(first_claim["claim_id"], pack["claim_index"])
        self.assertEqual(pack["claim_index"][first_claim["claim_id"]]["evidence_id"], pack["evidence_items"][0]["id"])
        validation = validate_evidence_pack(pack)
        self.assertTrue(validation["valid"], validation)
        self.assertEqual(validation["error_count"], 0)

    def test_validate_evidence_pack_reports_missing_claim_fields(self):
        broken = {
            "run_id": "run1",
            "market": "CN_A_SHARE",
            "query": "机器人",
            "retrieval_plan": [],
            "evidence_items": [
                {"id": "E001", "source_type": "announcement", "source_tier": "tier_1_primary_fact", "claims": [{"claim_text": "missing id"}]}
            ],
            "unresolved_gaps": [],
        }

        validation = validate_evidence_pack(broken)

        self.assertFalse(validation["valid"])
        self.assertIn("evidence_items[0].claims[0].claim_id missing", validation["errors"])


if __name__ == "__main__":
    unittest.main()
