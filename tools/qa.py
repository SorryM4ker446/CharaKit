"""Repeatable, read-only QA of saved projects and exports; never grades artwork."""
import argparse
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import zipfile

from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def load_core(plugin=None):
    path = (Path(plugin) if plugin else REPO / 'plugins/charakit') / 'lib/studio_core.py'
    spec = importlib.util.spec_from_file_location('qa_studio_core', path)
    core = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(core)
    return core


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def audit_export(project, archive, ids=None, core=None):
    """Compare ZIP bytes and declared metadata with current, eligible project assets.

    Defaults to the current selection. Pass explicit IDs to audit an older export.
    No export or project mutation is performed, and no saved visual grade is changed.
    """
    core = core or load_core()
    project, archive = Path(project), Path(archive)
    checks = []

    def check(name, passed):
        checks.append({'name': name, 'passed': bool(passed)})

    try:
        before = (project / 'run.json').read_bytes()
        state = core.read_state(project)
        expected = list(ids) if ids is not None else list(state['selected'].values())
        check('nonempty_unique_expected_selection', bool(expected) and len(expected) == len(set(expected)))
        with zipfile.ZipFile(archive) as pack:
            names = pack.namelist()
            check('unique_safe_archive_paths', len(names) == len(set(names)) and all(
                not PurePosixPath(n).is_absolute() and '..' not in PurePosixPath(n).parts
                and '\\' not in n and ':' not in n for n in names))
            if pack.getinfo('manifest.json').file_size > core.MAX_BYTES:
                raise ValueError('Oversized manifest')
            manifest = json.loads(pack.read('manifest.json'))
            sprites = manifest['sprites']
            check('selected_versions_exact', sorted(s['asset_id'] for s in sprites) == sorted(expected))
            paths = [s['path'] for s in sprites]
            check('unique_sprite_paths', len(paths) == len(set(paths)))
            check('no_unlisted_sprites', set(n for n in names if n.startswith('sprites/')) == set(paths))
            check('source_canvas_explicit', manifest['canvas'] == state['canvas'] == manifest['source_canvas']
                  and manifest['canvas_scope'] == 'source')
            check('project_identity', manifest['character_key'] == state['character_key']
                  and manifest['background_mode'] == state['background_mode'])
            module = state.get('module', 'expressions')
            check('asset_kind', manifest['asset_kind'] == {
                'expressions': 'full_character_expression', 'outfits': 'full_character_outfit',
                'poses': 'full_character_pose'}[module])
            slots = []
            for sprite in sprites:
                asset = core.get_asset(state, sprite['asset_id'])
                key = asset['id']
                slot = core.asset_slot(asset)
                slots.append(slot)
                suffix = slot + '.png' if module == 'expressions' else module + '/' + slot + '.png'
                check(key + ':slot_path', sprite['path'] == f'sprites/{state["character_key"]}/' + suffix)
                identity_keys = ('expression',) if module == 'expressions' else (('pose_id', 'pose', 'side') if module == 'poses' else ('outfit_id', 'edit_type'))
                check(key + ':slot_metadata', all(sprite[k] == asset[k] for k in identity_keys)
                      and sprite.get('mouth_state', 'default') == asset.get('mouth_state', 'default'))
                check(key + ':accepted', asset['art_review_status'] == 'accepted'
                      and sprite['art_review_status'] == 'accepted')
                validation = core.check_asset(project, state, asset)
                check(key + ':current_file_gates', validation['passed'])
                core.require_fidelity(asset)
                core.require_quality(project, state, asset)
                core.workflow_call('require_user_feedback', project, state, asset)
                if pack.getinfo(sprite['path']).file_size > core.MAX_BYTES:
                    raise ValueError('Oversized sprite: ' + key)
                raw = pack.read(sprite['path'])
                check(key + ':original_bytes', raw == core.contained(project, asset['path']).read_bytes()
                      and sha(raw) == sprite['sha256'] == asset['sha256'])
                with Image.open(io.BytesIO(raw)) as image:
                    image.load()
                    canvas = dict(width=image.width, height=image.height)
                    check(key + ':png', image.format == 'PNG')
                check(key + ':actual_canvas', sprite['canvas'] == canvas
                      and sprite['source_canvas'] == state['canvas'])
                mismatch = canvas != state['canvas']
                # Validate the visible contract as well as the machine warning.
                # Build it from trusted project locale and decoded PNG dimensions.
                messages = []
                if mismatch:
                    t = core.presentation_context([project]).texts('report')
                    original = state['canvas']
                    messages = [f'{t["canvas_warning"]} · {t["source"]}: '
                                f'{original["width"]} × {original["height"]}; '
                                f'{t["dimensions"]}: {canvas["width"]} × {canvas["height"]}']
                check(key + ':resolution_notice', ('CANVAS_MISMATCH' in sprite['warnings']) == mismatch
                      and sprite['warning_messages'] == messages)
                check(key + ':version', sprite['source_version'] == asset['version'])
            check('one_version_per_slot', len(slots) == len(set(slots)))
        check('project_state_unchanged', before == (project / 'run.json').read_bytes())
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, zipfile.BadZipFile, core.StudioError) as exc:
        checks.append(dict(name='audit_error', passed=False, detail=str(exc)))
    return dict(passed=all(c['passed'] for c in checks), checks=checks,
                visual_quality='not_assessed', archive=str(archive.resolve()))


