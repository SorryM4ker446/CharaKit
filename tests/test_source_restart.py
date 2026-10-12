"""Source restart inputs, evidence and compatibility; no generated-art quality claims."""
import copy
import json
from pathlib import Path
import unittest

import test_candidate_review as legacy
from test_studio import studio
from test_quality import assessment
import test_poses as pose_fixtures

poses = pose_fixtures.poses


class SourceRestartTests(unittest.TestCase):
    call = legacy.CandidateReviewTests.call
    code = legacy.CandidateReviewTests.code
    next = legacy.CandidateReviewTests.next
    compare = legacy.CandidateReviewTests.compare
    feedback = legacy.CandidateReviewTests.feedback
    correction = legacy.CandidateReviewTests.correction
    import_correction = legacy.CandidateReviewTests.import_correction

    def setUp(self):
        legacy.CandidateReviewTests.setUp(self)
        state = studio.read_state(self.root)
        state['candidate_pools'][self.key]['version'] = '1.2'
        studio.write_state(self.root, state)

    def review(self, asset, passed=False, dim='identity', score=3, domain_only=False, target_domain=False):
        sheet = self.call('review_sheet', self.root, [asset['id']], 'assistant')
        state = studio.read_state(self.root)
        current = studio.get_asset(state, asset['id'])
        data = assessment(scores=dict.fromkeys(studio.QUALITY_WEIGHTS_V12, 5))
        data.update(rubric_version='1.2', criteria=copy.deepcopy(state['candidate_pools'][current['candidate_pool']]['contract']),
                    normal_display_height=420, blind_packet=sheet['packet'])
        for check in data['criteria']:
            check.update(score=5, status='passed', observed='Synthetic inspected observation.')
        if not passed:
            if not domain_only:
                check = next(x for x in data['criteria'] if x['dimension'] == dim)
                check.update(score=score, status='failed')
                data['dimensions'][dim]['score'] = score
            domain = 'emotion' if target_domain else 'face_design' if dim == 'identity' else 'nonface_protection'
            data['domain_review']['checks'][domain].update(status='failed', evidence='Synthetic observed failure.')
        preview = self.root/'preview'/f'{asset["id"]}.png'
        studio.make_preview(self.root, preview, [asset['id']])
        return studio.record_quality(self.root, asset['id'], data, [preview])

    def two_failures(self, first=None, second=None, preferred=None):
        self.review(self.first, **(first or {}))
        other = self.next()
        self.review(other, **(second or {}))
        self.compare(preferred or other['id'], False)
        return other

    def test_stalled_protection_restarts_from_source_with_review_lineage(self):
        other = self.two_failures(first=dict(dim='protection'), second=dict(dim='protection'))
        before = (self.root/'run.json').read_bytes()
        status = self.call('pool_status', self.root, self.key)
        self.assertEqual(status['next_strategy'], 'source_restart')
        self.assertEqual(before, (self.root/'run.json').read_bytes())
        plan = self.call('pool_reserve', self.root, self.key)
        self.assertEqual(plan['number'], 3)
        self.assertEqual(plan['strategy'], 'source_restart')
        self.assertEqual(plan['parent'], other['id'])
        self.assertEqual(plan['reference_paths'], [str((self.root/'source.png').resolve())])
        self.assertEqual(plan['restart_evidence']['asset_ids'], [self.key, other['id']])
        self.assertIn('protection', [x['id'] for x in plan['restart_evidence']['checks']])
        child = self.call('pool_import', self.root, self.key, plan['token'], self.image, self.prompt,
                          [Path(p) for p in plan['reference_paths']])['asset']
        self.assertEqual(child['parent_asset_id'], other['id'])
        self.assertEqual(child['generation_inputs']['restart_evidence'], plan['restart_evidence'])
        self.assertEqual((self.root/child['path']).read_bytes(), self.image.read_bytes())
        self.review(child, True)
        self.compare(child['id'])
        page = self.call('review_sheet', self.root, [child['id']], 'user')
        self.assertEqual(page['review_summary']['displayed'], 3)
        self.assertEqual(studio.read_state(self.root)['selected'], {})
        for lang, label in [('zh-CN', '从原图重新生成'), ('en', 'Restart from source')]:
            report = studio.generate_report([self.root], Path(self.temp.name)/('report-'+lang), language=lang)
            self.assertIn(label, Path(report['report']).read_text(encoding='utf-8'))
            record = json.loads(Path(report['manifest']).read_text(encoding='utf-8'))['cases'][0]
            self.assertEqual(record['history'][-1]['generation_inputs']['references'], plan['references'])

    def test_improving_identity_continues_candidate(self):
        self.two_failures(first=dict(score=2), second=dict(score=3))
        plan = self.call('pool_reserve', self.root, self.key)
        self.assertEqual(plan['strategy'], 'review_redraw')
        self.assertEqual(len(plan['reference_paths']), 2)

    def test_different_failed_properties_do_not_establish_stall(self):
        self.two_failures(first=dict(dim='identity'), second=dict(dim='protection'))
        self.assertEqual(self.call('pool_reserve', self.root, self.key)['strategy'], 'review_redraw')

    def test_failed_target_or_target_domain_prevents_restart(self):
        for domain_only in (False, True):
            with self.subTest(domain_only=domain_only):
                if domain_only:
                    self.setUp()
                self.two_failures(first=dict(dim='protection'),
                                  second=dict(dim='target' if not domain_only else 'protection', target_domain=True))
                self.assertEqual(self.call('pool_reserve', self.root, self.key)['strategy'], 'review_redraw')

    def test_repeated_domain_only_protection_failure_restarts(self):
        self.two_failures(first=dict(dim='protection', domain_only=True), second=dict(dim='protection', domain_only=True))
        plan = self.call('pool_reserve', self.root, self.key)
        self.assertEqual(plan['strategy'], 'source_restart')
        self.assertEqual(plan['restart_evidence']['checks'][0]['kind'], 'domain')

    def test_old_pool_retains_two_image_strategy(self):
        state = studio.read_state(self.root)
        state['candidate_pools'][self.key]['version'] = '1.1'
        studio.write_state(self.root, state)
        self.two_failures()
        plan = self.call('pool_reserve', self.root, self.key)
        self.assertEqual(plan['strategy'], 'review_redraw')
        self.assertEqual(len(plan['reference_paths']), 2)
        self.assertNotIn('restart_evidence', plan)

    def test_preferred_earlier_candidate_cannot_bypass_restart(self):
        self.two_failures(preferred=self.key)
        plan = self.call('pool_reserve', self.root, self.key)
        self.assertEqual(plan['strategy'], 'source_restart')
        self.assertEqual(plan['parent'], self.key)
        self.assertEqual(len(plan['reference_paths']), 1)

    def test_restart_failure_spends_last_attempt(self):
        self.two_failures()
        plan = self.call('pool_reserve', self.root, self.key)
        status = self.call('pool_import', self.root, self.key, plan['token'], None, None, None, 'Tool failed on source restart.')
        self.assertEqual((status['action'], status['used']), ('exhausted', 3))
        self.code('POOL_NOT_READY', self.call, 'pool_reserve', self.root, self.key)
        page = self.call('review_sheet', self.root, [self.key], 'user')
        self.assertEqual(page['review_summary']['displayed'], 2)
        self.assertEqual(len(page['review_summary']['failed_calls']), 1)

    def test_tampered_reference_or_evidence_rejected(self):
        self.two_failures()
        plan = self.call('pool_reserve', self.root, self.key)
        original = studio.read_state(self.root)
        for mutation in ('reference', 'evidence'):
            with self.subTest(mutation=mutation):
                state = copy.deepcopy(original)
                attempt = state['candidate_pools'][self.key]['attempts'][-1]
                if mutation == 'reference':
                    attempt['references'].append(dict(path=self.first['path'], sha256=self.first['sha256'], role='edit_target'))
                else:
                    attempt['restart_evidence']['checks'].clear()
                studio.write_state(self.root, state)
                self.code('INVALID_CANDIDATE_REVIEW', studio.read_state, self.root)
        studio.write_state(self.root, original)
        child = self.call('pool_import', self.root, self.key, plan['token'], self.image, self.prompt,
                          [Path(p) for p in plan['reference_paths']])['asset']
        state = studio.read_state(self.root)
        studio.get_asset(state, child['id'])['generation_inputs']['strategy'] = 'review_redraw'
        studio.write_state(self.root, state)
        self.code('INVALID_CANDIDATE_REVIEW', studio.read_state, self.root)

    def test_human_revision_keeps_user_chosen_baseline(self):
        self.review(self.first, True)
        revision = self.correction(self.key, 'Keep this version and correct the contact.')
        child = self.import_correction(revision)
        self.review(child)
        self.key = child['id']
        second = self.next()
        self.review(second)
        self.compare(second['id'], False)
        plan = self.call('pool_reserve', self.root, self.key)
        self.assertEqual(plan['strategy'], 'review_redraw')
        self.assertEqual(plan['reference_paths'], [str((self.root/second['path']).resolve()),
                                                  str((self.root/'source.png').resolve())])
        self.assertEqual(plan['revision_policy']['baseline_asset'], self.first['id'])


