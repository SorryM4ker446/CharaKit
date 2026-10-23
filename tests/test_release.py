"""Release archive installability, licensing and extraction boundary regressions."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import zipfile

REPO = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, REPO / f'tools/{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


builder = load('build_plugin')
verifier = load('verify_release')


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def test_marketplace_archive_resolves_plugin_and_includes_matching_license_and_release_notes(self):
        archive = self.folder / 'release.zip'
        result = builder.build(REPO, archive, marketplace=True)
        destination = self.folder / 'installed'
        manifest, files = verifier.unpack(archive, destination)
        catalog = json.loads((destination / '.agents/plugins/marketplace.json').read_text(encoding='utf-8'))
        plugin = destination / catalog['plugins'][0]['source']['path']
        self.assertEqual(json.loads((plugin / 'plugin.json').read_text(encoding='utf-8')), manifest)
        self.assertEqual(result['version'], manifest['version'])
        self.assertEqual((destination / 'LICENSE').read_bytes(), (plugin / 'LICENSE').read_bytes())
        self.assertIn('MIT License', (plugin / 'LICENSE').read_text(encoding='utf-8'))
        for readme in (destination / 'README.md', destination / 'README.zh-CN.md', plugin / 'README.md', plugin / 'RELEASE_NOTES.md'):
            self.assertIn(manifest['version'], readme.read_text(encoding='utf-8'))
        self.assertEqual({name for name in files if name.endswith('/SKILL.md')}, {
            f'skills/charakit-{module}/SKILL.md' for module in ('expressions', 'outfits', 'poses')})

    def test_plugin_only_archive_keeps_license_and_has_no_marketplace_wrapper(self):
        archive = self.folder / 'plugin.zip'
        builder.build(REPO, archive)
        with zipfile.ZipFile(archive) as pack:
            self.assertEqual(pack.read('LICENSE'), (REPO / 'LICENSE').read_bytes())
            self.assertIn('RELEASE_NOTES.md', pack.namelist())
            self.assertNotIn('.agents/plugins/marketplace.json', pack.namelist())

    def test_mismatched_license_cannot_produce_a_release(self):
        root = self.folder / 'repo'
        plugin = root / 'plugins/charakit'
        shutil.copytree(REPO / 'plugins/charakit', plugin, ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copyfile(REPO / 'LICENSE', root / 'LICENSE')
        (plugin / 'LICENSE').write_text('MIT License\nChanged license text', encoding='utf-8')
        archive = self.folder / 'must-not-exist.zip'
        with self.assertRaisesRegex(ValueError, 'licenses must match'):
            builder.build(root, archive)
        self.assertFalse(archive.exists())

    def test_unsafe_archive_is_rejected_before_extraction(self):
        archive = self.folder / 'unsafe.zip'
        with zipfile.ZipFile(archive, 'w') as pack:
            pack.writestr('../outside.txt', b'unexpected')
        destination = self.folder / 'installed'
        with self.assertRaisesRegex(ValueError, 'unsafe or duplicate'):
            verifier.unpack(archive, destination)
        self.assertFalse(destination.exists())
        self.assertFalse((self.folder / 'outside.txt').exists())


if __name__ == '__main__':
    unittest.main()
