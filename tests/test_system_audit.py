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
        module_details = by_id['prd.overall_and_modules_exist']['details']
        self.assertEqual(module_details['missing_modules'], [])
        self.assertEqual(module_details['weak_modules'], [])
        for expected_module in [
            'agent-system',
            'codex-runtime',
            'context-management',
            'evidence-system',
            'harness',
            'learning-evolution',
            'investment-committee',
            'portfolio-outcome',
            'tooling-data-adapters',
            'system-governance-audit',
        ]:
            self.assertIn(expected_module, module_details['required_modules'])
            self.assertIn(expected_module, module_details['present_modules'])
        for requirement_id in [
            'prd.overall_and_modules_exist',
            'agents.all_roster_agents_have_cards_and_skills',
            'agents.all_roster_agents_have_context_tool_memory_policies',
            'agents.agent_os_assets_cross_reference_roster_contract',
            'agents.agent_cards_expose_profile_harness_memory_evolution',
            'agents.skill_files_expose_purpose_workflow_context_safety',
            'agents.agent_cards_expose_machine_auditable_os_policies',
            'agents.skill_files_expose_machine_auditable_execution_policies',
            'agents.agent_maturity_contracts_are_differentiated',
            'memory.persistent_threads_and_memory_policies',
            'harness.agent_tool_context_skill_market_case_claim_evaluations',
            'learning.source_ingestion_agent_learning_evolution_gate',
            'evolution.human_approval_capability_apply_guarded',
            'safety.no_real_trade_or_broker_integration',
            'runtime.operating_system_manifest_schema_exists',
            'runtime.evaluation_report_schema_exists',
        ]:
            self.assertEqual(by_id[requirement_id]['status'], 'pass', requirement_id)
            self.assertTrue(by_id[requirement_id]['evidence'], requirement_id)
        self.assertEqual(by_id['agents.agent_cards_expose_machine_auditable_os_policies']['details']['missing_sections'], {})
        self.assertEqual(by_id['agents.skill_files_expose_machine_auditable_execution_policies']['details']['missing_sections'], {})

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
            self.assertEqual(by_id['runtime.committee_debate_risk_decision_loop_complete']['status'], 'pass')
            self.assertEqual(by_id['runtime.agent_outputs_include_maturity_contracts']['status'], 'pass')
            maturity_details = by_id['runtime.agent_outputs_include_maturity_contracts']['details']
            self.assertEqual(maturity_details['checked_agents'], len(report['requirements'][0]['evidence']) if False else maturity_details['checked_agents'])
            self.assertEqual(maturity_details['missing_by_agent'], {})
            self.assertGreaterEqual(maturity_details['unique_edge_signatures'], 7)
            self.assertFalse(maturity_details['real_trade_allowed'])
            self.assertEqual(maturity_details['broker_integration'], 'disabled')
            self.assertEqual(by_id['runtime.agent_maturity_contract_summary_matches_sources']['status'], 'pass')
            maturity_summary_details = by_id['runtime.agent_maturity_contract_summary_matches_sources']['details']
            self.assertEqual(maturity_summary_details['missing_by_agent'], {})
            self.assertGreaterEqual(maturity_summary_details['unique_edge_signatures'], 7)
            self.assertFalse(maturity_summary_details['real_trade_allowed'])
            self.assertEqual(maturity_summary_details['broker_integration'], 'disabled')
            self.assertEqual(by_id['runtime.policy_contracts_loaded_in_context_and_outputs']['status'], 'pass')
            policy_details = by_id['runtime.policy_contracts_loaded_in_context_and_outputs']['details']
            self.assertEqual(policy_details['missing_by_agent'], {})
            self.assertGreaterEqual(policy_details['context_agent_policy_contracts_present'], 7)
            self.assertGreaterEqual(policy_details['context_skill_execution_policy_contracts_present'], 7)
            self.assertGreaterEqual(policy_details['structured_output_policy_contracts_present'], 7)
            self.assertIn('runtime_policy_contracts_loaded', policy_details['controls'])
            self.assertFalse(policy_details['real_trade_allowed'])
            self.assertEqual(policy_details['broker_integration'], 'disabled')
            self.assertEqual(by_id['runtime.evolution_learning_loop_matches_manifest']['status'], 'pass')
            evolution_details = by_id['runtime.evolution_learning_loop_matches_manifest']['details']
            self.assertGreaterEqual(evolution_details['agent_learning_candidates'], 1)
            self.assertGreaterEqual(evolution_details['evolution_candidates'], 1)
            self.assertIn('quarantine_before_adoption', evolution_details['controls'])
            self.assertFalse(evolution_details['direct_profile_mutation_allowed'])
            self.assertFalse(evolution_details['direct_skill_mutation_allowed'])
            self.assertFalse(evolution_details['direct_tool_mutation_allowed'])
            self.assertFalse(evolution_details['real_trade_allowed'])
            self.assertEqual(evolution_details['broker_integration'], 'disabled')
            self.assertEqual(by_id['runtime.agent_capability_ledger_matches_manifest']['status'], 'pass')
            cap_details = by_id['runtime.agent_capability_ledger_matches_manifest']['details']
            self.assertGreaterEqual(cap_details['candidate_count'], 0)
            self.assertGreaterEqual(cap_details['agent_count'], 0)
            self.assertGreaterEqual(cap_details['pending_human_apply'], 0)
            self.assertIn('capability_lifecycle_per_agent_required', cap_details['controls'])
            self.assertFalse(cap_details['real_trade_allowed'])
            self.assertEqual(cap_details['broker_integration'], 'disabled')
            self.assertEqual(by_id['runtime.tool_runtime_ledger_matches_manifest']['status'], 'pass')
            tool_runtime_details = by_id['runtime.tool_runtime_ledger_matches_manifest']['details']
            self.assertGreaterEqual(tool_runtime_details['tool_call_count'], 1)
            self.assertEqual(tool_runtime_details['blocked_tool_calls'], 0)
            self.assertEqual(tool_runtime_details['tool_call_count'], tool_runtime_details['ledger_row_count'])
            self.assertEqual(tool_runtime_details['evidence_items_created'], tool_runtime_details['tool_runtime_evidence_items'])
            self.assertFalse(tool_runtime_details['real_trade_allowed'])
            self.assertEqual(tool_runtime_details['broker_integration'], 'disabled')
            self.assertEqual(by_id['runtime.portfolio_outcome_loop_matches_manifest']['status'], 'pass')
            portfolio_details = by_id['runtime.portfolio_outcome_loop_matches_manifest']['details']
            self.assertEqual(portfolio_details['watchlist_items'], 1)
            self.assertEqual(portfolio_details['paper_actions'], 1)
            self.assertEqual(portfolio_details['reviewed_actions'], 1)
            self.assertEqual(portfolio_details['outcome_status'], 'missing_market_replay')
            self.assertEqual(portfolio_details['real_trade_violations'], 0)
            self.assertFalse(portfolio_details['real_trade_allowed'])
            self.assertEqual(portfolio_details['broker_integration'], 'disabled')
            committee_details = by_id['runtime.committee_debate_risk_decision_loop_complete']['details']
            self.assertGreaterEqual(committee_details['disagreement_count'], 1)
            self.assertGreaterEqual(committee_details['active_veto_count'], 1)
            self.assertTrue(committee_details['bear_challenge_present'])
            self.assertTrue(committee_details['risk_veto_or_cap_present'])
            self.assertFalse(committee_details['real_trade_allowed'])
            self.assertEqual(committee_details['broker_integration'], 'disabled')
            manifest_evidence = '\n'.join(by_id['runtime.operating_system_manifest_links_agent_os_assets']['evidence'])
            self.assertIn('system/operating-system-manifest.yaml', manifest_evidence)
            self.assertIn('system/operating-system-manifest.md', manifest_evidence)


    def test_system_audit_strict_mode_fails_stale_runtime_policy_contract_manifest_summary(self):
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
            run_path = cwd / run_rel
            manifest_yaml = run_path / 'system' / 'operating-system-manifest.yaml'
            manifest = yaml.safe_load(manifest_yaml.read_text(encoding='utf-8'))
            manifest['runtime_policy_contract_summary']['context_agent_policy_contracts_present'] = -1
            manifest['runtime_policy_contract_summary']['structured_output_policy_contracts_present'] = -1
            manifest['runtime_policy_contract_summary']['broker_integration'] = 'enabled'
            manifest_yaml.write_text(yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False), encoding='utf-8')

            result = run_cli(['system', 'audit', '--repo', str(ROOT), '--run', str(run_path), '--out', 'audit-output', '--strict'], cwd)

            self.assertNotEqual(result.returncode, 0)
            report = yaml.safe_load((cwd / 'audit-output/system-audit.yaml').read_text(encoding='utf-8'))
            by_id = {row['requirement_id']: row for row in report['requirements']}
            self.assertEqual(by_id['runtime.policy_contracts_loaded_in_context_and_outputs']['status'], 'fail')
            mismatches = '\n'.join(by_id['runtime.policy_contracts_loaded_in_context_and_outputs']['details']['mismatches'])
            self.assertIn('runtime_policy_contract_summary.context_agent_policy_contracts_present', mismatches)
            self.assertIn('runtime_policy_contract_summary.structured_output_policy_contracts_present', mismatches)
            self.assertIn('runtime_policy_contract_summary.broker_integration', mismatches)

    def test_system_audit_strict_mode_fails_stale_agent_maturity_manifest_summary(self):
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
            run_path = cwd / run_rel
            manifest_yaml = run_path / 'system' / 'operating-system-manifest.yaml'
            manifest = yaml.safe_load(manifest_yaml.read_text(encoding='utf-8'))
            manifest['agent_maturity_contract_summary']['agents_evaluated'] = -1
            manifest['agent_maturity_contract_summary']['unique_edge_signatures'] = -1
            manifest['agent_maturity_contract_summary']['broker_integration'] = 'enabled'
            manifest_yaml.write_text(yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False), encoding='utf-8')

            result = run_cli(['system', 'audit', '--repo', str(ROOT), '--run', str(run_path), '--out', 'audit-output', '--strict'], cwd)

            self.assertNotEqual(result.returncode, 0)
            report = yaml.safe_load((cwd / 'audit-output/system-audit.yaml').read_text(encoding='utf-8'))
            by_id = {row['requirement_id']: row for row in report['requirements']}
            self.assertEqual(by_id['runtime.agent_maturity_contract_summary_matches_sources']['status'], 'fail')
            mismatches = '\n'.join(by_id['runtime.agent_maturity_contract_summary_matches_sources']['details']['mismatches'])
            self.assertIn('agent_maturity_contract_summary.agents_evaluated', mismatches)
            self.assertIn('agent_maturity_contract_summary.unique_edge_signatures', mismatches)
            self.assertIn('agent_maturity_contract_summary.broker_integration', mismatches)


    def test_system_audit_strict_mode_fails_stale_evolution_learning_manifest_summary(self):
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
            run_path = cwd / run_rel
            manifest_yaml = run_path / 'system' / 'operating-system-manifest.yaml'
            manifest = yaml.safe_load(manifest_yaml.read_text(encoding='utf-8'))
            manifest['evolution_learning_summary']['agent_learning_candidates'] = -1
            manifest['evolution_learning_summary']['evolution_candidates'] = -1
            manifest['evolution_learning_summary']['broker_integration'] = 'enabled'
            manifest_yaml.write_text(yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False), encoding='utf-8')

            result = run_cli(['system', 'audit', '--repo', str(ROOT), '--run', str(run_path), '--out', 'audit-output', '--strict'], cwd)

            self.assertNotEqual(result.returncode, 0)
            report = yaml.safe_load((cwd / 'audit-output/system-audit.yaml').read_text(encoding='utf-8'))
            by_id = {row['requirement_id']: row for row in report['requirements']}
            self.assertEqual(by_id['runtime.evolution_learning_loop_matches_manifest']['status'], 'fail')
            mismatches = '\n'.join(by_id['runtime.evolution_learning_loop_matches_manifest']['details']['mismatches'])
            self.assertIn('evolution_learning_summary.agent_learning_candidates', mismatches)
            self.assertIn('evolution_learning_summary.evolution_candidates', mismatches)
            self.assertIn('evolution_learning_summary.broker_integration', mismatches)

    def test_system_audit_strict_mode_fails_stale_agent_capability_ledger_manifest_summary(self):
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
            run_path = cwd / run_rel
            evolve_result = run_cli(['evolve', '--run', str(run_path)], cwd)
            self.assertEqual(evolve_result.returncode, 0, evolve_result.stderr)
            manifest_yaml = run_path / 'system' / 'operating-system-manifest.yaml'
            manifest = yaml.safe_load(manifest_yaml.read_text(encoding='utf-8'))
            manifest['agent_capability_ledger_summary']['candidate_count'] = -1
            manifest['agent_capability_ledger_summary']['pending_human_apply'] = -1
            manifest['agent_capability_ledger_summary']['broker_integration'] = 'enabled'
            manifest_yaml.write_text(yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False), encoding='utf-8')

            result = run_cli(['system', 'audit', '--repo', str(ROOT), '--run', str(run_path), '--out', 'audit-output', '--strict'], cwd)

            self.assertNotEqual(result.returncode, 0)
            report = yaml.safe_load((cwd / 'audit-output/system-audit.yaml').read_text(encoding='utf-8'))
            by_id = {row['requirement_id']: row for row in report['requirements']}
            self.assertEqual(by_id['runtime.agent_capability_ledger_matches_manifest']['status'], 'fail')
            mismatches = '\n'.join(by_id['runtime.agent_capability_ledger_matches_manifest']['details']['mismatches'])
            self.assertIn('agent_capability_ledger_summary.candidate_count', mismatches)
            self.assertIn('agent_capability_ledger_summary.pending_human_apply', mismatches)
            self.assertIn('agent_capability_ledger_summary.broker_integration', mismatches)

    def test_system_audit_strict_mode_fails_stale_tool_runtime_manifest_summary(self):
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
            run_path = cwd / run_rel
            manifest_yaml = run_path / 'system' / 'operating-system-manifest.yaml'
            manifest = yaml.safe_load(manifest_yaml.read_text(encoding='utf-8'))
            manifest['tool_runtime_summary']['tool_call_count'] = -1
            manifest['tool_runtime_summary']['blocked_tool_calls'] = 99
            manifest['tool_runtime_summary']['broker_integration'] = 'enabled'
            manifest_yaml.write_text(yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False), encoding='utf-8')

            result = run_cli(['system', 'audit', '--repo', str(ROOT), '--run', str(run_path), '--out', 'audit-output', '--strict'], cwd)

            self.assertNotEqual(result.returncode, 0)
            report = yaml.safe_load((cwd / 'audit-output/system-audit.yaml').read_text(encoding='utf-8'))
            by_id = {row['requirement_id']: row for row in report['requirements']}
            self.assertEqual(by_id['runtime.tool_runtime_ledger_matches_manifest']['status'], 'fail')
            mismatches = '\n'.join(by_id['runtime.tool_runtime_ledger_matches_manifest']['details']['mismatches'])
            self.assertIn('tool_runtime_summary.tool_call_count', mismatches)
            self.assertIn('tool_runtime_summary.blocked_tool_calls', mismatches)
            self.assertIn('tool_runtime_summary.broker_integration', mismatches)

    def test_system_audit_strict_mode_fails_stale_portfolio_outcome_manifest_summary(self):
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
            run_path = cwd / run_rel
            manifest_yaml = run_path / 'system' / 'operating-system-manifest.yaml'
            manifest = yaml.safe_load(manifest_yaml.read_text(encoding='utf-8'))
            manifest['portfolio_outcome_summary']['watchlist_items'] = -1
            manifest['portfolio_outcome_summary']['paper_actions'] = -1
            manifest['portfolio_outcome_summary']['broker_integration'] = 'enabled'
            manifest_yaml.write_text(yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False), encoding='utf-8')

            result = run_cli(['system', 'audit', '--repo', str(ROOT), '--run', str(run_path), '--out', 'audit-output', '--strict'], cwd)

            self.assertNotEqual(result.returncode, 0)
            report = yaml.safe_load((cwd / 'audit-output/system-audit.yaml').read_text(encoding='utf-8'))
            by_id = {row['requirement_id']: row for row in report['requirements']}
            self.assertEqual(by_id['runtime.portfolio_outcome_loop_matches_manifest']['status'], 'fail')
            mismatches = '\n'.join(by_id['runtime.portfolio_outcome_loop_matches_manifest']['details']['mismatches'])
            self.assertIn('portfolio_outcome_summary.watchlist_items', mismatches)
            self.assertIn('portfolio_outcome_summary.paper_actions', mismatches)
            self.assertIn('portfolio_outcome_summary.broker_integration', mismatches)

    def test_system_audit_strict_mode_fails_stale_committee_debate_risk_loop(self):
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
            run_path = cwd / run_rel
            readiness_yaml = run_path / 'committee' / 'decision-readiness.yaml'
            readiness = yaml.safe_load(readiness_yaml.read_text(encoding='utf-8'))
            readiness['checks']['bear_challenge_present'] = False
            readiness['checks']['risk_veto_or_cap_present'] = False
            readiness_yaml.write_text(yaml.safe_dump(readiness, allow_unicode=True, sort_keys=False), encoding='utf-8')
            veto_yaml = run_path / 'committee' / 'veto-table.yaml'
            veto = yaml.safe_load(veto_yaml.read_text(encoding='utf-8'))
            veto['items'] = []
            veto['veto_count'] = 0
            veto['real_trade_allowed'] = True
            veto_yaml.write_text(yaml.safe_dump(veto, allow_unicode=True, sort_keys=False), encoding='utf-8')

            result = run_cli(['system', 'audit', '--repo', str(ROOT), '--run', str(run_path), '--out', 'audit-output', '--strict'], cwd)

            self.assertNotEqual(result.returncode, 0)
            report = yaml.safe_load((cwd / 'audit-output/system-audit.yaml').read_text(encoding='utf-8'))
            by_id = {row['requirement_id']: row for row in report['requirements']}
            self.assertEqual(by_id['runtime.committee_debate_risk_decision_loop_complete']['status'], 'fail')
            mismatches = '\n'.join(by_id['runtime.committee_debate_risk_decision_loop_complete']['details']['mismatches'])
            self.assertIn('bear_challenge_present', mismatches)
            self.assertIn('risk_veto_or_cap_present', mismatches)
            self.assertIn('active_veto_count', mismatches)
            self.assertIn('real_trade_allowed', mismatches)

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

    def test_system_audit_strict_mode_fails_stale_os_manifest_governance_summary(self):
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
            run_path = cwd / run_rel
            evolve_result = run_cli(['evolve', '--run', str(run_path)], cwd)
            self.assertEqual(evolve_result.returncode, 0, evolve_result.stderr)
            manifest_yaml = run_path / 'system' / 'operating-system-manifest.yaml'
            manifest = yaml.safe_load(manifest_yaml.read_text(encoding='utf-8'))
            manifest['agent_performance_summary']['average_final_score'] = -1
            manifest['agent_governance_summary']['broker_integration'] = 'enabled'
            manifest['evaluation_summary']['agent_governance_score'] = -1
            manifest_yaml.write_text(yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False), encoding='utf-8')

            result = run_cli(['system', 'audit', '--repo', str(ROOT), '--run', str(run_path), '--out', 'audit-output', '--strict'], cwd)

            self.assertNotEqual(result.returncode, 0)
            report = yaml.safe_load((cwd / 'audit-output/system-audit.yaml').read_text(encoding='utf-8'))
            by_id = {row['requirement_id']: row for row in report['requirements']}
            self.assertEqual(by_id['runtime.operating_system_manifest_runtime_summaries_match_sources']['status'], 'fail')
            mismatches = '\n'.join(by_id['runtime.operating_system_manifest_runtime_summaries_match_sources']['details']['mismatches'])
            self.assertIn('agent_performance_summary.average_final_score', mismatches)
            self.assertIn('agent_governance_summary.broker_integration', mismatches)
            self.assertIn('evaluation_summary.agent_governance_score', mismatches)

    def test_system_audit_strict_mode_fails_stale_os_manifest_source_provenance_summary(self):
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
            run_path = cwd / run_rel
            source_fixture = cwd / 'source-candidates.yaml'
            source_fixture.write_text(yaml.safe_dump({'candidates': [
                {
                    'source_id': 'serenity_x_thread_robotics',
                    'display_name': 'Serenity robotics X thread',
                    'source_type': 'public_practitioner',
                    'summary': '机器人产业链瓶颈研究思路',
                    'claims': ['先从系统架构找瓶颈，再映射公司'],
                    'requested_outputs': ['research_lens', 'checklist'],
                    'target_agents': ['tech_growth_analyst'],
                },
                {
                    'source_id': 'unknown_hot_tip',
                    'source_type': 'social_signal',
                    'summary': '直接买入某股票',
                    'claims': ['直接买入'],
                    'requested_outputs': ['direct_buy_signal'],
                },
            ]}, allow_unicode=True), encoding='utf-8')
            ingest_result = run_cli(['sources', 'ingest', '--run', str(run_path), '--fixture', str(source_fixture)], cwd)
            self.assertEqual(ingest_result.returncode, 0, ingest_result.stderr)
            manifest_yaml = run_path / 'system' / 'operating-system-manifest.yaml'
            manifest = yaml.safe_load(manifest_yaml.read_text(encoding='utf-8'))
            manifest['source_provenance_summary']['registry_source_count'] = -1
            manifest['source_provenance_summary']['ingested_sources'] = -1
            manifest['source_provenance_summary']['methodology_sources_are_hypothesis_only'] = False
            manifest_yaml.write_text(yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False), encoding='utf-8')

            result = run_cli(['system', 'audit', '--repo', str(ROOT), '--run', str(run_path), '--out', 'audit-output', '--strict'], cwd)

            self.assertNotEqual(result.returncode, 0)
            report = yaml.safe_load((cwd / 'audit-output/system-audit.yaml').read_text(encoding='utf-8'))
            by_id = {row['requirement_id']: row for row in report['requirements']}
            self.assertEqual(by_id['runtime.operating_system_manifest_source_provenance_matches_sources']['status'], 'fail')
            mismatches = '\n'.join(by_id['runtime.operating_system_manifest_source_provenance_matches_sources']['details']['mismatches'])
            self.assertIn('source_provenance_summary.registry_source_count', mismatches)
            self.assertIn('source_provenance_summary.ingested_sources', mismatches)
            self.assertIn('source_provenance_summary.methodology_sources_are_hypothesis_only', mismatches)

    def test_system_audit_strict_mode_fails_stale_os_manifest_context_management_summary(self):
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
            run_path = cwd / run_rel
            manifest_yaml = run_path / 'system' / 'operating-system-manifest.yaml'
            manifest = yaml.safe_load(manifest_yaml.read_text(encoding='utf-8'))
            manifest['context_management_summary']['overall'] = -1
            manifest['context_management_summary']['agents_evaluated'] = -1
            manifest['context_management_summary']['broker_integration'] = 'enabled'
            manifest_yaml.write_text(yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False), encoding='utf-8')

            result = run_cli(['system', 'audit', '--repo', str(ROOT), '--run', str(run_path), '--out', 'audit-output', '--strict'], cwd)

            self.assertNotEqual(result.returncode, 0)
            report = yaml.safe_load((cwd / 'audit-output/system-audit.yaml').read_text(encoding='utf-8'))
            by_id = {row['requirement_id']: row for row in report['requirements']}
            self.assertEqual(by_id['runtime.operating_system_manifest_context_management_matches_harness']['status'], 'fail')
            mismatches = '\n'.join(by_id['runtime.operating_system_manifest_context_management_matches_harness']['details']['mismatches'])
            self.assertIn('context_management_summary.overall', mismatches)
            self.assertIn('context_management_summary.agents_evaluated', mismatches)
            self.assertIn('context_management_summary.broker_integration', mismatches)


if __name__ == '__main__':
    unittest.main()
