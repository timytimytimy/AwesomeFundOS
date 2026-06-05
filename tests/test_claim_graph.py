import tempfile
import unittest
from pathlib import Path

from fundos.claim_graph import load_claim_graph_report, load_claim_graph_spec, write_claim_graph
from fundos.decision import make_decision_memo
from fundos.evidence import make_evidence_pack
from fundos.harness import make_evaluation_for_run
from fundos.io import REPO_ROOT, read_yaml, write_yaml
from fundos.tool_runtime import run_fixture_tool_runtime


class ClaimGraphTests(unittest.TestCase):
    def test_source_controlled_claim_graph_spec_defines_traceability_controls(self):
        path = REPO_ROOT / "specs" / "evidence" / "claim-graph.yaml"
        self.assertTrue(path.exists(), path)
        spec = load_claim_graph_spec()
        self.assertEqual(spec["graph_id"], "claim_graph_v1")
        self.assertIn("claim_to_evidence_trace_required", spec["controls"])
        self.assertIn("tool_result_trace_required_for_tool_evidence", spec["controls"])
        self.assertIn("low_tier_claims_cannot_drive_decision", spec["controls"])
        self.assertIn("methodology_sources_are_not_direct_trade_evidence", spec["controls"])
        self.assertFalse(spec["real_trade_allowed"])
        self.assertEqual(spec["broker_integration"], "disabled")

    def test_write_claim_graph_links_decision_agent_claims_evidence_and_tool_results(self):
        pack = make_evidence_pack("claim-run", "topic", "机器人产业链投资机会")
        selected = [
            {"agent_id": "fund_manager", "role": "FundManager"},
            {"agent_id": "risk_manager", "role": "RiskManager"},
        ]
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            write_yaml(run_path / "evidence" / "evidence-pack.yaml", pack)
            run_fixture_tool_runtime(run_path, selected, pack)
            memo = make_decision_memo("claim-run", "机器人产业链投资机会", pack, agent_outputs=[])
            write_yaml(run_path / "decision" / "final-decision-memo.yaml", memo)
            write_yaml(run_path / "agent_work" / "fund_manager.structured.yaml", {
                "agent_id": "fund_manager",
                "stance": "continue_research",
                "confidence": "medium",
                "key_claims": [
                    {"evidence_id": pack["evidence_items"][0]["id"], "claim_id": pack["evidence_items"][0]["claims"][0]["claim_id"], "source_tier": "tier_1_primary_fact"}
                ],
            })

            report = write_claim_graph(run_path, pack)

            self.assertEqual(report["artifact_type"], "claim_graph_report")
            self.assertEqual(report["run_id"], "claim-run")
            self.assertGreaterEqual(report["claim_node_count"], len(pack["evidence_items"]))
            self.assertGreaterEqual(report["evidence_node_count"], len(pack["evidence_items"]))
            self.assertGreaterEqual(report["decision_claim_count"], 1)
            self.assertGreaterEqual(report["agent_claim_count"], 1)
            self.assertGreaterEqual(report["tool_result_node_count"], 1)
            self.assertGreaterEqual(report["traceability_score"], 85)
            self.assertEqual(report["unsupported_decision_claims"], [])
            self.assertFalse(report["real_trade_allowed"])
            self.assertEqual(report["broker_integration"], "disabled")
            self.assertTrue((run_path / "evidence" / "claim-graph.yaml").exists())
            self.assertTrue((run_path / "harness" / "claim-graph.yaml").exists())

            graph = read_yaml(run_path / "evidence" / "claim-graph.yaml")
            node_kinds = {node["kind"] for node in graph["nodes"]}
            edge_kinds = {edge["kind"] for edge in graph["edges"]}
            self.assertTrue({"evidence", "claim", "decision", "agent_output", "tool_result"} <= node_kinds)
            self.assertIn("supported_by", edge_kinds)
            self.assertIn("derived_from_tool_result", edge_kinds)
            self.assertTrue(all(node.get("source_tier") != "tier_5_social_signal" or node.get("decision_eligible") is False for node in graph["nodes"] if node["kind"] == "claim"))

            loaded = load_claim_graph_report(run_path)
            self.assertEqual(loaded["artifact_type"], "claim_graph_report")
            self.assertEqual(loaded["traceability_score"], report["traceability_score"])

    def test_claim_graph_flags_unsupported_decision_references_and_low_tier_decision_claims(self):
        pack = make_evidence_pack("claim-bad", "topic", "机器人产业链投资机会")
        low_item = pack["evidence_items"][0].copy()
        low_item["id"] = "LOW001"
        low_item["source_tier"] = "tier_5_social_signal"
        low_item["claims"] = [{"claim_id": "LOWC001", "claim_text": "社媒热度很高", "claim_type": "hypothesis", "confidence": "low", "relevant_to": ["sentiment"]}]
        pack["evidence_items"].append(low_item)
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            write_yaml(run_path / "decision" / "final-decision-memo.yaml", {
                "run_id": "claim-bad",
                "evidence_references": [
                    {"evidence_id": "MISSING", "claim_id": "NOPE", "usage": "supports final decision"},
                    {"evidence_id": "LOW001", "claim_id": "LOWC001", "usage": "supports final decision"},
                ],
            })

            report = write_claim_graph(run_path, pack)

            self.assertIn({"evidence_id": "MISSING", "claim_id": "NOPE"}, report["unsupported_decision_claims"])
            self.assertIn({"evidence_id": "LOW001", "claim_id": "LOWC001", "source_tier": "tier_5_social_signal"}, report["low_tier_decision_claims"])
            self.assertIn("unsupported_decision_claims", report["blocking_issues"])
            self.assertIn("low_tier_decision_claim_used", report["blocking_issues"])
            self.assertLess(report["traceability_score"], 85)
            self.assertFalse(report["real_trade_allowed"])

    def test_evaluation_reads_claim_graph_quality_and_accepts_output(self):
        pack = make_evidence_pack("claim-eval", "topic", "机器人产业链投资机会")
        selected = [{"agent_id": "fund_manager", "role": "FundManager"}]
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            write_yaml(run_path / "harness" / "claim-graph.yaml", {
                "artifact_type": "claim_graph_report",
                "traceability_score": 94,
                "claim_node_count": 11,
                "evidence_node_count": 11,
                "decision_claim_count": 4,
                "agent_claim_count": 3,
                "tool_result_node_count": 2,
                "unsupported_decision_claims": [],
                "low_tier_decision_claims": [],
                "blocking_issues": [],
                "controls": ["claim_to_evidence_trace_required"],
                "real_trade_allowed": False,
                "broker_integration": "disabled",
            })

            evaluation = make_evaluation_for_run("claim-eval", selected, pack, run_path)

        self.assertIn("claim_graph_quality", evaluation)
        self.assertEqual(evaluation["claim_graph_quality"]["traceability_score"], 94)
        self.assertIn("claim_graph", evaluation["accepted_outputs"])
        self.assertEqual(evaluation["dimension_scores"]["claim_traceability"], 94)


if __name__ == "__main__":
    unittest.main()
