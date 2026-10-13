"""Arbitrary language packs, task inheritance, display provenance and text layout."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw, features

from test_studio import studio, SCRIPT, fixture
from test_quality import assessment
from test_localization import renderer

locale = studio.localization
task = locale.task
JA = Path(__file__).parent / 'fixtures/locales/ja.json'
HAS_JAPANESE_FONT = any(Path(path).is_file() for path in (
    'C:/Windows/Fonts/YuGothR.ttc', 'C:/Windows/Fonts/msgothic.ttc',
    '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc', '/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc'))


class TaskLanguageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.root = self.folder / 'project'
        self.source = self.folder / 'source.png'
        self.image = self.folder / 'image.png'
        fixture(self.source)
        fixture(self.image, color='#446688')
        studio.init_project(self.root, self.source, 'fixture')
        self.prompt = self.folder / 'prompt.txt'
        self.prompt.write_text('Historical English request.', encoding='utf-8')
        self.asset = studio.add_asset(self.root, self.image, 'happy', self.prompt)['asset']
        evidence = self.root / 'preview/evidence.png'
        studio.make_preview(self.root, evidence)
        review = assessment(scores=dict.fromkeys(studio.QUALITY_WEIGHTS, 4))
        review['rubric_version'] = '1.1'
        studio.record_quality(self.root, self.asset['id'], review, [evidence])
        self.original = (self.root / 'run.json').read_bytes()
        self.original_quality = copy.deepcopy(studio.read_state(self.root)['assets'][0]['quality_review'])
        self.translations = self.folder / 'translations.json'
        plan = task.content_plan(locale.locale_proxy(), [self.root], 'ja')
        translated = {'Synthetic fixture gate exercise only': '合成テスト画像の条件確認のみ',
                      'Synthetic test observation; not an artistic evaluation.': '合成テストの観察であり、作品品質の評価ではありません。',
                      'Synthetic requested component': '合成テストの編集対象',
                      'Synthetic gate fixture only': '合成画像による条件確認のみ'}
        for entry in plan['entries']:
            entry.update(translation=translated[entry['source']], source_language='en', reviewed=True)
        self.translations.write_text(json.dumps(plan, ensure_ascii=False), encoding='utf-8')

    def configure(self, **options):
        return task.configure(locale.locale_proxy(), self.root, 'ja', JA, self.translations,
                              basis='user_request', request='表情を変えて、元の細部を保持してください。', **options)

    def code(self, expected, call, *args, **kwargs):
        with self.assertRaises((studio.StudioError, ValueError)) as caught:
            call(*args, **kwargs)
        self.assertEqual(caught.exception.code, expected)

    def test_complete_japanese_pack_and_unknown_language_tags(self):
        pack = task.validate_pack(locale.locale_proxy(), task.read_json(JA), 'ja')
        self.assertEqual(sum(map(len, pack['catalogs'].values())), 316)
        for language in ('es-MX', 'ar', 'zh-TW', 'fr-CA', 'ja-JP'):
            data = task.template(locale.locale_proxy(), language)
            self.assertEqual(data['language'], language)
        self.assertEqual(locale.normalize_language('JA-jp'), 'ja-JP')
        # A regional tag must not silently substitute Simplified Chinese.
        self.code('MISSING_LOCALE_FILE', locale.resolve, language='zh-TW')

    def test_task_language_inheritance_and_explicit_override_do_not_mutate_reviews(self):
        result = self.configure()
        self.assertEqual(result['language'], 'ja')
        self.assertEqual((self.root / 'run.json').read_bytes(), self.original)
        self.assertEqual(studio.presentation_context([self.root]).language, 'ja')
        self.assertEqual(studio.presentation_context([self.root], 'en').language, 'en')
        self.assertEqual(studio.presentation_context([self.root]).language, 'ja')
        data = json.loads((self.root / 'presentation.json').read_text(encoding='utf-8'))
        self.assertEqual(data['source'], 'user_request')
        self.assertIsNotNone(data['request_sha256'])
        self.assertTrue((self.root / 'presentation-history' / (data['sha256'] + '.json')).is_file())

    def test_incomplete_pack_stale_pack_and_placeholder_changes_are_rejected(self):
        original = task.read_json(JA)
        for corrupt in ('missing', 'placeholder', 'stale', 'unreviewed'):
            data = copy.deepcopy(original)
            if corrupt == 'missing':
                data['catalogs']['png'].pop('reference')
            elif corrupt == 'placeholder':
                data['catalogs']['report']['summary'] = '{cases} {cases} {passed} {other} {images}'
            elif corrupt == 'stale':
                data['catalog_sha256'] = '0' * 64
            else:
                data['reviewed'] = False
            self.code('INVALID_LOCALE_FILE', task.validate_pack, locale.locale_proxy(), data, 'ja')
        self.assertEqual((self.root / 'run.json').read_bytes(), self.original)

    def test_explicit_preference_wins_and_short_input_retains_task_language(self):
        task.configure(locale.locale_proxy(), self.root, 'en', basis='explicit')
        result = task.configure(locale.locale_proxy(), self.root, 'ja', JA, self.translations, basis='user_request')
        self.assertEqual(result['language'], 'en')
        result = task.configure(locale.locale_proxy(), self.root, 'ja', JA, self.translations,
                                basis='user_request', clear_preference=True)
        self.assertEqual(result['language'], 'ja')
        result = task.configure(locale.locale_proxy(), self.root, 'en', basis='task_context', request='test.png')
        self.assertEqual(result['language'], 'ja')
        self.assertEqual((self.root / 'run.json').read_bytes(), self.original)

    def test_translations_bind_original_text_and_preserve_numbers(self):
        source = 'Score 80/100; face is unchanged.'
        data = {'schema_version': '1.0', 'language': 'ja', 'entries': [
            {'source': source, 'source_sha256': task.text_hash(source), 'source_language': 'en',
             'translation': '点数は80/100で、顔は変更されていません。', 'reviewed': True}]}
        self.assertTrue(task.validate_translations(locale.locale_proxy(), data, 'ja'))
        invalid = copy.deepcopy(data)
        invalid['entries'][0]['translation'] = '点数は85/100で、顔は変更されていません。'
        self.code('TRANSLATION_FACTS_CHANGED', task.validate_translations, locale.locale_proxy(), invalid, 'ja')
        invalid = copy.deepcopy(data)
        invalid['entries'][0]['source'] = 'The face changed.'
        self.code('INVALID_DISPLAY_TRANSLATIONS', task.validate_translations, locale.locale_proxy(), invalid, 'ja')

    def test_missing_historical_translation_blocks_before_report_output(self):
        task.configure(locale.locale_proxy(), self.root, 'ja', JA)
        output = self.folder / 'missing'
        self.code('MISSING_DISPLAY_TRANSLATION', studio.generate_report, [self.root], output)
        self.code('MISSING_DISPLAY_TRANSLATION', studio.workflow_call, 'review_sheet', self.root, [self.asset['id']])
        self.assertFalse(output.exists())
        self.assertFalse((self.root / 'reviews').exists())
        self.assertEqual((self.root / 'run.json').read_bytes(), self.original)

    def test_new_japanese_prose_is_registered_without_translation_or_score_changes(self):
        self.configure()
        value = {'request': '片手を腰に当ててください。', 'evidence': '顔と衣服は変更されていません。', 'score': 80}
        task.register_content(locale.locale_proxy(), self.root, value)
        context = studio.presentation_context([self.root])
        self.assertEqual(context.display_tree(value), value)
        self.assertEqual(context.entries[task.text_hash(value['request'])]['source_language'], 'ja')
        self.assertEqual((self.root / 'run.json').read_bytes(), self.original)

    def test_reference_notes_translate_but_omission_codes_and_paths_remain_stable(self):
        self.configure()
        original = {'edit_references': [{'id': 'design_ref', 'path': 'references/design.png',
                    'scope': ['expression'], 'notes': 'Use only the expression design.'}],
                    'omissions': [{'asset_id': 'A', 'reason': 'unavailable_file'}], 'score': 80}
        sources = list(task.human_strings(original))
        self.assertEqual(sources, ['Use only the expression design.'])
        context = studio.presentation_context([self.root])
        entry = {'source': sources[0], 'source_sha256': task.text_hash(sources[0]),
                 'source_language': 'en', 'translation': '表情のデザインのみ参照してください。', 'reviewed': True}
        context.entries.update(task.validate_translations(locale.locale_proxy(),
                               {'schema_version': '1.0', 'language': 'ja', 'entries': [entry]}, 'ja'))
        shown = context.display_tree(original)
        self.assertEqual(shown['edit_references'][0]['notes'], entry['translation'])
        self.assertEqual(shown['edit_references'][0]['path'], original['edit_references'][0]['path'])
        self.assertEqual(shown['omissions'], original['omissions'])
        self.assertEqual(shown['score'], 80)
        self.assertEqual(original['edit_references'][0]['notes'], entry['source'])
        finding = {'id': 'inspection:full_image', 'status': 'uncertain',
                   'observed': 'Required inspection is incomplete.'}
        shown = context.display_tree(finding)
        self.assertEqual(shown['status'], 'uncertain')
        self.assertEqual(shown['observed'], '確認の実施状況 · 未確認')
        self.assertEqual(finding['observed'], 'Required inspection is incomplete.')

    def test_japanese_html_preserves_originals_refresh_and_feedback_codes(self):
        self.configure()
        result = studio.workflow_call('review_sheet', self.root, [self.asset['id']])
        html = Path(result['page']).read_text(encoding='utf-8')
        public = task.read_json(result['public_packet'])
        self.assertIn('lang="ja" dir="ltr"', html)
        self.assertIn('この版を採用', html)
        self.assertIn('合成テスト画像の条件確認のみ', html)
        self.assertNotIn('Synthetic test observation;', html)
        self.assertEqual(public['request'], 'Synthetic fixture gate exercise only')
        self.assertEqual(public['display_content']['request'], '合成テスト画像の条件確認のみ')
        self.assertEqual(studio.read_state(self.root)['assets'][0]['quality_review'], self.original_quality)
        task.configure(locale.locale_proxy(), self.root, 'en')
        refreshed = studio.workflow_call('refresh_review_sheet', self.root, result['packet'])
        self.assertIn('lang="ja"', Path(refreshed['page']).read_text(encoding='utf-8'))
        self.assertIn('value="accept"', html)

    @unittest.skipUnless(HAS_JAPANESE_FONT, 'Japanese PNG verification requires an installed CJK font')
    def test_japanese_png_report_and_full_images_keep_original_bytes(self):
        self.configure()
        raw = (self.root / self.asset['path']).read_bytes()
        lines = []
        original = ImageDraw.ImageDraw.text
        def record(draw, xy, text, *args, **kwargs):
            lines.append(text)
            return original(draw, xy, text, *args, **kwargs)
        with patch.object(ImageDraw.ImageDraw, 'text', record):
            preview = studio.make_preview(self.root, self.folder / 'ja.png', labels={'happy': 'User Name'})
            report = studio.generate_report([self.root], self.folder / 'ja-report')
        drawn = '\n'.join(lines)
        self.assertEqual(preview['language'], 'ja')
        for text in ('元画像', 'User Name', '内部品質：通過', '80/100'):
            self.assertIn(text, drawn)
        markdown = Path(report['report']).read_text(encoding='utf-8')
        self.assertIn('結果の一覧', markdown)
        self.assertIn('合成画像による条件確認のみ', markdown)
        data = task.read_json(report['manifest'])
        self.assertEqual(data['cases'][0]['history'][0]['request'], 'Synthetic fixture gate exercise only')
        self.assertEqual(data['display_content']['cases'][0]['history'][0]['request'], '合成テスト画像の条件確認のみ')
        self.assertEqual(data['cases'][0]['history'][0]['recorded_score'], 80)
        self.assertTrue((self.folder / 'ja-report/translations.json').is_file())
        self.assertEqual(Path(report['images'][0]).read_bytes(), raw)
        self.assertEqual((self.root / 'run.json').read_bytes(), self.original)

    def test_missing_glyphs_and_rtl_engine_fail_explicitly(self):
        context = studio.presentation_context(language='en')
        context.strict = True
        painter = studio.text_layout.TextPainter(context, studio.font)
        painter.paths = []
        self.code('FONT_GLYPHS_MISSING', painter.font, '\U0010ffff', 16)
        context.direction = 'rtl'
        with patch.object(features, 'check_feature', return_value=False):
            self.code('TEXT_LAYOUT_UNAVAILABLE', studio.text_layout.TextPainter, context, studio.font)
        context = studio.presentation_context(language='en')
        html = renderer.render_sheet('key', ['A'], 'Original', [], 'user', 'ar', renderer.PREVIEW_EN)
        self.assertIn('dir="rtl"', html)

    def test_long_captions_wrap_and_expand_without_truncating(self):
        context = studio.presentation_context(language='en')
        painter = studio.text_layout.TextPainter(context, studio.font)
        text = 'A long custom name that must remain completely readable ' * 7
        lines = painter.wrap(text, 340, 17)
        self.assertGreater(len(lines), 2)
        self.assertEqual(' '.join(' '.join(lines).split()), ' '.join(text.split()))
        self.assertTrue(all(painter.width(line, 17) <= 340 for line in lines))
        result = studio.make_preview(self.root, self.folder / 'long.png', language='en', labels={'happy': text})
        self.assertGreater(result['size'][1], 544)

    def test_multi_project_languages_require_explicit_choice_and_snapshots_detect_changes(self):
        self.configure()
        other = self.folder / 'other'
        studio.init_project(other, self.source, 'other')
        task.configure(locale.locale_proxy(), other, 'en')
        self.code('AMBIGUOUS_TASK_LANGUAGE', studio.presentation_context, [self.root, other])
        self.assertEqual(studio.presentation_context([self.root, other], 'en').language, 'en')
        data = task.read_json(self.root / 'presentation.json')
        data['language'] = 'en'
        self.code('STALE_PRESENTATION', task.from_snapshot, locale.locale_proxy(), data)

    def test_cli_template_configure_and_inherited_html_workflow(self):
        template = self.folder / 'template.json'
        def run(*args):
            result = subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, encoding='utf-8')
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)
        run('language-template', '--language', 'ja', '--output', template)
        self.assertEqual(task.read_json(template)['language'], 'ja')
        run('language-set', '--project', self.root, '--language', 'ja', '--locale-file', JA, '--translations-file', self.translations)
        status = run('language-status', '--project', self.root)
        self.assertEqual(status['language'], 'ja')
        page = run('review-sheet', '--project', self.root, '--asset', self.asset['id'])
        self.assertIn('lang="ja"', Path(page['page']).read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
