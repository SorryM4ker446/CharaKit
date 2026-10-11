"""Bounded host-tool refinement workflow; synthetic fixtures do not establish art quality."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_studio import studio, SCRIPT, fixture
from test_outfits import outfits, SCRIPT as OUTFITS_SCRIPT
from test_quality import assessment


class RefinementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.source = self.folder / '原图.png'
        fixture(self.source)
        self.root = self.folder / '角色'
        studio.init_project(self.root, self.source, 'test_character')
        self.image = self.folder / 'generated.png'
        fixture(self.image, color='#225577')
        self.prompt = self.folder / 'prompt.txt'
        self.prompt.write_text('Synthetic source plus previous candidate targeted repair.', encoding='utf-8')

    def candidate(self, expression='happy', mouth_state='default'):
        return studio.add_asset(self.root, self.image, expression, self.prompt, mouth_state)['asset']

    def review(self, asset, passed=False, module=studio, root=None):
        root = root or self.root
        data = assessment(domain='garment_recolor' if 'outfit_id' in asset else ('mouth_state' if asset.get('mouth_state', 'default') != 'default' else 'expression'))
        data['rubric_version'] = '1.1'
        if not passed:
            check = 'face_expression' if 'outfit_id' in asset else 'face_design'
            data['domain_review']['checks'][check] = {'status': 'failed', 'evidence': 'Synthetic face design deviation to repair.'}
        preview = root / 'preview' / (asset['id'] + '.png')
        if not preview.exists():
            module.make_preview(root, preview, [asset['id']])
        return module.record_quality(root, asset['id'], data, [preview])

    def revision(self, case_id, root=None, module=studio, references=None):
        root = root or self.root
        plan = module.refinement_status(root, case_id)
        refs = references if references is not None else [Path(p) for p in plan['references'].values()]
        return module.add_refinement(root, case_id, self.image, self.prompt, refs,
                                     strategy=plan['strategy'] or 'continue_previous')['asset']

    def code(self, expected, call, *args, **kwargs):
        with self.assertRaises((studio.StudioError, outfits.StudioError)) as caught:
            call(*args, **kwargs)
        self.assertEqual(caught.exception.code, expected)

    def test_three_round_limit_preserves_history_without_accepting_best_failed(self):
        first = self.candidate()
        original = (self.root / first['path']).read_bytes()
        self.review(first)
        plan = studio.start_refinement(self.root, first['id'])
        self.assertEqual((plan['round'], plan['remaining_revisions'], plan['action']), (1, 2, 'revise'))
        self.assertTrue(any(i['check'] == 'face_design' for i in plan['issues']))
        for round_number in (2, 3):
            asset = self.revision(first['id'])
            self.assertEqual(asset['refinement_round'], round_number)
            self.assertNotIn('quality_review', asset)
            self.assertEqual(studio.refinement_status(self.root, first['id'])['action'], 'review')
            self.review(asset)
        plan = studio.refinement_status(self.root, first['id'])
        self.assertEqual((plan['action'], plan['remaining_revisions'], plan['final_asset']), ('exhausted', 0, None))
        before = (self.root / 'run.json').read_bytes()
        self.code('REFINEMENT_NOT_READY', self.revision, first['id'])
        self.code('REFINEMENT_NOT_PASSED', studio.deliver_refinement, self.root, first['id'])
        self.assertEqual((self.root / 'run.json').read_bytes(), before)
        self.assertEqual((self.root / first['path']).read_bytes(), original)
        self.assertEqual(len(plan['history']), 3)
        self.assertEqual(studio.read_state(self.root)['selected'], {})

    def test_pass_stops_on_second_round_and_only_final_is_deliverable(self):
        first = self.candidate()
        self.review(first)
        studio.start_refinement(self.root, first['id'])
        final = self.revision(first['id'])
        self.review(final, passed=True)
        plan = studio.refinement_status(self.root, first['id'])
        self.assertEqual((plan['action'], plan['final_asset']), ('deliver', final['id']))
        result = studio.deliver_refinement(self.root, first['id'])
        self.assertEqual([a['asset_id'] for a in result['delivery']], [final['id']])
        self.assertEqual(result['rounds_used'], 2)
        self.assertEqual(result['delivery'][0]['art_review_status'], 'unreviewed')
        self.code('REFINEMENT_INTERMEDIATE', studio.delivery_assets, self.root, [first['id']])
        self.code('REFINEMENT_NOT_READY', self.revision, first['id'])
        self.assertEqual(studio.read_state(self.root)['selected'], {})

    def test_first_pass_does_not_generate_and_restarting_does_not_reset_budget(self):
        first = self.candidate()
        self.review(first, passed=True)
        result = studio.start_refinement(self.root, first['id'])
        self.assertEqual(result['action'], 'deliver')
        before = (self.root / 'run.json').read_bytes()
        self.assertEqual(studio.start_refinement(self.root, first['id'])['round'], 1)
        self.assertEqual((self.root / 'run.json').read_bytes(), before)
        self.code('REFINEMENT_BUDGET_FIXED', studio.start_refinement, self.root, first['id'], 2)
        for value in (0, 4, True):
            self.code('INVALID_REFINEMENT_BUDGET', studio.start_refinement, self.root, first['id'], value)

    def test_pending_review_cannot_spend_another_generation(self):
        first = self.candidate()
        self.assertEqual(studio.start_refinement(self.root, first['id'])['action'], 'review')
        self.code('REFINEMENT_NOT_READY', self.revision, first['id'])
        self.review(first)
        self.assertEqual(studio.refinement_status(self.root, first['id'])['action'], 'revise')
        self.code('REFINEMENT_ALREADY_REVIEWED', self.review, first, True)

    def test_explicit_mouth_states_have_independent_cases_and_budgets(self):
        closed = self.candidate(mouth_state='closed')
        opened = self.candidate(mouth_state='open')
        for asset in (closed, opened):
            self.review(asset)
            studio.start_refinement(self.root, asset['id'])
        revision = self.revision(opened['id'])
        self.assertEqual(revision['mouth_state'], 'open')
        self.assertEqual(studio.refinement_status(self.root, closed['id'])['round'], 1)
        self.assertEqual(studio.refinement_status(self.root, opened['id'])['round'], 2)

    def test_reference_roles_are_recorded_and_wrong_inputs_do_not_mutate_project(self):
        first = self.candidate()
        self.review(first)
        plan = studio.start_refinement(self.root, first['id'])
        before = (self.root / 'run.json').read_bytes()
        wrong = [Path(plan['references']['edit_target']), Path(plan['references']['source'])]
        self.code('INVALID_REFINEMENT_REFERENCES', self.revision, first['id'], references=wrong)
        self.assertEqual((self.root / 'run.json').read_bytes(), before)
        revision = self.revision(first['id'])
        inputs = revision['refinement_inputs']
        self.assertEqual(inputs['edit_target']['sha256'], first['sha256'])
        self.assertEqual(inputs['source']['sha256'], studio.read_state(self.root)['source_sha256'])
        self.assertEqual(revision['parent_asset_id'], first['id'])

    def test_stale_evidence_and_changed_edit_target_block_refinement(self):
        for kind in ('preview', 'candidate'):
            with self.subTest(kind=kind):
                first = self.candidate(expression='happy' if kind == 'preview' else 'angry')
                self.review(first)
                studio.start_refinement(self.root, first['id'])
                fixture(self.root / ('preview/' + first['id'] + '.png' if kind == 'preview' else first['path']), color='#111111')
                self.assertEqual(studio.refinement_status(self.root, first['id'])['action'], 'blocked')
                self.code('REFINEMENT_NOT_READY', self.revision, first['id'])

    def test_invalid_budget_and_lineage_metadata_are_rejected(self):
        first = self.candidate()
        self.review(first)
        studio.start_refinement(self.root, first['id'])
        original = json.loads((self.root / 'run.json').read_text(encoding='utf-8'))
        for change in ('budget', 'empty', 'round', 'orphan'):
            altered = copy.deepcopy(original)
            if change == 'budget':
                altered['refinements'][first['id']]['max_rounds'] = 4
            elif change == 'empty':
                altered['refinements'][first['id']]['asset_ids'] = []
            elif change == 'round':
                altered['assets'][0]['refinement_round'] = True
            else:
                altered.pop('refinements')
            (self.root / 'run.json').write_text(json.dumps(altered), encoding='utf-8')
            self.code('INVALID_PROJECT', studio.read_state, self.root)
        (self.root / 'run.json').write_text(json.dumps(original), encoding='utf-8')

    def test_outfits_require_fidelity_and_retain_target_and_color(self):
        root = self.folder / 'outfits'
        outfits.init_project(root, self.source, 'test_character')
        first = outfits.add_asset(root, self.image, 'stockings_white', '丝袜', '白色', self.prompt)['asset']
        self.review(first, module=outfits, root=root)
        self.assertEqual(outfits.start_refinement(root, first['id'])['action'], 'review')
        outfits.record_fidelity(root, first['id'], 'passed', 'failed', 'Synthetic protected design deviation.')
        self.code('REFINEMENT_ALREADY_REVIEWED', outfits.record_fidelity, root, first['id'], 'passed', 'passed', 'Synthetic attempted regrade without new art.')
        revision = self.revision(first['id'], root=root, module=outfits)
        self.assertEqual((revision['outfit_id'], revision['target'], revision['color']), ('stockings_white', '丝袜', '白色'))
        self.assertNotIn('fidelity_review', revision)
        self.review(revision, True, outfits, root)
        self.assertEqual(outfits.refinement_status(root, first['id'])['action'], 'review')
        outfits.record_fidelity(root, revision['id'], 'passed', 'passed', 'Synthetic checks pass.')
        self.assertEqual(outfits.refinement_status(root, first['id'])['action'], 'deliver')
        self.assertEqual(outfits.deliver_refinement(root, first['id'])['delivery'][0]['asset_id'], revision['id'])

    def test_rubric_11_accepts_minor_imperfections_but_retains_hard_vetoes(self):
        data = assessment(scores=dict.fromkeys(studio.QUALITY_WEIGHTS, 4))
        self.assertEqual(studio.quality_result(data)['status'], 'failed')
        data['rubric_version'] = '1.1'
        self.assertEqual(studio.quality_result(data), {'status': 'passed', 'total': 80.0, 'threshold': 80, 'dimension_floor': 4})
        for deviation in ('dimension', 'domain', 'uncertain', 'critical'):
            altered = copy.deepcopy(data)
            if deviation == 'dimension':
                altered['dimensions']['identity']['score'] = 3
            elif deviation == 'domain':
                altered['domain_review']['checks']['face_design']['status'] = 'failed'
            elif deviation == 'uncertain':
                altered['domain_review']['checks']['face_design']['status'] = 'uncertain'
            else:
                altered['critical_defects'] = ['Synthetic wrong component changed.']
            self.assertNotEqual(studio.quality_result(altered)['status'], 'passed')

    def outfit_rounds(self, *, improving=False, legacy=False, target_failed=False):
        root = self.folder / 'outfits'
        outfits.init_project(root, self.source, 'test_character')
        first = outfits.add_asset(root, self.image, 'coat_white', 'coat', 'white', self.prompt)['asset']
        current = first
        for number in (1, 2):
            data = assessment(domain='garment_recolor')
            data['rubric_version'] = '1.1'
            data['dimensions']['identity']['score'] = 4 if improving and number == 2 else 3
            data['domain_review']['checks']['face_expression'] = {'status': 'failed', 'evidence': 'Eye shape changed.'}
            if target_failed:
                data['domain_review']['checks']['target_color'] = {'status': 'failed', 'evidence': 'Wrong color.'}
            preview = root / 'preview' / (current['id'] + '.png')
            outfits.make_preview(root, preview, [current['id']])
            outfits.record_fidelity(root, current['id'], 'failed' if target_failed else 'passed', 'failed', 'Eye shape changed.')
            outfits.record_quality(root, current['id'], data, [preview])
            if number == 1:
                outfits.start_refinement(root, first['id'])
                if legacy:
                    state = outfits.read_state(root)
                    state['refinements'][first['id']]['version'] = '1.0'
                    outfits.write_state(root, state)
                current = self.revision(first['id'], root=root, module=outfits)
        return root, first, current

    def test_stalled_outfit_round_three_rebases_with_explicit_reference_roles(self):
        root, first, previous = self.outfit_rounds()
        before = (root / 'run.json').read_bytes()
        plan = outfits.refinement_status(root, first['id'])
        self.assertEqual(plan['strategy'], 'source_rebase')
        self.assertEqual(plan['stalled_checks'], ['face_expression'])
        self.assertEqual(plan['repair_brief']['edit_target'], plan['references']['source'])
        self.assertEqual(Path(plan['references']['design_reference']), (root / previous['path']).resolve())
        refs = [Path(p) for p in plan['references'].values()]
        self.code('REFINEMENT_STRATEGY_MISMATCH', outfits.add_refinement, root, first['id'], self.image, self.prompt, refs)
        self.assertEqual((root / 'run.json').read_bytes(), before)
        final = self.revision(first['id'], root=root, module=outfits)
        inputs = final['refinement_inputs']
        self.assertEqual(inputs['strategy'], 'source_rebase')
        self.assertEqual(inputs['edit_target'], inputs['source'])
        self.assertEqual(inputs['design_reference']['sha256'], previous['sha256'])
        self.assertEqual(final['parent_asset_id'], previous['id'])
        self.assertEqual(final['refinement_round'], 3)
        self.assertEqual(outfits.read_state(root)['selected'], {})
        self.assertEqual((root / final['path']).read_bytes(), self.image.read_bytes())
        outfits.record_fidelity(root, final['id'], 'passed', 'failed', 'Eye shape still changed.')
        self.review(final, module=outfits, root=root)
        self.assertEqual(outfits.refinement_status(root, first['id'])['action'], 'exhausted')
        self.code('REFINEMENT_NOT_READY', self.revision, first['id'], root=root, module=outfits)
        report = outfits.generate_report([root], self.folder / 'strategy-report')
        manifest = json.loads(Path(report['manifest']).read_text(encoding='utf-8'))
        self.assertEqual(manifest['cases'][0]['history'][-1]['strategy'], 'source_rebase')
        self.assertEqual(report['images'], [])
        altered = outfits.read_state(root)
        altered['assets'][-1]['refinement_inputs']['design_reference']['sha256'] = '0' * 64
        (root / 'run.json').write_text(json.dumps(altered), encoding='utf-8')
        self.code('INVALID_PROJECT', outfits.read_state, root)

    def test_improving_protection_keeps_previous_candidate_strategy(self):
        root, first, _ = self.outfit_rounds(improving=True)
        self.assertEqual(outfits.refinement_status(root, first['id'])['strategy'], 'continue_previous')

    def test_unsuccessful_target_does_not_become_a_design_reference(self):
        root, first, _ = self.outfit_rounds(target_failed=True)
        self.assertEqual(outfits.refinement_status(root, first['id'])['strategy'], 'continue_previous')

    def test_legacy_case_keeps_original_strategy_and_reads_without_writes(self):
        root, first, _ = self.outfit_rounds(legacy=True)
        # Pre-0.1.17 candidates do not have a strategy field.
        state = outfits.read_state(root)
        state['assets'][-1]['refinement_inputs'].pop('strategy')
        outfits.write_state(root, state)
        before = (root / 'run.json').read_bytes()
        self.assertEqual(outfits.refinement_status(root, first['id'])['strategy'], 'continue_previous')
        self.assertEqual((root / 'run.json').read_bytes(), before)

    def test_compact_findings_deduplicate_evidence_without_losing_distinct_defects(self):
        issues = [
            {'check': 'face_expression', 'status': 'failed', 'evidence': 'Eye shape changed.'},
            {'check': 'identity', 'status': 'failed', 'evidence': '  Eye  shape changed. '},
            {'check': 'fidelity', 'status': 'failed', 'evidence': 'Eye shape changed。'},
            {'check': 'non_target_protection', 'status': 'failed', 'evidence': 'Weapon fork missing.'},
        ]
        findings = studio.compact_repair_findings(issues)
        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[0]['checks'], ['face_expression', 'identity', 'fidelity'])
        self.assertEqual(findings[1]['evidence'], 'Weapon fork missing.')
        self.assertEqual(len(issues), 4)

    def test_cli_records_source_rebase_strategy(self):
        root, first, _ = self.outfit_rounds()
        plan = outfits.refinement_status(root, first['id'])
        result = subprocess.run([sys.executable, str(OUTFITS_SCRIPT), 'refine-add', '--project', str(root),
                                 '--case', first['id'], '--image', str(self.image), '--prompt-file', str(self.prompt),
                                 '--strategy', 'source_rebase', '--reference', plan['references']['source'],
                                 '--reference', plan['references']['design_reference']], capture_output=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['asset']['refinement_inputs']['strategy'], 'source_rebase')

    def test_cli_bounded_workflow_and_wrong_module_guard(self):
        first = self.candidate()
        self.review(first)
        def cli(script, *args):
            return subprocess.run([sys.executable, str(script), *map(str, args)], capture_output=True, encoding='utf-8')
        result = cli(SCRIPT, 'refine-start', '--project', self.root, '--asset', first['id'])
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)
        result = cli(SCRIPT, 'refine-add', '--project', self.root, '--case', first['id'], '--image', self.image,
                     '--prompt-file', self.prompt, '--reference', plan['references']['source'], '--reference', plan['references']['edit_target'])
        self.assertEqual(result.returncode, 0, result.stderr)
        revision = json.loads(result.stdout)['asset']
        self.review(revision, passed=True)
        result = cli(SCRIPT, 'refine-deliver', '--project', self.root, '--case', first['id'])
        self.assertEqual(json.loads(result.stdout)['delivery'][0]['asset_id'], revision['id'])
        before = (self.root / 'run.json').read_bytes()
        result = cli(OUTFITS_SCRIPT, 'refine-start', '--project', self.root, '--asset', first['id'])
        self.assertEqual(json.loads(result.stderr)['error']['code'], 'WRONG_MODULE')
        self.assertEqual((self.root / 'run.json').read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