class PoseSourceRestartTests(unittest.TestCase):
    setUp = pose_fixtures.PoseTests.setUp
    call = pose_fixtures.PoseTests.call
    code = pose_fixtures.PoseTests.code
    prepare = pose_fixtures.PoseTests.prepare
    candidate = pose_fixtures.PoseTests.candidate
    reference = pose_fixtures.PoseTests.reference
    evidence = pose_fixtures.PoseTests.evidence
    compare = pose_fixtures.PoseTests.compare

    def review(self, asset, target='passed', protection='failed'):
        data, preview = self.evidence(asset)
        poses.record_fidelity(self.root, asset['id'], target, protection, 'Synthetic fidelity observation.')
        return poses.record_quality(self.root, asset['id'], data, [preview])

    def two(self, target='passed', budget=3):
        first = self.candidate(side='left', budget=budget, reference_file=self.reference())
        self.review(first)
        plan = self.call('pool_reserve', self.root, first['id'])
        second = self.call('pool_import', self.root, first['id'], plan['token'], self.raw, self.prompt,
                           [Path(p) for p in plan['reference_paths']])['asset']
        self.review(second, target=target)
        self.compare(first['id'], second['id'])
        return first, second

    def test_pose_restart_preserves_action_side_and_all_scoped_references(self):
        first, second = self.two()
        self.assertEqual(poses.read_state(self.root)['candidate_pools'][first['id']]['version'], '1.2')
        plan = self.call('pool_reserve', self.root, first['id'])
        self.assertEqual(plan['strategy'], 'source_restart')
        self.assertEqual([r['role'] for r in plan['references']], ['immutable_source', 'edit_reference'])
        self.assertEqual(plan['references'][1], first['edit_references'][0])
        self.assertNotIn(str((self.root/second['path']).resolve()), plan['reference_paths'])
        before = (self.root/'run.json').read_bytes()
        self.code('INVALID_CANDIDATE_REVIEW', self.call, 'pool_import', self.root, first['id'], plan['token'],
                  self.raw, self.prompt, [Path(p) for p in plan['reference_paths']] + [self.root/second['path']])
        self.assertEqual(before, (self.root/'run.json').read_bytes())
        child = self.call('pool_import', self.root, first['id'], plan['token'], self.raw, self.prompt,
                          [Path(p) for p in plan['reference_paths']])['asset']
        for key in ('pose', 'side', 'anchors', 'target', 'edit_brief', 'edit_references'):
            self.assertEqual(child[key], first[key])
        self.assertEqual(child['parent_asset_id'], second['id'])
        self.assertEqual(child['generation_inputs']['references'], plan['references'])

    def test_target_fidelity_failure_blocks_restart(self):
        first, _ = self.two(target='failed')
        self.assertEqual(self.call('pool_reserve', self.root, first['id'])['strategy'], 'review_redraw')

    def test_two_attempt_budget_exhausts_without_restart(self):
        first, _ = self.two(budget=2)
        self.assertEqual(self.call('pool_status', self.root, first['id'])['action'], 'exhausted')
        self.code('POOL_NOT_READY', self.call, 'pool_reserve', self.root, first['id'])


if __name__ == '__main__':
    unittest.main()
