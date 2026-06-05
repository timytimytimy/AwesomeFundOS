import json
import tempfile
import unittest
from pathlib import Path

import yaml

from fundos.evolution import run_evolution_gate
from fundos.agent_learning import generate_agent_learning_candidates, load_agent_learning_report


class AgentLearningCandidateTests(unittest.TestCase):
    def test_agent_learning_spec_declares_safe_controls(self):
        spec_path = Path('specs/learning/agent-learning-candidates.yaml')
        self.assertTrue(spec_path.exists())
        spec = yaml.safe_load(spec_path.read_text(encoding='utf-8'))
        self.assertEqual(spec['artifact_type'], 'agent_learning_candidate_spec')
        controls = set(spec['controls'])
        self.assertIn('no_direct_profile_mutation', controls)
        self.assertIn('no_real_trade_action', controls)
        self.assertIn('requires_evolution_gate', controls)
        self.assertIn('quarantine_before_memory_write', controls)
        self.assertIn('tool_permission_changes_forbidden', controls)
        self.assertFalse(spec['real_trade_allowed'])
        self.assertEqual(spec['broker_integration'], 'disabled')
        self.assertNotIn('profile_update', spec['allowed_candidate_types'])
        self.assertNotIn('tool_permission_update', spec['allowed_candidate_types'])
        self.assertNotIn('risk_limit_update', spec['allowed_candidate_types'])

    def test_missing_required_tools_generate_safe_learning_candidate_and_merge_to_evolution(self):
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            write_minimal_run(run_path, 'run_missing_tools')
            write_agent_tool_use(run_path, [
                {
                    'agent_id': 'position_trend_trader',
                    'score': 32,
                    'called_tools': ['memory_retrieval'],
                    'missing_required_tools': ['market_data_query', 'chart_summary'],
                    'forbidden_called_tools': [],
                    'confidence_cap_required': True,
                    'tool_results_linked_to_claim_graph': 0,
                    'real_trade_allowed': False,
                    'broker_integration': 'disabled',
                }
            ])

            report = generate_agent_learning_candidates(run_path)

            self.assertEqual(report['artifact_type'], 'agent_learning_candidate_report')
            self.assertEqual(report['run_id'], 'run_missing_tools')
            self.assertEqual(report['candidate_count'], 1)
            self.assertEqual(report['merged_to_evolution'], 1)
            self.assertFalse(report['real_trade_allowed'])
            self.assertEqual(report['broker_integration'], 'disabled')
            self.assertTrue((run_path / 'learning/agent-learning-candidates.jsonl').exists())
            self.assertTrue((run_path / 'learning/agent-learning-report.yaml').exists())
            self.assertTrue((run_path / 'evolution/candidates.jsonl').exists())

            candidates = read_jsonl(run_path / 'learning/agent-learning-candidates.jsonl')
            self.assertEqual(len(candidates), 1)
            candidate = candidates[0]
            self.assertEqual(candidate['target_agent'], 'position_trend_trader')
            self.assertEqual(candidate['candidate_type'], 'workflow_update')
            self.assertEqual(candidate['target_scope'], 'agent_memory')
            self.assertEqual(candidate['status'], 'proposed')
            self.assertEqual(candidate['origin'], 'agent_learning_generator_v1')
            self.assertFalse(candidate['real_trade_allowed'])
            self.assertEqual(candidate['broker_integration'], 'disabled')
            self.assertIn('market_data_query', candidate['proposal'])
            self.assertIn('chart_summary', candidate['proposal'])
            self.assertIn('agent_tool_use_reconciliation', candidate['required_tests'])
            self.assertIn('role_drift_check', candidate['required_tests'])
            self.assertIn('evidence_quality_check', candidate['required_tests'])
            self.assertIn('historical_case_replay', candidate['required_tests'])
            self.assertIn('no_direct_profile_mutation', candidate['controls'])
            self.assertIn('requires_evolution_gate', candidate['controls'])
            self.assertNotEqual(candidate['candidate_type'], 'tool_permission_update')
            self.assertNotEqual(candidate['target_scope'], 'tool_permission')

            evolution_candidates = read_jsonl(run_path / 'evolution/candidates.jsonl')
            self.assertEqual([row['candidate_id'] for row in evolution_candidates], [candidate['candidate_id']])

    def test_agent_learning_generation_is_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            write_minimal_run(run_path, 'run_idempotent')
            write_agent_tool_use(run_path, [
                {
                    'agent_id': 'fund_manager',
                    'score': 42,
                    'called_tools': ['context_reader'],
                    'missing_required_tools': ['memo_writer'],
                    'forbidden_called_tools': [],
                    'confidence_cap_required': True,
                    'tool_results_linked_to_claim_graph': 0,
                    'real_trade_allowed': False,
                    'broker_integration': 'disabled',
                }
            ])

            first = generate_agent_learning_candidates(run_path)
            second = generate_agent_learning_candidates(run_path)

            self.assertEqual(first['candidate_count'], 1)
            self.assertEqual(second['candidate_count'], 1)
            self.assertEqual(len(read_jsonl(run_path / 'learning/agent-learning-candidates.jsonl')), 1)
            self.assertEqual(len(read_jsonl(run_path / 'evolution/candidates.jsonl')), 1)

    def test_evolution_gate_consumes_agent_learning_candidates(self):
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            write_minimal_run(run_path, 'run_evolve_learning')
            write_agent_tool_use(run_path, [
                {
                    'agent_id': 'risk_manager',
                    'score': 38,
                    'called_tools': ['risk_checklist'],
                    'missing_required_tools': ['liquidity_check'],
                    'forbidden_called_tools': [],
                    'confidence_cap_required': True,
                    'tool_results_linked_to_claim_graph': 0,
                    'real_trade_allowed': False,
                    'broker_integration': 'disabled',
                }
            ])

            generated = generate_agent_learning_candidates(run_path)
            results = run_evolution_gate(run_path)

            candidate_ids = {row['candidate_id'] for row in generated['candidates']}
            result_ids = {row['candidate_id'] for row in results}
            self.assertTrue(candidate_ids <= result_ids)
            gate_rows = read_jsonl(run_path / 'evolution/evolution-gate-results.jsonl')
            self.assertTrue(any(row['candidate_id'] in candidate_ids for row in gate_rows))
            for row in gate_rows:
                if row['candidate_id'] in candidate_ids:
                    self.assertIn(row['decision'], {'accept', 'quarantine', 'reject'})
                    self.assertNotEqual(row['candidate_type'], 'profile_update')
                    self.assertNotEqual(row['target_scope'], 'tool_permission')


