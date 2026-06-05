import tempfile
import unittest
from pathlib import Path

from fundos.io import REPO_ROOT, read_yaml, write_yaml
from fundos.tool_adapters import (
    evaluate_tool_adapter_contracts,
    load_tool_adapter_contracts,
    write_tool_adapter_manifest,
)


class ToolAdapterContractTests(unittest.TestCase):
    def test_source_controlled_tool_adapter_contracts_define_read_only_adapters(self):
        path = REPO_ROOT / "specs" / "tools" / "tool-adapter-contracts.yaml"
        self.assertTrue(path.exists(), path)
        spec = load_tool_adapter_contracts()
        self.assertEqual(spec["contract_id"], "tool_adapter_contracts_v1")
        adapter_ids = {adapter["adapter_id"] for adapter in spec["adapters"]}
        self.assertTrue({
            "market_data_query",
            "announcement_search",
            "financial_report_parser",
            "news_search",
            "public_web_search",
            "case_library_reader",
            "memory_retrieval",
        } <= adapter_ids)
        for adapter in spec["adapters"]:
            self.assertEqual(adapter["permission_level"], "read_only_analysis")
            self.assertFalse(adapter["real_trade_allowed"])
            self.assertEqual(adapter["broker_integration"], "disabled")
            self.assertIn("tool_result_id", adapter["output_contract"]["required_fields"])
            self.assertIn("evidence_items", adapter["output_contract"]["required_fields"])
        self.assertIn("order_placement", spec["forbidden_adapter_categories"])
        self.assertIn("broker_api", spec["forbidden_adapter_categories"])

    def test_evaluate_tool_adapter_contracts_maps_agent_required_tools_and_blocks_broker_tools(self):
        roster = read_yaml(REPO_ROOT / "specs" / "agents" / "default-roster.yaml")
        report = evaluate_tool_adapter_contracts(roster)

        self.assertEqual(report["artifact_type"], "tool_adapter_contract_report")
        self.assertGreaterEqual(report["adapter_count"], 7)
        self.assertEqual(report["unmapped_required_tools"], [])
        self.assertTrue(report["all_agent_required_tools_mapped"])
        self.assertTrue(report["all_adapters_read_only"])
        self.assertTrue(report["broker_integration_disabled"])
        self.assertFalse(report["real_trade_allowed"])
        self.assertEqual(report["blocking_issues"], [])
        self.assertIn("position_trend_trader", report["agent_tool_mapping"])
        self.assertIn("market_data_query", report["agent_tool_mapping"]["position_trend_trader"]["mapped_required_tools"])

    def test_write_tool_adapter_manifest_creates_runtime_manifest(self):
        roster = read_yaml(REPO_ROOT / "specs" / "agents" / "default-roster.yaml")
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            report = write_tool_adapter_manifest(root, roster)
            manifest_path = root / "tools" / "tool-adapter-manifest.yaml"

            self.assertTrue(manifest_path.exists())
            loaded = read_yaml(manifest_path)
            self.assertEqual(loaded["artifact_type"], "tool_adapter_contract_report")
            self.assertEqual(loaded["adapter_count"], report["adapter_count"])
            self.assertIn("source_contract_path", loaded)
            self.assertFalse(loaded["real_trade_allowed"])

    def test_tool_adapter_contracts_flag_unmapped_required_tools(self):
        roster = {
            "agents": [
                {
                    "id": "rogue_agent",
                    "role": "RogueAgent",
                    "tools": ["broker_api"],
                }
            ]
        }
        report = evaluate_tool_adapter_contracts(roster)

        self.assertFalse(report["all_agent_required_tools_mapped"])
        self.assertIn("unmapped_required_tools", report["blocking_issues"])
        self.assertIn({"agent_id": "rogue_agent", "tool": "broker_api"}, report["unmapped_required_tools"])
        self.assertFalse(report["real_trade_allowed"])


if __name__ == "__main__":
    unittest.main()
