"""Presentation locale coverage and compatibility; no generated-art quality claims."""
import importlib.util
import json
from pathlib import Path
from string import Formatter
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import ImageDraw

from test_studio import studio, SCRIPT, fixture
from test_quality import assessment
from test_outfits import builder, REPO

spec = importlib.util.spec_from_file_location('localized_review', SCRIPT.parents[3] / 'lib/candidate_review.py')
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)
locale = studio.localization


class LocalizationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.source = self.folder / 'source.png'
        self.image = self.folder / 'candidate.png'
        fixture(self.source)
        fixture(self.image, color='#223355')
        self.prompt = self.folder / 'prompt.txt'
        self.prompt.write_text('保留原始角色。', encoding='utf-8')
        self.root = self.folder / 'project'
        studio.init_project(self.root, self.source, 'test_character')
        self.asset = studio.add_asset(self.root, self.image, 'happy', self.prompt, 'open')['asset']

    def capture(self, call, *args, **kwargs):
        lines = []
        original = ImageDraw.ImageDraw.text

        def record(draw, xy, text, *rest, **options):
            lines.append(text)
            return original(draw, xy, text, *rest, **options)

        with patch.object(ImageDraw.ImageDraw, 'text', record):
            result = call(*args, **kwargs)
        return result, '\n'.join(lines)

    def test_bilingual_catalogs_have_identical_keys_and_format_fields(self):
        zh, en = locale.CATALOGS['zh-CN'], locale.CATALOGS['en']
        self.assertEqual(set(zh), set(en))
        formatter = Formatter()
        for section in zh:
            self.assertEqual(set(zh[section]), set(en[section]), section)
            for key in zh[section]:
                with self.subTest(section=section, key=key):
                    for value in (zh[section][key], en[section][key]):
                        self.assertIsInstance(value, str)
                        self.assertTrue(value.strip())
                    fields = lambda text: {field for _, field, _, _ in formatter.parse(text) if field is not None}
                    self.assertEqual(fields(zh[section][key]), fields(en[section][key]))
        self.assertEqual(set(zh['names']), set(studio.EXPRESSIONS) | {'source', 'mouth_default', 'mouth_open', 'mouth_closed'})
        for language in ('zh-CN', 'en'):
            png = locale.texts('png', language)
            report = locale.texts('report', language)
            for checks in studio.DOMAIN_CHECKS.values():
                self.assertTrue(set(checks) <= set(report))
            self.assertTrue(set(studio.QUALITY_INSPECTIONS) <= set(report))
            self.assertTrue({'reference', 'unreviewed', 'accepted', 'rejected', 'technical_passed', 'technical_failed'} <= set(png))
            for status in ('passed', 'failed', 'uncertain', 'pending', 'unrecorded', 'stale'):
                self.assertIn('quality_' + status, png)
                self.assertIn('fidelity_' + status, png)
            for code in ('OUTPUT_NOT_PNG', 'CANVAS_MISMATCH', 'EMPTY_IMAGE', 'NO_TRANSPARENCY', 'ASSET_CHANGED',
                         'FILE_NOT_FOUND', 'INVALID_IMAGE', 'IMAGE_TOO_LARGE', 'EDIT_REFERENCE_CHANGED'):
                self.assertIn(code, png)
                self.assertIn(code, locale.texts('report', language))
        detached = locale.texts('html', 'en')
        detached['原图'] = 'Custom'
        self.assertEqual(locale.texts('html', 'en')['原图'], 'Source')

    def test_all_outputs_use_same_locale_with_partial_custom_names(self):
        evidence = self.root / 'preview/evidence.png'
        studio.make_preview(self.root, evidence)
        review = assessment(scores=dict.fromkeys(studio.QUALITY_WEIGHTS, 4), domain='mouth_state')
        review['rubric_version'] = '1.1'
        studio.record_quality(self.root, self.asset['id'], review, [evidence])
        before = (self.root / 'run.json').read_bytes()
        image_bytes = (self.root / self.asset['path']).read_bytes()
        for language, canonical in (('zh-Hans', 'zh-CN'), ('en-US', 'en')):
            with self.subTest(language=language):
                labels = {'happy': '自定义名', 'source': '我的原图'}
                result, png_text = self.capture(studio.make_preview, self.root, self.folder / (language + '.png'),
                                                language=language, labels=labels)
                self.assertEqual(result['language'], canonical)
                self.assertIn('自定义名 / ' + locale.texts('names', language)['mouth_open'], png_text)
                self.assertIn('我的原图', png_text)
                for key in ('unreviewed', 'technical_passed', 'quality_passed'):
                    self.assertIn(locale.texts('png', language)[key], png_text)
                report_result, report_png = self.capture(studio.generate_report, [self.root], self.folder / ('report-' + language),
                                                        language=language, labels=labels)
                data = json.loads(Path(report_result['manifest']).read_text(encoding='utf-8'))
                markdown = Path(report_result['report']).read_text(encoding='utf-8')
                self.assertEqual(data['language'], canonical)
                self.assertIn(locale.texts('report', language)['overview'], markdown)
                self.assertIn(locale.texts('report', language)['passed'], report_png)
                self.assertIn('自定义名', report_png)
                self.assertIn('我的原图', report_png)
                html = renderer.render_sheet('test', ['A'], '保留原始意见。', [], 'user', language)
                self.assertIn(locale.texts('html', language)['采用此版本'], html)
                self.assertIn('保留原始意见。', html)
                self.assertEqual(renderer.preview_text(language), locale.texts('html', language))
        self.assertEqual((self.root / 'run.json').read_bytes(), before)
        self.assertEqual((self.root / self.asset['path']).read_bytes(), image_bytes)

    def test_default_and_failure_text_are_localized_without_overrides(self):
        fixture(self.image, size=(32, 48), transparent=False)
        studio.add_asset(self.root, self.image, 'sad', self.prompt)
        result, drawn = self.capture(studio.make_preview, self.root, self.folder / 'default.png')
        self.assertEqual(result['language'], 'zh-CN')
        for text in ('原图', '开心 / 张嘴', '文件检查：未通过', '尺寸与原图不同', '缺少透明背景', '内部质量：待评审'):
            self.assertIn(text, drawn)
        _, drawn = self.capture(studio.make_preview, self.root, self.folder / 'en.png', language='en')
        for text in ('Source', 'Happy / Mouth open', 'File validation: Failed', 'Canvas differs from source', 'No transparency'):
            self.assertIn(text, drawn)

    def test_unsupported_or_invalid_language_creates_no_output(self):
        before = (self.root / 'run.json').read_bytes()
        for language in ('ja', 'en"', ''):
            output = self.folder / 'invalid'
            with self.assertRaises(studio.StudioError) as caught:
                studio.make_preview(self.root, output, language=language)
            self.assertEqual(caught.exception.code, 'INVALID_PREVIEW_LANGUAGE')
            with self.assertRaises(studio.StudioError) as caught:
                studio.generate_report([self.root], output, language=language)
            self.assertEqual(caught.exception.code, 'INVALID_REPORT_OPTIONS')
            with self.assertRaises(ValueError):
                renderer.preview_text(language)
            self.assertFalse(output.exists())
        self.assertEqual((self.root / 'run.json').read_bytes(), before)

    def test_full_slot_and_legacy_status_overrides_remain_supported(self):
        _, drawn = self.capture(studio.make_preview, self.root, self.folder / 'custom.png', language='en',
                                labels={'happy_mouth_open': 'Custom full slot', 'technical_passed': 'Legacy status'})
        self.assertIn('Custom full slot v001', drawn)
        self.assertIn('Legacy status', drawn)
        self.assertIn('Unreviewed', drawn)

    def test_packaged_entrypoints_accept_language_and_share_catalog(self):
        archive = self.folder / 'plugin.zip'
        builder.build(REPO, archive)
        import zipfile
        with zipfile.ZipFile(archive) as package:
            self.assertIn('lib/localization.py', package.namelist())
            package.extractall(self.folder / 'installed plugin')
        for module in ('expressions', 'outfits', 'poses'):
            entrypoint = self.folder / f'installed plugin/skills/charakit-{module}/scripts/studio.py'
            output = self.folder / (module + '.png')
            root = self.folder / (module + '-project')
            studio.init_project(root, self.source, 'test_character', module=module)
            result = subprocess.run([sys.executable, str(entrypoint), 'preview', '--project', str(root),
                                     '--output', str(output), '--language', 'en-US'], capture_output=True, encoding='utf-8')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['language'], 'en')
            self.assertTrue(output.exists())


if __name__ == '__main__':
    unittest.main()
