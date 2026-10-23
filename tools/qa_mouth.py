"""Evidence-bound manual continuity acceptance, separate from static PNG delivery."""
import hashlib
import json
from pathlib import Path

CHECKS = ('mouth_target', 'eyes_brows', 'head_identity', 'waist_skirt', 'feet_position', 'edges_framing')
VIEWS = ('420_height', '720_height', '420_scale', '720_scale', 'native_detail', 'light_dark', 'alternating')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def make_template(manifest):
    assets = manifest['assets']
    pairs = []
    for a in assets:
        if a.get('mouth_state') != 'open':
            continue
        closed = [b for b in assets if b['source_id'] == a['source_id']
                  and b.get('expression') == a.get('expression') and b.get('mouth_state') == 'closed']
        if not closed and a.get('expression') == 'neutral':
            closed = [b for b in assets if b['id'] == a['source_id']]
        for b in closed or [None]:
            pairs.append(dict(first=b['id'] if b else None, second=a['id'],
                              sha256=[b['sha256'] if b else None, a['sha256']],
                              source_baseline=dict(status='not_reviewed', evidence=''),
                              views={v: False for v in VIEWS},
                              evidence=[], checks={k: dict(status='not_reviewed', evidence='') for k in CHECKS}))
    return dict(schema_version='1.0', purpose='mouth_continuity', basis='unrecorded',
                source_sha256=[p['source_sha256'] for p in manifest['projects']],
                engine_tested=False, pairs=pairs)


def audit_mouth(inspection, record, output):
    """Require complete explicit observations; never compute a visual score from pixels."""
    inspection, record, output = Path(inspection).resolve(), Path(record).resolve(), Path(output).resolve()
    if output.exists():
        raise FileExistsError(output)
    if output.is_relative_to(inspection) or inspection.is_relative_to(output):
        raise ValueError('Write acceptance results outside the immutable snapshot.')
    checks, pairs = [], []
    def check(name, passed):
        checks.append(dict(name=name, passed=bool(passed)))
    try:
        manifest = json.loads((inspection / 'manifest.json').read_text(encoding='utf-8'))
        data = json.loads(record.read_text(encoding='utf-8'))
        assets = {a['id']: a for a in manifest['assets']}
        check('schema_and_basis', data['schema_version'] == '1.0' and data['purpose'] == 'mouth_continuity'
              and data['basis'] in ('assistant_visual_observation', 'human_visual_observation'))
        check('source_binding', data['source_sha256'] == [p['source_sha256'] for p in manifest['projects']])
        required = {a['id'] for a in assets.values() if a.get('mouth_state') in ('open', 'closed') and a['review_status'] != 'source'}
        covered, seen = set(), set()
        check('nonempty_pairs', bool(data['pairs']))
        for i, pair in enumerate(data['pairs']):
            prefix = f'pair_{i}:'
            a, b = assets[pair['first']], assets[pair['second']]
            key = tuple(sorted((a['id'], b['id'])))
            check(prefix+'unique', key not in seen)
            seen.add(key)
            source_pair = a['review_status'] == 'source' and b.get('expression') == 'neutral' and b.get('mouth_state') == 'open'
            baseline = pair.get('source_baseline', {})
            check(prefix+'same_source_expression_opposite_mouth', a['source_id'] == b['source_id'] and (
                (a.get('expression') == b.get('expression') and {a.get('mouth_state'), b.get('mouth_state')} == {'open', 'closed'})
                or (source_pair and baseline.get('status') == 'passed' and isinstance(baseline.get('evidence'), str) and bool(baseline['evidence'].strip()))))
            check(prefix+'fingerprints', pair['sha256'] == [a['sha256'], b['sha256']])
            for item in (a, b, assets[a['source_id']]):
                path = (inspection / item['src']).resolve()
                check(prefix+item['id']+':snapshot_bytes', path.is_relative_to(inspection) and digest(path) == item['sha256'])
            covered.update((a['id'], b['id']))
            check(prefix+'all_views_inspected', all(pair['views'].get(k) is True for k in VIEWS))
            evidence = pair.get('evidence', [])
            check(prefix+'saved_comparisons', bool(evidence) and all(
                isinstance(e, dict) and digest(record.parent / e['path']) == e['sha256'] for e in evidence))
            for k in CHECKS:
                item = pair['checks'][k]
                check(prefix+k, item['status'] == 'passed' and isinstance(item['evidence'], str) and bool(item['evidence'].strip()))
            pairs.append(dict(first=a['id'], second=b['id'], observations=pair['checks']))
        check('all_mouth_assets_covered', required <= covered)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        checks.append(dict(name='invalid_or_stale_record', passed=False, detail=str(exc)))
    result = dict(passed=bool(checks) and all(c['passed'] for c in checks), checks=checks, pairs=pairs,
                  scope='recorded_visual_mouth_continuity', automatic_visual_grading=False,
                  engine_acceptance='not_verified', static_export_affected=False)
    output.mkdir(parents=True)
    (output / 'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = ['# 口型连续性验收', '', '结果：'+('通过' if result['passed'] else '未通过 / 证据不完整'), '',
             '范围：记录所覆盖帧对的目视连续性。引擎集成未验证；静态 PNG 导出资格独立判断。', '']
    for pair in pairs:
        lines += [f"## {pair['first']} → {pair['second']}", '']
        for k, item in pair['observations'].items():
            lines.append(f"- {k}: {item['status']} — {item['evidence']}")
        lines.append('')
    lines += ['## 未通过的检查', ''] + ['- '+c['name'] for c in checks if not c['passed']]
    (output / 'report.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    return result
