import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from fundos.system_audit import run_system_audit

ROOT = Path(__file__).resolve().parents[1]
CLI = [sys.executable, '-m', 'fundos.cli']


def run_cli(args, cwd):
    import os
    env = os.environ.copy()
    env['PYTHONPATH'] = str(ROOT) + os.pathsep + env.get('PYTHONPATH', '')
    return subprocess.run(CLI + args, cwd=cwd, text=True, capture_output=True, env=env)


class SystemAuditTests(unittest.TestCase):
    def test_system_audit_covers_original_organization_requirements(self):
        report = run_system_audit(ROOT)

        self.assertEqual(report['artifact_type'], 'system_requirement_coverage_audit')
        self.assertEqual(report['agent_count'], 19)
        self.assertGreaterEqual(report['overall_coverage_score'], 90)
        self.assertFalse(report['real_trade_allowed'])
        self.assertEqual(report['broker_integration'], 'disabled')
        categories = {row['category'] for row in report['requirements']}
        for expected in {
            'prd',
            'agent_identity',
            'agent_skills_tools_memory',
            'context_management',
            'harness_evaluation',
            'learning_evolution',
            'case_library',
            'tooling',
            'governance',
            'safety_boundaries',
            'cli_operability',
        }:
            self.assertIn(expected, categories)
        by_id = {row['requirement_id']: row for row in report['requirements']}
        for requirement_id in [
            'prd.overall_and_modules_exist',
            'agents.all_roster_agents_have_cards_and_skills',
            'agents.all_roster_agents_have_context_tool_memory_policies',
            'agents.agent_cards_expose_profile_harness_memory_evolution',
            'agents.skill_files_expose_purpose_workflow_context_safety',
            'memory.persistent_threads_and_memory_policies',
            'harness.agent_tool_context_skill_market_case_claim_evaluations',
            'learning.source_ingestion_agent_learning_evolution_gate',
            'evolution.human_approval_capability_apply_guarded',
            'safety.no_real_trade_or_broker_integration',
        ]:
            self.assertEqual(by_id[requirement_id]['status'], 'pass', requirement_id)
            self.assertTrue(by_id[requirement_id]['evidence'], requirement_id)

    def test_system_audit_writes_report_files(self):
        with tempfile.TemporaryDirectory() as d:
            out_dir = Path(d)
            report = run_system_audit(ROOT, out_dir=out_dir)

            yaml_path = out_dir / 'system-audit.yaml'
            md_path = out_dir / 'system-audit.md'
            self.assertTrue(yaml_path.exists())
            self.assertTrue(md_path.exists())
            loaded = yaml.safe_load(yaml_path.read_text(encoding='utf-8'))
            self.assertEqual(loaded['artifact_type'], 'system_requirement_coverage_audit')
            self.assertIn('Requirement Coverage Audit', md_path.read_text(encoding='utf-8'))
            self.assertEqual(report['output_paths']['yaml'], str(yaml_path))

    def test_system_audit_cli_outputs_summary_and_writes_reports(self):
        with tempfile.TemporaryDirectory() as d:
            cwd = Path(d)
            result = run_cli(['system', 'audit', '--repo', str(ROOT), '--out', 'audit-output'], cwd)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('system_audit=', result.stdout)
            self.assertIn('overall_coverage_score=', result.stdout)
            self.assertTrue((cwd / 'audit-output/system-audit.yaml').exists())
            report = yaml.safe_load((cwd / 'audit-output/system-audit.yaml').read_text(encoding='utf-8'))
            self.assertGreaterEqual(report['overall_coverage_score'], 90)
            self.assertFalse(report['real_trade_allowed'])


if __name__ == '__main__':
    unittest.main()
