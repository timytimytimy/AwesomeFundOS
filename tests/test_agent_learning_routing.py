import json
import tempfile
import unittest
from pathlib import Path

import yaml

from fundos.agent_learning import generate_agent_learning_candidates, route_agent_learning_candidate
from fundos.evolution import run_evolution_gate, write_jsonl
from fundos.memory import load_memory_writeback_summary
from fundos.capabilities import load_capability_summary


class AgentLearningRoutingTests(unittest.TestCase):
    def test_route_agent_learning_candidate_classifies_memory_capability_skill_and_protected_layers(self):
        memory = route_agent_learning_candidate({'candidate_type': 'reflection_update', 'target_scope': 'agent_memory'})
        self.assertEqual(memory['adoption_route'], 'memory_writeback_after_evolution')
        self.assertEqual(memory['memory_write_policy'], 'auto_after_evolution_accept')
        self.assertFalse(memory['human_approval_required'])

        workflow = route_agent_learning_candidate({'candidate_type': 'workflow_update', 'target_scope': 'workflow'})
        self.assertEqual(workflow['adoption_route'], 'managed_capability_pending_human_apply')
        self.assertEqual(workflow['capability_kind'], 'workflow')
        self.assertEqual(workflow['memory_write_policy'], 'no_direct_memory_write')
        self.assertTrue(workflow['human_approval_required'])

        skill = route_agent_learning_candidate({'candidate_type': 'skill_update', 'target_scope': 'skill'})
        self.assertEqual(skill['adoption_route'], 'skill_patch_pending_human_apply')
        self.assertEqual(skill['capability_kind'], 'skill')
        self.assertEqual(skill['memory_write_policy'], 'no_direct_memory_write')
        self.assertTrue(skill['human_approval_required'])

        protected = route_agent_learning_candidate({'candidate_type': 'tool_permission_update', 'target_scope': 'tool_permission'})
        self.assertEqual(protected['adoption_route'], 'forbidden_protected_mutation')
        self.assertEqual(protected['memory_write_policy'], 'blocked')
        self.assertFalse(protected['protected_mutation_allowed'])

    def test_generated_candidates_include_route_counts_and_no_protected_auto_apply(self):
        with tempfile.TemporaryDirectory() as d:
            run_path = Path(d)
            write_minimal_run(run_path, 'run_routes')
            write_agent_tool_use(run_path, [
                {
                    'agent_id': 'position_trend_trader',
                    'score': 30,
                    'called_tools': ['memory_retrieval'],
                    'missing_required_tools': ['market_data_query'],
                    'forbidden_called_tools': [],
                    'confidence_cap_required': True,
                    'tool_results_linked_to_claim_graph': 0,
                    'real_trade_allowed': False,
                    'broker_integration': 'disabled',
                }
            ])
            write_failure_patterns(run_path, [
                {
                    'pattern_id': 'fp_low_reflection',
                    'agent_id': 'fund_manager',
                    'category': 'missing_evidence',
                    'severity': 'medium',
                    'description': 'missed filing check',
                    'prevention_check': 'cite filing before confidence upgrade',
                }
            ])

            report = generate_agent_learning_candidates(run_path)

            self.assertGreaterEqual(report['route_counts']['managed_capability_pending_human_apply'], 1)
            self.assertGreaterEqual(report['route_counts']['memory_writeback_after_evolution'], 1)
            for candidate in report['candidates']:
                self.assertIn('adoption_route', candidate)
                self.assertIn('memory_write_policy', candidate)
                self.assertFalse(candidate['real_trade_allowed'])
                self.assertEqual(candidate['broker_integration'], 'disabled')
                self.assertFalse(candidate['protected_mutation_allowed'])
                self.assertNotIn(candidate['candidate_type'], {'profile_update', 'tool_permission_update', 'risk_limit_update'})
                self.assertNotIn(candidate['target_scope'], {'core_profile', 'tool_permission', 'risk_limit'})

    def test_evolution_routes_capability_candidate_to_human_apply_without_auto_memory_write(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            run_path = root / 'runs' / 'run_capability_route'
            write_acceptance_artifacts(run_path)
            write_jsonl(run_path / 'evolution/candidates.jsonl', [
                {
                    'candidate_id': 'agent_learning_workflow_route',
                    'run_id': 'run_capability_route',
                    'source_agent': 'evaluation_harness',
                    'target_agent': 'position_trend_trader',
                    'candidate_type': 'workflow_update',
                    'target_scope': 'workflow',
                    'proposal': '缺失行情工具时必须降低置信度并生成补证据任务。',
                    'source_basis': [{'evidence_id': 'harness/agent-tool-use.yaml', 'source_tier': 'tier_2_canonical_framework'}],
                    'required_tests': ['historical_case_replay', 'role_drift_check', 'evidence_quality_check'],
                    'adoption_route': 'managed_capability_pending_human_apply',
                    'memory_write_policy': 'no_direct_memory_write',
                    'human_approval_required': True,
                    'protected_mutation_allowed': False,
                    'controls': ['no_direct_profile_mutation', 'no_real_trade_action'],
                    'real_trade_allowed': False,
                    'broker_integration': 'disabled',
                }
            ])

            results = run_evolution_gate(run_path)

            self.assertEqual(results[0]['decision'], 'accept')
            memory_summary = load_memory_writeback_summary(run_path)
            self.assertEqual(memory_summary['memory_writes'], 0)
            cap_summary = load_capability_summary(run_path)
            self.assertEqual(cap_summary['pending_human_apply'], 1)
            registry = root / 'memory/agents/position_trend_trader/capabilities/workflow.jsonl'
            self.assertTrue(registry.exists())
            row = json.loads(registry.read_text(encoding='utf-8').splitlines()[0])
            self.assertEqual(row['application_status'], 'pending_human_apply')
            self.assertEqual(row['adoption_route'], 'managed_capability_pending_human_apply')
            self.assertEqual(row['memory_write_policy'], 'no_direct_memory_write')

    def test_evolution_routes_reflection_candidate_to_memory_only(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            run_path = root / 'runs' / 'run_memory_route'
            write_acceptance_artifacts(run_path)
            write_jsonl(run_path / 'evolution/candidates.jsonl', [
                {
                    'candidate_id': 'agent_learning_memory_route',
                    'run_id': 'run_memory_route',
                    'source_agent': 'evaluation_harness',
                    'target_agent': 'fund_manager',
                    'candidate_type': 'reflection_update',
                    'target_scope': 'agent_memory',
                    'proposal': '复盘时记录一手证据缺口，防止方法论源替代事实。',
                    'source_basis': [{'evidence_id': 'learning/failure-patterns.yaml', 'source_tier': 'tier_2_canonical_framework'}],
                    'required_tests': ['historical_case_replay', 'role_drift_check', 'evidence_quality_check'],
                    'adoption_route': 'memory_writeback_after_evolution',
                    'memory_write_policy': 'auto_after_evolution_accept',
                    'human_approval_required': False,
                    'protected_mutation_allowed': False,
                    'controls': ['no_direct_profile_mutation', 'no_real_trade_action'],
                    'real_trade_allowed': False,
                    'broker_integration': 'disabled',
                }
            ])

            results = run_evolution_gate(run_path)

            self.assertEqual(results[0]['decision'], 'accept')
            memory_summary = load_memory_writeback_summary(run_path)
            self.assertEqual(memory_summary['memory_writes'], 1)
            self.assertFalse((root / 'memory/agents/fund_manager/capabilities/reflection.jsonl').exists())
            semantic = root / 'memory/agents/fund_manager/semantic_memory.md'
            self.assertIn('agent_learning_memory_route', semantic.read_text(encoding='utf-8'))


def write_minimal_run(run_path: Path, run_id: str) -> None:
    (run_path / 'harness').mkdir(parents=True, exist_ok=True)
    (run_path / 'learning').mkdir(parents=True, exist_ok=True)
    (run_path / 'evolution').mkdir(parents=True, exist_ok=True)
    (run_path / 'run.yaml').write_text(yaml.safe_dump({'run_id': run_id, 'selected_agents': []}, allow_unicode=True), encoding='utf-8')


def write_agent_tool_use(run_path: Path, agent_results: list[dict]) -> None:
    report = {
        'artifact_type': 'agent_tool_use_report',
        'run_id': yaml.safe_load((run_path / 'run.yaml').read_text(encoding='utf-8'))['run_id'],
        'overall_score': 30,
        'agent_count': len(agent_results),
        'agents_with_missing_required_tools': sum(1 for row in agent_results if row.get('missing_required_tools')),
        'agents_with_forbidden_tool_calls': 0,
        'agent_results': agent_results,
        'controls': ['confidence_cap_when_tools_missing', 'no_real_trade_action'],
        'real_trade_allowed': False,
        'broker_integration': 'disabled',
    }
    (run_path / 'harness/agent-tool-use.yaml').write_text(yaml.safe_dump(report, allow_unicode=True), encoding='utf-8')


def write_failure_patterns(run_path: Path, patterns: list[dict]) -> None:
    report = {
        'artifact_type': 'failure_pattern_report',
        'run_id': yaml.safe_load((run_path / 'run.yaml').read_text(encoding='utf-8'))['run_id'],
        'pattern_count': len(patterns),
        'patterns': patterns,
        'controls': ['review_before_evolution', 'no_real_trade_action'],
        'real_trade_allowed': False,
        'broker_integration': 'disabled',
    }
    (run_path / 'learning/failure-patterns.yaml').write_text(yaml.safe_dump(report, allow_unicode=True), encoding='utf-8')


def write_acceptance_artifacts(run_path: Path) -> None:
    (run_path / 'evolution').mkdir(parents=True, exist_ok=True)
    (run_path / 'harness').mkdir(parents=True, exist_ok=True)
    (run_path / 'evaluations').mkdir(parents=True, exist_ok=True)
    (run_path / 'run.yaml').write_text(yaml.safe_dump({'run_id': run_path.name, 'selected_agents': []}, allow_unicode=True), encoding='utf-8')
    (run_path / 'harness/historical-case-replay.yaml').write_text(yaml.safe_dump({'case_replay_score': 82, 'case_results_total': 3}, allow_unicode=True), encoding='utf-8')
    (run_path / 'harness/agent-harness.yaml').write_text(yaml.safe_dump({'aggregate_scores': {'role_consistency': 88, 'skill_invocation': 90}}, allow_unicode=True), encoding='utf-8')
    (run_path / 'evaluations/evaluation-report.yaml').write_text(yaml.safe_dump({'source_coverage': {'tier_1_primary_fact': 2}, 'dimension_scores': {'evidence_quality': 86}}, allow_unicode=True), encoding='utf-8')


if __name__ == '__main__':
    unittest.main()
