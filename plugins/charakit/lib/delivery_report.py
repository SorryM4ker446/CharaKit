"""Assemble reviewed deliverables and an evidence-based report; never generate or regrade art."""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path
import tempfile

from PIL import Image, ImageDraw


# Load beside this file so installed entrypoints need no sys.path changes.
import importlib.util

_locale_spec = importlib.util.spec_from_file_location("charakit_localization", Path(__file__).with_name("localization.py"))
localization = importlib.util.module_from_spec(_locale_spec)
_locale_spec.loader.exec_module(localization)

ZH = localization.texts("report", "zh-CN")
EN = localization.texts("report", "en")
EXPRESSION_ZH = localization.texts("names", "zh-CN")


def md(value) -> str:
    """Treat persisted prose/labels as text, not report markup."""
    text = str(value).replace('\n', ' ').replace('\r', ' ')
    for char in ('\\', '`', '*', '_', '{', '}', '[', ']', '<', '>', '|', '#'):
        text = text.replace(char, '\\' + char)
    return text


def link(label: str, path: str | Path) -> str:
    from urllib.parse import quote
    target = quote(Path(path).resolve().as_posix(), safe='/:')
    return f'[{md(label)}](<{target}>)'


def label_for(core, asset: dict, labels: dict, language: str) -> str:
    names = localization.texts('names', language)
    if 'pose_id' in asset:
        return labels.get(asset['pose_id'], asset['target'])
    if 'outfit_id' in asset:
        if asset['edit_type'] == 'prop_edit':
            t = localization.texts('report', language)
            name = t['prop_'+asset['prop_action']]+' · '+asset['target']
            if 'replacement' in asset:
                name += ' → '+asset['replacement']
            return labels.get(asset['outfit_id'], name)
        change = asset['color'] if asset['edit_type'] == 'recolor' else asset['replacement']
        return labels.get(asset['outfit_id'], f"{asset['target']} → {change}")
    label = labels.get(asset['expression'], names[asset['expression']])
    mouth = asset.get('mouth_state', 'default')
    if mouth != 'default':
        suffix = labels.get('mouth_' + mouth, names['mouth_' + mouth])
        label += ' / ' + suffix
    return labels.get(core.asset_slot(asset), label)


def round_record(core, root: Path, state: dict, asset: dict, number: int) -> dict:
    review = asset.get('quality_review', {})
    raw = core.check_asset(root, state, asset)
    gate = core.delivery_validation(raw)
    quality = core.quality_status(root, state, asset)
    issues = list(gate['errors'])
    if quality in ('stale', 'pending', 'unrecorded'):
        issues.append('quality_' + quality)
    issues.extend(finding['evidence'] for finding in review.get('domain_review', {}).get('checks', {}).values() if finding['status'] != 'passed')
    issues.extend(finding['evidence'] for finding in review.get('domain_review', {}).get('component_checks', {}).values() if finding['status'] != 'passed')
    issues.extend(finding['evidence'] for finding in review.get('dimensions', {}).values() if finding['score'] < 4)
    issues.extend(review.get('critical_defects', []))
    issues.extend(review.get('uncertainties', []))
    fidelity = core.fidelity_status(asset)
    if fidelity in ('failed', 'uncertain', 'pending'):
        issues.append(asset.get('fidelity_review', {}).get('note', 'fidelity_pending'))
    if asset['art_review_status'] == 'rejected':
        issues.append('user_rejected')
    return {
        'round': number, 'asset_id': asset['id'], 'image': str(core.contained(root, asset['path'])),
        'sha256': asset['sha256'], 'quality_status': quality,
        'model': asset.get('model', 'unknown'), 'origin': asset.get('origin'),
        'parent_asset_id': asset.get('parent_asset_id'), 'refinement_inputs': asset.get('refinement_inputs'),
        'human_revision': state.get('human_revisions', {}).get(asset.get('human_revision')),
        'outfit_components': asset.get('outfit_components'),
        'edit_references': asset.get('edit_references'),
        'generation_inputs': asset.get('generation_inputs'),
        'prop_action': asset.get('prop_action'),
        'recorded_score': review.get('result', {}).get('total'),
        'gate_summary': {
            'threshold': review.get('result', {}).get('threshold'),
            'dimension_floor': review.get('result', {}).get('dimension_floor'),
            'total_passed': (review['result']['total'] >= review['result']['threshold']) if review else None,
            'failed_dimensions': [key for key, finding in review.get('dimensions', {}).items() if finding['score'] < 4],
            'failed_domain_checks': [key for key, finding in review.get('domain_review', {}).get('checks', {}).items() if finding['status'] != 'passed'],
            'failed_component_checks': [key for key, finding in review.get('domain_review', {}).get('component_checks', {}).items() if finding['status'] != 'passed'],
            'incomplete_inspections': [key for key, done in review.get('inspection', {}).items() if not done],
        },
        'strategy': asset.get('generation_inputs', {}).get('strategy', asset.get('refinement_inputs', {}).get('strategy', 'source_sample' if asset.get('candidate_pool') else ('continue_previous' if asset.get('refinement_round', 1) > 1 else 'initial'))),
        'score_valid': bool(review) and quality != 'stale' and gate['passed'],
        'rubric': review.get('rubric_version'), 'basis': review.get('basis'),
        'dimensions': review.get('dimensions', {}), 'domain_review': review.get('domain_review'),
        'critical_defects': review.get('critical_defects', []), 'uncertainties': review.get('uncertainties', []),
        'fidelity_review': asset.get('fidelity_review'),
        'criteria': review.get('criteria'), 'human_feedback': asset.get('human_feedback'),
        'inspection': review.get('inspection', {}), 'issues': list(dict.fromkeys(issues)),
        'validation': raw, 'warnings': gate['warnings'], 'fidelity_status': fidelity,
        'art_review_status': asset['art_review_status'], 'request': review.get('request'),
        'prompt': str(core.contained(root, asset['prompt_path'])) if 'prompt_path' in asset else None,
        'recorded_prompt_sha256': review.get('prompt_sha256'),
        'comparisons': [{**entry, 'path': str(core.contained(root, entry['path']))} for entry in review.get('comparisons', [])],
    }


