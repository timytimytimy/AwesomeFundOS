import tempfile
import unittest
from pathlib import Path

import yaml

from fundos.committee import load_committee_protocol, write_committee_artifacts, load_collaboration_harness
from fundos.context import make_context_pack
from fundos.agent_outputs import write_agent_output
from fundos.evidence import make_evidence_pack
from fundos.harness import make_evaluation_for_run
from fundos.io import REPO_ROOT, read_yaml, write_yaml


class CommitteeProtocolTests(unittest.TestCase):
    def test_source_controlled_committee_protocol_defines_roles_gates_and_handoffs(self):
        protocol_path = REPO_ROOT / "specs" / "protocols" / "investment-committee-protocol.yaml"
        debate_path = REPO_ROOT / "specs" / "protocols" / "debate-protocol.yaml"
        handoff_path = REPO_ROOT / "specs" / "protocols" / "handoff-contract.yaml"
        for path in [protocol_path, debate_path, handoff_path]:
            self.assertTrue(path.exists(), path)
        protocol = read_yaml(protocol_path)
        self.assertEqual(protocol["protocol_id"], "investment_committee_v1")
        self.assertIn("required_roles", protocol)
        self.assertTrue({"fund_manager", "risk_manager", "bear_debater", "evaluation_harness"} <= set(protocol["required_roles"]))
        self.assertIn("decision_gates", protocol)
        self.assertIn("bear_challenge_required", protocol["decision_gates"])
        self.assertIn("risk_veto_or_position_cap_required", protocol["decision_gates"])
        self.assertIn("disagreement_preservation_required", protocol["decision_gates"])
        self.assertIn("handoff_contract", protocol)
        self.assertIn("no_real_trade_action", protocol["safety_controls"])

    def test_write_committee_artifacts_preserves_disagreement_and_vetoes(self):
        roster = read_yaml(REPO_ROOT / "specs" / "agents" / "default-roster.yaml")
        agents = {agent["id"]: agent for agent in roster["agents"]}
        selected_ids = ["fund_manager", "risk_manager", "bear_debater", "tech_growth_analyst", "position_trend_trader", "evaluation_harness"]
        pack = make_evidence_pack("committee-run", "topic", "机器人产业链投资机会")
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            outputs = []
            selected = []
            for aid in selected_ids:
                agent = agents[aid]
                selected.append({"agent_id": aid, "role": agent["role"]})
                context = make_context_pack("committee-run", agent, pack)
                write_yaml(run_path / "context" / f"{aid}.context-pack.yaml", context)
                outputs.append(write_agent_output(run_path / "agent_work" / f"{aid}.md", agent, context, "机器人产业链投资机会", pack))

            report = write_committee_artifacts(run_path, "committee-run", "机器人产业链投资机会", selected, outputs, pack)

            self.assertEqual(report["artifact_type"], "collaboration_harness_report")
            self.assertTrue((run_path / "committee" / "committee-protocol.yaml").exists())
            self.assertTrue((run_path / "committee" / "handoffs.yaml").exists())
            self.assertTrue((run_path / "committee" / "disagreement-register.yaml").exists())
            self.assertTrue((run_path / "committee" / "veto-table.yaml").exists())
            self.assertTrue((run_path / "committee" / "decision-readiness.yaml").exists())
            self.assertTrue((run_path / "debate" / "issue-table.yaml").exists())
            self.assertTrue((run_path / "harness" / "collaboration-harness.yaml").exists())
            disagreements = yaml.safe_load((run_path / "committee" / "disagreement-register.yaml").read_text())
            vetoes = yaml.safe_load((run_path / "committee" / "veto-table.yaml").read_text())
            self.assertGreaterEqual(disagreements["disagreement_count"], 1)
            self.assertTrue(any(row["owner_agent"] == "bear_debater" for row in disagreements["items"]))
            self.assertTrue(any(row["owner_agent"] == "risk_manager" for row in vetoes["items"]))
            self.assertFalse(vetoes["real_trade_allowed"])
            self.assertGreaterEqual(report["overall_score"], 70)
            self.assertTrue(report["checks"]["mandatory_roles_present"])
            self.assertTrue(report["checks"]["bear_challenge_present"])
            self.assertTrue(report["checks"]["risk_veto_or_cap_present"])

    def test_decision_memo_references_committee_protocol_and_collaboration_artifacts(self):
        roster = read_yaml(REPO_ROOT / "specs" / "agents" / "default-roster.yaml")
        agents = {agent["id"]: agent for agent in roster["agents"]}
        selected_ids = ["fund_manager", "risk_manager", "bear_debater", "tech_growth_analyst", "position_trend_trader", "evaluation_harness"]
        pack = make_evidence_pack("committee-memo-run", "topic", "机器人产业链投资机会")
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            outputs = []
            selected = []
            for aid in selected_ids:
                agent = agents[aid]
                selected.append({"agent_id": aid, "role": agent["role"]})
                context = make_context_pack("committee-memo-run", agent, pack)
                outputs.append(write_agent_output(run_path / "agent_work" / f"{aid}.md", agent, context, "机器人产业链投资机会", pack))
            collab = write_committee_artifacts(run_path, "committee-memo-run", "机器人产业链投资机会", selected, outputs, pack)
            from fundos.decision import make_decision_memo
            memo = make_decision_memo("committee-memo-run", "机器人产业链投资机会", pack, agent_outputs=outputs, collaboration_report=collab)

        self.assertIn("committee_protocol", memo)
        self.assertEqual(memo["committee_protocol"]["protocol_id"], "investment_committee_v1")
        self.assertIn("collaboration_summary", memo)
        self.assertGreaterEqual(memo["collaboration_summary"]["disagreement_count"], 1)
        self.assertIn("bear_debater", memo["committee_protocol"]["required_roles"])
        self.assertIn("risk_manager", memo["committee_protocol"]["required_roles"])
        self.assertIn("反方和风控", " ".join(memo["kill_criteria"]))

    def test_evaluation_reads_collaboration_harness_quality(self):
        pack = make_evidence_pack("committee-eval-run", "topic", "机器人产业链投资机会")
        selected = [
            {"agent_id": "fund_manager", "role": "FundManagerAgent"},
            {"agent_id": "risk_manager", "role": "RiskManagerAgent"},
            {"agent_id": "bear_debater", "role": "BearDebaterAgent"},
            {"agent_id": "evaluation_harness", "role": "EvaluationHarnessAgent"},
        ]
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            (run_path / "harness").mkdir(parents=True)
            write_yaml(run_path / "harness" / "collaboration-harness.yaml", {
                "artifact_type": "collaboration_harness_report",
                "overall_score": 86,
                "checks": {
                    "mandatory_roles_present": True,
                    "bear_challenge_present": True,
                    "risk_veto_or_cap_present": True,
                    "disagreement_preserved": True,
                },
                "blocking_issues": [],
            })

            evaluation = make_evaluation_for_run("committee-eval-run", selected, pack, run_path)

        self.assertIn("collaboration_harness_quality", evaluation)
        self.assertEqual(evaluation["collaboration_harness_quality"]["overall_score"], 86)
        self.assertIn("collaboration_harness", evaluation["accepted_outputs"])


if __name__ == "__main__":
    unittest.main()
