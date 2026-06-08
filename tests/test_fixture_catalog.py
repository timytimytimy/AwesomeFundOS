import json
import unittest
from pathlib import Path

from fundos.fixture_catalog import (
    REPO_ROOT,
    fixture_catalog_missing_paths,
    list_fixture_summaries,
    load_fixture_catalog,
    resolve_fixture,
)


REQUIRED_CATEGORIES = {"announcement", "policy", "news", "market_data", "social_signal", "case_library"}
REQUIRED_FIXTURES = {"robotics", "consumer_healthcare", "cyclical_macro", "policy_event"}


class FixtureCatalogTests(unittest.TestCase):
    def test_catalog_lists_cross_industry_public_research_fixtures(self):
        catalog = load_fixture_catalog()

        self.assertEqual(catalog["artifact_type"], "public_research_fixture_catalog")
        self.assertEqual(catalog["fixture_count"], 4)
        self.assertEqual(set(catalog["fixtures"]), REQUIRED_FIXTURES)
        self.assertFalse(catalog["real_trade_allowed"])
        self.assertEqual(catalog["broker_integration"], "disabled")
        self.assertIn("social_signal_never_direct_buy", catalog["controls"])

    def test_catalog_paths_exist_and_each_fixture_covers_required_categories(self):
        catalog = load_fixture_catalog()

        self.assertEqual(fixture_catalog_missing_paths(catalog), [])
        for fixture_id, row in catalog["fixtures"].items():
            path = Path(row["research_fixture"])
            if not path.is_absolute():
                path = REPO_ROOT / path
            payload = json.loads(path.read_text(encoding="utf-8"))
            categories = {item.get("fixture_category") for item in payload if isinstance(item, dict)}
            self.assertTrue(REQUIRED_CATEGORIES.issubset(categories), fixture_id)
            social_rows = [item for item in payload if item.get("fixture_category") == "social_signal"]
            self.assertTrue(social_rows, fixture_id)
            self.assertTrue(all(item.get("source_tier") == "tier_5_social_signal" for item in social_rows), fixture_id)

    def test_resolve_fixture_returns_absolute_paths_and_unknown_id_fails(self):
        row = resolve_fixture("consumer_healthcare")

        self.assertEqual(row["fixture_id"], "consumer_healthcare")
        self.assertTrue(Path(row["research_fixture"]).is_absolute())
        self.assertTrue(Path(row["research_fixture"]).exists())
        self.assertTrue(Path(row["market_replay_fixture"]).is_absolute())
        self.assertTrue(Path(row["market_replay_fixture"]).exists())
        with self.assertRaises(KeyError):
            resolve_fixture("missing_fixture")

    def test_list_fixture_summaries_is_sorted_for_stable_cli_output(self):
        ids = [row["fixture_id"] for row in list_fixture_summaries()]

        self.assertEqual(ids, sorted(REQUIRED_FIXTURES))


if __name__ == "__main__":
    unittest.main()