def inspect_projects(projects, output, all_candidates=False, core=None):
    """Copy verified raw bytes into a portable inspection page, with an ungraded checklist."""
    core = core or load_core()
    output = Path(output).resolve()
    roots = [Path(p).resolve() for p in projects]
    if output.exists():
        raise FileExistsError(output)
    if any(output.is_relative_to(root) or root.is_relative_to(output) for root in roots):
        raise ValueError('QA output must be separate from every input project.')
    rows, snapshots, payloads = [], [], []
    for index, root in enumerate(roots):
        state_bytes = (root / 'run.json').read_bytes()
        state = core.read_state(root)
        source = core.contained(root, state['source'])
        source_bytes = source.read_bytes()
        if sha(source_bytes) != state['source_sha256']:
            raise ValueError('Source changed: ' + str(root))
        selected = list(state['selected'].values())
        ids = [a['id'] for a in state['assets']] if all_candidates else selected
        if not ids:
            raise ValueError('No selected candidates; use --all-candidates for inspection only: ' + str(root))
        snapshots.append(dict(project=str(root), state_sha256=sha(state_bytes),
                              source_sha256=sha(source_bytes), selected=selected))
        entries = [('source', source, source_bytes, None)]
        for key in ids:
            asset = core.get_asset(state, key)
            path = core.contained(root, asset['path'])
            raw = path.read_bytes()
            if sha(raw) != asset['sha256']:
                raise ValueError('Candidate changed: ' + key)
            entries.append((key, path, raw, asset))
        for key, path, raw, asset in entries:
            info = core.image_info(path)
            if info['sha256'] != sha(raw):
                raise ValueError('Image changed during inspection: ' + str(path))
            validation = core.check_asset(root, state, asset) if asset else {'errors': [], 'warnings': []}
            rel = f'assets/{len(rows):04d}.' + ('jpg' if info['format'] == 'JPEG' else 'png')
            rows.append(dict(id=f'{index}:{key}', label=f'{index + 1} · {key}', source_id=f'{index}:source',
                             src=rel, width=info['width'], height=info['height'],
                             source_canvas=state['canvas'], sha256=sha(raw), alpha_bounds=info['alpha_bounds'],
                             expression=asset.get('expression') if asset else None,
                             mouth_state=asset.get('mouth_state', 'default') if asset else 'unknown',
                             selected=key in selected, errors=validation['errors'], warnings=validation['warnings'],
                             review_status=asset.get('art_review_status') if asset else 'source',
                             scope=asset.get('edit_brief', {}).get('protected_regions', []) if asset else []))
            payloads.append((rel, raw))
        if (root / 'run.json').read_bytes() != state_bytes:
            raise ValueError('Project changed during inspection: ' + str(root))
    data = dict(schema_version='1.0', purpose='inspection_only', visual_quality='not_assessed',
                projects=snapshots, assets=rows, auto_alignment=False, auto_resizing_files=False)
    template = Path(__file__).with_name('qa_view.html').read_text(encoding='utf-8')
    embedded = json.dumps(data, ensure_ascii=False).replace('<', '\\u003c').replace('&', '\\u0026')
    output.mkdir(parents=True)
    (output / 'assets').mkdir()
    for rel, raw in payloads:
        (output / rel).write_bytes(raw)
    (output / 'index.html').write_text(template.replace('__QA_DATA__', embedded), encoding='utf-8')
    write_json(output / 'manifest.json', data)
    from tools.qa_mouth import make_template
    write_json(output / 'mouth-continuity.template.json', make_template(data))
    write_json(output / 'observations.template.json', dict(
        basis='unrecorded', intended_use=None, inspected_display_heights=[], engine_tested=False,
        assets=[dict(id=row['id'], sha256=row['sha256'], checks={
            name: dict(status='not_reviewed', evidence='') for name in (
                'target', 'identity', 'protected_regions', 'structure_contacts_occlusion',
                'rendering_alpha', 'framing_new_extremities', 'switching_continuity')})
            for row in rows if row['review_status'] != 'source']))
    return dict(page=str(output / 'index.html'), manifest=str(output / 'manifest.json'),
                assets=len(rows), visual_quality='not_assessed')


