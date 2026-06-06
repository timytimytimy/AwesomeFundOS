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
            'agents.agent_os_assets_cross_reference_roster_contract',
            'agents.agent_cards_expose_profile_harness_memory_evolution',
            'agents.skill_files_expose_purpose_workflow_context_safety',
            'memory.persistent_threads_and_memory_policies',
            'harness.agent_tool_context_skill_market_case_claim_evaluations',
            'learning.source_ingestion_agent_learning_evolution_gate',
            'evolution.human_approval_capability_apply_guarded',
            'safety.no_real_trade_or_broker_integration',
            'runtime.operating_system_manifest_schema_exists',
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

    def test_system_audit_strict_mode_checks_run_artifacts_and_fails_stub_runs(self):
        with tempfile.TemporaryDirectory() as d:
            cwd = Path(d)
            run_result = run_cli(['run', '--topic', '机器人产业链投资机会'], cwd)
            self.assertEqual(run_result.returncode, 0, run_result.stderr)
            run_rel = [line for line in run_result.stdout.splitlines() if line.startswith('run_path=')][-1].split('=', 1)[1]

            result = run_cli(['system', 'audit', '--repo', str(ROOT), '--run', run_rel, '--out', 'audit-output', '--strict'], cwd)

            self.assertNotEqual(result.returncode, 0)
            report = yaml.safe_load((cwd / 'audit-output/system-audit.yaml').read_text(encoding='utf-8'))
            self.assertIn('runtime.run_has_public_research_primary_evidence', {row['requirement_id'] for row in report['requirements']})
            self.assertGreater(report['failed_requirements'], 0)
            self.assertIn('runtime.run_has_public_research_primary_evidence', '\n'.join(report['blocking_issues']))

    def test_system_audit_strict_mode_passes_fixture_backed_run(self):
        with tempfile.TemporaryDirectory() as d:
            cwd = Path(d)
            fixture = cwd / 'research.json'
            fixture.write_text('''[
                {"title":"机器人公告","url":"https://www.cninfo.com.cn/new/disclosure/detail","snippet":"公告验证机器人订单。"},
                {"title":"机器人政策","url":"https://www.gov.cn/zhengce/content/test.htm","snippet":"政策支持机器人。"},
                {"title":"机器人新闻","url":"https://example.com/news","snippet":"新闻关注机器人。","fixture_category":"news"},
                {"title":"机器人行情","url":"https://example.com/market","snippet":"行情成交摘要。","source_type":"market_data","source_tier":"tier_1_primary_fact"},
                {"title":"机器人热度","url":"https://x.com/example/status/1","snippet":"社媒热度。"},
                {"title":"机器人案例","url":"https://example.com/case","snippet":"历史案例复盘。","source_type":"case","source_tier":"tier_2_canonical_framework"}
            ]''', encoding='utf-8')
            run_result = run_cli(['run', '--topic', '机器人产业链投资机会', '--research-fixture', str(fixture)], cwd)
            self.assertEqual(run_result.returncode, 0, run_result.stderr)
            run_rel = [line for line in run_result.stdout.splitlines() if line.startswith('run_path=')][-1].split('=', 1)[1]

            result = run_cli(['system', 'audit', '--repo', str(ROOT), '--run', run_rel, '--out', 'audit-output', '--strict'], cwd)

            self.assertEqual(result.returncode, 0, result.stderr)
            report = yaml.safe_load((cwd / 'audit-output/system-audit.yaml').read_text(encoding='utf-8'))
            self.assertEqual(report['failed_requirements'], 0)
            self.assertEqual(Path(report['runtime_run_path']).resolve(), (cwd / run_rel).resolve())
            by_id = {row['requirement_id']: row for row in report['requirements']}
            self.assertEqual(by_id['runtime.run_has_public_research_primary_evidence']['status'], 'pass')
            self.assertEqual(by_id['runtime.run_has_no_stub_blocking_issues']['status'], 'pass')
            self.assertEqual(by_id['runtime.model_records_have_concrete_policy_fields']['status'], 'pass')
            self.assertEqual(by_id['runtime.operating_system_manifest_links_agent_os_assets']['status'], 'pass')
            manifest_evidence = '\n'.join(by_id['runtime.operating_system_manifest_links_agent_os_assets']['evidence'])
            self.assertIn('system/operating-system-manifest.yaml', manifest_evidence)
            self.assertIn('system/operating-system-manifest.md', manifest_evidence)

    def test_system_audit_strict_mode_fails_missing_runtime_model_record_policy_fields(self):
        with tempfile.TemporaryDirectory() as d:
            cwd = Path(d)
            fixture = cwd / 'research.json'
            fixture.write_text('''[
                {"title":"机器人公告","url":"https://www.cninfo.com.cn/new/disclosure/detail","snippet":"公告验证机器人订单。"},
                {"title":"机器人政策","url":"https://www.gov.cn/zhengce/content/test.htm","snippet":"政策支持机器人。"},
                {"title":"机器人新闻","url":"https://example.com/news","snippet":"新闻关注机器人。","fixture_category":"news"},
                {"title":"机器人行情","url":"https://example.com/market","snippet":"行情成交摘要。","source_type":"market_data","source_tier":"tier_1_primary_fact"},
                {"title":"机器人热度","url":"https://x.com/example/status/1","snippet":"社媒热度。"},
                {"title":"机器人案例","url":"https://example.com/case","snippet":"历史案例复盘。","source_type":"case","source_tier":"tier_2_canonical_framework"}
            ]''', encoding='utf-8')
            run_result = run_cli(['run', '--topic', '机器人产业链投资机会', '--research-fixture', str(fixture)], cwd)
            self.assertEqual(run_result.returncode, 0, run_result.stderr)
            run_rel = [line for line in run_result.stdout.splitlines() if line.startswith('run_path=')][-1].split('=', 1)[1]
            run_yaml = cwd / run_rel / 'run.yaml'
            run_doc = yaml.safe_load(run_yaml.read_text(encoding='utf-8'))
            for record in run_doc['model_records']:
                record.pop('model_policy_id', None)
            run_yaml.write_text(yaml.safe_dump(run_doc, allow_unicode=True, sort_keys=False), encoding='utf-8')

            result = run_cli(['system', 'audit', '--repo', str(ROOT), '--run', run_rel, '--out', 'audit-output', '--strict'], cwd)

            self.assertNotEqual(result.returncode, 0)
            report = yaml.safe_load((cwd / 'audit-output/system-audit.yaml').read_text(encoding='utf-8'))
            by_id = {row['requirement_id']: row for row in report['requirements']}
            self.assertEqual(by_id['runtime.model_records_have_concrete_policy_fields']['status'], 'fail')
            self.assertIn('missing_model_record_fields', by_id['runtime.model_records_have_concrete_policy_fields']['details'])

    def test_system_audit_strict_mode_fails_operating_system_manifest_schema_violation(self):
        with tempfile.TemporaryDirectory() as d:
            cwd = Path(d)
            fixture = cwd / 'research.json'
            fixture.write_text('''[
                {"title":"机器人公告","url":"https://www.cninfo.com.cn/new/disclosure/detail","snippet":"公告验证机器人订单。"},
                {"title":"机器人政策","url":"https://www.gov.cn/zhengce/content/test.htm","snippet":"政策支持机器人。"},
                {"title":"机器人新闻","url":"https://example.com/news","snippet":"新闻关注机器人。","fixture_category":"news"},
                {"title":"机器人行情","url":"https://example.com/market","snippet":"行情成交摘要。","source_type":"market_data","source_tier":"tier_1_primary_fact"},
                {"title":"机器人热度","url":"https://x.com/example/status/1","snippet":"社媒热度。"},
                {"title":"机器人案例","url":"https://example.com/case","snippet":"历史案例复盘。","source_type":"case","source_tier":"tier_2_canonical_framework"}
            ]''', encoding='utf-8')
            run_result = run_cli(['run', '--topic', '机器人产业链投资机会', '--research-fixture', str(fixture)], cwd)
            self.assertEqual(run_result.returncode, 0, run_result.stderr)
            run_rel = [line for line in run_result.stdout.splitlines() if line.startswith('run_path=')][-1].split('=', 1)[1]
            manifest_yaml = cwd / run_rel / 'system' / 'operating-system-manifest.yaml'
            manifest = yaml.safe_load(manifest_yaml.read_text(encoding='utf-8'))
            manifest['evolution_summary'].pop('pending_human_apply', None)
            manifest['safety_invariants'].pop('durable_learning_requires_harness_and_evolution_gate', None)
            manifest_yaml.write_text(yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False), encoding='utf-8')

            result = run_cli(['system', 'audit', '--repo', str(ROOT), '--run', run_rel, '--out', 'audit-output', '--strict'], cwd)

            self.assertNotEqual(result.returncode, 0)
            report = yaml.safe_load((cwd / 'audit-output/system-audit.yaml').read_text(encoding='utf-8'))
            by_id = {row['requirement_id']: row for row in report['requirements']}
            self.assertEqual(by_id['runtime.operating_system_manifest_matches_schema']['status'], 'fail')
            self.assertIn('schema_errors', by_id['runtime.operating_system_manifest_matches_schema']['details'])

    def test_system_audit_strict_mode_fails_evaluation_report_schema_violation(self):
        with tempfile.TemporaryDirectory() as d:
            cwd = Path(d)
            fixture = cwd / 'research.json'
            fixture.write_text('''[
                {"title":"机器人公告","url":"https://www.cninfo.com.cn/new/disclosure/detail","snippet":"公告验证机器人订单。"},
                {"title":"机器人政策","url":"https://www.gov.cn/zhengce/content/test.htm","snippet":"政策支持机器人。"},
                {"title":"机器人新闻","url":"https://example.com/news","snippet":"新闻关注机器人。","fixture_category":"news"},
                {"title":"机器人行情","url":"https://example.com/market","snippet":"行情成交摘要。","source_type":"market_data","source_tier":"tier_1_primary_fact"},
                {"title":"机器人热度","url":"https://x.com/example/status/1","snippet":"社媒热度。"},
                {"title":"机器人案例","url":"https://example.com/case","snippet":"历史案例复盘。","source_type":"case","source_tier":"tier_2_canonical_framework"}
            ]''', encoding='utf-8')
            run_result = run_cli(['run', '--topic', '机器人产业链投资机会', '--research-fixture', str(fixture)], cwd)
            self.assertEqual(run_result.returncode, 0, run_result.stderr)
            run_rel = [line for line in run_result.stdout.splitlines() if line.startswith('run_path=')][-1].split('=', 1)[1]
            evaluation_yaml = cwd / run_rel / 'evaluations' / 'evaluation-report.yaml'
            evaluation = yaml.safe_load(evaluation_yaml.read_text(encoding='utf-8'))
            evaluation['overall_score'] = 'invalid-score-type'
            evaluation['agent_governance_quality'] = {'real_trade_allowed': True, 'broker_integration': 'enabled'}
            evaluation_yaml.write_text(yaml.safe_dump(evaluation, allow_unicode=True, sort_keys=False), encoding='utf-8')

            result = run_cli(['system', 'audit', '--repo', str(ROOT), '--run', run_rel, '--out', 'audit-output', '--strict'], cwd)

            self.assertNotEqual(result.returncode, 0)
            report = yaml.safe_load((cwd / 'audit-output/system-audit.yaml').read_text(encoding='utf-8'))
            by_id = {row['requirement_id']: row for row in report['requirements']}
            self.assertEqual(by_id['runtime.evaluation_report_matches_schema']['status'], 'fail')
            errors = '\n'.join(by_id['runtime.evaluation_report_matches_schema']['details']['schema_errors'])
            self.assertIn('$.overall_score', errors)
            self.assertIn('$.agent_governance_quality.real_trade_allowed', errors)


if __name__ == '__main__':
    unittest.main()
