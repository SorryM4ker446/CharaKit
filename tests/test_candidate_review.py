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

    def call(self, name, *args, **kwargs):
        return studio.workflow_call(name, *args, **kwargs)

    def code(self, expected, fn, *args, **kwargs):
        with self.assertRaises(studio.StudioError) as exc:
            fn(*args, **kwargs)
        self.assertEqual(exc.exception.code, expected)

    def review(self, asset, passed=False, dim='protection'):
        sheet = self.call('review_sheet', self.root, [asset['id']], 'assistant')
        data = assessment(scores=dict.fromkeys(studio.QUALITY_WEIGHTS_V12, 5))
        data.update(rubric_version='1.2', criteria=contract(), normal_display_height=420, blind_packet=sheet['packet'])
        for item in data['criteria']:
            item.update(observed='Synthetic inspected finding.', status='passed', score=5)
        if not passed:
            next(x for x in data['criteria'] if x['dimension'] == dim).update(status='failed', score=3)
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
        ids = [a['id'] for a in state['assets']]
        sheet = self.call('review_sheet', self.root, ids, 'assistant')
        packet = studio.read_state(self.root)['review_packets'][sheet['packet']]
        label = next((k for k, v in packet['items'].items() if v['asset_id'] == preferred), None)
        return self.call('compare', self.root, self.key, {'packet': sheet['packet'], 'basis': 'assistant',
                         'preferred': label, 'repairable': repairable, 'evidence': 'Synthetic pairwise evidence.',
                         'repair_plan': 'Synthetic single localized correction.'})

    def feedback(self, aid, decision='accept', note='Actual user fixture response.'):
        sheet = self.call('review_sheet', self.root, [aid], 'user')
        data = {'packet': sheet['packet'], 'basis': 'user', 'candidate': 'A', 'decision': decision, 'note': note}
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

    def test_changed_decision_gets_new_packet_and_preserves_history(self):
        self.review(self.first, True)
        result, data = self.feedback(self.key, 'reject')
        self.assertEqual(result['next_action'], 'stopped')
        result, _ = self.feedback(self.key, 'accept')
        self.assertEqual(result['next_action'], 'export')
        asset = studio.read_state(self.root)['assets'][0]
        self.assertEqual([x['decision'] for x in asset['human_feedback_history']], ['reject', 'accept'])


if __name__ == '__main__':
    unittest.main()