def make_browser_fixture(output, core=None):
    """Synthetic failed-review fixtures for browser gates, never actual art judgments."""
    core = core or load_core()
    output = Path(output)
    output.mkdir(parents=True)
    for name, size, color in [('source', (160, 320), '#446688'), ('first', (80, 160), '#776699'),
                               ('second', (80, 161), '#996677')]:
        image = Image.new('RGBA', size)
        draw = ImageDraw.Draw(image)
        w, h = size
        draw.ellipse((w*.3, h*.04, w*.7, h*.24), fill='#ddbb99')
        draw.rectangle((w*.2, h*.25, w*.8, h*.95), fill=color)
        image.save(output / (name + '.png'))
    root = output / 'project'
    core.init_project(root, output / 'source.png', 'qa_fixture')
    assets = [core.add_asset(root, output / (name + '.png'), 'happy')['asset']['id']
              for name in ('first', 'second')]
    for key in assets:
        preview = root / 'preview' / (key + '.png')
        core.make_preview(root, preview, [key])
        evidence = 'QA FIXTURE: synthetic failed review to exercise UI, not an artistic observation.'
        core.record_quality(root, key, dict(
            rubric_version='1.1', basis='assistant', request=evidence,
            dimensions={name: dict(score=1, evidence=evidence) for name in core.QUALITY_WEIGHTS},
            inspection=dict.fromkeys(core.QUALITY_INSPECTIONS, True), critical_defects=[], uncertainties=[],
            domain_review=dict(version='1.0', kind='expression', component='synthetic_fixture',
                               checks={name: dict(status='failed', evidence=evidence)
                                       for name in core.DOMAIN_CHECKS['expression']})), [preview])
    (root / 'QA_ONLY.txt').write_text('Synthetic failed gate records; no actual art scoring or user acceptance.', encoding='utf-8')
    sheet = core.workflow_call('review_sheet', root, assets, 'user', face_box=[40, 0, 120, 90])
    view = inspect_projects([root], output / 'inspection', all_candidates=True, core=core)
    return dict(review=sheet['page'], inspection=view['page'])


def run(output, browser=False):
    """Run tests, build, then exercise the extracted package. Preserve failed evidence."""
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    steps = []

    def command(name, args):
        print(name, flush=True)
        with (output / (name + '.log')).open('w', encoding='utf-8') as log:
            result = subprocess.run(args, cwd=REPO, stdout=log, stderr=subprocess.STDOUT,
                                    env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
        steps.append(dict(name=name, passed=result.returncode == 0))
        return result.returncode == 0

    try:
        command('unit-tests', [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'])
        package = output / 'charakit.zip'
        if command('build', [sys.executable, str(REPO / 'tools/build_plugin.py'), '--output', str(package)]):
            with zipfile.ZipFile(package) as pack:
                if pack.testzip() is not None:
                    raise ValueError('Corrupt plugin archive')
                if any(name.endswith('.pyc') or name.startswith(('art-output/', '.dev-checks/')) for name in pack.namelist()):
                    raise ValueError('Unexpected package content')
                extracted = output / 'plugin'
                pack.extractall(extracted)
            for module in ('expressions', 'outfits', 'poses'):
                command('packaged-' + module, [sys.executable, str(extracted / f'skills/charakit-{module}/scripts/studio.py'), '--help'])
            fixture = make_browser_fixture(output / 'fixture', core=load_core(extracted))
            write_json(output / 'browser-inputs.json', fixture)
            steps.append(dict(name='packaged-inspection-fixture', passed=True))
            if browser:
                command('browser', [sys.executable, str(REPO / 'tools/qa_browser.py'),
                                    '--inputs', str(output / 'browser-inputs.json'), '--output', str(output / 'browser')])
    except Exception as exc:
        steps.append(dict(name='runner_error', passed=False, detail=str(exc)))
    summary = dict(passed=bool(steps) and all(s['passed'] for s in steps), steps=steps,
                   browser='requested' if browser else 'not_run', visual_quality='not_assessed')
    write_json(output / 'summary.json', summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    inspect = commands.add_parser('inspect', help='Create a portable, read-only raw-image inspection snapshot.')
    inspect.add_argument('--project', type=Path, action='append', required=True)
    inspect.add_argument('--output', type=Path, required=True)
    inspect.add_argument('--all-candidates', action='store_true')
    audit = commands.add_parser('audit-export', help='Independently verify a ZIP against the current selection or explicit IDs.')
    audit.add_argument('--project', type=Path, required=True)
    audit.add_argument('--archive', type=Path, required=True)
    audit.add_argument('--asset', action='append', dest='ids')
    runner = commands.add_parser('run', help='Run workflow tests and packaged smoke checks; optionally exercise Chromium.')
    runner.add_argument('--output', type=Path, required=True)
    runner.add_argument('--browser', action='store_true')
    mouth = commands.add_parser('audit-mouth', help='Validate recorded visual mouth-pair continuity; never infers visual passage.')
    mouth.add_argument('--inspection', type=Path, required=True)
    mouth.add_argument('--record', type=Path, required=True)
    mouth.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'inspect':
            result = inspect_projects(args.project, args.output, args.all_candidates)
        elif args.command == 'audit-export':
            result = audit_export(args.project, args.archive, args.ids)
        elif args.command == 'audit-mouth':
            from tools.qa_mouth import audit_mouth
            result = audit_mouth(args.inspection, args.record, args.output)
        else:
            result = run(args.output, args.browser)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get('passed', True) else 1
    except Exception as exc:
        print(json.dumps(dict(passed=False, error=str(exc)), ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
