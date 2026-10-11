"""Candidate visibility and human decisions; synthetic assessments are workflow fixtures."""
import copy
import json
from pathlib import Path
import unittest

from test_studio import studio
from test_candidate_review import contract
import test_review_redraw as redraw


class UserReviewPresentationTests(unittest.TestCase):
    setUp = redraw.ReviewRedrawTests.setUp
    call = redraw.ReviewRedrawTests.call
    code = redraw.ReviewRedrawTests.code
    review = redraw.ReviewRedrawTests.review
    next = redraw.ReviewRedrawTests.next
    compare = redraw.ReviewRedrawTests.compare
    feedback = redraw.ReviewRedrawTests.feedback
    correction = redraw.ReviewRedrawTests.correction
    import_correction = redraw.ReviewRedrawTests.import_correction

    def three_failures(self):
        self.review(self.first)
        second = self.next(); self.review(second); self.compare(self.key)
        third = self.next(); self.review(third); self.compare(self.key)
        return [self.first, second, third]

    def mapping(self, page):
        return {v['asset_id']: k for k,v in studio.read_state(self.root)['review_packets'][page['packet']]['items'].items()}

    def test_first_pass_displays_exactly_one_and_recommendation_is_separate(self):
        self.review(self.first, True)
        page = self.call('review_sheet', self.root, [self.key], 'user')
        self.assertEqual(page['review_summary']['generated'], 1)
        self.assertEqual(set(page['candidates']), {'A'})
        self.assertEqual(page['review_summary']['recommendation']['candidate'], 'A')
        self.assertNotIn('review_summary', self.call('review_sheet', self.root, [self.key], 'assistant'))

    def test_second_pass_includes_failed_first_and_recommends_recorded_pass(self):
        self.review(self.first)
        second = self.next(); self.review(second, True); self.compare(second['id'])
        page = self.call('review_sheet', self.root, [second['id']], 'user')
        aliases = self.mapping(page)
        self.assertEqual(set(aliases), {self.key, second['id']})
        summary = page['review_summary']
        self.assertEqual(summary['candidates'][aliases[self.key]]['status'], 'failed')
        self.assertEqual(summary['candidates'][aliases[second['id']]]['status'], 'passed')
        self.assertEqual(summary['recommendation']['candidate'], aliases[second['id']])
        self.assertEqual(summary['displayed'], 2)

    def test_exhaustion_displays_all_three_even_when_only_latest_is_requested(self):
        assets = self.three_failures()
        before = copy.deepcopy(studio.read_state(self.root)['candidate_pools'])
        page = self.call('review_sheet', self.root, [assets[-1]['id']], 'user')
        self.assertEqual(set(self.mapping(page)), {a['id'] for a in assets})
        self.assertEqual(page['review_summary']['displayed'], 3)
        self.assertEqual(page['review_summary']['recommendation']['candidate'], self.mapping(page)[self.key])
        self.assertEqual(set(x['status'] for x in page['review_summary']['candidates'].values()), {'failed'})
        self.assertEqual(before, studio.read_state(self.root)['candidate_pools'])
        self.assertEqual(studio.read_state(self.root)['selected'], {})

    def test_failed_candidate_can_request_revision_with_exact_parent(self):
        assets = self.three_failures()
        page = self.call('review_sheet', self.root, [assets[-1]['id']], 'user')
        parent = assets[1]
        result = self.call('human_feedback', self.root, dict(packet=page['packet'], basis='user', candidate=self.mapping(page)[parent['id']], decision='revise', note='只修正人物位置，保留成功的目标修改。'))
        self.assertEqual(result['next_action'], 'revision_request')
        plan = self.call('revision_prepare', self.root, page['packet'], contract())
        self.assertEqual(plan['parent_asset'], parent['id'])
        self.assertEqual(plan['budget'], 3)
        child = self.import_correction(plan); self.review(child)
        original = self.key; self.key = child['id']
        redrawn = self.next(); self.review(redrawn, True); self.compare(redrawn['id'])
        revised_page = self.call('review_sheet', self.root, [redrawn['id']], 'user')
        self.assertEqual(set(self.mapping(revised_page)), {child['id'], redrawn['id']})
        self.assertEqual(Path(revised_page['revision_parent']).read_bytes(), (self.root/parent['path']).read_bytes())
        self.assertNotIn(original, self.mapping(revised_page))

    def test_positive_opinion_on_failed_candidate_does_not_export_recommended_one(self):
        self.review(self.first)
        second = self.next(); self.review(second, True); self.compare(second['id'])
        self.feedback(second['id'])
        page = self.call('review_sheet', self.root, [self.key], 'user')
        result = self.call('human_feedback', self.root, dict(packet=page['packet'], basis='user', candidate=self.mapping(page)[self.key], decision='accept', note='我更喜欢这个版本。'))
        self.assertEqual(result['next_action'], 'blocked')
        self.assertEqual(studio.read_state(self.root)['selected'], {})
        with self.assertRaises(studio.StudioError): studio.export_pack(self.root)

    def test_reject_all_stops_every_displayed_candidate(self):
        assets = self.three_failures()
        page = self.call('review_sheet', self.root, [assets[-1]['id']], 'user')
        result = self.call('human_feedback', self.root, dict(packet=page['packet'], basis='user', candidate=None, decision='reject', note='都需要再调整。'))
        self.assertEqual(set(result['asset_ids']), {a['id'] for a in assets})
        self.assertTrue(all(a['art_review_status']=='rejected' for a in studio.read_state(self.root)['assets']))

    def test_only_explicit_user_subset_can_omit_readable_candidates(self):
        assets = self.three_failures()
        page = self.call('review_sheet', self.root, [assets[-1]['id']], 'user', selection_note='用户明确要求只看最后一个版本。')
        self.assertEqual(set(self.mapping(page)), {assets[-1]['id']})
        self.assertEqual(len(page['review_summary']['omissions']), 2)
        self.assertTrue(all(x['reason']=='user_requested_subset' for x in page['review_summary']['omissions']))
        self.assertIsNone(page['review_summary']['recommendation'])
        self.assertIn('用户明确要求', Path(page['page']).read_text(encoding='utf-8'))

    def test_missing_file_is_explicitly_reported_after_exhaustion(self):
        assets = self.three_failures()
        (self.root/assets[0]['path']).unlink()
        page = self.call('review_sheet', self.root, [assets[-1]['id']], 'user')
        self.assertEqual(len(page['candidates']), 2)
        self.assertEqual(page['review_summary']['generated'], 3)
        self.assertEqual(page['review_summary']['omissions'][0]['reason'], 'unavailable_file')
        self.assertIn('未展示原因', Path(page['page']).read_text(encoding='utf-8'))
        self.assertIsNone(page['review_summary']['recommendation'])

    def test_tool_failure_does_not_create_a_phantom_candidate(self):
        self.review(self.first)
        attempt = self.call('pool_reserve', self.root, self.key)
        self.call('pool_import', self.root, self.key, attempt['token'], None, None, None, '合成调用失败')
        third = self.next(); self.review(third); self.compare(self.key)
        page = self.call('review_sheet', self.root, [third['id']], 'user')
        self.assertEqual(page['review_summary']['generated'], 2)
        self.assertEqual(page['review_summary']['displayed'], 2)
        self.assertEqual(page['review_summary']['failed_calls'], [dict(number=2, failure='合成调用失败')])

    def test_recommendation_never_changes_choice_and_summary_is_integrity_bound(self):
        assets = self.three_failures()
        page = self.call('review_sheet', self.root, [assets[-1]['id']], 'user', language='en')
        html = Path(page['page']).read_text(encoding='utf-8')
        self.assertIn('Recommendation and internal checks', html)
        self.assertNotIn('推荐版本', html.split('<script>')[0])
        self.assertNotIn('selected>', html)
        refreshed = self.call('refresh_review_sheet', self.root, page['packet'])
        self.assertEqual(refreshed['review_summary'], page['review_summary'])
        public_path = Path(page['public_packet'])
        data = json.loads(public_path.read_text(encoding='utf-8')); data['review_summary']['displayed'] = 1
        public_path.write_text(json.dumps(data), encoding='utf-8')
        self.code('STALE_REVIEW_PACKET', self.call, 'human_feedback', self.root, dict(packet=page['packet'], basis='user', candidate='A', decision='revise', note='修正位置'))

    def test_cannot_mix_original_and_revision_batches_in_one_user_page(self):
        self.review(self.first, True)
        plan = self.correction(self.key); child = self.import_correction(plan); self.review(child, True)
        before = (self.root/'run.json').read_bytes()
        self.code('INVALID_CANDIDATE_REVIEW', self.call, 'review_sheet', self.root, [self.key, child['id']], 'user')
        self.assertEqual(before, (self.root/'run.json').read_bytes())


if __name__ == '__main__': unittest.main()
