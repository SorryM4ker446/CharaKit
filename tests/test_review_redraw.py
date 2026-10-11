"""Synthetic review-redraw state transitions; no image-quality claims."""
from pathlib import Path
import json
import unittest

import test_candidate_review as legacy
from test_studio import studio


class ReviewRedrawTests(unittest.TestCase):
    call = legacy.CandidateReviewTests.call
    code = legacy.CandidateReviewTests.code
    review = legacy.CandidateReviewTests.review
    next = legacy.CandidateReviewTests.next
    compare = legacy.CandidateReviewTests.compare
    feedback = legacy.CandidateReviewTests.feedback
    correction = legacy.CandidateReviewTests.correction
    import_correction = legacy.CandidateReviewTests.import_correction

    def setUp(self):
        legacy.CandidateReviewTests.setUp(self)
        state = studio.read_state(self.root)
        state['candidate_pools'][self.key]['version'] = '1.1'
        studio.write_state(self.root, state)

    def test_high_total_with_failed_dimension_redraws_before_user_review(self):
        for dim, expression in zip(studio.QUALITY_WEIGHTS_V12, ('happy','sad','angry','surprised','shy')):
            with self.subTest(dim=dim):
                # Separate source slot/pool for each five-dimensional veto.
                asset = studio.add_asset(self.root, self.image, expression, self.prompt)['asset'] if dim != 'target' else self.first
                key = asset['id']
                if key != self.key:
                    self.call('pool_start', self.root, key, legacy.contract())
                result = self.review(asset, dim=dim)
                self.assertGreaterEqual(result['score']['total'], 80)
                plan = self.call('pool_status', self.root, key)
                self.assertEqual(plan['action'], 'redraw')
                before = (self.root/'run.json').read_bytes()
                self.code('INTERNAL_REVIEW_INCOMPLETE', self.call, 'review_sheet', self.root, [key], 'user')
                self.assertEqual(before, (self.root/'run.json').read_bytes())
                attempt = self.call('pool_reserve', self.root, key)
                self.assertEqual(attempt['strategy'], 'review_redraw')
                self.assertEqual(attempt['parent'], key)
                self.assertEqual(len(attempt['reference_paths']), 2)
                self.assertTrue(attempt['blocking_findings'])
                self.assertEqual(attempt['review_sha256'], studio.review_fingerprint(studio.read_state(self.root)['assets'][-1 if key != self.key else 0]['quality_review']))

    def test_first_pass_stops_without_spending_three_rounds(self):
        self.review(self.first, True)
        self.assertEqual(self.call('pool_status', self.root, self.key)['action'], 'human_review')
        self.code('POOL_NOT_READY', self.call, 'pool_reserve', self.root, self.key)
        result, _ = self.feedback(self.key)
        self.assertEqual(result['next_action'], 'export')
        self.assertEqual(len(studio.read_state(self.root)['assets']), 1)

    def test_three_failures_show_reasons_and_cannot_start_fourth(self):
        self.review(self.first, dim='target')
        second = self.next()
        self.assertEqual(second['parent_asset_id'], self.key)
        self.review(second, dim='identity')
        self.assertEqual(self.call('pool_status', self.root, self.key)['action'], 'compare')
        self.compare(self.key, False)
        self.assertEqual(self.call('pool_status', self.root, self.key)['action'], 'redraw')
        third = self.next()
        self.assertEqual(third['parent_asset_id'], self.key)
        self.review(third)
        self.compare(second['id'], False)
        plan = self.call('pool_status', self.root, self.key)
        self.assertEqual(plan['action'], 'exhausted')
        self.assertEqual(plan['used'], 3)
        self.assertEqual(len(plan['blocking_findings']), 3)
        self.code('POOL_NOT_READY', self.call, 'pool_reserve', self.root, self.key)
        result, _ = self.feedback(second['id'])
        self.assertEqual(result['next_action'], 'blocked')
        self.assertEqual(studio.read_state(self.root)['selected'], {})

    def test_second_pass_stops_even_when_preferred_first_failed(self):
        self.review(self.first)
        second = self.next()
        self.review(second, True)
        self.code('INVALID_CANDIDATE_REVIEW', self.compare, self.key)
        plan = self.compare(second['id'])
        self.assertEqual(plan['action'], 'human_review')
        self.code('POOL_NOT_READY', self.call, 'pool_reserve', self.root, self.key)
        self.assertEqual(self.feedback(second['id'])[0]['next_action'], 'export')

    def test_domain_only_failure_still_redraws_at_100(self):
        packet = self.call('review_sheet', self.root, [self.key], 'assistant')
        from test_quality import assessment
        data = assessment(scores=dict.fromkeys(studio.QUALITY_WEIGHTS_V12, 5))
        data.update(rubric_version='1.2', criteria=legacy.contract(), normal_display_height=420, blind_packet=packet['packet'])
        for check in data['criteria']:
            check.update(score=5, status='passed', observed='Synthetic passed criterion.')
        data['domain_review']['checks']['nonface_protection'].update(status='failed', evidence='Synthetic domain veto.')
        comparison = self.root/'preview/domain.png'
        studio.make_preview(self.root, comparison, [self.key])
        result = studio.record_quality(self.root, self.key, data, [comparison])
        self.assertEqual(result['score']['total'], 100)
        self.assertEqual(self.call('pool_status', self.root, self.key)['action'], 'redraw')
        self.assertIn('nonface_protection', [x['id'] for x in self.call('pool_reserve', self.root, self.key)['blocking_findings']])

    def test_tool_failure_consumes_round_but_allows_remaining_attempt(self):
        self.review(self.first)
        second = self.call('pool_reserve', self.root, self.key)
        plan = self.call('pool_import', self.root, self.key, second['token'], None, None, None, 'Tool failed.')
        self.assertEqual(plan['used'], 2)
        self.assertEqual(plan['action'], 'redraw')
        third = self.call('pool_reserve', self.root, self.key)
        self.assertEqual(third['number'], 3)
        plan = self.call('pool_import', self.root, self.key, third['token'], None, None, None, 'Tool failed again.')
        self.assertEqual(plan['action'], 'exhausted')
        self.assertEqual(self.feedback(self.key)[0]['next_action'], 'blocked')
        report = studio.generate_report([self.root], Path(self.temp.name)/'tool-failure-report')
        data = json.loads(Path(report['manifest']).read_text(encoding='utf-8'))
        self.assertEqual(data['cases'][0]['attempt_count'], 3)
        text = Path(report['report']).read_text(encoding='utf-8')
        self.assertIn('Tool failed again.', text)

    def test_explicit_one_attempt_stays_one_and_cannot_be_reset(self):
        root = Path(self.temp.name)/'limited'
        studio.init_project(root, self.source, 'test_character')
        first = studio.add_asset(root, self.image, 'happy', self.prompt)['asset']
        original = self.root
        self.root = root
        self.call('pool_start', root, first['id'], legacy.contract(), 1)
        self.review(first)
        self.assertEqual(self.call('pool_status', root, first['id'])['action'], 'exhausted')
        self.code('INVALID_CANDIDATE_REVIEW', self.call, 'pool_start', root, first['id'], legacy.contract(), 3)
        self.call('review_sheet', root, [first['id']], 'user')
        self.root = original

    def test_human_correction_redraw_preserves_chosen_parent_and_comment(self):
        self.review(self.first, True)
        plan = self.correction(self.key, 'Keep the requested change and fix the contact.')
        self.assertEqual(plan['budget'], 3)
        child = self.import_correction(plan)
        self.review(child)
        self.code('INTERNAL_REVIEW_INCOMPLETE', self.call, 'review_sheet', self.root, [child['id']], 'user')
        attempt = self.call('pool_reserve', self.root, child['id'])
        redrawn = self.call('pool_import', self.root, child['id'], attempt['token'], self.image, self.prompt,
                            [Path(p) for p in attempt['reference_paths']])['asset']
        self.assertEqual(redrawn['human_revision'], plan['revision'])
        self.assertEqual(redrawn['candidate_pool'], child['id'])
        self.assertEqual(redrawn['parent_asset_id'], child['id'])
        self.review(redrawn, True)
        previous = self.key
        self.key = child['id']
        self.compare(redrawn['id'])
        self.key = previous
        packet = self.call('review_sheet', self.root, [redrawn['id']], 'user')
        self.assertEqual(Path(packet['revision_parent']).read_bytes(), (self.root/self.first['path']).read_bytes())
        self.assertEqual(packet['revision_note'], plan['note'])
        self.assertEqual(studio.read_state(self.root)['human_revisions'][plan['revision']]['asset_id'], child['id'])
        self.call('human_feedback', self.root, {'packet':packet['packet'],'basis':'user','candidate':'A','decision':'accept','note':'Use the corrected version.'})
        report = studio.generate_report([self.root], Path(self.temp.name)/'redrawn-revision-report', stage='final')
        data = json.loads(Path(report['manifest']).read_text(encoding='utf-8'))
        self.assertEqual(data['cases'][0]['human_revision']['parent_asset'], self.first['id'])
        self.assertEqual(Path(data['cases'][0]['revision_parent_image']).read_bytes(), (self.root/self.first['path']).read_bytes())

    def test_report_keeps_internal_redraw_status_before_user_review(self):
        self.review(self.first)
        report = studio.generate_report([self.root], Path(self.temp.name)/'internal-redraw')
        data = json.loads(Path(report['manifest']).read_text(encoding='utf-8'))
        self.assertEqual(data['cases'][0]['status'], 'redraw')
        self.assertEqual(data['cases'][0]['max_rounds'], 3)
        self.assertEqual(report['images'], [])

    def test_recorded_uncertainty_redraws_and_is_carried_to_next_attempt(self):
        packet = self.call('review_sheet', self.root, [self.key], 'assistant')
        from test_quality import assessment
        data = assessment(scores=dict.fromkeys(studio.QUALITY_WEIGHTS_V12, 5))
        data.update(rubric_version='1.2', criteria=legacy.contract(), normal_display_height=420, blind_packet=packet['packet'])
        for check in data['criteria']:
            check.update(score=5, status='passed', observed='Synthetic passed criterion.')
        data['domain_review']['checks']['nonface_protection'].update(status='uncertain', evidence='Contact could not be confirmed.')
        data['uncertainties'] = ['Contact could not be confirmed.']
        comparison = self.root/'preview/uncertain.png'
        studio.make_preview(self.root, comparison, [self.key])
        studio.record_quality(self.root, self.key, data, [comparison])
        attempt = self.call('pool_reserve', self.root, self.key)
        self.assertIn('uncertainties', [x['id'] for x in attempt['blocking_findings']])
        self.code('INTERNAL_REVIEW_INCOMPLETE', self.call, 'review_sheet', self.root, [self.key], 'user')

    def test_report_preserves_actual_round_numbers_after_failed_call(self):
        self.review(self.first)
        second = self.call('pool_reserve', self.root, self.key)
        self.call('pool_import', self.root, self.key, second['token'], None, None, None, 'Second tool call failed.')
        third = self.next()
        self.review(third, True)
        self.compare(third['id'])
        report = studio.generate_report([self.root], Path(self.temp.name)/'round-gap')
        data = json.loads(Path(report['manifest']).read_text(encoding='utf-8'))
        self.assertEqual([r['round'] for r in data['cases'][0]['history']], [1, 3])
        self.assertEqual(data['cases'][0]['attempt_count'], 3)

    def test_exhausted_report_requests_human_review_in_both_languages(self):
        self.review(self.first)
        for _ in range(2):
            attempt = self.call('pool_reserve', self.root, self.key)
            self.call('pool_import', self.root, self.key, attempt['token'], None, None, None, 'Image call failed.')
        for lang, expected in [('zh-CN','进入人工评图'), ('en','present anonymous human review')]:
            report = studio.generate_report([self.root], Path(self.temp.name)/('exhausted-'+lang), language=lang)
            data = json.loads(Path(report['manifest']).read_text(encoding='utf-8'))
            self.assertEqual(data['cases'][0]['status'], 'exhausted')
            self.assertIn(expected, Path(report['report']).read_text(encoding='utf-8'))

    def test_multiple_revision_candidates_keep_before_and_original_comment(self):
        self.review(self.first, True)
        _, feedback = self.feedback(self.key, 'revise', 'Only fix the contact; keep the original framing.')
        plan = self.call('revision_prepare', self.root, feedback['packet'], legacy.contract(), 2)
        child = self.import_correction(plan)
        self.review(child)
        initial = self.key
        self.key = child['id']
        redrawn = self.next()
        self.review(redrawn, True)
        self.compare(redrawn['id'])
        page = self.call('review_sheet', self.root, [child['id'], redrawn['id']], 'user')
        self.assertEqual(page['revision_note'], plan['note'])
        self.assertEqual(Path(page['revision_parent']).read_bytes(), (self.root/self.first['path']).read_bytes())
        public = json.loads(Path(page['public_packet']).read_text(encoding='utf-8'))
        self.assertEqual(len(public['candidates']), 2)
        self.assertEqual(public['revision']['note'], plan['note'])
        self.key = initial


if __name__ == '__main__':
    unittest.main()