def score_text(record: dict, t: dict) -> str:
    score = record['recorded_score']
    if score is None:
        return '—'
    return f'{score:g}' + (f" ({t['stale']})" if not record['score_valid'] else '')


def display_issues(record: dict, t: dict) -> list[str]:
    """Avoid repeating the same observations from domain, dimensions and fidelity notes."""
    issues = [f['evidence'] for f in (record['domain_review'] or {}).get('checks', {}).values() if f['status'] != 'passed']
    issues += [f['evidence'] for f in (record['domain_review'] or {}).get('component_checks', {}).values() if f['status'] != 'passed']
    issues += record['uncertainties']
    if not issues:
        issues += record['critical_defects']
        issues += [d['evidence'] for d in record['dimensions'].values() if d['score'] < 4]
    issues += [t.get(code, code) for code in record['issues'] if code in ('quality_stale','quality_pending','quality_unrecorded','fidelity_pending','user_rejected')]
    issues += [t.get(code, code) for code in record['validation']['errors']] if not record['score_valid'] else []
    if not issues and record['fidelity_status'] in ('failed','uncertain'):
        issues.append((record['fidelity_review'] or {}).get('note', t[record['fidelity_status']]))
    return list(dict.fromkeys(issues))


def blocking_summary(record: dict, t: dict) -> str:
    """Show gate failures beside the total without inventing new visual findings."""
    gate = record['gate_summary']
    reasons = []
    if gate['total_passed'] is False:
        reasons.append(f"{t['threshold']} {record['recorded_score']:g} < {gate['threshold']:g}")
    for key in gate['failed_dimensions']:
        reasons.append(f"{t[key]} {record['dimensions'][key]['score']}/5 < {gate['dimension_floor']}/5")
    for key in gate['failed_domain_checks']:
        evidence = ' '.join(record['domain_review']['checks'][key]['evidence'].split())
        excerpt = evidence if len(evidence) <= 120 else evidence[:120] + '…'
        reasons.append(t.get(key, key) + ': ' + excerpt)
    for key in gate['failed_component_checks']:
        finding = record['domain_review']['component_checks'][key]
        names = {item['id']: item['source'] for item in record['outfit_components'] or []}
        reasons.append(t['component_checks'] + ' ' + names.get(key,key) + ': ' + finding['evidence'])
    reasons.extend(t.get(key, key) + ': ' + t['unchecked'] for key in gate['incomplete_inspections'])
    if record['quality_status'] in ('stale', 'pending', 'unrecorded'):
        reasons.append(t['quality_' + record['quality_status']])
    reasons.extend(t.get(code, code) for code in record['validation']['errors'] if code != 'CANVAS_MISMATCH')
    if record['fidelity_status'] in ('failed', 'uncertain', 'pending'):
        reasons.append(t['fidelity'] + ': ' + t[record['fidelity_status']])
    if record['art_review_status'] == 'rejected':
        reasons.append(t['user_rejected'])
    if not reasons:
        reasons.extend(record['critical_defects'] + record['uncertainties'])
    return '; '.join(dict.fromkeys(reasons)) or t['none']


