import json
import tempfile
import unittest
from pathlib import Path

import yaml

from fundos.public_research import PublicResearchClient
from fundos.research_cache import load_research_manifest, write_run_research_manifest


class ResearchCacheTests(unittest.TestCase):
    def test_public_research_client_writes_query_cache_and_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            fixture = root / "fixture.json"
            fixture.write_text(json.dumps([
                {"title": "机器人公告", "url": "https://www.cninfo.com.cn/new/disclosure/detail", "snippet": "公告验证订单。"},
                {"title": "机器人政策", "url": "https://www.gov.cn/zhengce/content/test.htm", "snippet": "政策支持机器人。"},
            ], ensure_ascii=False), encoding="utf-8")
            client = PublicResearchClient(fixture_path=fixture, cache_root=root / "cache" / "research", adapter_name="fixture")

            first = client.search("机器人产业链", limit=5)
            second = client.search("机器人产业链", limit=5)

            self.assertEqual(first, second)
            cache_files = list((root / "cache" / "research").glob("*.json"))
            self.assertEqual(len(cache_files), 1)
            cached = json.loads(cache_files[0].read_text(encoding="utf-8"))
            self.assertEqual(cached["query"], "机器人产业链")
            self.assertEqual(cached["adapter_name"], "fixture")
            self.assertEqual(cached["cache_status"], "stored")
            self.assertEqual(len(cached["results"]), 2)
            self.assertTrue(cached["results"][0]["retrieval_id"].startswith("pr_"))
            self.assertIn("source_hash", cached["results"][0])
            self.assertEqual(second[0]["cache_status"], "hit")

    def test_write_run_research_manifest_records_cache_and_boundaries(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            run_path = root / "runs" / "run-cache"
            results = [
                {"title": "公告", "url": "https://www.cninfo.com.cn/new/disclosure/detail", "snippet": "公告", "source_type": "announcement", "source_tier": "tier_1_primary_fact", "retrieval_id": "pr_001", "cache_status": "stored"},
                {"title": "大V", "url": "https://x.com/example/status/1", "snippet": "观点", "source_type": "web", "source_tier": "tier_5_social_signal", "retrieval_id": "pr_002", "cache_status": "stored"},
            ]

            manifest = write_run_research_manifest(run_path, query="机器人产业链", results=results, adapter_name="fixture", cache_root=root / "cache" / "research")

            self.assertEqual(manifest["artifact_type"], "public_research_manifest")
            self.assertEqual(manifest["query"], "机器人产业链")
            self.assertEqual(manifest["result_count"], 2)
            self.assertEqual(manifest["source_tier_counts"]["tier_1_primary_fact"], 1)
            self.assertEqual(manifest["source_tier_counts"]["tier_5_social_signal"], 1)
            self.assertIn("social_signal_never_direct_buy", manifest["boundary_controls"])
            self.assertTrue((run_path / "evidence" / "public-research-manifest.yaml").exists())
            loaded = load_research_manifest(run_path)
            self.assertEqual(loaded["result_count"], 2)

    def test_public_research_cache_key_separates_query_and_adapter(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            fixture = root / "fixture.json"
            fixture.write_text(json.dumps([{"title": "公告", "url": "https://example.com/a", "snippet": "A"}], ensure_ascii=False), encoding="utf-8")
            client_a = PublicResearchClient(fixture_path=fixture, cache_root=root / "cache", adapter_name="fixture_a")
            client_b = PublicResearchClient(fixture_path=fixture, cache_root=root / "cache", adapter_name="fixture_b")

            client_a.search("机器人")
            client_b.search("机器人")
            client_a.search("低空经济")

            self.assertEqual(len(list((root / "cache").glob("*.json"))), 3)


if __name__ == "__main__":
    unittest.main()
