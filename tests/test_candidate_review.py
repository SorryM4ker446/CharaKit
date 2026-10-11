"""Synthetic mechanics tests; scores are fixtures, never image-quality claims."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

from test_studio import studio, SCRIPT, fixture
from test_outfits import outfits
from test_outfits import builder, REPO
from test_quality import assessment


def contract():
    return [{"id": k, "dimension": k, "component": "Synthetic " + k, "property": "fixture property",
             "expected": "fixture requirement", "view": "full_image"} for k in studio.QUALITY_WEIGHTS_V12]


class CandidateReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'project'
        self.source = Path(self.temp.name) / 'source.png'
        fixture(self.source)
        studio.init_project(self.root, self.source, 'test_character')
        self.image = Path(self.temp.name) / 'generated.png'
        fixture(self.image, color='#225577')
        self.prompt = Path(self.temp.name) / 'prompt.txt'
        self.prompt.write_text('Synthetic request.', encoding='utf-8')
        self.first = studio.add_asset(self.root, self.image, 'happy', self.prompt)['asset']
        self.key = self.first['id']
        self.call('pool_start', self.root, self.key, contract())
        # Recreate a saved 0.1.22 pool to keep legacy mechanics covered unchanged.
        state = studio.read_state(self.root)
        state['candidate_pools'][self.key]['version'] = '1.0'
        studio.write_state(self.root, state)

    def call(self, name, *args, **kwargs):
        return studio.workflow_call(name, *args, **kwargs)

    def code(self, expected, fn, *args, **kwargs):
        with self.assertRaises(studio.StudioError) as exc:
            fn(*args, **kwargs)
        self.assertEqual(exc.exception.code, expected)

    def review(self, asset, passed=False, dim='protection', check_id=None):
        sheet = self.call('review_sheet', self.root, [asset['id']], 'assistant')
        state = studio.read_state(self.root)
        asset = studio.get_asset(state, asset['id'])
        data = assessment(scores=dict.fromkeys(studio.QUALITY_WEIGHTS_V12, 5), domain=studio.quality_domain(state, asset))
        data.update(rubric_version='1.2', criteria=copy.deepcopy(state['candidate_pools'][asset['candidate_pool']]['contract']), normal_display_height=420, blind_packet=sheet['packet'])
        for item in data['criteria']:
            item.update(observed='Synthetic inspected finding.', status='passed', score=5)
        if not passed:
            failed = next(x for x in data['criteria'] if x['id'] == check_id) if check_id else next(x for x in data['criteria'] if x['dimension'] == dim)
            failed.update(status='failed', score=3)
            data['dimensions'][dim]['score'] = 3
            data['domain_review']['checks']['nonface_protection'].update(status='failed', evidence='Synthetic structural deviation.')
        comparison = self.root / 'preview' / (asset['id'] + '.png')
        studio.make_preview(self.root, comparison, [asset['id']])
        return studio.record_quality(self.root, asset['id'], data, [comparison])

    def next(self):
        attempt = self.call('pool_reserve', self.root, self.key)
        result = self.call('pool_import', self.root, self.key, attempt['token'], self.image, self.prompt,
                           [Path(p) for p in attempt['reference_paths']])
        return result['asset']

    def compare(self, preferred, repairable=False):
        state = studio.read_state(self.root)
        ids = [a['id'] for a in state['assets'] if a.get('candidate_pool') == self.key]
        sheet = self.call('review_sheet', self.root, ids, 'assistant')
        packet = studio.read_state(self.root)['review_packets'][sheet['packet']]
        label = next((k for k, v in packet['items'].items() if v['asset_id'] == preferred), None)
        return self.call('compare', self.root, self.key, {'packet': sheet['packet'], 'basis': 'assistant',
                         'preferred': label, 'repairable': repairable, 'evidence': 'Synthetic pairwise evidence.',
                         'repair_plan': 'Synthetic single localized correction.'})

    def feedback(self, aid, decision='accept', note='Actual user fixture response.'):
        sheet = self.call('review_sheet', self.root, [aid], 'user')
        packet = studio.read_state(self.root)['review_packets'][sheet['packet']]
        alias = next(k for k,v in packet['items'].items() if v['asset_id']==aid)
        data = {'packet': sheet['packet'], 'basis': 'user', 'candidate': alias, 'decision': decision, 'note': note}
        return self.call('human_feedback', self.root, data), data

    def test_independent_second_and_repair_selected_first_with_fixed_budget(self):
        self.review(self.first)
        self.assertEqual(self.call('pool_status', self.root, self.key)['action'], 'sample')
        second = self.next()
        self.assertIsNone(second['parent_asset_id'])
        self.assertEqual(len(second['generation_inputs']['references']), 1)
        self.review(second)
        self.assertEqual(self.compare(self.key, True)['action'], 'repair')
        third = self.next()
        self.assertEqual(third['parent_asset_id'], self.key)
        self.assertEqual(third['generation_inputs']['strategy'], 'repair_best')
        self.review(third)
        self.compare(self.key, True)
        self.assertEqual(self.call('pool_status', self.root, self.key)['action'], 'exhausted')
        self.code('POOL_NOT_READY', self.call, 'pool_reserve', self.root, self.key)
        self.code('POOL_IMPORT_REQUIRED', studio.start_refinement, self.root, self.key)
        self.code('POOL_IMPORT_REQUIRED', studio.add_asset, self.root, self.image, 'happy', self.prompt)

    def test_first_pass_stops_and_requires_actual_user_before_export(self):
        self.review(self.first, True)
        self.assertEqual(self.call('pool_status', self.root, self.key)['action'], 'human_review')
        self.code('HUMAN_REVIEW_REQUIRED', studio.review_asset, self.root, self.key, 'accepted')
        self.code('HUMAN_REVIEW_REQUIRED', studio.delivery_assets, self.root, [self.key])
        self.code('POOL_NOT_READY', self.call, 'pool_reserve', self.root, self.key)
        result, data = self.feedback(self.key)
        self.assertEqual(result['next_action'], 'export')
        self.assertEqual(self.call('human_feedback', self.root, data), result)
        exported = studio.export_pack(self.root)
        with zipfile.ZipFile(exported['export']) as pack:
            record = exported['manifest']['sprites'][0]
            self.assertEqual(pack.read(record['path']), self.image.read_bytes())
            self.assertEqual(record['human_feedback']['basis'], 'user')

    def test_failed_candidate_positive_opinion_is_retained_without_accepting(self):
        self.review(self.first)
        result, _ = self.feedback(self.key)
        self.assertEqual(result['next_action'], 'blocked')
        state = studio.read_state(self.root)
        self.assertEqual(state['assets'][0]['human_feedback']['decision'], 'accept')
        self.assertEqual(state['selected'], {})
        self.assertEqual(state['assets'][0]['art_review_status'], 'unreviewed')

    def test_changed_packet_image_rejects_feedback(self):
        self.review(self.first, True)
        sheet = self.call('review_sheet', self.root, [self.key], 'user')
        fixture(Path(sheet['candidates']['A']), color='#111111')
        before = (self.root / 'run.json').read_bytes()
        self.code('STALE_REVIEW_PACKET', self.call, 'human_feedback', self.root,
                  {'packet': sheet['packet'], 'basis': 'user', 'candidate': 'A', 'decision': 'accept', 'note': ''})
        self.assertEqual(before, (self.root / 'run.json').read_bytes())

    def test_pending_and_failures_cannot_expand_budget(self):
        self.code('POOL_NOT_READY', self.call, 'pool_reserve', self.root, self.key)
        self.review(self.first)
        attempt = self.call('pool_reserve', self.root, self.key)
        self.code('POOL_NOT_READY', self.call, 'pool_reserve', self.root, self.key)
        self.call('pool_import', self.root, self.key, attempt['token'], None, None, None, 'Tool failed.')
        self.assertEqual(self.call('pool_status', self.root, self.key)['used'], 2)
        self.code('INVALID_CANDIDATE_REVIEW', self.call, 'pool_start', self.root, self.key, contract(), 2)

    def test_rubric_cannot_average_away_check_or_change_contract(self):
        data = assessment(scores=dict.fromkeys(studio.QUALITY_WEIGHTS_V12, 5))
        data.update(rubric_version='1.2', criteria=contract(), normal_display_height=420, blind_packet='fixture')
        for item in data['criteria']:
            item.update(observed='Fixture', status='passed', score=5)
        data['criteria'][0].update(status='failed', score=3)
        self.code('INVALID_CANDIDATE_REVIEW', studio.quality_result, data)
        data['dimensions']['target']['score'] = 3
        self.assertEqual(studio.quality_result(data)['status'], 'failed')

    def test_public_packet_contains_no_versions_scores_or_prompt(self):
        sheet = self.call('review_sheet', self.root, [self.key], 'assistant')
        text = Path(sheet['page']).read_text(encoding='utf-8') + Path(sheet['public_packet']).read_text(encoding='utf-8')
        for secret in (self.key, 'quality_review', 'rubric_version', 'Synthetic request.'):
            self.assertNotIn(secret, text)
        self.assertEqual(Path(sheet['candidates']['A']).read_bytes(), self.image.read_bytes())

    def test_reject_and_revision_are_not_acceptance_or_silent_generation(self):
        self.review(self.first, True)
        result, data = self.feedback(self.key, 'revise', 'Make the intended expression softer.')
        self.assertEqual(result['next_action'], 'revision_request')
        state = studio.read_state(self.root)
        self.assertEqual(state['selected'], {})
        self.assertEqual(len(state['assets']), 1)
        self.code('POOL_NOT_READY', self.call, 'pool_reserve', self.root, self.key)
        # A real new user revision gets its own explicit budget; the old record stays intact.
        revision = studio.add_asset(self.root, self.image, 'happy', self.prompt)['asset']
        self.call('pool_start', self.root, revision['id'], contract(), 1)
        self.assertEqual(studio.read_state(self.root)['candidate_pools'][self.key]['budget'], 3)

    def correction(self, aid, note='Make the intended expression softer.', checks=None):
        _, feedback = self.feedback(aid, 'revise', note)
        return self.call('revision_prepare', self.root, feedback['packet'], checks or contract())

    def import_correction(self, plan):
        return self.call('revision_import', self.root, plan['revision'], self.image, self.prompt,
                         [Path(p) for p in plan['reference_paths']])['asset']

    def test_human_revision_uses_chosen_earlier_candidate_and_preserves_old_pool(self):
        self.review(self.first)
        second = self.next()
        self.review(second)
        plan = self.correction(self.key, 'Keep A; soften only the mouth corners.')
        before = studio.read_state(self.root)
        original = {a['path']: (self.root / a['path']).read_bytes() for a in before['assets']}
        self.assertEqual(plan['parent_asset'], self.key)
        self.assertEqual(Path(plan['reference_paths'][0]), (self.root / self.first['path']).resolve())
        self.assertEqual(plan['references'][0]['role'], 'edit_target')
        child = self.import_correction(plan)
        after = studio.read_state(self.root)
        self.assertEqual(child['parent_asset_id'], self.key)
        self.assertNotEqual(child['parent_asset_id'], second['id'])
        self.assertEqual(before['assets'], after['assets'][:-1])
        self.assertEqual(before['candidate_pools'][self.key], after['candidate_pools'][self.key])
        self.assertEqual(after['candidate_pools'][child['id']]['budget'], 3)
        self.assertEqual(child['generation_inputs']['strategy'], 'user_revision')
        for path, raw in original.items():
            self.assertEqual((self.root / path).read_bytes(), raw)
        self.assertEqual((self.root / child['path']).read_bytes(), self.image.read_bytes())
        for field in ('quality_review', 'human_feedback', 'fidelity_review'):
            self.assertNotIn(field, child)

    def test_revision_contract_updates_target_without_weakening_protection(self):
        self.review(self.first, True)
        _, feedback = self.feedback(self.key, 'revise', 'Reduce the smile intensity.')
        revised = contract()
        revised[0]['expected'] = 'A softer smile preserving the requested emotion.'
        before = (self.root / 'run.json').read_bytes()
        for dimension in ('identity', 'protection', 'integration', 'rendering'):
            invalid = copy.deepcopy(revised)
            next(x for x in invalid if x['dimension'] == dimension)['expected'] = 'Anything is acceptable.'
            self.code('INVALID_CANDIDATE_REVIEW', self.call, 'revision_prepare', self.root, feedback['packet'], invalid)
            self.assertEqual((self.root / 'run.json').read_bytes(), before)
        plan = self.call('revision_prepare', self.root, feedback['packet'], revised)
        child = self.import_correction(plan)
        self.review(child, True)
        state = studio.read_state(self.root)
        self.assertEqual(state['candidate_pools'][self.key]['contract'], contract())
        self.assertEqual(state['candidate_pools'][child['id']]['contract'], plan['contract'])
        self.assertEqual(plan['contract'][:-2], revised)
        self.assertEqual([x['id'] for x in plan['contract'][-2:]], ['revision_continuity','source_protection_recheck'])

    def test_revision_requires_actual_feedback_and_rejects_superseded_choice(self):
        self.review(self.first, True)
        sheet = self.call('review_sheet', self.root, [self.key], 'user')
        before = (self.root / 'run.json').read_bytes()
        self.code('HUMAN_REVISION_REQUIRED', self.call, 'revision_prepare', self.root, sheet['packet'], contract())
        self.assertEqual((self.root / 'run.json').read_bytes(), before)
        plan = self.correction(self.key)
        self.feedback(self.key, 'reject', 'Cancel this correction.')
        before = (self.root / 'run.json').read_bytes()
        self.code('HUMAN_REVISION_NOT_READY', self.import_correction, plan)
        self.assertEqual((self.root / 'run.json').read_bytes(), before)
        cancelled = self.call('revision_prepare', self.root, plan['revision'], contract())
        self.assertEqual(cancelled['next_action'], 'stopped')
        self.assertEqual(cancelled['status'], 'cancelled')
        replacement = self.correction(self.key, 'Use this new, specific correction instead.')
        self.assertNotEqual(replacement['revision'], plan['revision'])
        self.assertEqual(replacement['next_action'], 'generate_revision')

    def test_revision_references_and_consumed_budget_cannot_be_bypassed(self):
        self.review(self.first)
        plan = self.correction(self.key)
        before = (self.root / 'run.json').read_bytes()
        self.code('INVALID_REVISION_REFERENCES', self.call, 'revision_import', self.root, plan['revision'], self.image, self.prompt,
                  [Path(p) for p in reversed(plan['reference_paths'])])
        self.code('HUMAN_REVISION_NOT_READY', studio.add_asset, self.root, self.image, 'happy', self.prompt)
        self.assertEqual((self.root / 'run.json').read_bytes(), before)
        self.assertEqual(self.call('revision_prepare', self.root, plan['revision'], contract()), plan)
        child = self.import_correction(plan)
        before = (self.root / 'run.json').read_bytes()
        self.code('HUMAN_REVISION_NOT_READY', self.import_correction, plan)
        self.assertEqual((self.root / 'run.json').read_bytes(), before)
        self.assertEqual(self.call('revision_prepare', self.root, plan['revision'], contract())['asset_id'], child['id'])
        self.code('POOL_NOT_READY', self.call, 'pool_reserve', self.root, child['id'])

    def test_failed_revision_call_stays_spent_without_extra_candidate(self):
        self.review(self.first)
        plan = self.correction(self.key)
        result = self.call('revision_import', self.root, plan['revision'], None, None, None, 'Image tool failed.')
        self.assertEqual(result['next_action'], 'stopped')
        self.assertEqual(len(studio.read_state(self.root)['assets']), 1)
        self.code('HUMAN_REVISION_NOT_READY', self.import_correction, plan)
        self.assertEqual(self.call('revision_prepare', self.root, plan['revision'], contract())['status'], 'failed')
        report = studio.generate_report([self.root], Path(self.temp.name) / 'failed-revision', stage='final')
        data = json.loads(Path(report['manifest']).read_text(encoding='utf-8'))
        self.assertEqual(data['cases'][0]['status'], 'revision_failed')
        self.assertEqual(data['cases'][0]['requested_revision']['failure'], 'Image tool failed.')
        self.assertIn('Image tool failed.', Path(report['report']).read_text(encoding='utf-8'))
        self.assertEqual(report['images'], [])

    def test_revision_parent_changes_block_import(self):
        self.review(self.first)
        plan = self.correction(self.key)
        fixture(self.root / self.first['path'], color='#334422')
        before = (self.root / 'run.json').read_bytes()
        self.code('STALE_REVIEW_PACKET', self.import_correction, plan)
        self.code('STALE_REVIEW_PACKET', self.call, 'revision_prepare', self.root, plan['revision'], contract())
        self.assertEqual((self.root / 'run.json').read_bytes(), before)

    def test_missing_revision_parent_blocks_import_without_another_candidate(self):
        self.review(self.first)
        plan = self.correction(self.key)
        (self.root / self.first['path']).unlink()
        before = (self.root / 'run.json').read_bytes()
        self.code('STALE_REVIEW_PACKET', self.import_correction, plan)
        self.assertEqual((self.root / 'run.json').read_bytes(), before)

    def test_refresh_legacy_custom_locale_without_revision_labels(self):
        from importlib.util import module_from_spec, spec_from_file_location
        spec = spec_from_file_location('preview_legacy', SCRIPT.parents[3] / 'lib/candidate_review.py')
        renderer = module_from_spec(spec); spec.loader.exec_module(renderer)
        self.review(self.first, True)
        labels = dict(renderer.PREVIEW_EN)
        labels['原图'] = 'Custom source label'
        sheet = self.call('review_sheet', self.root, [self.key], 'user', language='ja', translations=labels)
        public_path = Path(sheet['public_packet'])
        public = json.loads(public_path.read_text(encoding='utf-8'))
        for key in ('修订前', '本次修改'):
            del public['ui_labels'][key]
        for key in renderer.INTERACTION_LABELS:
            del public['ui_labels'][key]
        public_path.write_text(json.dumps(public, ensure_ascii=False), encoding='utf-8')
        state = studio.read_state(self.root)
        for artifact in state['review_packets'][sheet['packet']]['artifacts']:
            if artifact['path'].endswith('/packet.json'):
                artifact['sha256'] = studio.digest(public_path)
        studio.write_state(self.root, state)
        refreshed = self.call('refresh_review_sheet', self.root, sheet['packet'])
        page = Path(refreshed['page']).read_text(encoding='utf-8')
        self.assertIn('lang="ja"', page)
        self.assertIn('Custom source label', page)
        self.assertNotIn('Copy review feedback', page.split('<script>')[0])

    def test_revision_rechecks_reviews_and_exports_with_feedback_lineage(self):
        self.review(self.first, True)
        plan = self.correction(self.key, 'Only soften the smile; preserve the rest.')
        child = self.import_correction(plan)
        self.assertEqual(self.call('pool_status', self.root, child['id'])['action'], 'review')
        self.code('HUMAN_REVIEW_REQUIRED', studio.generate_report, [self.root], Path(self.temp.name) / 'premature', stage='final')
        self.review(child, True)
        self.assertEqual(self.call('pool_status', self.root, child['id'])['action'], 'human_review')
        self.code('HUMAN_REVIEW_REQUIRED', studio.delivery_assets, self.root, [child['id']])
        sheet = self.call('review_sheet', self.root, [child['id']], 'user', language='en')
        public = json.loads(Path(sheet['public_packet']).read_text(encoding='utf-8'))
        page = Path(sheet['page']).read_text(encoding='utf-8')
        self.assertIn('Before revision', page)
        self.assertIn(plan['note'], page)
        self.assertEqual((Path(sheet['page']).parent / public['revision']['source']).read_bytes(), (self.root / self.first['path']).read_bytes())
        refreshed = self.call('refresh_review_sheet', self.root, sheet['packet'])
        self.assertIn('Before revision', Path(refreshed['page']).read_text(encoding='utf-8'))
        self.call('human_feedback', self.root, {'packet': sheet['packet'], 'basis': 'user', 'candidate': 'A', 'decision': 'accept', 'note': 'Use this correction.'})
        result = studio.generate_report([self.root], Path(self.temp.name) / 'revision-final', stage='final', language='en')
        report = json.loads(Path(result['manifest']).read_text(encoding='utf-8'))
        self.assertEqual(report['cases'][0]['human_revision']['parent_asset'], self.key)
        self.assertIn(plan['note'], Path(result['report']).read_text(encoding='utf-8'))
        exported = studio.export_pack(self.root)
        record = exported['manifest']['sprites'][0]
        self.assertEqual(record['asset_id'], child['id'])
        self.assertEqual(record['human_revision']['note'], plan['note'])
        with zipfile.ZipFile(exported['export']) as archive:
            self.assertEqual(archive.read(record['path']), self.image.read_bytes())

    def test_revision_can_be_revised_again_only_from_new_actual_feedback(self):
        self.review(self.first, True)
        first_plan = self.correction(self.key)
        child = self.import_correction(first_plan)
        self.review(child, True)
        next_plan = self.correction(child['id'], 'Adjust the mouth corners once more.')
        grandchild = self.import_correction(next_plan)
        self.assertEqual(grandchild['parent_asset_id'], child['id'])
        self.assertEqual(studio.read_state(self.root)['human_revisions'][first_plan['revision']]['asset_id'], child['id'])

    def test_revision_preserves_outfit_brief_and_mouth_state(self):
        folder = Path(self.temp.name)
        for mode in ('mouth', 'recolor', 'replace'):
            with self.subTest(mode=mode):
                self.root = folder / mode
                if mode == 'mouth':
                    studio.init_project(self.root, self.source, 'test_character')
                    parent = studio.add_asset(self.root, self.image, 'happy', self.prompt, mouth_state='open')['asset']
                else:
                    outfits.init_project(self.root, self.source, 'test_character')
                    change = {'edit_type': 'replace', 'replacement': 'Synthetic short jacket'} if mode == 'replace' else {}
                    color = None if mode == 'replace' else 'blue'
                    brief = outfits.prepare_outfit(self.root, 'coat', 'jacket fabric', color, 'Synthetic target boundary', ['Synthetic protected remainder'], [8, 8, 50, 70], **change)
                    parent = outfits.add_asset(self.root, self.image, 'coat', 'jacket fabric', color, self.prompt, Path(brief['brief_file']), **change)['asset']
                self.call('pool_start', self.root, parent['id'], contract(), 1)
                if mode != 'mouth':
                    outfits.record_fidelity(self.root, parent['id'], 'passed', 'passed', 'Synthetic fidelity fixture.', basis='assistant')
                self.review(parent, True)
                plan = self.correction(parent['id'], 'Adjust only the requested target detail.')
                child = self.import_correction(plan)
                for field in ('expression', 'mouth_state', 'outfit_id', 'edit_type', 'target', 'color', 'replacement', 'edit_brief'):
                    self.assertEqual(child.get(field), parent.get(field))
                self.assertNotIn('fidelity_review', child)
                self.assertEqual(studio.fidelity_status(child), 'pending' if mode != 'mouth' else 'unrecorded')
                self.review(child, True)
                if mode != 'mouth':
                    self.assertEqual(self.call('pool_status', self.root, child['id'])['action'], 'review')
                    outfits.record_fidelity(self.root, child['id'], 'passed', 'passed', 'Fresh synthetic fidelity fixture.', basis='assistant')
                self.assertEqual(self.call('pool_status', self.root, child['id'])['action'], 'human_review')

    def test_packaged_revision_cli_uses_unicode_feedback_outside_repository(self):
        self.review(self.first, True)
        _, feedback = self.feedback(self.key, 'revise', '只调整嘴角，保留其他细节。')
        folder = Path(self.temp.name)
        package = folder / 'plugin.zip'
        builder.build(REPO, package)
        installed = folder / 'installed plugin'
        with zipfile.ZipFile(package) as archive:
            archive.extractall(installed)
        entrypoint = installed / 'skills/charakit-expressions/scripts/studio.py'
        checks = folder / '修改要求.json'
        checks.write_text(json.dumps(contract(), ensure_ascii=False), encoding='utf-8')
        def cli(*args):
            result = subprocess.run([sys.executable, str(entrypoint), *map(str, args)], cwd=folder,
                                    capture_output=True, encoding='utf-8')
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)
        plan = cli('revision-prepare', '--project', self.root, '--packet', feedback['packet'], '--contract-file', checks)
        self.assertEqual(plan['note'], feedback['note'])
        result = cli('revision-import', '--project', self.root, '--revision', plan['revision'], '--image', self.image,
                     '--prompt-file', self.prompt, '--reference', plan['reference_paths'][0], '--reference', plan['reference_paths'][1])
        self.assertEqual(result['asset']['parent_asset_id'], self.key)
        self.assertEqual(cli('pool-status', '--project', self.root, '--case', result['asset']['id'])['action'], 'review')

    def test_duplicate_assessments_are_rejected_and_cli_has_workflow(self):
        self.review(self.first, True)
        self.code('REFINEMENT_ALREADY_REVIEWED', studio.record_quality, self.root, self.key, {}, [])
        result = subprocess.run([sys.executable, str(SCRIPT), 'pool-status', '--project', str(self.root), '--case', self.key], capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['action'], 'human_review')

    def test_report_before_and_after_user_acceptance(self):
        self.review(self.first, True)
        before = studio.generate_report([self.root], Path(self.temp.name) / 'before')
        self.assertEqual(before['images'], [])
        self.feedback(self.key)
        after = studio.generate_report([self.root], Path(self.temp.name) / 'after')
        self.assertEqual(len(after['images']), 1)
        text = Path(after['report']).read_text(encoding='utf-8')
        self.assertIn('Actual user fixture response.', text)

    def test_final_report_requires_human_feedback_and_draft_has_no_assets(self):
        self.review(self.first, True)
        output=Path(self.temp.name)/'premature-final'
        before=(self.root/'run.json').read_bytes()
        self.code('HUMAN_REVIEW_REQUIRED', studio.generate_report, [self.root], output, stage='final')
        self.assertFalse(output.exists())
        self.assertEqual((self.root/'run.json').read_bytes(),before)
        draft=studio.generate_report([self.root],Path(self.temp.name)/'draft',title='Custom title')
        self.assertEqual(draft['stage'],'draft')
        self.assertEqual(draft['images'],[])
        self.assertIn('内部检查草稿',Path(draft['report']).read_text(encoding='utf-8'))
        self.feedback(self.key)
        final=studio.generate_report([self.root],Path(self.temp.name)/'final',stage='final')
        self.assertEqual(final['stage'],'final')
        self.assertEqual(len(final['images']),1)

    def test_final_report_includes_revision_or_rejection_without_delivering(self):
        self.review(self.first)
        self.feedback(self.key,'revise','Restore protected equipment.')
        result=studio.generate_report([self.root],Path(self.temp.name)/'revision-report',stage='final')
        data=json.loads(Path(result['manifest']).read_text(encoding='utf-8'))
        self.assertEqual(result['stage'],'final')
        self.assertEqual(result['images'],[])
        self.assertEqual(data['cases'][0]['human_result']['next_action'],'revision_request')
        self.assertEqual(data['cases'][0]['status'],'revise')
        self.assertIn('Restore protected equipment.',Path(result['report']).read_text(encoding='utf-8'))
        self.feedback(self.key,'reject','Neither candidate is suitable.')
        rejected=studio.generate_report([self.root],Path(self.temp.name)/'reject-report',stage='final')
        reject_data=json.loads(Path(rejected['manifest']).read_text(encoding='utf-8'))
        self.assertEqual(reject_data['cases'][0]['status'],'user_declined')
        self.assertEqual(rejected['images'],[])

    def test_report_uses_human_chosen_earlier_candidate_and_its_evidence(self):
        self.review(self.first)
        second=self.next()
        self.review(second,dim='identity')
        self.compare(second['id'])
        self.feedback(self.key,'accept','Prefer the earlier candidate despite its defect.')
        result=studio.generate_report([self.root],Path(self.temp.name)/'earlier-report',stage='final')
        data=json.loads(Path(result['manifest']).read_text(encoding='utf-8'))
        case=data['cases'][0]
        self.assertEqual(case['assessed_asset_id'],self.key)
        self.assertEqual(case['human_result']['next_action'],'blocked')
        self.assertEqual(case['human_feedback']['note'],'Prefer the earlier candidate despite its defect.')
        self.assertEqual(result['images'],[])

    def test_refresh_unanswered_page_preserves_aliases_evidence_and_old_page(self):
        self.review(self.first)
        sheet=self.call('review_sheet',self.root,[self.key],'user')
        before=studio.read_state(self.root)
        old_page=Path(sheet['page']).read_bytes()
        refreshed=self.call('refresh_review_sheet',self.root,sheet['packet'])
        after=studio.read_state(self.root)
        self.assertNotEqual(refreshed['page'],sheet['page'])
        self.assertEqual(Path(sheet['page']).read_bytes(),old_page)
        self.assertEqual(before['assets'],after['assets'])
        self.assertEqual(before['candidate_pools'],after['candidate_pools'])
        self.assertEqual(before['review_packets'][sheet['packet']]['items'],after['review_packets'][sheet['packet']]['items'])
        self.call('packet_valid',self.root,after,after['review_packets'][sheet['packet']])
        self.call('human_feedback',self.root,{'packet':sheet['packet'],'basis':'user','candidate':'A','decision':'reject','note':'Fixture rejection.'})
        self.code('INVALID_CANDIDATE_REVIEW',self.call,'refresh_review_sheet',self.root,sheet['packet'])

    def assert_refresh_with_project_alias(self, root):
        self.review(self.first)
        sheet = self.call('review_sheet', self.root, [self.key], 'user')
        before = studio.read_state(self.root)
        old_page = Path(sheet['page']).read_bytes()
        refreshed = self.call('refresh_review_sheet', root, sheet['packet'])
        after = studio.read_state(self.root)
        packet = after['review_packets'][sheet['packet']]
        relative = Path(refreshed['page']).relative_to(self.root.resolve()).as_posix()
        self.assertEqual(packet['latest_page'], relative)
        self.assertEqual(packet['artifacts'][-1]['path'], relative)
        self.assertEqual(Path(sheet['page']).read_bytes(), old_page)
        for field in ('assets', 'candidate_pools', 'selected'):
            self.assertEqual(before[field], after[field])
        self.assertEqual(before['review_packets'][sheet['packet']]['items'], packet['items'])
        self.call('packet_valid', self.root, after, packet)

    def test_refresh_resolves_noncanonical_project_path(self):
        self.assert_refresh_with_project_alias(self.root / 'reviews' / '..')

    @unittest.skipUnless(os.name == 'nt', 'Windows short paths only')
    def test_refresh_resolves_windows_short_project_path(self):
        import ctypes
        from ctypes import wintypes

        short_path = ctypes.WinDLL('kernel32', use_last_error=True).GetShortPathNameW
        short_path.argtypes = (wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD)
        short_path.restype = wintypes.DWORD
        source = str(self.root.resolve())
        size = short_path(source, None, 0)
        if not size:
            raise ctypes.WinError(ctypes.get_last_error())
        buffer = ctypes.create_unicode_buffer(size)
        length = short_path(source, buffer, size)
        if not length or length >= size:
            raise ctypes.WinError(ctypes.get_last_error())
        alias = Path(buffer.value)
        if alias == self.root.resolve():
            self.skipTest('8.3 short directory names are disabled on this volume')
        self.assert_refresh_with_project_alias(alias)

    def test_preview_language_covers_controls_and_refresh_preserves_it(self):
        self.review(self.first)
        sheet=self.call('review_sheet',self.root,[self.key],'user',language='en')
        public=json.loads(Path(sheet['public_packet']).read_text(encoding='utf-8'))
        text=Path(sheet['page']).read_text(encoding='utf-8')
        self.assertEqual(public['language'],'en')
        for value in ('lang="en"','Enlarge preview','Your review','Fit to window','Source','Download feedback JSON'):
            self.assertIn(value,text)
        self.assertNotIn('切换明暗底色',text.split('<script>')[0])
        refreshed=self.call('refresh_review_sheet',self.root,sheet['packet'])
        self.assertIn('lang="en"',Path(refreshed['page']).read_text(encoding='utf-8'))

    def test_unsupported_or_incomplete_locale_fails_without_creating_packet(self):
        self.review(self.first)
        before=(self.root/'run.json').read_bytes()
        for language,labels in [('ja',None),('ja',{}),('en',{'原图':'Source'}),('en\"',None)]:
            self.code('INVALID_REVIEW_LANGUAGE',self.call,'review_sheet',self.root,[self.key],'user',language=language,translations=labels)
        self.assertEqual(before,(self.root/'run.json').read_bytes())

    def test_custom_locale_and_request_are_escaped_in_html_and_script(self):
        from importlib.util import module_from_spec,spec_from_file_location
        spec=spec_from_file_location('preview_test',SCRIPT.parents[3]/'lib/candidate_review.py')
        renderer=module_from_spec(spec);spec.loader.exec_module(renderer)
        translations=dict(renderer.PREVIEW_EN)
        translations['原图']='Source </script><script>alert(1)</script>'
        text=renderer.render_sheet('fixture',['A'],'Literal __UI_0__ <script>alert(2)</script>',contract(),'user','ja',translations)
        self.assertIn('lang="ja"',text)
        self.assertIn('Literal __UI_0__ &lt;script&gt;',text)
        self.assertNotIn('</script><script>alert(1)',text)
        self.assertEqual(text.count('<script>'),1)

    def test_wrong_reference_does_not_consume_or_import_again(self):
        self.review(self.first)
        attempt = self.call('pool_reserve', self.root, self.key)
        before = (self.root / 'run.json').read_bytes()
        self.code('INVALID_CANDIDATE_REVIEW', self.call, 'pool_import', self.root, self.key, attempt['token'], self.image, self.prompt, [self.image])
        self.assertEqual(before, (self.root / 'run.json').read_bytes())

    def test_passed_candidate_cannot_lose_to_failed_candidate(self):
        self.review(self.first)
        second = self.next()
        self.review(second, True)
        self.code('INVALID_CANDIDATE_REVIEW', self.compare, self.key)
        self.assertEqual(self.compare(second['id'])['best_asset'], second['id'])

    def test_repair_regression_retains_preferred_earlier_candidate(self):
        self.review(self.first)
        second = self.next()
        self.review(second)
        self.compare(self.key, True)
        third = self.next()
        self.review(third, dim='identity')
        self.compare(self.key, True)
        state = studio.read_state(self.root)
        self.assertEqual(state['candidate_pools'][self.key]['comparisons'][-1]['preferred'], self.key)
        self.assertEqual(len(state['assets']), 3)

    def test_canvas_mismatch_retains_positive_feedback_but_blocks_export(self):
        folder = Path(self.temp.name)
        root = folder / 'mismatch'
        studio.init_project(root, self.source, 'test_character')
        small = folder / 'small.png'
        fixture(small, size=(32, 48))
        asset = studio.add_asset(root, small, 'happy', self.prompt)['asset']
        previous = self.root
        self.root = root
        self.call('pool_start', root, asset['id'], contract(), 1)
        self.review(asset, True)
        result, _ = self.feedback(asset['id'])
        self.assertEqual(result['next_action'], 'blocked')
        self.assertIn('CANVAS_MISMATCH', result['blockers']['technical'])
        self.assertEqual(studio.read_state(root)['assets'][0]['quality_review']['result']['total'], 100)
        self.code('NO_SELECTED_ASSETS', studio.export_pack, root)
        self.root = previous

    def test_outfits_require_fidelity_before_sampling(self):
        root = Path(self.temp.name) / 'outfits'
        outfits.init_project(root, self.source, 'test_character')
        asset = outfits.add_asset(root, self.image, 'coat_blue', '外套', '蓝色', self.prompt)['asset']
        self.call('pool_start', root, asset['id'], contract())
        self.assertEqual(studio.fidelity_status(studio.read_state(root)['assets'][0]), 'pending')
        self.assertEqual(self.call('pool_status', root, asset['id'])['action'], 'review')

    def test_missing_source_copy_invalidates_anonymous_evidence(self):
        self.review(self.first, True)
        state = studio.read_state(self.root)
        packet = state['review_packets'][state['assets'][0]['quality_review']['blind_packet']]
        source_copy = self.root / packet['artifacts'][0]['path']
        fixture(source_copy, color='#987654')
        self.assertEqual(studio.quality_status(self.root, state, state['assets'][0]), 'stale')
        self.assertEqual(self.call('pool_status', self.root, self.key)['action'], 'blocked')

    def test_unsafe_repair_is_not_authorized(self):
        self.review(self.first, dim='target')
        second = self.next()
        self.review(second, dim='target')
        self.code('INVALID_CANDIDATE_REVIEW', self.compare, self.key, True)
        self.assertEqual(self.compare(self.key, False)['action'], 'exhausted')

    def test_contract_cannot_be_weakened_at_assessment(self):
        sheet = self.call('review_sheet', self.root, [self.key], 'assistant')
        data = assessment(scores=dict.fromkeys(studio.QUALITY_WEIGHTS_V12, 5))
        data.update(rubric_version='1.2', criteria=contract(), normal_display_height=420, blind_packet=sheet['packet'])
        for item in data['criteria']:
            item.update(observed='Fixture', status='passed', score=5)
        data['criteria'][0]['expected'] = 'A weaker retrospective requirement'
        self.code('INVALID_CANDIDATE_REVIEW', studio.record_quality, self.root, self.key, data, [])

    def test_review_details_use_source_coordinates_and_preserve_raw_artwork(self):
        from PIL import Image
        self.review(self.first, True)
        before = studio.digest(self.root/self.first['path'])
        page = self.call('review_sheet', self.root, [self.key], 'user', face_box=[16, 20, 48, 44], detail_box=[16, 44, 48, 88])
        folder = Path(page['page']).parent
        public = json.loads(Path(page['public_packet']).read_text(encoding='utf-8'))
        self.assertEqual([r['id'] for r in public['inspection']['regions']], ['face', 'target'])
        for name, filename in [('source', 'source.png'), ('A', 'A.png')]:
            with Image.open(folder/filename) as original, Image.open(folder/('face-'+name+'.png')) as crop:
                self.assertEqual(crop.size, (32, 24))
                self.assertEqual(crop.tobytes(), original.convert('RGBA').crop((16,20,48,44)).tobytes())
        self.assertEqual(studio.digest(self.root/self.first['path']), before)
        refreshed = self.call('refresh_review_sheet', self.root, page['packet'])
        self.assertEqual(json.loads(Path(refreshed['public_packet']).read_text(encoding='utf-8'))['inspection'], public['inspection'])

    def test_invalid_review_region_is_rejected_without_creating_a_packet(self):
        self.review(self.first, True)
        before = (self.root/'run.json').read_bytes()
        packets = set((self.root/'reviews').iterdir())
        for box in ([0,0,65,96], [16,20,16,44], [0.5,0,32,40], [True,0,32,40]):
            self.code('INVALID_REVIEW_BOX', self.call, 'review_sheet', self.root, [self.key], 'user', face_box=box)
        self.assertEqual((self.root/'run.json').read_bytes(), before)
        self.assertEqual(set((self.root/'reviews').iterdir()), packets)

    def test_mismatched_canvas_details_map_coordinates_without_fixing_the_candidate(self):
        from PIL import Image
        fixture(self.image, size=(128,192), color='#112233')
        other = studio.add_asset(self.root, self.image, 'angry', self.prompt)['asset']
        page = self.call('review_sheet', self.root, [other['id']], 'assistant', face_box=[16,20,48,44])
        folder = Path(page['page']).parent
        public = json.loads(Path(page['public_packet']).read_text(encoding='utf-8'))
        self.assertEqual(public['inspection']['sizes']['A'], [128,192])
        with Image.open(folder/'A.png') as original, Image.open(folder/'face-A.png') as crop:
            self.assertEqual(crop.tobytes(), original.convert('RGBA').crop((32,40,96,88)).tobytes())
        self.assertIn('CANVAS_MISMATCH', studio.check_asset(self.root, studio.read_state(self.root), other)['errors'])

    def test_changed_detail_evidence_blocks_feedback_and_refresh(self):
        self.review(self.first, True)
        page = self.call('review_sheet', self.root, [self.key], 'user', face_box=[16,20,48,44])
        (Path(page['page']).parent/'face-A.png').write_bytes(b'changed inspection')
        self.code('STALE_REVIEW_PACKET', self.call, 'refresh_review_sheet', self.root, page['packet'])
        self.code('STALE_REVIEW_PACKET', self.call, 'human_feedback', self.root, dict(packet=page['packet'],basis='user',candidate='A',decision='accept',note='Actual fixture feedback'))

    def test_final_report_includes_only_selected_version_details_after_actual_feedback(self):
        self.review(self.first, True)
        page = self.call('review_sheet', self.root, [self.key], 'user', face_box=[16,20,48,44], detail_box=[16,44,48,88])
        output = Path(self.temp.name)/'final-details'
        self.code('HUMAN_REVIEW_REQUIRED', studio.generate_report, [self.root], output, stage='final')
        self.assertFalse(output.exists())
        self.call('human_feedback', self.root, dict(packet=page['packet'],basis='user',candidate='A',decision='accept',note='Actual acceptance fixture'))
        report = studio.generate_report([self.root], output, stage='final')
        data = json.loads(Path(report['manifest']).read_text(encoding='utf-8'))
        details = data['cases'][0]['detail_previews']
        self.assertEqual([d['id'] for d in details], ['face','target'])
        self.assertEqual({d['asset_id'] for d in details}, {self.key})
        self.assertEqual(len(report['images']), 1)
        for detail in details:
            self.assertTrue((output/detail['path']).is_file())
            self.assertIn(detail['path'], Path(report['report']).read_text(encoding='utf-8'))
        self.assertEqual(studio.digest(Path(report['images'][0])), self.first['sha256'])

    def test_revision_drops_unrelated_prior_regions_and_keeps_parent_nonselectable(self):
        self.review(self.first, True)
        page = self.call('review_sheet', self.root, [self.key], 'user', face_box=[16,20,48,44])
        self.call('human_feedback', self.root, dict(packet=page['packet'],basis='user',candidate='A',decision='revise',note='Actual fixture correction'))
        plan = self.call('revision_prepare', self.root, page['packet'], contract())
        child = self.import_correction(plan)
        self.review(child, True)
        new = self.call('review_sheet', self.root, [child['id']], 'user')
        public = json.loads(Path(new['public_packet']).read_text(encoding='utf-8'))
        self.assertEqual(public['inspection']['regions'], [])
        self.assertEqual(public['inspection']['comparison_base'], 'parent')
        self.assertEqual(set(public['candidates']), {'A'})
        self.assertFalse((Path(new['page']).parent/'face-parent.png').exists())

    def test_changed_decision_gets_new_packet_and_preserves_history(self):
        self.review(self.first, True)
        result, data = self.feedback(self.key, 'reject')
        self.assertEqual(result['next_action'], 'stopped')
        result, _ = self.feedback(self.key, 'accept')
        self.assertEqual(result['next_action'], 'export')
        asset = studio.read_state(self.root)['assets'][0]
        self.assertEqual([x['decision'] for x in asset['human_feedback_history']], ['reject', 'accept'])

    def test_revision_redraw_retains_chosen_baseline_and_continuity_gate(self):
        self.review(self.first, True)
        plan = self.correction(self.key)
        child = self.import_correction(plan)
        self.review(child, False)
        attempt = self.call('pool_reserve', self.root, child['id'])
        self.assertEqual(attempt['references'][0]['path'], child['path'])
        self.assertEqual(attempt['references'][1]['path'], 'source.png')
        self.assertEqual(attempt['revision_policy']['baseline_asset'], self.key)
        result = self.call('pool_import', self.root, child['id'], attempt['token'], self.image, self.prompt,
                           [Path(p) for p in attempt['reference_paths']])['asset']
        self.assertEqual(result['parent_asset_id'], child['id'])
        self.assertEqual(result['generation_inputs']['revision_policy'], plan['revision_policy'])
        self.assertIn('revision_continuity', [x['id'] for x in studio.read_state(self.root)['candidate_pools'][child['id']]['contract']])

    def test_revision_preservation_checks_each_veto_high_total(self):
        self.review(self.first, True)
        for check_id in ('revision_continuity', 'source_protection_recheck'):
            with self.subTest(check=check_id):
                plan = self.correction(self.key, 'Adjust only the target.')
                child = self.import_correction(plan)
                self.review(child, False, check_id=check_id)
                saved = studio.get_asset(studio.read_state(self.root), child['id'])
                self.assertEqual(saved['quality_review']['result']['total'], 90)
                self.assertEqual(self.call('pool_status', self.root, child['id'])['action'], 'redraw')
                self.code('INTERNAL_REVIEW_INCOMPLETE', self.call, 'review_sheet', self.root, [child['id']], 'user')
                # Close only this synthetic batch to exercise the other independent veto.
                state = studio.read_state(self.root); state['candidate_pools'][child['id']]['stopped'] = True
                studio.write_state(self.root, state)

    def test_focused_revision_regions_apply_to_assistant_human_and_final_report(self):
        self.review(self.first, True)
        _, feedback = self.feedback(self.key, 'revise', 'Adjust only the requested detail.')
        region = {'id':'edited_detail','box':[8,8,48,70], 'label':'修改部位', 'reason':'本次修改范围'}
        plan = self.call('revision_prepare', self.root, feedback['packet'], contract(), inspection=[region])
        child = self.import_correction(plan)
        internal = self.call('review_sheet', self.root, [child['id']], 'assistant')
        self.assertEqual(internal['inspection']['regions'], [region])
        self.assertEqual(internal['inspection']['comparison_base'], 'parent')
        self.assertTrue(Path(internal['revision_parent']).is_file())
        self.review(child, True)
        page = self.call('review_sheet', self.root, [child['id']], 'user')
        self.assertEqual(page['inspection']['regions'], [region])
        self.assertTrue(Path(page['detail_views']['edited_detail']['parent']).is_file())
        self.call('human_feedback', self.root, dict(packet=page['packet'], basis='user',candidate='A',decision='accept',note='Actual fixture acceptance'))
        report = studio.generate_report([self.root], self.root/'focused-final', ids=[child['id']], stage='final')
        case = json.loads(Path(report['manifest']).read_text(encoding='utf-8'))['cases'][0]
        self.assertEqual(case['inspection_base'], 'parent')
        self.assertEqual(case['detail_previews'][0]['label'], '修改部位')
        self.assertEqual(len(report['images']), 1)

    def test_full_only_review_stays_full_only_in_final_report(self):
        self.review(self.first, True)
        page = self.call('review_sheet', self.root, [self.key], 'user', inspection=[])
        self.assertEqual(page['detail_views'], {})
        self.call('human_feedback', self.root, dict(packet=page['packet'],basis='user',candidate='A',decision='accept',note='Actual fixture acceptance'))
        report = studio.generate_report([self.root], self.root/'full-only', face_box=[16,20,48,44], stage='final')
        self.assertEqual(report['detail_previews'], [])

    def test_invalid_inspection_or_restore_scope_does_not_reserve_a_revision(self):
        self.review(self.first, True)
        _, feedback = self.feedback(self.key, 'revise', 'Adjust only the target.')
        before = (self.root/'run.json').read_bytes()
        for checks in (['target'], ['identity','identity'], [{}], ['missing']):
            self.code('INVALID_CANDIDATE_REVIEW', self.call, 'revision_prepare', self.root, feedback['packet'], contract(), restore_checks=checks)
            self.assertEqual((self.root/'run.json').read_bytes(), before)
        self.code('INVALID_REVIEW_BOX', self.call, 'revision_prepare', self.root, feedback['packet'], contract(), inspection=[{'id':'bad','box':[0,0,10000,10000],'label':'部位','reason':'修改'}])
        self.assertEqual((self.root/'run.json').read_bytes(), before)
        plan = self.call('revision_prepare', self.root, feedback['packet'], contract(), restore_checks=['identity'])
        self.assertEqual(plan['revision_policy']['restore_checks'], ['identity'])
        self.code('INVALID_CANDIDATE_REVIEW', self.call, 'revision_prepare', self.root, feedback['packet'], contract(), restore_checks=[])

    def test_legacy_reserved_revision_keeps_reference_order_budget_and_regions(self):
        self.review(self.first, True)
        page = self.call('review_sheet', self.root, [self.key], 'user', face_box=[16,20,48,44])
        self.call('human_feedback', self.root, dict(packet=page['packet'],basis='user',candidate='A',decision='revise',note='Actual legacy fixture correction'))
        plan = self.call('revision_prepare', self.root, page['packet'], contract(), budget=1)
        state = studio.read_state(self.root)
        old = state['human_revisions'][page['packet']]
        old.pop('policy'); old['contract'] = contract(); old['references'].reverse()
        studio.write_state(self.root, state)
        plan = self.call('revision_prepare', self.root, page['packet'], contract())
        self.assertEqual(plan['budget'], 1)
        self.assertEqual(plan['references'][0]['role'], 'immutable_source')
        self.assertNotIn('revision_policy', plan)
        child = self.import_correction(plan)
        self.review(child, True)
        new = self.call('review_sheet', self.root, [child['id']], 'user')
        self.assertEqual(new['inspection']['regions'], [{'id':'face','box':[16,20,48,44]}])

    def test_duplicate_or_unsafe_region_ids_do_not_write_review_files(self):
        self.review(self.first, True)
        before = (self.root/'run.json').read_bytes()
        folders = set((self.root/'reviews').iterdir())
        region = {'id':'detail','box':[8,8,48,70],'label':'部位','reason':'本次修改'}
        for requested in ([region,region], [{**region,'id':'../bad'}], [{**region,'id':'full'}]):
            self.code('INVALID_REVIEW_BOX', self.call, 'review_sheet', self.root, [self.key], 'user', inspection=requested)
            self.assertEqual((self.root/'run.json').read_bytes(), before)
            self.assertEqual(set((self.root/'reviews').iterdir()), folders)


if __name__ == '__main__':
    unittest.main()