def write_preview(core, cases: list[dict], sources: list[dict], output: Path, t: dict,
                  face_box: list[int] | None, background: str) -> None:
    # This display sheet never appears in assessment bindings or replaces raw PNGs.
    cards = [(s['label'], s['image'], None, s['canvas']) for s in sources]
    cards += [(c['label'], c['final']['original_image'], c, c['source_canvas']) for c in cases if c['final']]
    width, height = 360, 510 + (210 if face_box else 0)
    columns = min(3, len(cards))
    sheet = Image.new('RGB', (columns * width, math.ceil(len(cards) / columns) * height), '#ffffff')
    draw = ImageDraw.Draw(sheet)
    for index, (label, path, case, canvas) in enumerate(cards):
        x, y = index % columns * width, index // columns * height
        with Image.open(path) as opened:
            image = opened.convert('RGBA')
        tile = image.copy(); tile.thumbnail((340, 400), Image.Resampling.LANCZOS)
        panel = core.backdrop((width, 420), background)
        panel.alpha_composite(tile, ((width-tile.width)//2, (420-tile.height)//2))
        sheet.paste(panel.convert('RGB'), (x,y))
        # Long user labels wrap rather than overwrite neighboring cards.
        remaining = label
        for line_no in range(2):
            line = ''
            while remaining and draw.textlength(line + remaining[0], font=core.font(16)) < 338:
                line += remaining[0]; remaining = remaining[1:]
            if line_no == 1 and remaining:
                line = line[:-1] + '…'
            draw.text((x+10,y+424+line_no*20),line,font=core.font(16),fill='#222222')
        suffix = f'{image.width} × {image.height}'
        if case:
            final_record = next(r for r in case['history'] if r['asset_id'] == case['final']['asset_id'])
            suffix = f"{t['passed']} · {len(case['history'])}{t['round_unit']} · {score_text(final_record,t)}/100 · " + suffix
        draw.text((x+10,y+469),suffix,font=core.font(13),fill='#267048' if case else '#444444')
        if case and 'CANVAS_MISMATCH' in case['history'][-1]['warnings']:
            draw.text((x+10,y+489),t['canvas_warning'],font=core.font(12),fill='#b45309')
        if face_box:
            box = tuple(round(v*image.size[i%2]/canvas['width' if i%2==0 else 'height']) for i,v in enumerate(face_box))
            face = image.crop(box)
            face.thumbnail((340,190),Image.Resampling.LANCZOS)
            panel = core.backdrop((width,210),background)
            panel.alpha_composite(face,((width-face.width)//2,(210-face.height)//2))
            sheet.paste(panel.convert('RGB'),(x,y+510))
    sheet.save(output,format='PNG')


def case_record(case):
    return next((record for record in case['history'] if record['asset_id'] == case.get('assessed_asset_id')), case['history'][-1])


def write_detail_preview(core, case, region, output, t, background):
    """Display the accepted version and source at the recorded source coordinates."""
    sheet = Image.new('RGB', (720, 340), '#ffffff')
    draw = ImageDraw.Draw(sheet)
    baseline = (t['revision_parent'], case['revision_parent_image']) if case.get('inspection_base') == 'parent' else (t['source'], case['source'])
    for index, (label, path) in enumerate((baseline, (case['label'], case['final']['original_image']))):
        with Image.open(path) as opened:
            image = opened.convert('RGBA')
        box = tuple(round(v*image.size[i%2]/case['source_canvas']['width' if i%2==0 else 'height']) for i,v in enumerate(region['box']))
        detail = image.crop(box)
        detail.thumbnail((340, 290), Image.Resampling.LANCZOS)
        panel = core.backdrop((360, 310), background)
        panel.alpha_composite(detail, ((360-detail.width)//2, (310-detail.height)//2))
        sheet.paste(panel.convert('RGB'), (index*360, 0))
        draw.text((index*360+10, 316), label[:36], font=core.font(15), fill='#222222')
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, format='PNG')


def render_markdown(data: dict, output: Path, t: dict) -> str:
    lines = [f"# {md(data['title'])}", '', data['created_at'] + ' (UTC)', '',
             t['draft_note' if data['stage'] == 'draft' else 'final_note'] if any(c.get('candidate_pool') for c in data['cases']) else t['snapshot'], '',
             t['summary'].format(**data['summary']), '', t['gate_note'], '', '## '+t['overview'], '',
             '| '+' | '.join(t[k] for k in ('module','case','rounds','scores','status','blockers','final'))+' |',
             '|---|---|---:|---|---|---|---|']
    for c in data['cases']:
        final = link('PNG',output/c['final']['path']) if c['final'] else t['report_only']
        lines.append('| '+' | '.join((t[c['kind']],md(c['label']),str(c.get('attempt_count', len(c['history']))),
            ' → '.join(score_text(r,t) for r in c['history']),t[c['status']],
            md(blocking_summary(case_record(c),t)),final))+' |')
    if data['preview']:
        lines += ['',link(t['preview'],output/data['preview'])]
    if any(c.get('detail_previews') for c in data['cases']):
        lines += ['', '## '+t['detail_preview'], '']
        for case in data['cases']:
            for detail in case.get('detail_previews', []):
                label = case['label']+' · '+(detail.get('label') or t['face_region' if detail['id']=='face' else 'target_region'])
                lines += ['!'+link(label, output/detail['path']), '']
    for c in data['cases']:
        if not c['final']:
            lines += ['',f"**{md(c['label'])} — {t[c['status']]}**", '']
            issues = display_issues(case_record(c),t)
            lines += ['- '+md(issue) for issue in issues]
            if not issues and c.get('delivery_error'):
                lines.append('- '+md(c['delivery_error']['code']))
            next_step = t['next_revision_request'] if (c.get('human_result') or {}).get('next_action')=='revision_request' and c['status']!='revision_failed' else t.get('next_'+c['status'],t['next_failed'])
            if c['status']=='exhausted' and (c.get('candidate_pool') or {}).get('version') in ('1.1', '1.2') and not c.get('human_result'):
                next_step=t['next_exhausted_human']
            lines += ['',t['next']+'：'+next_step]
    lines += ['', '## '+t['details'], '']
    for c in data['cases']:
        last = case_record(c)
        domain = last['domain_review'] or {}
        lines += ['### '+md(c['label']), '',t['source']+'：'+link(c['character'],c['source']),
                  '',t['request']+'：'+md(c['history'][0]['request'] or last['request'] or '—'),
                  '',t['component']+'：'+md(domain.get('component','—')), '']
        if c.get('edit'):
            edit = c['edit']
            if edit['edit_type'] == 'pose_edit':
                lines += [t['edit_definition']+'：'+t['pose_edit']+' · '+md(edit['target']), '',
                          t['pose']+'：'+md(edit['pose'])+' · '+t['side']+'：'+t.get(edit['side'], edit['side']), '']
                if edit['anchors']:
                    lines += [t['anchors']+'：'+md('; '.join(edit['anchors'])), '']
                if edit.get('pose_interaction'):
                    lines += ['**'+t['pose_interaction']+'**', '']
                    lines += ['- '+t[key]+'：'+md(value) for key, value in edit['pose_interaction'].items()]
                    lines.append('')
            else:
                change = t['prop_remove'] if edit.get('prop_action') == 'remove' else edit.get('replacement', edit.get('color', '—'))
                lines += [t['edit_definition']+'：'+t[edit['edit_type']]+' · '+md(edit['target'])+' → '+md(change), '']
            if edit.get('prop_action'):
                lines += [t['prop_action']+'：'+t['prop_'+edit['prop_action']], '']
            if edit.get('outfit_components'):
                lines += ['**'+t['outfit_components']+'**', '']
                lines += ['- '+md(item['source'])+' → '+md(item['replacement']) for item in edit['outfit_components']]
                lines.append('')
        if c.get('edit_references'):
            lines += ['**'+t['edit_references']+'**', '']
            lines += ['- '+link(ref['id'],ref['image'])+' · '+md(', '.join(ref['scope']))+' · '+md(ref['notes']) for ref in c['edit_references']]
            lines.append('')
        if c.get('human_revision'):
            revision = c['human_revision']
            lines += [t['revision_parent']+'：'+link(revision['parent_asset'],c['revision_parent_image']),
                      '',t['revision_note']+'：'+md(revision['note']), '']
        if c.get('requested_revision'):
            requested = c['requested_revision']
            lines += [t['revision_attempt']+'：'+(t['revision_failed'] if requested['status']=='failed' else t.get(requested['status'],requested['status'])), '']
            if requested.get('failure'):
                lines += ['- '+md(requested['failure']), '']
        if c.get('candidate_pool'):
            pool = c['candidate_pool']
            lines += [t['attempt_budget']+'：'+str(len(pool['attempts']))+' / '+str(pool['budget']), '']
            for attempt in pool['attempts']:
                if attempt['status'] == 'failed':
                    lines += ['- '+t['round']+' '+str(attempt['number'])+' · '+t['tool_failure']+'：'+md(attempt['failure']), '']
            feedback = c.get('human_feedback')
            lines += [t['human']+'：'+(md(t.get(feedback['decision'],feedback['decision'])+' · '+feedback['note']) if feedback else t['human_review']), '']
            result = c.get('human_result')
            if result:
                action = result['next_action']
                lines += [t['human_action']+'：'+t.get('feedback_blocked' if action == 'blocked' else action,action), '']
            facets = (feedback or {}).get('facets', {})
            ratings = [t.get(k,k)+': '+str(v) for k,v in facets.items() if v != 'unspecified']
            if ratings:
                lines += [t['human_facets']+'：'+md('；'.join(ratings)), '']
        gate = last['gate_summary']
        if gate['threshold'] is not None:
            lines += [f"{t['threshold']}: {gate['threshold']}/100; {t['dimension_floor']}: {gate['dimension_floor']}/5", '']
        lines += ['| '+' | '.join(t[k] for k in ('round','asset','strategy','target','identity','protection','integration','rendering','scores','quality','fidelity','blockers'))+' |',
                  '|---:|---|---|---:|---:|---:|---:|---:|---:|---|---|---|']
        for r in c['history']:
            dims = [str(r['dimensions'].get(k,{}).get('score','—')) for k in ('target','identity','protection','integration','rendering')]
            fidelity = t.get(r['fidelity_status'],r['fidelity_status']) if c['kind'] in ('garment_recolor','garment_replace','outfit_replace','prop_edit') else t['not_applicable']
            lines.append('| '+' | '.join([str(r['round']),md(r['asset_id']),t[r['strategy']],*dims,score_text(r,t),t.get(r['quality_status'],r['quality_status']),fidelity,md(blocking_summary(r,t))])+' |')
        lines += ['', '**'+t['domain']+'**', '', '| '+t['check']+' | '+t['status']+' | '+t['evidence']+' |', '|---|---|---|']
        for key,finding in domain.get('checks',{}).items():
            lines.append('| '+t.get(key,key)+' | '+t[finding['status']]+' | '+md(finding['evidence'])+' |')
        if domain.get('component_checks'):
            names = {item['id']: item['source'] for item in (c.get('edit') or {}).get('outfit_components', [])}
            lines += ['', '**'+t['component_checks']+'**', '', '| '+t['component']+' | '+t['status']+' | '+t['evidence']+' |', '|---|---|---|']
            for key, finding in domain['component_checks'].items():
                lines.append('| '+md(names.get(key,key))+' | '+t[finding['status']]+' | '+md(finding['evidence'])+' |')
        coverage = '；'.join(t[key]+': '+t['checked' if value else 'unchecked'] for key,value in last['inspection'].items())
        actual = last['validation'].get('image')
        size = f"{actual['width']} × {actual['height']}" if actual else '—'
        technical = t['canvas_warning'] if last['validation']['errors']==['CANVAS_MISMATCH'] else t['passed' if last['validation']['passed'] else 'failed']
        lines += ['',t['inspection']+'：'+(coverage or '—'),
                  '',t['dimensions']+f"：{size}; "+t['technical']+': '+technical,
                  '',t['history']+'：', '']
        for r in c['history']:
            refs = [link(t['prompt'],r['prompt'])] if r['prompt'] else []
            refs += [link(t['comparison']+f' {i+1}',p['path']) for i,p in enumerate(r['comparisons'])]
            lines.append(f"- {t['round']} {r['round']}: "+(' · '.join(refs) or '—'))
            lines += ['  - '+md(issue) for issue in display_issues(r,t)]
        lines.append('')
    lines += ['', '## '+t['limits'], '',t['note'], '',t['scope_note'], '',t['canvas_note'], '',t['snapshot'], '',
              link('JSON',output/'report.json'), '']
    return '\n'.join(lines)


def generate_report(core, projects: list[Path], output: Path, *, ids: list[str] | None = None,
                    language: str = localization.DEFAULT_LANGUAGE, title: str | None = None, labels: dict | None = None,
                    face_box: list[int] | None = None, background: str = 'light', stage: str = 'auto') -> dict:
    try:
        language = localization.normalize_language(language)
    except ValueError as exc:
        raise core.StudioError('INVALID_REPORT_OPTIONS', str(exc)) from exc
    if background not in ('light','dark','checker') or stage not in ('auto','final'):
        raise core.StudioError('INVALID_REPORT_OPTIONS','Unsupported report language or preview background.')
    roots = [p.resolve() for p in projects]; output = output.resolve()
    if not roots or len(set(roots)) != len(roots) or (ids is not None and (len(roots)!=1 or not ids or len(ids)!=len(set(ids)))):
        raise core.StudioError('INVALID_REPORT_SCOPE','Use unique projects; explicit asset IDs require one project.')
    if output.exists():
        raise FileExistsError(output)
    t = localization.texts('report', language)
    labels = labels or {}
    if any(not isinstance(k,str) or not core.valid_edit_text(v,200) for k,v in labels.items()):
        raise core.StudioError('INVALID_REPORT_OPTIONS','Report labels must be short single-line text.')
    if title is not None and not core.valid_edit_text(title,200):
        raise core.StudioError('INVALID_REPORT_OPTIONS','Use a short single-line title.')
    cases=[]; sources=[]; bindings=[]
    for project_index,root in enumerate(roots,1):
        state=core.read_state(root)
        bindings.append((root,core.digest(root/'run.json')))
        if face_box is not None and not core.valid_source_box(face_box,state['canvas']):
            raise core.StudioError('INVALID_FACE_BOX','Face box must fit every source canvas.')
        chosen = [core.get_asset(state,i) for i in ids] if ids is not None else list({core.asset_slot(a):a for a in sorted(state['assets'],key=lambda a:a['version'])}.values())
        slots=set()
        for selected in chosen:
            case_id=selected.get('refinement_case')
            plan=core.refinement_status(root,case_id) if case_id else None
            pool_id=selected.get('candidate_pool')
            human_result=None
            feedback=None
            if pool_id:
                pool=state['candidate_pools'][pool_id]
                history=[core.get_asset(state,a['asset_id']) for a in pool['attempts'] if a['status']=='imported']
                accepted=state['selected'].get(core.asset_slot(selected))
                history_ids={a['id'] for a in history}
                packet=next((p for p in reversed(list(state.get('review_packets',{}).values()))
                             if p['purpose']=='user' and p.get('feedback')
                             and {item['asset_id'] for item in p['items'].values()} <= history_ids),None)
                if packet:
                    core.workflow_call('packet_valid',root,state,packet)
                    human_result=packet['feedback']['result']
                    feedback=packet['feedback']['input']
                preferred=pool['comparisons'][-1]['preferred'] if pool['comparisons'] else selected['id']
                reviewed=human_result['asset_ids'][0] if human_result else preferred
                asset=next((a for a in history if a['id']==accepted), next((a for a in history if a['id']==reviewed),selected))
            elif plan:
                asset=core.get_asset(state,plan['current_asset'])
                history=[core.get_asset(state,h['asset_id']) for h in plan['history']]
            else:
                asset=selected
                history=sorted((a for a in state['assets'] if core.asset_slot(a)==core.asset_slot(asset) and a['version']<=asset['version'] and not a.get('refinement_case')),key=lambda a:a['version'])
            slot=core.asset_slot(asset)
            if slot in slots:
                raise core.StudioError('INVALID_REPORT_SCOPE','Each case may appear once; a tracked asset selects its whole refinement case.')
            slots.add(slot)
            attempt_numbers={a['asset_id']:a['number'] for a in pool['attempts'] if a['status']=='imported'} if pool_id else {}
            records=[round_record(core,root,state,a,attempt_numbers.get(a['id'],i+1)) for i,a in enumerate(history)]
            last=records[-1]
            internal_plan = core.workflow_call('pool_status',root,pool_id) if pool_id and pool['version'] in ('1.1', '1.2') else None
            action=internal_plan['action'] if internal_plan else plan['action'] if plan else ('review' if last['quality_status'] in ('pending','unrecorded') or last['fidelity_status']=='pending' else 'failed')
            delivered=None; error=None
            try:
                delivery=core.delivery_assets(root,[asset['id']])['delivery'][0]
                delivered={'asset_id':asset['id'],'path':f'final/{project_index:03d}_{asset["id"]}.png','original_image':str(core.contained(root,asset['path'])),'sha256':asset['sha256'],'canvas':delivery['canvas'],'warnings':delivery['warnings']}
                action='passed'
            except core.StudioError as exc:
                error={'code':exc.code,'message':exc.message}
                if exc.code=='HUMAN_REVIEW_REQUIRED' and not internal_plan:
                    action='human_review'
                elif plan and action=='deliver':
                    action='blocked'
                elif last['quality_status']=='stale' or 'ASSET_CHANGED' in last['validation']['errors'] or asset['art_review_status']=='rejected':
                    action='blocked'
                elif action=='failed' and last['quality_status']=='uncertain':
                    action='uncertain'
            if human_result and not delivered:
                if feedback['decision']=='reject':
                    action='user_declined'
                elif feedback['decision']=='revise':
                    action='revise'
                elif human_result['next_action']=='blocked':
                    action='failed'
            requested_revision = state.get('human_revisions',{}).get((feedback or {}).get('packet'))
            if requested_revision and requested_revision['status']=='failed' and not delivered:
                action='revision_failed'
            accepted_packet = state.get('review_packets', {}).get(asset.get('human_feedback', {}).get('packet'), {}) if delivered else {}
            detail_regions = accepted_packet.get('inspection', {}).get('regions', [])
            # Legacy reports may use an explicitly requested face box or saved outfit target.
            if delivered and not detail_regions and 'inspection' not in accepted_packet:
                detail_regions = ([{'id': 'face', 'box': face_box}] if face_box else [])
                target_box = asset.get('edit_brief', {}).get('target_box')
                if target_box:
                    detail_regions += [{'id': 'target', 'box': target_box}]
            cases.append({'project':str(root),'character':state['character_key'],'case_id':pool_id or case_id or asset['id'],'kind':core.quality_domain(state,asset),
                          'inspection_regions': copy.deepcopy(detail_regions),
                          'inspection_base': accepted_packet.get('inspection', {}).get('comparison_base', 'source'),
                          'requested_revision':requested_revision,
                          'human_revision':state.get('human_revisions',{}).get(asset.get('human_revision')),
                          'revision_parent_image':str(core.contained(root,core.get_asset(state,state['human_revisions'][asset['human_revision']]['parent_asset'])['path'])) if asset.get('human_revision') else None,
                          'human_feedback':feedback or asset.get('human_feedback'), 'human_result':human_result,
                          'assessed_asset_id':asset['id'], 'candidate_pool':state.get('candidate_pools',{}).get(pool_id),
                          'label':label_for(core,asset,labels,language),'status':action,'max_rounds':pool['budget'] if pool_id else plan['max_rounds'] if plan else None,
                          'attempt_count':len(pool['attempts']) if pool_id else len(records),
                          'edit':{key:asset[key] for key in ('edit_type','target','color','replacement','outfit_components','prop_action','edit_brief','pose_id','pose','side','anchors','pose_interaction') if key in asset} if 'outfit_id' in asset or 'pose_id' in asset else None,
                          'edit_references':[{**ref,'image':str(core.contained(root,ref['path']))} for ref in asset.get('edit_references',[])],
                          'source':str(core.contained(root,state['source'])),'source_sha256':state['source_sha256'],
                          'source_canvas':state['canvas'],'history':records,'final':delivered,'delivery_error':error})
        if state['source_sha256'] not in {s['sha256'] for s in sources}:
            sources.append({'label':labels.get('source',t['source']+' · '+state['character_key']),'image':str(core.contained(root,state['source'])),'sha256':state['source_sha256'],'canvas':state['canvas']})
    if not cases:
        raise core.StudioError('NO_REPORT_ASSETS','No candidates in the requested scope.')
    pending=[c['case_id'] for c in cases if c.get('candidate_pool') and not c.get('human_result')]
    if stage=='final' and pending:
        raise core.StudioError('HUMAN_REVIEW_REQUIRED','Record actual human feedback for every requested pool before generating the final review report.')
    resolved_stage='draft' if pending else 'final'
    if resolved_stage=='draft':
        for case in cases:
            if case['final']:
                case['final']=None
                case['status']='awaiting_report'
    passed=sum(c['final'] is not None for c in cases)
    report_title=title or (t['draft_title'] if resolved_stage=='draft' else (t['final_title'] if any(c.get('candidate_pool') for c in cases) else t['title']))
    if resolved_stage=='draft' and title:
        report_title=t['draft_title']+' · '+title
    data={'schema_version':'1.0','created_at':core.timestamp(),'title':report_title,'language':language,
          'stage':resolved_stage,'pending_human_cases':pending,
          'summary':{'cases':len(cases),'passed':passed,'other':len(cases)-passed,'images':sum(len(c['history']) for c in cases)},
          'cases':cases,'preview':'preview.png' if passed else None,'project_bindings':[{'project':str(r),'run_sha256':sha} for r,sha in bindings]}
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent,prefix='.report-') as temp:
        staging=Path(temp)/'delivery';staging.mkdir()
        for c in cases:
            if c['final']:
                core.copy_exclusive(Path(c['final']['original_image']),staging/c['final']['path'])
                if core.digest(staging/c['final']['path'])!=c['final']['sha256']:
                    raise core.StudioError('ASSET_CHANGED','A final candidate changed while assembling the report.')
                c['detail_previews'] = []
                for region in c['inspection_regions']:
                    if not core.valid_source_box(region['box'], c['source_canvas']):
                        raise core.StudioError('INVALID_REVIEW_BOX', 'Saved detail region must fit the source canvas.')
                    detail = {**region, 'asset_id': c['final']['asset_id'], 'path': 'details/'+Path(c['final']['path']).stem+'-'+region['id']+'.png'}
                    write_detail_preview(core, c, region, staging/detail['path'], t, background)
                    c['detail_previews'].append(detail)
        if passed:
            write_preview(core,cases,sources,staging/'preview.png',t,face_box,background)
        data['artifacts']=[{'path':p.relative_to(staging).as_posix(),'sha256':core.digest(p)} for p in sorted(staging.rglob('*')) if p.is_file()]
        (staging/'report.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        (staging/'report.md').write_text(render_markdown(data,output,t),encoding='utf-8')
        for root,sha in bindings:
            core.read_state(root)
            if core.digest(root/'run.json')!=sha:
                raise core.StudioError('PROJECT_CHANGED','Project changed while assembling the report; retry after edits finish.')
        for c in cases:
            if c['final']:
                core.delivery_assets(Path(c['project']),[c['final']['asset_id']])
        if output.exists():
            raise FileExistsError(output)
        staging.rename(output)
    return {'report':str(output/'report.md'),'manifest':str(output/'report.json'),'stage':resolved_stage,
            'preview':str(output/'preview.png') if passed else None,
            'detail_previews': [str(output/d['path']) for case in cases for d in case.get('detail_previews', [])],
            'images':[str(output/c['final']['path']) for c in cases if c['final']],
            'summary':data['summary']}
