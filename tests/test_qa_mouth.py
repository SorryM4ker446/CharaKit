"""Synthetic record validation; no claim of actual artistic passage."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from tools.qa_mouth import CHECKS, VIEWS, audit_mouth, digest, make_template


class MouthQATests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.snapshot = self.root / 'inspection'
        self.snapshot.mkdir()
        assets = []
        for name, mouth, status in [('source', 'closed', 'source'), ('open', 'open', 'unreviewed'), ('closed', 'closed', 'unreviewed')]:
            path = self.snapshot / (name+'.png')
            path.write_bytes(('QA FIXTURE '+name).encode())
            assets.append(dict(id='0:'+name, src=path.name, source_id='0:source', expression='neutral',
                               mouth_state=mouth, review_status=status, sha256=digest(path)))
        self.manifest = dict(projects=[dict(source_sha256=assets[0]['sha256'])], assets=assets)
        (self.snapshot/'manifest.json').write_text(json.dumps(self.manifest))
        self.record = make_template(self.manifest)
        self.record['basis'] = 'assistant_visual_observation'
        evidence = self.root/'comparison.png'
        evidence.write_bytes(b'QA FIXTURE only')
        for pair in self.record['pairs']:
            pair['views'] = dict.fromkeys(VIEWS, True)
            pair['evidence'] = [dict(path=evidence.name, sha256=digest(evidence))]
            pair['checks'] = {k:dict(status='passed', evidence='QA FIXTURE observation') for k in CHECKS}
        self.n = 0

    def run_record(self, record=None):
        self.n += 1
        path = self.root/'record.json'
        path.write_text(json.dumps(record or self.record))
        return audit_mouth(self.snapshot, path, self.root/str(self.n))

    def test_complete_record_passes_without_mutating_inputs(self):
        before = (self.snapshot/'manifest.json').read_bytes()
        self.assertTrue(self.run_record()['passed'])
        self.assertEqual(before, (self.snapshot/'manifest.json').read_bytes())

    def test_blank_template_is_not_acceptance(self):
        self.assertFalse(self.run_record(make_template(self.manifest))['passed'])

    def test_failure_uncertainty_unseen_views_and_empty_evidence_veto(self):
        for status in ('failed', 'uncertain', 'not_reviewed'):
            record = copy.deepcopy(self.record)
            record['pairs'][0]['checks']['waist_skirt']['status'] = status
            self.assertFalse(self.run_record(record)['passed'])
        for edit in ('view', 'evidence', 'text'):
            record = copy.deepcopy(self.record)
            if edit == 'view': record['pairs'][0]['views']['420_scale'] = False
            if edit == 'evidence': record['pairs'][0]['evidence'] = []
            if edit == 'text': record['pairs'][0]['checks']['feet_position']['evidence'] = ' '
            self.assertFalse(self.run_record(record)['passed'])

    def test_omitted_pair_or_changed_pair_binding_cannot_pass(self):
        for edit in ('omit', 'sha', 'same_mouth'):
            record = copy.deepcopy(self.record)
            if edit == 'omit': record['pairs'] = record['pairs'][:1]
            if edit == 'sha': record['pairs'][0]['sha256'][0] = 'wrong'
            if edit == 'same_mouth': record['pairs'][0]['first'] = record['pairs'][0]['second']
            self.assertFalse(self.run_record(record)['passed'])

    def test_stale_comparison_and_image_are_rejected(self):
        (self.root/'comparison.png').write_bytes(b'changed')
        self.assertFalse(self.run_record()['passed'])
        (self.snapshot/'open.png').write_bytes(b'changed')
        self.assertFalse(self.run_record()['passed'])

    def test_no_open_pair_is_not_vacuous_pass(self):
        record = copy.deepcopy(self.record)
        record['pairs'] = []
        self.assertFalse(self.run_record(record)['passed'])

    def test_source_baseline_requires_explicit_visual_confirmation(self):
        manifest = copy.deepcopy(self.manifest)
        manifest['assets'][0].update(expression=None, mouth_state='unknown')
        manifest['assets'] = manifest['assets'][:2]
        (self.snapshot/'manifest.json').write_text(json.dumps(manifest))
        record = copy.deepcopy(self.record)
        record['pairs'] = record['pairs'][:1]
        self.assertFalse(self.run_record(record)['passed'])
        record['pairs'][0]['source_baseline'] = dict(status='passed', evidence='QA FIXTURE: visually confirmed neutral closed mouth')
        self.assertTrue(self.run_record(record)['passed'])