def write_minimal_run(run_path: Path, run_id: str) -> None:
    (run_path / 'harness').mkdir(parents=True, exist_ok=True)
    (run_path / 'learning').mkdir(parents=True, exist_ok=True)
    (run_path / 'evolution').mkdir(parents=True, exist_ok=True)
    (run_path / 'run.yaml').write_text(yaml.safe_dump({'run_id': run_id, 'selected_agents': []}, allow_unicode=True), encoding='utf-8')


def write_agent_tool_use(run_path: Path, agent_results: list[dict]) -> None:
    report = {
        'artifact_type': 'agent_tool_use_report',
        'run_id': yaml.safe_load((run_path / 'run.yaml').read_text(encoding='utf-8'))['run_id'],
        'overall_score': round(sum(row['score'] for row in agent_results) / len(agent_results), 1),
        'agent_count': len(agent_results),
        'agents_with_missing_required_tools': sum(1 for row in agent_results if row.get('missing_required_tools')),
        'agents_with_forbidden_tool_calls': sum(1 for row in agent_results if row.get('forbidden_called_tools')),
        'agent_results': agent_results,
        'controls': ['confidence_cap_when_tools_missing', 'no_real_trade_action'],
        'real_trade_allowed': False,
        'broker_integration': 'disabled',
    }
    (run_path / 'harness/agent-tool-use.yaml').write_text(yaml.safe_dump(report, allow_unicode=True), encoding='utf-8')


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


if __name__ == '__main__':
    unittest.main()
