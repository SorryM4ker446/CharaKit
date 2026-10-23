"""Verify a marketplace release ZIP with fresh helper dependencies and optional Codex installation."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import sys
import zipfile


def unpack(archive, destination):
    """Check the distributable before extracting anything."""
    with zipfile.ZipFile(archive) as pack:
        entries = pack.infolist()
        names = [item.filename for item in entries]
        if not names or len(names) != len(set(names)) or any(
                PurePosixPath(name).is_absolute() or '..' in PurePosixPath(name).parts
                or '\\' in name or ':' in name for name in names):
            raise ValueError('Release archive contains unsafe or duplicate paths.')
        if any(stat.S_ISLNK(item.external_attr >> 16) or item.file_size > 50 * 1024 * 1024
               for item in entries) or sum(item.file_size for item in entries) > 100 * 1024 * 1024:
            raise ValueError('Release archive contains links or oversized files.')
        if any(Path(name).suffix.lower() in ('.html', '.htm', '.pyc', '.pyo') for name in names):
            raise ValueError('Release archive contains standalone HTML or bytecode.')
        catalog = json.loads(pack.read('.agents/plugins/marketplace.json'))
        if len(catalog['plugins']) != 1 or catalog['plugins'][0]['name'] != 'charakit' or catalog['plugins'][0]['source'] != {
                'source': 'local', 'path': './plugins/charakit'}:
            raise ValueError('Release catalog does not resolve the bundled CharaKit plugin.')
        manifest = json.loads(pack.read('plugins/charakit/plugin.json'))
        if manifest['name'] != 'charakit' or not manifest.get('version'):
            raise ValueError('Release plugin identity is missing.')
        license_bytes = pack.read('LICENSE')
        if license_bytes != pack.read('plugins/charakit/LICENSE') or not license_bytes.startswith(b'MIT License\n'):
            raise ValueError('Repository and plugin MIT licenses must match.')
        if manifest['version'] not in pack.read('plugins/charakit/RELEASE_NOTES.md').decode('utf-8'):
            raise ValueError('Release notes do not describe the packaged version.')
        if pack.testzip() is not None:
            raise ValueError('Release archive is corrupt.')
        expected = {name.removeprefix('plugins/charakit/'): hashlib.sha256(pack.read(name)).hexdigest()
                    for name in names if name.startswith('plugins/charakit/') and not name.endswith('/')}
        pack.extractall(destination)
    return manifest, expected


def smoke(plugin, output):
    """Run only the installed helper, with no artwork acceptance or model calls."""
    from PIL import Image, ImageDraw
    import PIL
    import fontTools

    plugin, output = Path(plugin).resolve(), Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    if sys.prefix == sys.base_prefix or not all(Path(module.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
                                               for module in (PIL, fontTools)):
        raise ValueError('Helper dependencies must come from the fresh virtual environment.')
    if importlib.util.find_spec('playwright') is not None:
        raise ValueError('Developer browser dependencies leaked into the runtime environment.')
    source = output / 'synthetic-source.png'
    candidate = output / 'synthetic-candidate.png'
    for path, size in ((source, (64, 96)), (candidate, (32, 48))):
        image = Image.new('RGBA', size)
        draw = ImageDraw.Draw(image)
        draw.rectangle((size[0] // 4, 4, size[0] * 3 // 4, size[1] - 4), fill='#667799')
        image.save(path)

    checks = []

    def cli(module, name, *args, expected_success=True):
        script = plugin / f'skills/charakit-{module}/scripts/studio.py'
        result = subprocess.run([sys.executable, '-I', str(script), *map(str, args)], cwd=output,
                                capture_output=True, encoding='utf-8', errors='replace', timeout=120)
        (output / (module + '-' + name + '.log')).write_text(result.stdout + result.stderr, encoding='utf-8')
        if (result.returncode == 0) != expected_success:
            raise RuntimeError(f'{module}/{name}: unexpected exit {result.returncode}: {result.stdout} {result.stderr}')
        checks.append(module + ':' + name)
        return json.loads(result.stdout if expected_success else result.stderr) if name != 'help' else None

    for module in ('expressions', 'outfits', 'poses'):
        project = output / module
        cli(module, 'help', '--help')
        cli(module, 'init', 'init', '--project', project, '--source', source, '--character', 'release')
        before = (project / 'run.json').read_bytes()
        cli(module, 'status', 'status', '--project', project)
        if before != (project / 'run.json').read_bytes():
            raise ValueError('Read-only installed status changed project state.')
        state = json.loads(before)
        if state.get('module', 'expressions') != module or state['selected']:
            raise ValueError('Installed module initialized the wrong state or selected artwork.')

    project = output / 'expressions'
    asset = cli('expressions', 'add', 'add', '--project', project, '--image', candidate, '--expression', 'happy')['asset']
    if not asset['validation']['passed'] or 'CANVAS_MISMATCH' not in asset['validation']['warnings']:
        raise ValueError('Installed helper did not preserve warning-only resolution behavior.')
    if (project / asset['path']).read_bytes() != candidate.read_bytes() or asset['art_review_status'] != 'unreviewed':
        raise ValueError('Installed helper changed raw bytes or manufactured acceptance.')
    cli('expressions', 'preview', 'preview', '--project', project, '--asset', asset['id'],
        '--output', output / 'preview.png', '--language', 'en')
    blocked = cli('expressions', 'export-unreviewed', 'export', '--project', project, '--asset', asset['id'],
                  '--output', output / 'must-not-export.zip', expected_success=False)
    if blocked.get('error', {}).get('code') != 'ART_REVIEW_REQUIRED' or (output / 'must-not-export.zip').exists():
        raise ValueError('Installed helper did not block unreviewed artwork cleanly.')
    result = dict(passed=True, checks=checks, synthetic_only=True, visual_quality='not_assessed',
                  python=sys.version, environment=sys.prefix, pillow=PIL.__version__, fonttools=fontTools.__version__,
                  developer_dependencies_present=False)
    (output / 'results.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result


def verify(archive, output, use_codex=False):
    archive, output = Path(archive).resolve(), Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    env = {key: value for key, value in os.environ.items() if key not in ('PYTHONPATH', 'PYTHONHOME')}
    env['PYTHONNOUSERSITE'] = '1'
    result = dict(passed=False, archive=str(archive), host_installation='not_run', steps=[], visual_quality='not_assessed')

    def command(name, args, command_env=env):
        print(name, flush=True)
        completed = subprocess.run(list(map(str, args)), cwd=output, env=command_env,
                                   capture_output=True, encoding='utf-8', errors='replace', timeout=600)
        (output / (name + '.log')).write_text(completed.stdout + completed.stderr, encoding='utf-8')
        result['steps'].append(dict(name=name, passed=completed.returncode == 0, command=list(map(str, args))))
        if completed.returncode:
            raise RuntimeError(f'{name} failed; see {output / (name + ".log")}')
        return completed

    try:
        result['archive_sha256'] = hashlib.sha256(archive.read_bytes()).hexdigest()
        marketplace = output / 'marketplace'
        manifest, expected = unpack(archive, marketplace)
        result.update(version=manifest['version'], plugin_files=len(expected))
        plugin = marketplace / 'plugins/charakit'
        if use_codex:
            executable = shutil.which('codex')
            if not executable:
                raise FileNotFoundError('Codex CLI is required when --codex is requested.')
            isolated_config = output / 'codex-home'
            isolated_config.mkdir()
            codex_env = {**env, 'CODEX_HOME': str(isolated_config)}
            command('codex-version', [executable, '--version'], codex_env)
            command('codex-marketplace-add', [executable, 'plugin', 'marketplace', 'add', marketplace, '--json'], codex_env)
            command('codex-plugin-add', [executable, 'plugin', 'add', 'charakit@charakit', '--json'], codex_env)
            matches = [path.parent for path in (isolated_config / 'plugins/cache').rglob('plugin.json')
                       if json.loads(path.read_text(encoding='utf-8')).get('name') == manifest['name']
                       and json.loads(path.read_text(encoding='utf-8')).get('version') == manifest['version']]
            if len(matches) != 1:
                raise ValueError('Expected exactly one fresh Codex cache matching the release version.')
            plugin = matches[0]
            result['host_installation'] = 'codex_cli'
        actual = {path.relative_to(plugin).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in plugin.rglob('*') if path.is_file()}
        if actual != expected:
            raise ValueError('Installed plugin files differ from the final archive.')
        result['installed_plugin'] = str(plugin)
        result['installed_bytes_match_archive'] = True
        environment = output / 'venv'
        command('create-environment', [sys.executable, '-m', 'venv', environment])
        python = environment / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        command('install-runtime-dependencies', [python, '-I', '-m', 'pip', '--isolated', 'install', '--no-user',
                                                 '-r', plugin / 'requirements.txt'])
        command('installed-smoke', [python, '-I', Path(__file__).resolve(), '--smoke-plugin', plugin,
                                    '--output', output / 'smoke'])
        result['smoke'] = json.loads((output / 'smoke/results.json').read_text(encoding='utf-8'))
        result['passed'] = True
    except Exception as exc:
        result['error'] = str(exc)
    (output / 'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--codex', action='store_true', help='Install through Codex using an isolated test configuration/cache.')
    parser.add_argument('--smoke-plugin', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.smoke_plugin:
        result = smoke(args.smoke_plugin, args.output)
    else:
        if not args.archive:
            parser.error('--archive is required')
        result = verify(args.archive, args.output, args.codex)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
