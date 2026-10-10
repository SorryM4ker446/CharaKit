"""Single-garment replacement gates/compatibility with synthetic art, not visual validation."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

from test_outfits import outfits, fixture, builder, REPO
from test_quality import assessment


class ReplacementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.source = self.folder / '原图.png'; fixture(self.source)
        self.raw = self.folder / 'raw.png'; fixture(self.raw, '#445577')
        self.prompt = self.folder / 'submitted.txt'
        self.prompt.write_text('Synthetic replacement gate fixture, not real art evaluation.', encoding='utf-8')
        self.root = self.folder / 'outfits 项目'
        outfits.init_project(self.root, self.source, 'test_character')
        # Replacement must gate even an old project without a quality policy.
        state = outfits.read_state(self.root); state.pop('quality_policy')
        outfits.write_state(self.root, state)
        self.target = '长靴'; self.design = '黑色低帮皮鞋，保持原姿势'

    def code(self, expected, call, *args, **kwargs):
        with self.assertRaises(outfits.StudioError) as caught:
            call(*args, **kwargs)
        self.assertEqual(caught.exception.code, expected)

    def prepare(self, option='low_shoes', **kwargs):
        return outfits.prepare_outfit(self.root, option, self.target, None,
                                      '仅鞋及必要的新鞋口交界，保留袜子和装备',
                                      ['脸部、头发、姿势、袜子、武器'], [20, 80, 75, 140],
                                      edit_type='replace', replacement=self.design, **kwargs)

    def candidate(self, option='low_shoes', **kwargs):
        brief = self.prepare(option)
        return outfits.add_asset(self.root, self.raw, option, self.target,
                                 prompt_file=self.prompt, brief_file=Path(brief['brief_file']),
                                 edit_type='replace', replacement=self.design, **kwargs)['asset']

    def review(self, asset, failed=None, uncertain=None):
        data = assessment(domain='garment_replace'); data['rubric_version'] = '1.1'
        for key, value in ((failed, 'failed'), (uncertain, 'uncertain')):
            if key:
                data['domain_review']['checks'][key] = {'status': value, 'evidence': 'Synthetic garment interface defect.'}
        preview = self.root / 'preview' / (asset['id'] + '.png')
        outfits.make_preview(self.root, preview, [asset['id']], detail_box=[20,80,75,140])
        outfits.record_fidelity(self.root, asset['id'], 'passed', 'passed', 'Synthetic target/protection observation.')
        return outfits.record_quality(self.root, asset['id'], data, [preview])

    def test_prepare_is_read_only_and_first_import_migrates_with_exact_backup(self):
        old = outfits.add_asset(self.root, self.raw, 'coat_blue', 'coat', 'blue')['asset']
        outfits.review_asset(self.root, old['id'], 'accepted', 'Synthetic user feedback.')
        before = (self.root / 'run.json').read_bytes()
        pixels = {p: p.read_bytes() for p in self.root.rglob('*.png')}
        prepared = self.prepare()
        self.assertEqual((self.root / 'run.json').read_bytes(), before)
        self.assertEqual(prepared['edit_brief']['schema_version'], '1.1')
        asset = outfits.add_asset(self.root, self.raw, 'low_shoes', self.target,
                                 prompt_file=self.prompt, brief_file=Path(prepared['brief_file']),
                                 edit_type='replace', replacement=self.design)['asset']
        state = outfits.read_state(self.root)
        self.assertEqual(state['schema_version'], '1.3')
        self.assertEqual((self.root / 'run.schema-1.2.backup.json').read_bytes(), before)
        self.assertEqual(state['assets'][0], outfits.get_asset(json.loads(before), old['id']))
        self.assertEqual(state['selected'], {'coat_blue': old['id']})
        self.assertEqual((self.root / asset['path']).read_bytes(), self.raw.read_bytes())
        self.assertNotIn('color', asset)
        for path, data in pixels.items(): self.assertEqual(path.read_bytes(), data)

    def test_missing_brief_or_prompt_does_not_migrate_or_save_candidate(self):
        before = (self.root / 'run.json').read_bytes()
        self.code('EDIT_BRIEF_REQUIRED', outfits.add_asset, self.root, self.raw, 'low_shoes', self.target,
                  edit_type='replace', replacement=self.design, prompt_file=self.prompt)
        brief = self.prepare()
        self.code('REPLACEMENT_PROMPT_REQUIRED', outfits.add_asset, self.root, self.raw, 'low_shoes', self.target,
                  edit_type='replace', replacement=self.design, brief_file=Path(brief['brief_file']))
        self.assertEqual((self.root / 'run.json').read_bytes(), before)
        self.assertFalse((self.root / 'run.schema-1.2.backup.json').exists())
        self.assertFalse((self.root / 'candidates').exists())

    def test_wrong_or_changed_reference_and_mixed_parameters_block_import(self):
        brief = self.prepare(); before = (self.root / 'run.json').read_bytes()
        args = (self.root, self.raw, 'low_shoes', self.target)
        options = dict(edit_type='replace', replacement=self.design, prompt_file=self.prompt,
                       brief_file=Path(brief['brief_file']))
        self.code('INVALID_REPLACEMENT', outfits.add_asset, *args, color='black', **options)
        self.code('INVALID_EDIT_BRIEF', outfits.add_asset, self.root, self.raw, 'another', self.target, **options)
        fixture(Path(brief['detail_reference']), '#ee7744', size=(55,60))
        self.code('REFERENCE_CHANGED', outfits.add_asset, *args, **options)
        self.assertEqual((self.root / 'run.json').read_bytes(), before)

    def test_conflicting_migration_backup_is_preserved(self):
        backup = self.root / 'run.schema-1.2.backup.json'; backup.write_bytes(b'existing backup')
        before = (self.root / 'run.json').read_bytes()
        self.code('MIGRATION_BACKUP_EXISTS', self.candidate)
        self.assertEqual(backup.read_bytes(), b'existing backup')
        self.assertEqual((self.root / 'run.json').read_bytes(), before)

    def test_definition_and_mode_cannot_change_within_an_option(self):
        first = self.candidate()
        self.code('OUTFIT_DEFINITION_CHANGED', outfits.add_asset, self.root, self.raw, 'low_shoes', self.target, 'white', edit_type='recolor')
        self.code('OUTFIT_DEFINITION_CHANGED', outfits.add_asset, self.root, self.raw, 'low_shoes', self.target,
                  replacement='红色长靴', edit_type='replace', prompt_file=self.prompt)
        second = outfits.add_asset(self.root, self.raw, 'low_shoes', self.target,
                                  replacement=self.design, prompt_file=self.prompt)['asset']
        self.assertEqual(second['edit_brief'], first['edit_brief'])
        self.assertEqual(second['edit_type'], 'replace')
        self.assertEqual(outfits.fidelity_status(second), 'pending')
        self.assertEqual(outfits.quality_status(self.root, outfits.read_state(self.root), second), 'pending')

    def test_recolor_review_cannot_satisfy_replacement_and_fidelity_is_required(self):
        asset = self.candidate()
        self.code('FIDELITY_REVIEW_REQUIRED', outfits.review_asset, self.root, asset['id'], 'accepted')
        preview = self.root / 'preview' / 'review.png'; outfits.make_preview(self.root, preview, [asset['id']])
        self.code('INVALID_DOMAIN_REVIEW', outfits.record_quality, self.root, asset['id'], assessment(domain='garment_recolor'), [preview])
        outfits.record_quality(self.root, asset['id'], assessment(domain='garment_replace'), [preview])
        self.code('FIDELITY_REVIEW_REQUIRED', outfits.delivery_assets, self.root, [asset['id']])
        outfits.record_fidelity(self.root, asset['id'], 'passed', 'passed', 'Synthetic evidence.')
        self.assertEqual(len(outfits.delivery_assets(self.root, [asset['id']])['delivery']), 1)

    def test_each_replacement_check_can_veto_a_perfect_total(self):
        for index, key in enumerate(outfits.DOMAIN_CHECKS['garment_replace']):
            with self.subTest(key=key):
                asset = self.candidate(f'option_{index}')
                result = self.review(asset, failed=key)
                self.assertEqual(result['score']['total'], 100)
                self.assertEqual(result['quality_status'], 'failed')
                self.code('QUALITY_CHECK_FAILED', outfits.delivery_assets, self.root, [asset['id']])

    def test_three_failed_rounds_return_report_only_and_no_fourth_revision(self):
        asset = self.candidate(); self.review(asset, failed='non_target_protection')
        case = asset['id']; outfits.start_refinement(self.root, case)
        for _ in range(2):
            plan = outfits.refinement_status(self.root, case)
            revised = outfits.add_refinement(self.root, case, self.raw, self.prompt,
                                             [Path(p) for p in plan['references'].values()])['asset']
            self.assertEqual(revised['replacement'], self.design)
            self.assertNotIn('fidelity_review', revised)
            self.review(revised, failed='fit_interfaces')
        self.assertEqual(outfits.refinement_status(self.root, case)['action'], 'exhausted')
        self.code('REFINEMENT_NOT_READY', outfits.add_refinement, self.root, case, self.raw, self.prompt, [])
        report = outfits.generate_report([self.root], self.folder / 'failure')
        self.assertEqual(report['images'], []); self.assertIsNone(report['preview'])
        text = Path(report['report']).read_text(encoding='utf-8')
        self.assertIn('outfits · 替换', text); self.assertIn('合身与交界', text)
        self.assertEqual(list((self.folder / 'failure').rglob('*.png')), [])

    def test_successful_revision_retains_definition_and_exports_raw_bytes(self):
        first = self.candidate(); self.review(first, uncertain='coverage_anatomy')
        outfits.start_refinement(self.root, first['id'])
        plan = outfits.refinement_status(self.root, first['id'])
        final = outfits.add_refinement(self.root, first['id'], self.raw, self.prompt,
                                       [Path(p) for p in plan['references'].values()])['asset']
        self.review(final)
        self.assertEqual(outfits.refinement_status(self.root, first['id'])['action'], 'deliver')
        self.code('REFINEMENT_INTERMEDIATE', outfits.delivery_assets, self.root, [first['id']])
        report = outfits.generate_report([self.root], self.folder / 'success')
        self.assertEqual(Path(report['images'][0]).read_bytes(), self.raw.read_bytes())
        text = Path(report['report']).read_text(encoding='utf-8')
        self.assertIn(self.design, text)
        self.assertNotIn('不适用', text)
        self.assertEqual(json.loads(Path(report['manifest']).read_text(encoding='utf-8'))['cases'][0]['edit']['replacement'], self.design)
        self.code('NO_SELECTED_ASSETS', outfits.export_pack, self.root)
        outfits.review_asset(self.root, final['id'], 'accepted', 'Synthetic chosen design.')
        result = outfits.export_pack(self.root)
        self.assertEqual(result['manifest']['schema_version'], '1.3')
        sprite = result['manifest']['sprites'][0]
        self.assertEqual(sprite['replacement'], self.design); self.assertNotIn('color', sprite)
        with zipfile.ZipFile(result['export']) as archive:
            self.assertEqual(archive.read(sprite['path']), self.raw.read_bytes())

    def test_mixed_recolor_and_replacement_report_and_canvas_export_gate(self):
        recolor = outfits.add_asset(self.root, self.raw, 'coat_blue', 'coat', 'blue')['asset']
        preview = self.root / 'preview' / 'recolor.png'; outfits.make_preview(self.root, preview, [recolor['id']])
        outfits.record_quality(self.root, recolor['id'], assessment(domain='garment_recolor'), [preview])
        fixture(self.raw, '#445577', size=(80,120))
        replacement = self.candidate(); self.review(replacement)
        report = outfits.generate_report([self.root], self.folder / 'mixed')
        self.assertEqual(len(report['images']), 2)
        data = json.loads(Path(report['manifest']).read_text(encoding='utf-8'))
        self.assertEqual({c['kind'] for c in data['cases']}, {'garment_recolor','garment_replace'})
        self.code('TECHNICAL_CHECK_FAILED', outfits.review_asset, self.root, replacement['id'], 'accepted')

    def test_tampered_project_or_brief_operation_is_rejected(self):
        asset = self.candidate()
        state = outfits.read_state(self.root)
        state['assets'][0]['edit_type'] = 'recolor'
        (self.root / 'run.json').write_text(json.dumps(state), encoding='utf-8')
        self.code('INVALID_PROJECT', outfits.read_state, self.root)

    def test_packaged_cli_runs_replacement_outside_repository_with_unicode_paths(self):
        package = self.folder / 'plugin.zip'; builder.build(REPO, package)
        installed = self.folder / 'installed plugin'
        with zipfile.ZipFile(package) as archive:
            self.assertIsNone(archive.testzip())
            self.assertIn('skills/charakit-outfits/references/replacement-guide.md', archive.namelist())
            archive.extractall(installed)
        script = installed / 'skills/charakit-outfits/scripts/studio.py'
        def cli(*args):
            result = subprocess.run([sys.executable, str(script), *map(str,args)], cwd=self.folder,
                                    capture_output=True, encoding='utf-8')
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)
        common = ('--project', self.root, '--outfit', 'short_socks', '--edit-type', 'replace',
                  '--target', '长袜', '--replacement', '白色短袜，保留鞋子')
        brief = cli('prepare', *common, '--boundary', '袜子及必要交界', '--protect', '面部及鞋子', '--target-box', 20,80,75,140)
        asset = cli('add', *common, '--image', self.raw, '--prompt-file', self.prompt, '--brief-file', brief['brief_file'])['asset']
        data = assessment(domain='garment_replace'); record = self.folder / '评审.json'
        record.write_text(json.dumps(data), encoding='utf-8')
        preview = self.root / 'preview' / '比较.png'
        cli('preview', '--project', self.root, '--asset', asset['id'], '--output', preview)
        cli('fidelity', '--project', self.root, '--asset', asset['id'], '--target-check', 'passed', '--protection-check', 'passed', '--note', 'Synthetic gate test.')
        cli('quality', '--project', self.root, '--asset', asset['id'], '--assessment-file', record, '--comparison', preview)
        result = cli('report', '--project', self.root, '--output', self.folder / '交付 文件')
        self.assertEqual(len(result['images']), 1)
        self.assertTrue(Path(result['report']).is_file())


if __name__ == '__main__':
    unittest.main()
