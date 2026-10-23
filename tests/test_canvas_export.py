"""Nonblocking resolution warnings across selection, review, reports and ZIPs."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from test_studio import studio, fixture
from test_quality import assessment
from test_candidate_review import contract


class CanvasExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.source = self.folder / 'source.png'
        self.raw = self.folder / 'generated.png'
        fixture(self.source)
        fixture(self.raw, size=(32, 48))
        self.root = self.folder / 'project'
        studio.init_project(self.root, self.source, 'canvas_test')

    def call(self, name, *args, **kwargs):
        return studio.workflow_call(name, *args, **kwargs)

    def reviewed(self, expression='happy', mouth='default', pool=False):
        asset = studio.add_asset(self.root, self.raw, expression, mouth_state=mouth)['asset']
        data = assessment(scores=dict.fromkeys(studio.QUALITY_WEIGHTS, 4),
                          domain='expression' if mouth == 'default' else 'mouth_state')
        data['rubric_version'] = '1.1'
        if pool:
            self.call('pool_start', self.root, asset['id'], contract(), 1)
            sheet = self.call('review_sheet', self.root, [asset['id']], 'assistant')
            checks = [dict(item, observed='Synthetic workflow fixture.', status='passed', score=4)
                      for item in contract()]
            data.update(rubric_version='1.2', criteria=checks, normal_display_height=420,
                        blind_packet=sheet['packet'],
                        dimensions={key: {'score': 4, 'evidence': 'Synthetic workflow fixture.'}
                                    for key in studio.QUALITY_WEIGHTS_V12})
        preview = self.root / 'preview' / f'{asset["id"]}.png'
        studio.make_preview(self.root, preview, [asset['id']])
        studio.record_quality(self.root, asset['id'], data, [preview])
        return asset

    def accept_pool(self, asset):
        sheet = self.call('review_sheet', self.root, [asset['id']], 'user')
        packet = studio.read_state(self.root)['review_packets'][sheet['packet']]
        alias = next(k for k, v in packet['items'].items() if v['asset_id'] == asset['id'])
        feedback = dict(packet=sheet['packet'], basis='user', candidate=alias,
                        decision='accept', note='Explicit synthetic test acceptance.')
        return sheet, self.call('human_feedback', self.root, feedback)

    def test_mixed_dimensions_roundtrip_selected_versions_and_per_sprite_manifest(self):
        closed = self.reviewed(mouth='closed')
        studio.review_asset(self.root, closed['id'], 'accepted')
        fixture(self.raw, size=(32, 49))
        opened = self.reviewed(mouth='open')
        studio.review_asset(self.root, opened['id'], 'accepted')
        newer = self.reviewed(mouth='closed')
        studio.review_asset(self.root, newer['id'], 'accepted')
        chosen = studio.select_asset(self.root, closed['id'])
        self.assertIn('CANVAS_MISMATCH', chosen['warnings'])
        self.assertIn('64 × 96', chosen['warning_messages'][0])
        self.assertIn('32 × 48', chosen['warning_messages'][0])
        exported = studio.export_pack(self.root)
        manifest = exported['manifest']
        self.assertEqual(manifest['canvas_scope'], 'source')
        self.assertEqual(manifest['source_canvas'], {'width': 64, 'height': 96})
        self.assertEqual([s['canvas'] for s in manifest['sprites']],
                         [{'width': 32, 'height': 48}, {'width': 32, 'height': 49}])
        with zipfile.ZipFile(exported['export']) as archive:
            self.assertEqual(json.loads(archive.read('manifest.json')), manifest)
            for sprite in manifest['sprites']:
                asset = studio.get_asset(studio.read_state(self.root), sprite['asset_id'])
                self.assertEqual(archive.read(sprite['path']), (self.root / asset['path']).read_bytes())
                self.assertIn('CANVAS_MISMATCH', sprite['warnings'])
        self.assertNotIn(newer['id'], exported['asset_ids'])

    def test_html_and_report_warn_with_source_and_actual_sizes_without_blocking(self):
        asset = self.reviewed(pool=True)
        _, feedback = self.accept_pool(asset)
        self.assertEqual(feedback['next_action'], 'export')
        self.assertIn('CANVAS_MISMATCH', feedback['warnings'])
        for language, text in [('zh-CN', '允许导出'), ('en', 'export is allowed')]:
            sheet = self.call('review_sheet', self.root, [asset['id']], 'user', language=language)
            html = Path(sheet['page']).read_text(encoding='utf-8')
            self.assertIn('class="canvas-warning"', html)
            for expected in (text, '64 × 96', '32 × 48'):
                self.assertIn(expected, html)
            report = studio.generate_report([self.root], self.folder / language, language=language, stage='final')
            markdown = Path(report['report']).read_text(encoding='utf-8')
            for expected in (text, '64 × 96', '32 × 48'):
                self.assertIn(expected, markdown)
            self.assertNotIn(studio.localization.texts('report', language)['feedback_blocked'], markdown)
            self.assertEqual(len(report['images']), 1)

    def test_legacy_blocked_feedback_report_uses_current_delivery_without_rewriting_history(self):
        asset = self.reviewed(pool=True)
        sheet, _ = self.accept_pool(asset)
        state = studio.read_state(self.root)
        old = state['review_packets'][sheet['packet']]['feedback']['result']
        old.update(next_action='blocked', blockers={'technical': ['CANVAS_MISMATCH']})
        state['assets'][0]['art_review_status'] = 'unreviewed'
        state['assets'][0]['validation'].update(passed=False, errors=['CANVAS_MISMATCH'])
        state['selected'] = {}
        studio.write_state(self.root, state)
        before = (self.root / 'run.json').read_bytes()
        report = studio.generate_report([self.root], self.folder / 'legacy', stage='final')
        markdown = Path(report['report']).read_text(encoding='utf-8')
        data = json.loads(Path(report['manifest']).read_text(encoding='utf-8'))
        self.assertEqual(len(report['images']), 1)
        self.assertNotIn('暂不能交付', markdown)
        self.assertEqual(data['cases'][0]['human_result']['next_action'], 'blocked')
        self.assertEqual((self.root / 'run.json').read_bytes(), before)

    def test_canvas_warning_does_not_hide_missing_alpha_or_changed_bytes(self):
        asset = self.reviewed()
        studio.review_asset(self.root, asset['id'], 'accepted')
        fixture(self.root / asset['path'], size=(32, 48), transparent=False)
        with self.assertRaises(studio.StudioError) as caught:
            studio.export_pack(self.root, self.folder / 'blocked.zip')
        self.assertEqual(caught.exception.code, 'TECHNICAL_CHECK_FAILED')
        self.assertIn('NO_TRANSPARENCY', str(caught.exception))
        self.assertIn('ASSET_CHANGED', str(caught.exception))
        self.assertFalse((self.folder / 'blocked.zip').exists())

    def test_legacy_warning_normalization_is_idempotent_and_retains_real_errors(self):
        raw = {'passed': False, 'errors': ['CANVAS_MISMATCH', 'NO_TRANSPARENCY'],
               'warnings': ['CANVAS_MISMATCH'], 'image': None}
        before = copy.deepcopy(raw)
        result = studio.delivery_validation(raw)
        self.assertFalse(result['passed'])
        self.assertEqual(result['errors'], ['NO_TRANSPARENCY'])
        self.assertEqual(result['warnings'], ['CANVAS_MISMATCH'])
        self.assertEqual(studio.delivery_validation(result), result)
        self.assertEqual(raw, before)


if __name__ == '__main__':
    unittest.main()
