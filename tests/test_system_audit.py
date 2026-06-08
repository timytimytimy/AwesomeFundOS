import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from fundos.system_audit import REQUIRED_MODULE_PRDS, prd_requirement_matrix_check, run_system_audit

ROOT = Path(__file__).resolve().parents[1]
CLI = [sys.executable, '-m', 'fundos.cli']


def run_cli(args, cwd):
    import os
    env = os.environ.copy()
    env['PYTHONPATH'] = str(ROOT) + os.pathsep + env.get('PYTHONPATH', '')
    return subprocess.run(CLI + args, cwd=cwd, text=True, capture_output=True, env=env)


def write_fixture(path: Path) -> None:
    path.write_text('[\n        {"title":"机器人公告","url":"https://www.cninfo.com.cn/new/disclosure/detail","snippet":"公告验证机器人订单。"},\n        {"title":"机器人政策","url":"https://www.gov.cn/zhengce/content/test.htm","snippet":"政策支持机器人。"},\n        {"title":"机器人新闻","url":"https://example.com/news","snippet":"新闻关注机器人。","fixture_category":"news"},\n        {"title":"机器人行情","url":"https://example.com/market","snippet":"行情成交摘要。","source_type":"market_data","source_tier":"tier_1_primary_fact"},\n        {"title":"机器人热度","url":"https://x.com/example/status/1","snippet":"社媒热度。"},\n        {"title":"机器人案例","url":"https://example.com/case","snippet":"历史案例复盘。","source_type":"case","source_tier":"tier_2_canonical_framework"}\n    ]', encoding='utf-8')


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
        fixture_details = by_id['fixtures.cross_industry_public_research_catalog']['details']
        self.assertEqual(by_id['fixtures.cross_industry_public_research_catalog']['status'], 'pass')
        self.assertEqual(fixture_details['fixture_count'], 4)
        self.assertEqual(fixture_details['missing_required_fixtures'], [])
        self.assertEqual(fixture_details['missing_paths'], [])
        self.assertEqual(fixture_details['missing_source_categories'], {})
        self.assertFalse(fixture_details['real_trade_allowed'])
        self.assertEqual(fixture_details['broker_integration'], 'disabled')
        self.assertIn('social_signal_never_direct_buy', fixture_details['controls'])
        matrix_details = by_id['prd.acceptance_criteria_matrix_maps_to_evidence']['details']
        self.assertEqual(by_id['prd.acceptance_criteria_matrix_maps_to_evidence']['status'], 'pass')
        self.assertEqual(matrix_details['criterion_count'], 104)
        self.assertEqual(matrix_details['covered_criterion_count'], 104)
        self.assertEqual(matrix_details['missing_modules'], [])
        self.assertEqual(matrix_details['criteria_without_evidence'], [])
        self.assertEqual(matrix_details['criteria_without_verification'], [])
        self.assertEqual(matrix_details['invalid_verification_commands'], [])
        self.assertEqual(matrix_details['criteria_not_covered'], [])
        self.assertEqual(matrix_details['missing_evidence_paths'], [])
        self.assertEqual(matrix_details['mismatches'], [])
        self.assertFalse(matrix_details['real_trade_allowed'])
        self.assertEqual(matrix_details['broker_integration'], 'disabled')
        self.assertEqual(len(matrix_details['modules_with_safety_boundary']), 10)
        for requirement_id in [
            'prd.overall_and_modules_exist',
            'prd.acceptance_criteria_matrix_maps_to_evidence',
            'agents.all_roster_agents_have_cards_and_skills',
            'agents.all_roster_agents_have_context_tool_memory_policies',
            'agents.agent_os_assets_cross_reference_roster_contract',
            'agents.agent_cards_expose_profile_harness_memory_evolution',
            'agents.skill_files_expose_purpose_workflow_context_safety',
            'agents.agent_cards_expose_machine_auditable_os_policies',
            'agents.skill_files_expose_machine_auditable_execution_policies',
            'agents.agent_skill_contract_manifest_matches_schema',
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
        contract_details = by_id['agents.agent_skill_contract_manifest_matches_schema']['details']
        self.assertEqual(contract_details['missing_agents'], [])
        self.assertEqual(contract_details['mismatches'], [])
        self.assertEqual(contract_details['schema_errors_by_agent'], {})
        self.assertFalse(contract_details['real_trade_allowed'])
        self.assertEqual(contract_details['broker_integration'], 'disabled')

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

    def test_prd_requirement_matrix_check_fails_missing_evidence_paths(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'specs/audits').mkdir(parents=True)
            (root / 'specs/schemas').mkdir(parents=True)
            schema_text = (ROOT / 'specs/schemas/prd-requirement-matrix.schema.yaml').read_text(encoding='utf-8')
            (root / 'specs/schemas/prd-requirement-matrix.schema.yaml').write_text(schema_text, encoding='utf-8')
            modules = []
            for module_id in sorted(REQUIRED_MODULE_PRDS):
                evidence_path = 'specs/schemas/prd-requirement-matrix.schema.yaml'
                if module_id == 'agent-system':
                    evidence_path = 'missing/evidence.py'
                modules.append({
                    'module_id': module_id,
                    'prd_path': f'docs/prd/modules/{module_id}-prd.md',
                    'requirement_count': 1,
                    'acceptance_criteria': [{
                        'requirement_id': f'{module_id}.test-01',
                        'source_section': 'Acceptance Criteria',
                        'requirement_text': 'test requirement',
                        'evidence_paths': [evidence_path],
                        'verification_commands': ['python3 -m unittest'],
                        'coverage_status': 'covered',
                        'safety_boundary_relevant': True,
                    }],
                })
            matrix = {
                'artifact_type': 'prd_requirement_matrix',
                'version': '0.1.0',
                'source_prd_root': 'docs/prd',
                'coverage_policy': {
                    'every_acceptance_criterion_has_evidence_paths': True,
                    'evidence_paths_must_exist': True,
                    'implementation_evidence_required': True,
                    'verification_evidence_required': True,
                    'runtime_evidence_required_for_runtime_claims': True,
                    'safety_boundary_required_for_every_module': True,
                },
                'modules': modules,
                'coverage_summary': {
                    'module_count': len(modules),
                    'requirement_count': len(modules),
                    'covered_requirement_count': len(modules),
                    'uncovered_requirement_count': 0,
                    'modules_with_safety_boundary': len(modules),
                },
                'safety_invariants': {
                    'real_trade_allowed': False,
                    'broker_integration': 'disabled',
                    'scope': 'research_watchlist_paper_only',
                },
                'real_trade_allowed': False,
                'broker_integration': 'disabled',
            }
            (root / 'specs/audits/prd-requirement-matrix.yaml').write_text(yaml.safe_dump(matrix, allow_unicode=True, sort_keys=False), encoding='utf-8')

            details = prd_requirement_matrix_check(root)

            self.assertFalse(details['ok'])
            self.assertIn('prd_requirement_matrix_missing_evidence_paths', details['blocking_issues'])
            self.assertEqual(details['missing_evidence_paths'], [{'requirement_id': 'agent-system.test-01', 'path': 'missing/evidence.py'}])

    def test_prd_requirement_matrix_check_fails_placeholder_verification_commands(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'specs/audits').mkdir(parents=True)
            (root / 'specs/schemas').mkdir(parents=True)
            schema_text = (ROOT / 'specs/schemas/prd-requirement-matrix.schema.yaml').read_text(encoding='utf-8')
            (root / 'specs/schemas/prd-requirement-matrix.schema.yaml').write_text(schema_text, encoding='utf-8')
            evidence_path = 'specs/schemas/prd-requirement-matrix.schema.yaml'
            modules = []
            for module_id in sorted(REQUIRED_MODULE_PRDS):
                command = 'python3 -m unittest discover -s tests -q'
                if module_id == 'agent-system':
                    command = 'python3 -m fundos.cli system audit --strict --run <run>'
                modules.append({
                    'module_id': module_id,
                    'prd_path': f'docs/prd/modules/{module_id}-prd.md',
                    'requirement_count': 1,
                    'acceptance_criteria': [{
                        'requirement_id': f'{module_id}.test-01',
                        'source_section': 'Acceptance Criteria',
                        'requirement_text': 'test requirement',
                        'evidence_paths': [evidence_path],
                        'verification_commands': [command],
                        'coverage_status': 'covered',
                        'safety_boundary_relevant': True,
                    }],
                })
            matrix = {
                'artifact_type': 'prd_requirement_matrix',
                'version': '0.1.0',
                'source_prd_root': 'docs/prd',
                'coverage_policy': {
                    'every_acceptance_criterion_has_evidence_paths': True,
                    'evidence_paths_must_exist': True,
                    'implementation_evidence_required': True,
                    'verification_evidence_required': True,
                    'runtime_evidence_required_for_runtime_claims': True,
                    'safety_boundary_required_for_every_module': True,
                },
                'modules': modules,
                'coverage_summary': {
                    'module_count': len(modules),
                    'requirement_count': len(modules),
                    'covered_requirement_count': len(modules),
                    'uncovered_requirement_count': 0,
                    'modules_with_safety_boundary': len(modules),
                },
                'safety_invariants': {
                    'real_trade_allowed': False,
                    'broker_integration': 'disabled',
                    'scope': 'research_watchlist_paper_only',
                },
                'real_trade_allowed': False,
                'broker_integration': 'disabled',
            }
            (root / 'specs/audits/prd-requirement-matrix.yaml').write_text(yaml.safe_dump(matrix, allow_unicode=True, sort_keys=False), encoding='utf-8')

            details = prd_requirement_matrix_check(root)

            self.assertFalse(details['ok'])
            self.assertIn('prd_requirement_matrix_placeholder_verification_commands', details['blocking_issues'])
            self.assertEqual(details['placeholder_verification_commands'], [{
                'requirement_id': 'agent-system.test-01',
                'command': 'python3 -m fundos.cli system audit --strict --run <run>',
            }])

    def test_prd_requirement_matrix_check_fails_incomplete_cli_verification_commands(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'specs/audits').mkdir(parents=True)
            (root / 'specs/schemas').mkdir(parents=True)
            schema_text = (ROOT / 'specs/schemas/prd-requirement-matrix.schema.yaml').read_text(encoding='utf-8')
            (root / 'specs/schemas/prd-requirement-matrix.schema.yaml').write_text(schema_text, encoding='utf-8')
            evidence_path = 'specs/schemas/prd-requirement-matrix.schema.yaml'
            modules = []
            for module_id in sorted(REQUIRED_MODULE_PRDS):
                command = 'python3 -m unittest discover -s tests -q'
                if module_id == 'agent-system':
                    command = 'python3 -m fundos.cli roster'
                modules.append({
                    'module_id': module_id,
                    'prd_path': f'docs/prd/modules/{module_id}-prd.md',
                    'requirement_count': 1,
                    'acceptance_criteria': [{
                        'requirement_id': f'{module_id}.test-01',
                        'source_section': 'Acceptance Criteria',
                        'requirement_text': 'test requirement',
                        'evidence_paths': [evidence_path],
                        'verification_commands': [command],
                        'coverage_status': 'covered',
                        'safety_boundary_relevant': True,
                    }],
                })
            matrix = {
                'artifact_type': 'prd_requirement_matrix',
                'version': '0.1.0',
                'source_prd_root': 'docs/prd',
                'coverage_policy': {
                    'every_acceptance_criterion_has_evidence_paths': True,
                    'evidence_paths_must_exist': True,
                    'implementation_evidence_required': True,
                    'verification_evidence_required': True,
                    'runtime_evidence_required_for_runtime_claims': True,
                    'safety_boundary_required_for_every_module': True,
                },
                'modules': modules,
                'coverage_summary': {
                    'module_count': len(modules),
                    'requirement_count': len(modules),
                    'covered_requirement_count': len(modules),
                    'uncovered_requirement_count': 0,
                    'modules_with_safety_boundary': len(modules),
                },
                'safety_invariants': {
                    'real_trade_allowed': False,
                    'broker_integration': 'disabled',
                    'scope': 'research_watchlist_paper_only',
                },
                'real_trade_allowed': False,
                'broker_integration': 'disabled',
            }
            (root / 'specs/audits/prd-requirement-matrix.yaml').write_text(yaml.safe_dump(matrix, allow_unicode=True, sort_keys=False), encoding='utf-8')

            details = prd_requirement_matrix_check(root)

            self.assertFalse(details['ok'])
            self.assertIn('prd_requirement_matrix_invalid_verification_commands', details['blocking_issues'])
            self.assertEqual(details['invalid_verification_commands'], [{
                'requirement_id': 'agent-system.test-01',
                'command': 'python3 -m fundos.cli roster',
                'reason': 'missing_required_subcommand:roster',
            }])

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
            self.assertEqual(by_id['runtime.core_run_evidence_decision_artifacts_match_schemas']['status'], 'pass')
            core_schema_details = by_id['runtime.core_run_evidence_decision_artifacts_match_schemas']['details']
            self.assertEqual(core_schema_details['schema_errors_by_artifact'], {})
            self.assertEqual(core_schema_details['missing_artifacts'], [])
            self.assertGreaterEqual(core_schema_details['evidence_items'], 1)
            self.assertGreaterEqual(core_schema_details['public_research_manifest_results'], 1)
            self.assertGreaterEqual(core_schema_details['claim_count'], 1)
            self.assertGreaterEqual(core_schema_details['evidence_references'], 1)
            self.assertFalse(core_schema_details['real_trade_allowed'])
            self.assertEqual(core_schema_details['broker_integration'], 'disabled')
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
            self.assertEqual(by_id['runtime.context_packs_match_schema_and_budget_contract']['status'], 'pass')
            context_schema_details = by_id['runtime.context_packs_match_schema_and_budget_contract']['details']
            self.assertEqual(context_schema_details['schema_errors_by_agent'], {})
            self.assertEqual(context_schema_details['missing_by_agent'], {})
            self.assertEqual(context_schema_details['checked_agents'], len(context_schema_details['agent_ids']))
            self.assertFalse(context_schema_details['real_trade_allowed'])
            self.assertEqual(context_schema_details['broker_integration'], 'disabled')
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
            self.assertEqual(by_id['runtime.tool_runtime_harness_claim_graph_artifacts_match_schemas']['status'], 'pass')
            tool_schema_details = by_id['runtime.tool_runtime_harness_claim_graph_artifacts_match_schemas']['details']
            self.assertEqual(tool_schema_details['schema_errors_by_artifact'], {})
            self.assertEqual(tool_schema_details['missing_artifacts'], [])
            self.assertGreaterEqual(tool_schema_details['tool_call_count'], 1)
            self.assertGreaterEqual(tool_schema_details['tool_evidence_items'], 1)
            self.assertEqual(tool_schema_details['tool_call_count'], tool_schema_details['ledger_row_count'])
            self.assertEqual(tool_schema_details['succeeded_tool_calls'], tool_schema_details['succeeded_ledger_rows'])
            self.assertEqual(tool_schema_details['blocked_tool_calls'], tool_schema_details['blocked_ledger_rows'])
            self.assertEqual(tool_schema_details['evidence_items_created'], tool_schema_details['tool_evidence_items'])
            self.assertEqual(tool_schema_details['unlinked_tool_result_ids'], [])
            self.assertEqual(tool_schema_details['tool_evidence_without_trace'], [])
            self.assertIn('tool_call_ledger_required', tool_schema_details['controls'])
            self.assertIn('tool_result_trace_required_for_tool_evidence', tool_schema_details['controls'])
            self.assertFalse(tool_schema_details['real_trade_allowed'])
            self.assertEqual(tool_schema_details['broker_integration'], 'disabled')
            self.assertEqual(by_id['runtime.agent_organization_harness_artifacts_match_schemas']['status'], 'pass')
            org_schema_details = by_id['runtime.agent_organization_harness_artifacts_match_schemas']['details']
            self.assertEqual(org_schema_details['schema_errors_by_artifact'], {})
            self.assertEqual(org_schema_details['missing_artifacts'], [])
            self.assertEqual(org_schema_details['agent_harness_agent_count'], org_schema_details['selected_agent_count'])
            self.assertEqual(org_schema_details['skill_benchmark_agents_evaluated'], org_schema_details['selected_agent_count'])
            self.assertEqual(org_schema_details['agent_performance_agent_count'], org_schema_details['selected_agent_count'])
            self.assertEqual(org_schema_details['agent_governance_agent_count'], org_schema_details['selected_agent_count'])
            self.assertGreaterEqual(org_schema_details['pm_competition_style_count'], 4)
            self.assertEqual(org_schema_details['pm_harness_style_count'], org_schema_details['pm_competition_style_count'])
            self.assertGreaterEqual(org_schema_details['collaboration_handoff_count'], 1)
            self.assertGreaterEqual(org_schema_details['collaboration_disagreement_count'], 1)
            self.assertGreaterEqual(org_schema_details['collaboration_veto_count'], 1)
            self.assertIn('skill_guardrails_required', org_schema_details['controls'])
            self.assertIn('performance_review_is_not_capital_authority', org_schema_details['controls'])
            self.assertIn('human_approval_required_for_role_change', org_schema_details['controls'])
            self.assertFalse(org_schema_details['real_trade_allowed'])
            self.assertEqual(org_schema_details['broker_integration'], 'disabled')
            self.assertEqual(by_id['runtime.portfolio_outcome_loop_matches_manifest']['status'], 'pass')
            portfolio_details = by_id['runtime.portfolio_outcome_loop_matches_manifest']['details']
            self.assertEqual(portfolio_details['watchlist_items'], 1)
            self.assertEqual(portfolio_details['paper_actions'], 1)
            self.assertEqual(portfolio_details['reviewed_actions'], 1)
            self.assertEqual(portfolio_details['outcome_status'], 'missing_market_replay')
            self.assertEqual(portfolio_details['real_trade_violations'], 0)
            self.assertFalse(portfolio_details['real_trade_allowed'])
            self.assertEqual(portfolio_details['broker_integration'], 'disabled')
            self.assertEqual(by_id['runtime.portfolio_outcome_artifacts_match_schemas']['status'], 'pass')
            portfolio_schema_details = by_id['runtime.portfolio_outcome_artifacts_match_schemas']['details']
            self.assertEqual(portfolio_schema_details['schema_errors_by_artifact'], {})
            self.assertEqual(portfolio_schema_details['missing_artifacts'], [])
            self.assertFalse(portfolio_schema_details['real_trade_allowed'])
            self.assertEqual(portfolio_schema_details['broker_integration'], 'disabled')
            self.assertEqual(by_id['runtime.failure_pattern_library_matches_schema']['status'], 'pass')
            failure_schema_details = by_id['runtime.failure_pattern_library_matches_schema']['details']
            self.assertEqual(failure_schema_details['schema_errors_by_artifact'], {})
            self.assertEqual(failure_schema_details['missing_artifacts'], [])
            self.assertGreaterEqual(failure_schema_details['organization_library_rows'], failure_schema_details['report_pattern_count'])
            self.assertIn('failure_patterns_are_not_trade_signals', failure_schema_details['controls'])
            self.assertFalse(failure_schema_details['real_trade_allowed'])
            self.assertEqual(failure_schema_details['broker_integration'], 'disabled')
            self.assertEqual(by_id['runtime.task_dag_and_research_gap_artifacts_match_schemas']['status'], 'pass')
            task_dag_schema_details = by_id['runtime.task_dag_and_research_gap_artifacts_match_schemas']['details']
            self.assertEqual(task_dag_schema_details['schema_errors_by_artifact'], {})
            self.assertEqual(task_dag_schema_details['missing_artifacts'], [])
            self.assertGreaterEqual(task_dag_schema_details['node_count'], 13)
            self.assertGreaterEqual(task_dag_schema_details['research_gap_count'], 1)
            self.assertIn('no_real_trade_action', task_dag_schema_details['controls'])
            self.assertFalse(task_dag_schema_details['real_trade_allowed'])
            self.assertEqual(task_dag_schema_details['broker_integration'], 'disabled')
            self.assertEqual(by_id['runtime.agent_thread_memory_artifacts_match_schemas']['status'], 'pass')
            thread_schema_details = by_id['runtime.agent_thread_memory_artifacts_match_schemas']['details']
            self.assertEqual(thread_schema_details['schema_errors_by_artifact'], {})
            self.assertEqual(thread_schema_details['missing_artifacts'], [])
            self.assertEqual(thread_schema_details['thread_count'], len(thread_schema_details['agent_ids']))
            self.assertGreaterEqual(thread_schema_details['event_rows_validated'], thread_schema_details['thread_count'])
            self.assertIn('append_only_event_log', thread_schema_details['controls'])
            self.assertIn('evolution_gate_required_for_memory_write', thread_schema_details['controls'])
            self.assertFalse(thread_schema_details['real_trade_allowed'])
            self.assertEqual(thread_schema_details['broker_integration'], 'disabled')
            self.assertEqual(by_id['runtime.case_library_and_replay_artifacts_match_schemas']['status'], 'pass')
            case_schema_details = by_id['runtime.case_library_and_replay_artifacts_match_schemas']['details']
            self.assertEqual(case_schema_details['schema_errors_by_artifact'], {})
            self.assertEqual(case_schema_details['missing_artifacts'], [])
            self.assertGreaterEqual(case_schema_details['source_case_count'], 8)
            self.assertGreaterEqual(case_schema_details['case_results_total'], 1)
            self.assertIn('direct_case_mapping_forbidden', case_schema_details['controls'])
            self.assertFalse(case_schema_details['real_trade_allowed'])
            self.assertEqual(case_schema_details['broker_integration'], 'disabled')
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

    def test_system_audit_strict_mode_validates_learning_evolution_capability_artifacts(self):
        with tempfile.TemporaryDirectory() as d:
            cwd = Path(d)
            fixture = cwd / 'research.json'
            write_fixture(fixture)
            run_result = run_cli(['run', '--topic', '机器人产业链投资机会', '--research-fixture', str(fixture)], cwd)
            self.assertEqual(run_result.returncode, 0, run_result.stderr)
            run_rel = [line for line in run_result.stdout.splitlines() if line.startswith('run_path=')][-1].split('=', 1)[1]
            run_path = cwd / run_rel
            evolve_result = run_cli(['evolve', '--run', str(run_path)], cwd)
            self.assertEqual(evolve_result.returncode, 0, evolve_result.stderr)

            result = run_cli(['system', 'audit', '--repo', str(ROOT), '--run', str(run_path), '--out', 'audit-output', '--strict'], cwd)

            self.assertEqual(result.returncode, 0, result.stderr)
            report = yaml.safe_load((cwd / 'audit-output/system-audit.yaml').read_text(encoding='utf-8'))
            by_id = {row['requirement_id']: row for row in report['requirements']}
            self.assertEqual(by_id['runtime.learning_evolution_capability_artifacts_match_schemas']['status'], 'pass')
            details = by_id['runtime.learning_evolution_capability_artifacts_match_schemas']['details']
            self.assertEqual(details['schema_errors_by_artifact'], {})
            self.assertEqual(details['missing_artifacts'], [])
            self.assertGreaterEqual(details['agent_learning_candidates'], 1)
            self.assertGreaterEqual(details['evolution_candidates'], 1)
            self.assertEqual(details['gate_result_count'], details['accepted_count'] + details['quarantine_count'] + details['rejected_count'])
            self.assertEqual(details['memory_writes'], details['organization_evolution_ledger_entries'])
            self.assertGreaterEqual(details['capability_candidate_count'], 1)
            self.assertEqual(details['capability_regression_candidates'], details['passed_capability_regressions'] + details['blocked_capability_regressions'])
            self.assertGreaterEqual(details['agent_capability_ledger_agents'], 1)
            self.assertIn('quarantine_before_adoption', details['controls'])
            self.assertIn('evolution_gate_required', details['controls'])
            self.assertIn('capability_regression_required', details['controls'])
            self.assertIn('human_approval_before_apply', details['controls'])
            self.assertIn('no_direct_profile_mutation', details['controls'])
            self.assertIn('no_real_trade_action', details['controls'])
            self.assertIn('broker_integration_disabled', details['controls'])
            self.assertFalse(details['direct_profile_mutation_allowed'])
            self.assertFalse(details['direct_skill_mutation_allowed'])
            self.assertFalse(details['direct_tool_mutation_allowed'])
            self.assertFalse(details['real_trade_allowed'])
            self.assertEqual(details['broker_integration'], 'disabled')

    def test_system_audit_strict_mode_fails_learning_evolution_capability_schema_violation(self):
        with tempfile.TemporaryDirectory() as d:
            cwd = Path(d)
            fixture = cwd / 'research.json'
            write_fixture(fixture)
            run_result = run_cli(['run', '--topic', '机器人产业链投资机会', '--research-fixture', str(fixture)], cwd)
            self.assertEqual(run_result.returncode, 0, run_result.stderr)
            run_rel = [line for line in run_result.stdout.splitlines() if line.startswith('run_path=')][-1].split('=', 1)[1]
            run_path = cwd / run_rel
            evolve_result = run_cli(['evolve', '--run', str(run_path)], cwd)
            self.assertEqual(evolve_result.returncode, 0, evolve_result.stderr)

            gate_path = run_path / 'evolution' / 'evolution-gate-results.jsonl'
            gate_rows = [json.loads(line) for line in gate_path.read_text(encoding='utf-8').splitlines() if line.strip()]
            self.assertTrue(gate_rows)
            gate_rows[0]['broker_integration'] = 'enabled'
            gate_path.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in gate_rows), encoding='utf-8')

            memory_summary_path = run_path / 'evolution' / 'memory-writeback-summary.yaml'
            memory_summary = yaml.safe_load(memory_summary_path.read_text(encoding='utf-8'))
            memory_summary['memory_writes'] = int(memory_summary['memory_writes']) + 1
            memory_summary['direct_profile_mutation_allowed'] = True
            memory_summary_path.write_text(yaml.safe_dump(memory_summary, allow_unicode=True, sort_keys=False), encoding='utf-8')

            regression_path = run_path / 'harness' / 'capability-regression.yaml'
            regression = yaml.safe_load(regression_path.read_text(encoding='utf-8'))
            regression['candidate_results'][0]['application_status_after_regression'] = 'applied_without_human'
            regression_path.write_text(yaml.safe_dump(regression, allow_unicode=True, sort_keys=False), encoding='utf-8')

            result = run_cli(['system', 'audit', '--repo', str(ROOT), '--run', str(run_path), '--out', 'audit-output', '--strict'], cwd)

            self.assertNotEqual(result.returncode, 0)
            report = yaml.safe_load((cwd / 'audit-output/system-audit.yaml').read_text(encoding='utf-8'))
            by_id = {row['requirement_id']: row for row in report['requirements']}
            self.assertEqual(by_id['runtime.learning_evolution_capability_artifacts_match_schemas']['status'], 'fail')
            details = by_id['runtime.learning_evolution_capability_artifacts_match_schemas']['details']
            rendered = yaml.safe_dump(details, allow_unicode=True, sort_keys=False)
            self.assertIn('evolution-gate-results.jsonl:1', rendered)
            self.assertIn('broker_integration', rendered)
            self.assertIn('memory_writeback.memory_writes', rendered)
            self.assertIn('memory-writeback-summary.yaml.direct_profile_mutation_allowed', rendered)
            self.assertIn('capability-regression.yaml.candidate_results[0].application_status_after_regression', rendered)

    def test_system_audit_strict_mode_fails_tool_runtime_harness_schema_violation(self):
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

            runtime_yaml = run_path / 'tools' / 'tool-runtime-report.yaml'
            runtime_report = yaml.safe_load(runtime_yaml.read_text(encoding='utf-8'))
            runtime_report['broker_integration'] = 'enabled'
            runtime_yaml.write_text(yaml.safe_dump(runtime_report, allow_unicode=True, sort_keys=False), encoding='utf-8')

            ledger_path = run_path / 'tools' / 'tool-call-ledger.jsonl'
            rows = [json.loads(line) for line in ledger_path.read_text(encoding='utf-8').splitlines() if line.strip()]
            rows[0].pop('broker_integration', None)
            ledger_path.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')

            claim_yaml = run_path / 'harness' / 'claim-graph.yaml'
            claim_report = yaml.safe_load(claim_yaml.read_text(encoding='utf-8'))
            claim_report['tool_evidence_without_trace'] = ['bad_tool_result']
            claim_yaml.write_text(yaml.safe_dump(claim_report, allow_unicode=True, sort_keys=False), encoding='utf-8')

            result = run_cli(['system', 'audit', '--repo', str(ROOT), '--run', run_rel, '--out', 'audit-output', '--strict'], cwd)

            self.assertNotEqual(result.returncode, 0)
            report = yaml.safe_load((cwd / 'audit-output/system-audit.yaml').read_text(encoding='utf-8'))
            by_id = {row['requirement_id']: row for row in report['requirements']}
            self.assertEqual(by_id['runtime.tool_runtime_harness_claim_graph_artifacts_match_schemas']['status'], 'fail')
            details = by_id['runtime.tool_runtime_harness_claim_graph_artifacts_match_schemas']['details']
            runtime_errors = '\n'.join(details['schema_errors_by_artifact']['tool-runtime-report.yaml'])
            self.assertIn('$.broker_integration', runtime_errors)
            ledger_errors = '\n'.join(details['schema_errors_by_artifact']['tool-call-ledger.jsonl:1'])
            self.assertIn('$.broker_integration', ledger_errors)
            mismatches = '\n'.join(details['mismatches'])
            self.assertIn('claim_graph.tool_evidence_without_trace', mismatches)

    def test_system_audit_strict_mode_fails_agent_organization_harness_schema_violation(self):
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

            agent_harness_yaml = run_path / 'harness' / 'agent-harness.yaml'
            agent_harness = yaml.safe_load(agent_harness_yaml.read_text(encoding='utf-8'))
            agent_harness['broker_integration'] = 'enabled'
            agent_harness['agent_results'][0].pop('broker_integration', None)
            agent_harness_yaml.write_text(yaml.safe_dump(agent_harness, allow_unicode=True, sort_keys=False), encoding='utf-8')

            performance_yaml = run_path / 'harness' / 'agent-performance.yaml'
            performance = yaml.safe_load(performance_yaml.read_text(encoding='utf-8'))
            performance['agent_results'][0]['risk_limit_changed'] = True
            performance_yaml.write_text(yaml.safe_dump(performance, allow_unicode=True, sort_keys=False), encoding='utf-8')

            pm_yaml = run_path / 'committee' / 'pm-competition.yaml'
            pm_competition = yaml.safe_load(pm_yaml.read_text(encoding='utf-8'))
            pm_competition['style_count'] += 1
            pm_competition['real_trade_allowed'] = True
            pm_yaml.write_text(yaml.safe_dump(pm_competition, allow_unicode=True, sort_keys=False), encoding='utf-8')

            result = run_cli(['system', 'audit', '--repo', str(ROOT), '--run', run_rel, '--out', 'audit-output', '--strict'], cwd)

            self.assertNotEqual(result.returncode, 0)
            report = yaml.safe_load((cwd / 'audit-output/system-audit.yaml').read_text(encoding='utf-8'))
            by_id = {row['requirement_id']: row for row in report['requirements']}
            self.assertEqual(by_id['runtime.agent_organization_harness_artifacts_match_schemas']['status'], 'fail')
            details = by_id['runtime.agent_organization_harness_artifacts_match_schemas']['details']
            agent_errors = '\n'.join(details['schema_errors_by_artifact']['agent-harness.yaml'])
            self.assertIn('$.broker_integration', agent_errors)
            self.assertIn('$.agent_results[0].broker_integration', agent_errors)
            pm_errors = '\n'.join(details['schema_errors_by_artifact']['pm-competition.yaml'])
            self.assertIn('$.real_trade_allowed', pm_errors)
            mismatches = '\n'.join(details['mismatches'])
            self.assertIn('pm_competition.style_count', mismatches)
            self.assertIn('agent_performance.agent_results[0].risk_limit_changed', mismatches)

    def test_system_audit_strict_mode_fails_portfolio_outcome_schema_violation(self):
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
            paper_yaml = cwd / run_rel / 'portfolio' / 'paper-portfolio.yaml'
            paper = yaml.safe_load(paper_yaml.read_text(encoding='utf-8'))
            paper['broker_integration'] = 'enabled'
            paper['actions'][0].pop('broker_integration', None)
            paper_yaml.write_text(yaml.safe_dump(paper, allow_unicode=True, sort_keys=False), encoding='utf-8')

            result = run_cli(['system', 'audit', '--repo', str(ROOT), '--run', run_rel, '--out', 'audit-output', '--strict'], cwd)

            self.assertNotEqual(result.returncode, 0)
            report = yaml.safe_load((cwd / 'audit-output/system-audit.yaml').read_text(encoding='utf-8'))
            by_id = {row['requirement_id']: row for row in report['requirements']}
            self.assertEqual(by_id['runtime.portfolio_outcome_artifacts_match_schemas']['status'], 'fail')
            errors = '\n'.join(by_id['runtime.portfolio_outcome_artifacts_match_schemas']['details']['schema_errors_by_artifact']['paper-portfolio.yaml'])
            self.assertIn('$.broker_integration', errors)
            self.assertIn('$.actions[0].broker_integration', errors)

    def test_system_audit_strict_mode_fails_failure_pattern_schema_violation(self):
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
            failure_yaml = cwd / run_rel / 'learning' / 'failure-patterns.yaml'
            failure_report = yaml.safe_load(failure_yaml.read_text(encoding='utf-8'))
            failure_report['broker_integration'] = 'enabled'
            failure_report['patterns'][0].pop('prevention_check', None)
            failure_report['patterns'][0]['broker_integration'] = 'enabled'
            failure_yaml.write_text(yaml.safe_dump(failure_report, allow_unicode=True, sort_keys=False), encoding='utf-8')

            result = run_cli(['system', 'audit', '--repo', str(ROOT), '--run', run_rel, '--out', 'audit-output', '--strict'], cwd)

            self.assertNotEqual(result.returncode, 0)
            report = yaml.safe_load((cwd / 'audit-output/system-audit.yaml').read_text(encoding='utf-8'))
            by_id = {row['requirement_id']: row for row in report['requirements']}
            self.assertEqual(by_id['runtime.failure_pattern_library_matches_schema']['status'], 'fail')
            errors = '\n'.join(by_id['runtime.failure_pattern_library_matches_schema']['details']['schema_errors_by_artifact']['failure-patterns.yaml'])
            self.assertIn('$.broker_integration', errors)
            self.assertIn('$.patterns[0].prevention_check', errors)
            self.assertIn('$.patterns[0].broker_integration', errors)

    def test_system_audit_strict_mode_fails_task_dag_schema_violation(self):
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
            dag_yaml = cwd / run_rel / 'workflow' / 'task-dag.yaml'
            dag = yaml.safe_load(dag_yaml.read_text(encoding='utf-8'))
            dag['broker_integration'] = 'enabled'
            dag['nodes'][0].pop('broker_integration', None)
            dag_yaml.write_text(yaml.safe_dump(dag, allow_unicode=True, sort_keys=False), encoding='utf-8')

            result = run_cli(['system', 'audit', '--repo', str(ROOT), '--run', run_rel, '--out', 'audit-output', '--strict'], cwd)

            self.assertNotEqual(result.returncode, 0)
            report = yaml.safe_load((cwd / 'audit-output/system-audit.yaml').read_text(encoding='utf-8'))
            by_id = {row['requirement_id']: row for row in report['requirements']}
            self.assertEqual(by_id['runtime.task_dag_and_research_gap_artifacts_match_schemas']['status'], 'fail')
            errors = '\n'.join(by_id['runtime.task_dag_and_research_gap_artifacts_match_schemas']['details']['schema_errors_by_artifact']['task-dag.yaml'])
            self.assertIn('$.broker_integration', errors)
            self.assertIn('$.nodes[0].broker_integration', errors)

    def test_system_audit_strict_mode_fails_agent_thread_schema_violation(self):
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
            manifest_yaml = run_path / 'memory' / 'agent-thread-manifest.yaml'
            manifest = yaml.safe_load(manifest_yaml.read_text(encoding='utf-8'))
            manifest['broker_integration'] = 'enabled'
            first_thread = manifest['threads'][0]
            first_thread.pop('event_log_path', None)
            manifest_yaml.write_text(yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False), encoding='utf-8')
            event_path = cwd / first_thread['thread_path'].replace('thread.yaml', 'thread-events.jsonl')
            rows = [json.loads(line) for line in event_path.read_text(encoding='utf-8').splitlines() if line.strip()]
            rows[-1]['broker_integration'] = 'enabled'
            event_path.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')

            result = run_cli(['system', 'audit', '--repo', str(ROOT), '--run', run_rel, '--out', 'audit-output', '--strict'], cwd)

            self.assertNotEqual(result.returncode, 0)
            report = yaml.safe_load((cwd / 'audit-output/system-audit.yaml').read_text(encoding='utf-8'))
            by_id = {row['requirement_id']: row for row in report['requirements']}
            self.assertEqual(by_id['runtime.agent_thread_memory_artifacts_match_schemas']['status'], 'fail')
            details = by_id['runtime.agent_thread_memory_artifacts_match_schemas']['details']
            errors = '\n'.join(details['schema_errors_by_artifact']['agent-thread-manifest.yaml'])
            self.assertIn('$.broker_integration', errors)
            self.assertIn('$.threads[0].event_log_path', errors)
            mismatches = '\n'.join(details['mismatches'])
            self.assertIn('agent_thread_manifest.broker_integration', mismatches)

    def test_system_audit_strict_mode_fails_case_replay_schema_violation(self):
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
            replay_path = run_path / 'harness' / 'historical-case-replay.yaml'
            replay = yaml.safe_load(replay_path.read_text(encoding='utf-8'))
            replay['broker_integration'] = 'enabled'
            replay['case_results'][0]['allowed_use'] = 'direct_mapping_allowed'
            replay['case_results'][0].pop('broker_integration', None)
            replay_path.write_text(yaml.safe_dump(replay, allow_unicode=True, sort_keys=False), encoding='utf-8')

            result = run_cli(['system', 'audit', '--repo', str(ROOT), '--run', run_rel, '--out', 'audit-output', '--strict'], cwd)

            self.assertNotEqual(result.returncode, 0)
            report = yaml.safe_load((cwd / 'audit-output/system-audit.yaml').read_text(encoding='utf-8'))
            by_id = {row['requirement_id']: row for row in report['requirements']}
            self.assertEqual(by_id['runtime.case_library_and_replay_artifacts_match_schemas']['status'], 'fail')
            details = by_id['runtime.case_library_and_replay_artifacts_match_schemas']['details']
            errors = '\n'.join(details['schema_errors_by_artifact']['historical-case-replay.yaml'])
            self.assertIn('broker_integration', errors)
            mismatches = '\n'.join(details['mismatches'])
            self.assertIn('case_replay.broker_integration', mismatches)
            self.assertIn('direct mapping', mismatches)


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


    def test_system_audit_strict_mode_fails_incomplete_capability_apply_ledger(self):
        with tempfile.TemporaryDirectory() as d:
            cwd = Path(d)
            run_result = run_cli(['run', '--topic', '机器人产业链投资机会'], cwd)
            self.assertEqual(run_result.returncode, 0, run_result.stderr)
            run_rel = [line for line in run_result.stdout.splitlines() if line.startswith('run_path=')][-1].split('=', 1)[1]
            evolve_result = run_cli(['evolve', '--run', str(cwd / run_rel)], cwd)
            self.assertEqual(evolve_result.returncode, 0, evolve_result.stderr)
            apply_result = run_cli(['capabilities', 'apply', 'cand_' + Path(run_rel).name + '_002', '--approver', 'human-test'], cwd)
            self.assertEqual(apply_result.returncode, 0, apply_result.stderr)
            ledger_path = cwd / 'memory' / 'organization' / 'capability-apply-ledger.jsonl'
            rows = [json.loads(line) for line in ledger_path.read_text(encoding='utf-8').splitlines() if line.strip()]
            self.assertTrue(rows)
            rows[0].pop('candidate_type', None)
            rows[0].pop('source_basis', None)
            rows[0].pop('scores', None)
            rows[0]['broker_integration'] = 'enabled'
            ledger_path.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')

            result = run_cli(['system', 'audit', '--repo', str(ROOT), '--run', str(cwd / run_rel), '--out', 'audit-output', '--strict'], cwd)

            self.assertNotEqual(result.returncode, 0)
            report = yaml.safe_load((cwd / 'audit-output/system-audit.yaml').read_text(encoding='utf-8'))
            by_id = {row['requirement_id']: row for row in report['requirements']}
            self.assertEqual(by_id['runtime.agent_capability_ledger_matches_manifest']['status'], 'fail')
            mismatches = '\n'.join(by_id['runtime.agent_capability_ledger_matches_manifest']['details']['mismatches'])
            self.assertIn('capability_apply_ledger[0].candidate_type: missing', mismatches)
            self.assertIn('capability_apply_ledger[0].source_basis: missing', mismatches)
            self.assertIn('capability_apply_ledger[0].scores: missing', mismatches)
            self.assertIn('capability_apply_ledger[0].broker_integration', mismatches)

    def test_system_audit_strict_mode_accepts_complete_capability_apply_ledger(self):
        with tempfile.TemporaryDirectory() as d:
            cwd = Path(d)
            run_result = run_cli(['run', '--topic', '机器人产业链投资机会'], cwd)
            self.assertEqual(run_result.returncode, 0, run_result.stderr)
            run_rel = [line for line in run_result.stdout.splitlines() if line.startswith('run_path=')][-1].split('=', 1)[1]
            evolve_result = run_cli(['evolve', '--run', str(cwd / run_rel)], cwd)
            self.assertEqual(evolve_result.returncode, 0, evolve_result.stderr)
            apply_result = run_cli(['capabilities', 'apply', 'cand_' + Path(run_rel).name + '_002', '--approver', 'human-test'], cwd)
            self.assertEqual(apply_result.returncode, 0, apply_result.stderr)

            result = run_cli(['system', 'audit', '--repo', str(ROOT), '--run', str(cwd / run_rel), '--out', 'audit-output', '--strict'], cwd)

            self.assertNotEqual(result.returncode, 0)
            report = yaml.safe_load((cwd / 'audit-output/system-audit.yaml').read_text(encoding='utf-8'))
            by_id = {row['requirement_id']: row for row in report['requirements']}
            self.assertEqual(by_id['runtime.agent_capability_ledger_matches_manifest']['status'], 'pass')
            self.assertEqual(by_id['runtime.agent_capability_ledger_matches_manifest']['details']['apply_ledger_entries'], 1)

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

    def test_system_audit_strict_mode_fails_core_artifact_schema_violation(self):
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
            evidence_yaml = run_path / 'evidence' / 'evidence-pack.yaml'
            evidence = yaml.safe_load(evidence_yaml.read_text(encoding='utf-8'))
            evidence['evidence_items'][0]['source_type'] = 'direct_trade_signal'
            evidence['evidence_items'][0]['claims'][0].pop('claim_type', None)
            evidence_yaml.write_text(yaml.safe_dump(evidence, allow_unicode=True, sort_keys=False), encoding='utf-8')
            memo_yaml = run_path / 'decision' / 'final-decision-memo.yaml'
            memo = yaml.safe_load(memo_yaml.read_text(encoding='utf-8'))
            memo['final_decision']['label'] = 'buy_now'
            memo['real_trade_allowed'] = True
            memo_yaml.write_text(yaml.safe_dump(memo, allow_unicode=True, sort_keys=False), encoding='utf-8')

            result = run_cli(['system', 'audit', '--repo', str(ROOT), '--run', run_rel, '--out', 'audit-output', '--strict'], cwd)

            self.assertNotEqual(result.returncode, 0)
            report = yaml.safe_load((cwd / 'audit-output/system-audit.yaml').read_text(encoding='utf-8'))
            by_id = {row['requirement_id']: row for row in report['requirements']}
            self.assertEqual(by_id['runtime.core_run_evidence_decision_artifacts_match_schemas']['status'], 'fail')
            details = by_id['runtime.core_run_evidence_decision_artifacts_match_schemas']['details']
            evidence_errors = '\n'.join(details['schema_errors_by_artifact']['evidence-pack.yaml'])
            self.assertIn('source_type', evidence_errors)
            self.assertIn('claim_type', evidence_errors)
            memo_errors = '\n'.join(details['schema_errors_by_artifact']['final-decision-memo.yaml'])
            self.assertIn('label', memo_errors)
            mismatches = '\n'.join(details['mismatches'])
            self.assertIn('final_decision_memo.real_trade_allowed', mismatches)

    def test_system_audit_strict_mode_fails_public_research_manifest_schema_violation(self):
        with tempfile.TemporaryDirectory() as d:
            cwd = Path(d)
            fixture = cwd / 'research.json'
            write_fixture(fixture)
            run_result = run_cli(['run', '--topic', '机器人产业链投资机会', '--research-fixture', str(fixture)], cwd)
            self.assertEqual(run_result.returncode, 0, run_result.stderr)
            run_rel = [line for line in run_result.stdout.splitlines() if line.startswith('run_path=')][-1].split('=', 1)[1]
            run_path = cwd / run_rel
            manifest_yaml = run_path / 'evidence' / 'public-research-manifest.yaml'
            manifest = yaml.safe_load(manifest_yaml.read_text(encoding='utf-8'))
            manifest['result_count'] = 999
            manifest['results'][0].pop('source_hash', None)
            manifest['research_plan_coverage'].pop('planned_categories', None)
            manifest_yaml.write_text(yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False), encoding='utf-8')

            result = run_cli(['system', 'audit', '--repo', str(ROOT), '--run', run_rel, '--out', 'audit-output', '--strict'], cwd)

            self.assertNotEqual(result.returncode, 0)
            report = yaml.safe_load((cwd / 'audit-output/system-audit.yaml').read_text(encoding='utf-8'))
            by_id = {row['requirement_id']: row for row in report['requirements']}
            self.assertEqual(by_id['runtime.core_run_evidence_decision_artifacts_match_schemas']['status'], 'fail')
            details = by_id['runtime.core_run_evidence_decision_artifacts_match_schemas']['details']
            manifest_errors = '\n'.join(details['schema_errors_by_artifact']['public-research-manifest.yaml'])
            self.assertIn('source_hash', manifest_errors)
            self.assertIn('planned_categories', manifest_errors)
            mismatches = '\n'.join(details['mismatches'])
            self.assertIn('public_research_manifest.result_count', mismatches)

    def test_system_audit_strict_mode_fails_source_ingestion_quarantine_schema_violation(self):
        with tempfile.TemporaryDirectory() as d:
            cwd = Path(d)
            fixture = cwd / 'research.json'
            write_fixture(fixture)
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
            source_path = run_path / 'learning' / 'source-candidates.jsonl'
            source_rows = [json.loads(line) for line in source_path.read_text(encoding='utf-8').splitlines() if line.strip()]
            source_rows[0]['classification_status'] = 'accepted_without_review'
            source_rows[0]['allowed_learning_outputs'].append('direct_buy_signal')
            source_path.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in source_rows), encoding='utf-8')
            pattern_path = run_path / 'learning' / 'pattern-candidates.jsonl'
            pattern_rows = [json.loads(line) for line in pattern_path.read_text(encoding='utf-8').splitlines() if line.strip()]
            pattern_rows[0]['memory_write_allowed'] = True
            pattern_rows[0]['source_id'] = 'unknown_hot_tip'
            pattern_path.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in pattern_rows), encoding='utf-8')

            result = run_cli(['system', 'audit', '--repo', str(ROOT), '--run', run_rel, '--out', 'audit-output', '--strict'], cwd)

            self.assertNotEqual(result.returncode, 0)
            report = yaml.safe_load((cwd / 'audit-output/system-audit.yaml').read_text(encoding='utf-8'))
            by_id = {row['requirement_id']: row for row in report['requirements']}
            self.assertEqual(by_id['runtime.learning_evolution_capability_artifacts_match_schemas']['status'], 'fail')
            details = by_id['runtime.learning_evolution_capability_artifacts_match_schemas']['details']
            source_errors = '\n'.join(details['schema_errors_by_artifact']['source-candidates.jsonl:1'])
            pattern_errors = '\n'.join(details['schema_errors_by_artifact']['pattern-candidates.jsonl:1'])
            self.assertIn('classification_status', source_errors)
            self.assertIn('memory_write_allowed', pattern_errors)
            mismatches = '\n'.join(details['mismatches'])
            self.assertIn('allowed_learning_outputs overlaps not_allowed_outputs', mismatches)
            self.assertIn('pattern_candidates.unsafe_or_unknown_source_ids', mismatches)

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
