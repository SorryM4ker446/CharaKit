"""Independent export auditing and immutable visual inspection snapshots."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from test_studio import studio, fixture
from test_quality import assessment

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('qa_tools', REPO / 'tools/qa.py')
qa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qa)


class QAToolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.source = self.folder / 'source.png'
        fixture(self.source)
        self.root = self.folder / 'project'
        studio.init_project(self.root, self.source, 'qa')

    def candidate(self, accept=False):
        raw = self.folder / 'raw.png'
        fixture(raw, size=(32, 48))
        asset = studio.add_asset(self.root, raw, 'happy')['asset']
        if accept:
            preview = self.folder / 'project/preview' / (asset['id'] + '.png')
            studio.make_preview(self.root, preview, [asset['id']])
            studio.record_quality(self.root, asset['id'], assessment(), [preview])
            studio.review_asset(self.root, asset['id'], 'accepted', '[QA FIXTURE]')
        return asset

    def rewrite(self, pack, change):
        with zipfile.ZipFile(pack) as archive:
            files = {name: archive.read(name) for name in archive.namelist()}
        manifest = json.loads(files['manifest.json'])
        change(manifest, files)
        files['manifest.json'] = json.dumps(manifest).encode()
        path = self.folder / ('modified-' + str(len(list(self.folder.glob('modified-*.zip')))) + '.zip')
        with zipfile.ZipFile(path, 'w') as archive:
            for name, raw in files.items():
                archive.writestr(name, raw)
        return path

    def test_valid_export_and_historical_selection_are_audited_without_mutation(self):
        first = self.candidate(True)
        pack = studio.export_pack(self.root)['export']
        before = (self.root / 'run.json').read_bytes()
        result = qa.audit_export(self.root, pack, core=studio)
        self.assertTrue(result['passed'], result)
        self.assertEqual(result['visual_quality'], 'not_assessed')
        self.assertEqual(before, (self.root / 'run.json').read_bytes())
        self.candidate(True)
        self.assertFalse(qa.audit_export(self.root, pack, core=studio)['passed'])
        self.assertTrue(qa.audit_export(self.root, pack, [first['id']], core=studio)['passed'])

    def test_independent_audit_catches_wrong_dimensions_notice_version_and_extra_sprite(self):
        self.candidate(True)
        pack = studio.export_pack(self.root)['export']
        changes = [lambda m, f: m['sprites'][0].update(canvas={'width': 64, 'height': 96}),
                   lambda m, f: m['sprites'][0].update(warnings=[]),
                   lambda m, f: m['sprites'][0].update(source_version=99),
                   lambda m, f: m['sprites'][0].update(expression='sad'),
                   lambda m, f: f.update({'sprites/extra.png': b'not a selected sprite'}),
                   lambda m, f: f.update({m['sprites'][0]['path']: self.source.read_bytes()}),
                   lambda m, f: m['sprites'].append(dict(m['sprites'][0]))]
        for change in changes:
            with self.subTest(change=change):
                self.assertFalse(qa.audit_export(self.root, self.rewrite(pack, change), core=studio)['passed'])

    def test_audit_rechecks_stale_quality_evidence_and_returns_failure_for_bad_zip(self):
        asset = self.candidate(True)
        pack = studio.export_pack(self.root)['export']
        (self.root / 'preview' / (asset['id'] + '.png')).write_bytes(b'changed evidence')
        self.assertFalse(qa.audit_export(self.root, pack, core=studio)['passed'])
        broken = self.folder / 'broken.zip'
        broken.write_bytes(b'not zip')
        self.assertFalse(qa.audit_export(self.root, broken, core=studio)['passed'])

    def test_visible_resolution_notice_rejects_blank_false_wrong_size_and_wrong_type(self):
        self.candidate(True)
        pack = studio.export_pack(self.root)['export']
        for messages in ([], [''], ['   '], ['All dimensions match; no warning.'], [None],
                         'warning', ['Original 32 × 48; actual 64 × 96']):
            with self.subTest(messages=messages):
                changed = self.rewrite(pack, lambda m, f: m['sprites'][0].update(warning_messages=messages))
                result = qa.audit_export(self.root, changed, core=studio)
                self.assertFalse(result['passed'])
                self.assertTrue(any(c['name'].endswith(':resolution_notice') and not c['passed'] for c in result['checks']))

    def test_resolution_notice_follows_project_locale(self):
        self.candidate(True)
        for language in ('zh-CN', 'en'):
            with self.subTest(language=language):
                studio.localization.task.configure(studio.localization.locale_proxy(), self.root, language,
                                                  request='QA language fixture')
                pack = studio.export_pack(self.root)['export']
                self.assertTrue(qa.audit_export(self.root, pack, core=studio)['passed'])

    def test_inspection_copies_raw_bytes_retains_failed_versions_and_leaves_reviews_blank(self):
        first = self.candidate()
        second = self.candidate()
        studio.review_asset(self.root, second['id'], 'rejected', '[QA FIXTURE]')
        before = {str(p): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        output = self.folder / 'inspection'
        qa.inspect_projects([self.root], output, True, core=studio)
        manifest = json.loads((output / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual([x['review_status'] for x in manifest['assets']], ['source', 'unreviewed', 'rejected'])
        self.assertEqual((output / manifest['assets'][1]['src']).read_bytes(), (self.root / first['path']).read_bytes())
        observations = json.loads((output / 'observations.template.json').read_text(encoding='utf-8'))
        self.assertTrue(all(x['status'] == 'not_reviewed' for a in observations['assets'] for x in a['checks'].values()))
        self.assertFalse(observations['engine_tested'])
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
        with self.assertRaises(FileExistsError):
            qa.inspect_projects([self.root], output, True, core=studio)

    def test_inspection_rejects_modified_bytes_and_nested_output_before_writing(self):
        asset = self.candidate()
        with self.assertRaises(ValueError):
            qa.inspect_projects([self.root], self.root / 'qa', True, core=studio)
        (self.root / asset['path']).write_bytes(self.source.read_bytes())
        output = self.folder / 'inspection'
        with self.assertRaisesRegex(ValueError, 'Candidate changed'):
            qa.inspect_projects([self.root], output, True, core=studio)
        self.assertFalse(output.exists())

    def test_cli_bad_export_has_nonzero_exit_status(self):
        broken = self.folder / 'broken.zip'
        broken.write_bytes(b'not zip')
        result = subprocess.run([sys.executable, str(REPO / 'tools/qa.py'), 'audit-export',
                                 '--project', str(self.root), '--archive', str(broken)], capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(json.loads(result.stdout)['passed'])

    def test_browser_fixture_never_manufactures_accepted_or_passing_art(self):
        output = self.folder / 'browser'
        pages = qa.make_browser_fixture(output, core=studio)
        state = studio.read_state(output / 'project')
        self.assertEqual(state['selected'], {})
        self.assertTrue(all(a['art_review_status'] == 'unreviewed' and
                            a['quality_review']['result']['status'] == 'failed' for a in state['assets']))
        self.assertTrue(all(Path(path).is_file() for path in pages.values()))

    def test_runner_preserves_failed_stage_results_and_logs(self):
        output = self.folder / 'run'
        # Test failure followed by build failure: preserve both and expose failure to CI.
        with patch.object(qa.subprocess, 'run', side_effect=[subprocess.CompletedProcess([], 1), subprocess.CompletedProcess([], 1)]):
            result = qa.run(output)
        self.assertFalse(result['passed'])
        self.assertEqual(len(result['steps']), 2)
        self.assertTrue((output / 'unit-tests.log').is_file())
        self.assertEqual(json.loads((output / 'summary.json').read_text()), result)

    def test_plugin_build_rejects_standalone_html_before_creating_archive(self):
        from tools.build_plugin import build
        root = self.folder / 'package-source'
        plugin = root / 'plugins/charakit'
        shutil.copytree(REPO / 'plugins/charakit', plugin, ignore=shutil.ignore_patterns('__pycache__'))
        archive = self.folder / 'plugin.zip'
        for name in ('view.html', 'VIEW.HTM'):
            with self.subTest(name=name):
                template = plugin / 'lib' / name
                template.write_text('<!doctype html><title>Unexpected template</title>', encoding='utf-8')
                try:
                    with self.assertRaisesRegex(ValueError, 'standalone HTML'):
                        build(root, archive)
                    self.assertFalse(archive.exists())
                finally:
                    template.unlink()


if __name__ == '__main__':
    unittest.main()
