"""Assemble reviewed deliverables and an evidence-based report; never generate or regrade art."""
from __future__ import annotations

import json
import math
from pathlib import Path
import tempfile

from PIL import Image, ImageDraw


ZH = {
    'title': '角色图像交付报告', 'overview': '结果概览', 'case': '情况', 'module': '模块',
    'rounds': '轮数', 'scores': '逐轮评分', 'status': '结果', 'final': '成品图',
    'passed': '通过', 'exhausted': '达到上限，未通过', 'blocked': '记录或文件失效',
    'review': '待评审', 'revise': '待修订', 'failed': '未通过', 'uncertain': '存在不确定项',
    'unrecorded': '未记录', 'pending': '待评审', 'stale': '证据失效',
    'expression': '表情', 'mouth_state': 'mouth', 'garment_recolor': 'outfits',
    'details': '评审与修订记录', 'round': '轮次', 'asset': '版本', 'quality': '质量',
    'target': '目标', 'identity': '身份', 'protection': '保护', 'rendering': '绘制',
    'issues': '未通过项', 'component': '编辑部位', 'request': '请求', 'source': '原图',
    'domain': '最终专项检查', 'check': '检查项', 'evidence': '观察依据',
    'limits': '检查范围与限制', 'preview': '最终版预览', 'history': '过程证据（供查看）',
    'prompt': '实际提示词', 'comparison': '对照', 'none': '无', 'report_only': '无合格成品，仅报告',
    'next': '后续处理', 'next_exhausted': '停止自动生成；根据上述未通过项调整编辑策略，后续尝试需另行明确授权。',
    'next_blocked': '先检查缺失或变更的文件及评审证据，不能复用失效分数作为通过依据。',
    'next_review': '完成本轮评审与适用的保真检查；尚未形成合格成品。',
    'next_revise': '按已记录的问题修订上一版，在剩余授权轮数内重新评审。',
    'next_failed': '保留当前候选及问题记录；需要修订时另行明确尝试次数。',
    'note': '分数与观察来自已保存的助手或用户评审；本命令只核对记录和门禁，不进行视觉评分。通过表示可供用户验收，不代表用户已接受。报告仅覆盖所列项目与情况。',
    'scope_note': '全图、目标细节、保护细节、正常展示和背景边缘的检查完成情况见下方记录；具体展示尺寸以原评审记录为准，本命令不新增游戏内验证。',
    'canvas_note': '画布差异仅作为预览交付警告；正式验收、选择及ZIP导出仍保留原画布要求。成品PNG按原字节复制，预览缩放仅用于展示。',
    'snapshot': '报告是生成时的快照；后续项目或文件变化需重新生成。过程图不作为验收标准。',
    'summary': '情况：{cases}；通过：{passed}；未交付：{other}；本报告范围内候选图：{images}。',
    'emotion': '情绪', 'face_design': '面部设计', 'nonface_protection': '非面部保护',
    'target_color': '目标颜色', 'garment_invariants': '衣物构造与材质', 'interfaces': '接口与排除区域',
    'face_expression': '面部与表情', 'non_target_protection': '非目标保护',
    'full_image': '全图', 'target_detail': '目标细节', 'protected_details': '保护细节',
    'normal_display': '正常展示', 'background_edges': '背景与边缘', 'inspection': '检查完成情况',
    'dimensions': '尺寸', 'technical': '文件检查', 'fidelity': '保真', 'checked': '已检查', 'unchecked': '未检查',
    'round_unit': '轮', 'canvas_warning': '尺寸与原图不同（预览允许）', 'not_applicable': '不适用',
    'quality_stale': '提示词或对照证据已变更，原评分不能作为当前通过依据。',
    'quality_pending': '本轮质量评审尚未完成。', 'quality_unrecorded': '尚未记录质量评审。',
    'fidelity_pending': '本轮保真检查尚未完成。', 'user_rejected': '用户已拒绝此版本。',
}
EN = {
    'title': 'Character image delivery report', 'overview': 'Results', 'case': 'Case', 'module': 'Module',
    'rounds': 'Rounds', 'scores': 'Scores by round', 'status': 'Result', 'final': 'Final PNG',
    'passed': 'Passed', 'exhausted': 'Limit reached; failed', 'blocked': 'Invalid records or files',
    'review': 'Review pending', 'revise': 'Revision pending', 'failed': 'Failed', 'uncertain': 'Uncertain',
    'unrecorded': 'Unrecorded', 'pending': 'Pending', 'stale': 'Stale evidence',
    'expression': 'Expressions', 'mouth_state': 'Mouth', 'garment_recolor': 'Outfits',
    'details': 'Review and revision history', 'round': 'Round', 'asset': 'Version', 'quality': 'Quality',
    'target': 'Target', 'identity': 'Identity', 'protection': 'Protection', 'rendering': 'Rendering',
    'issues': 'Unmet criteria', 'component': 'Component', 'request': 'Request', 'source': 'Source',
    'domain': 'Final domain checks', 'check': 'Check', 'evidence': 'Observation',
    'limits': 'Inspection scope and limitations', 'preview': 'Final preview', 'history': 'Process evidence (inspection only)',
    'prompt': 'Submitted prompt', 'comparison': 'Comparison', 'none': 'None', 'report_only': 'No qualified final; report only',
    'next': 'Next step', 'next_exhausted': 'Stop generation. Change the editing strategy using these findings; further attempts require explicit authorization.',
    'next_blocked': 'Resolve missing or changed files/evidence before relying on the recorded scores.',
    'next_review': 'Complete this round’s quality and applicable fidelity review; no qualified final yet.',
    'next_revise': 'Revise the previous candidate using the recorded findings within the remaining authorized rounds.',
    'next_failed': 'Retain the candidate and findings; obtain an explicit attempt budget for a further revision.',
    'note': 'Scores and observations are from saved assistant/user reviews. This command validates records and gates, not visual quality. Passed images are ready for user review, not automatically accepted. Only listed projects and cases are covered.',
    'scope_note': 'Recorded full-image, target, protected-detail, normal-display and edge inspection flags appear below. Display size follows the original assessment; this command does not add game integration testing.',
    'canvas_note': 'Canvas mismatch is a preview-delivery warning; formal acceptance, selection and ZIP export retain the source-canvas requirement. Final PNG bytes are copied unchanged; preview scaling is for display only.',
    'snapshot': 'This report is a snapshot. Regenerate after subsequent file/project changes. Process images are not acceptance criteria.',
    'summary': 'Cases: {cases}; passed: {passed}; not delivered: {other}; candidates within scope: {images}.',
    'emotion': 'Emotion', 'face_design': 'Facial design', 'nonface_protection': 'Non-face protection',
    'target_color': 'Target color', 'garment_invariants': 'Garment construction/material', 'interfaces': 'Interfaces/exclusions',
    'face_expression': 'Face/expression', 'non_target_protection': 'Non-target protection',
    'full_image': 'Full image', 'target_detail': 'Target detail', 'protected_details': 'Protected details',
    'normal_display': 'Normal display', 'background_edges': 'Background/edges', 'inspection': 'Inspection coverage',
    'dimensions': 'Dimensions', 'technical': 'File validation', 'fidelity': 'Fidelity', 'checked': 'Checked', 'unchecked': 'Not checked',
    'round_unit': ' rounds', 'canvas_warning': 'Canvas differs (preview allowed)', 'not_applicable': 'N/A',
    'quality_stale': 'Prompt/comparison evidence changed; recorded scores cannot establish current passage.',
    'quality_pending': 'Quality review is incomplete.', 'quality_unrecorded': 'No quality review recorded.',
    'fidelity_pending': 'Fidelity review is incomplete.', 'user_rejected': 'The user rejected this version.',
}
EXPRESSION_ZH = dict(zip(
    ('neutral', 'happy', 'sad', 'angry', 'surprised', 'eyes_closed', 'shy', 'confused', 'wry_smile', 'worried', 'confident', 'crying'),
    ('平静', '开心', '悲伤', '生气', '惊讶', '闭眼', '害羞', '困惑', '苦笑', '担忧', '自信', '哭泣')))


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
    if 'outfit_id' in asset:
        return labels.get(asset['outfit_id'], f"{asset['target']} → {asset['color']}")
    label = labels.get(asset['expression'], EXPRESSION_ZH[asset['expression']] if language == 'zh-CN' else core.EXPRESSION_PRESETS[asset['expression']]['name'])
    mouth = asset.get('mouth_state', 'default')
    if mouth != 'default':
        suffix = labels.get('mouth_' + mouth, ('张嘴' if mouth == 'open' else '闭嘴') if language == 'zh-CN' else core.MOUTH_PRESETS[mouth]['name'])
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
        'recorded_score': review.get('result', {}).get('total'),
        'score_valid': bool(review) and quality != 'stale' and gate['passed'],
        'rubric': review.get('rubric_version'), 'basis': review.get('basis'),
        'dimensions': review.get('dimensions', {}), 'domain_review': review.get('domain_review'),
        'critical_defects': review.get('critical_defects', []), 'uncertainties': review.get('uncertainties', []),
        'fidelity_review': asset.get('fidelity_review'),
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
    issues += record['uncertainties']
    if not issues:
        issues += record['critical_defects']
        issues += [d['evidence'] for d in record['dimensions'].values() if d['score'] < 4]
    issues += [t.get(code, code) for code in record['issues'] if code in ('quality_stale','quality_pending','quality_unrecorded','fidelity_pending','user_rejected')]
    issues += record['validation']['errors'] if not record['score_valid'] else []
    if not issues and record['fidelity_status'] in ('failed','uncertain'):
        issues.append((record['fidelity_review'] or {}).get('note', record['fidelity_status']))
    return list(dict.fromkeys(issues))


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
            suffix = f"{t['passed']} · {len(case['history'])}{t['round_unit']} · {score_text(case['history'][-1],t)}/100 · " + suffix
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


def render_markdown(data: dict, output: Path, t: dict) -> str:
    lines = [f"# {md(data['title'])}", '', data['created_at'] + ' (UTC)', '',
             t['summary'].format(**data['summary']), '', '## '+t['overview'], '',
             '| '+' | '.join(t[k] for k in ('module','case','rounds','scores','status','final'))+' |',
             '|---|---|---:|---|---|---|']
    for c in data['cases']:
        final = link('PNG',output/c['final']['path']) if c['final'] else t['report_only']
        lines.append('| '+' | '.join((t[c['kind']],md(c['label']),str(len(c['history'])),
            ' → '.join(score_text(r,t) for r in c['history']),t[c['status']],final))+' |')
    if data['preview']:
        lines += ['',link(t['preview'],output/data['preview'])]
    for c in data['cases']:
        if not c['final']:
            lines += ['',f"**{md(c['label'])} — {t[c['status']]}**", '']
            issues = display_issues(c['history'][-1],t)
            lines += ['- '+md(issue) for issue in issues]
            if not issues and c.get('delivery_error'):
                lines.append('- '+md(c['delivery_error']['code']))
            lines += ['',t['next']+'：'+t.get('next_'+c['status'],t['next_failed'])]
    lines += ['', '## '+t['details'], '']
    for c in data['cases']:
        last = c['history'][-1]
        domain = last['domain_review'] or {}
        lines += ['### '+md(c['label']), '',t['source']+'：'+link(c['character'],c['source']),
                  '',t['request']+'：'+md(c['history'][0]['request'] or last['request'] or '—'),
                  '',t['component']+'：'+md(domain.get('component','—')), '',
                  '| '+' | '.join(t[k] for k in ('round','asset','target','identity','protection','rendering','scores','quality','fidelity'))+' |',
                  '|---:|---|---:|---:|---:|---:|---:|---|---|']
        for r in c['history']:
            dims = [str(r['dimensions'].get(k,{}).get('score','—')) for k in ('target','identity','protection','rendering')]
            fidelity = t['not_applicable'] if c['kind'] != 'garment_recolor' else t.get(r['fidelity_status'],r['fidelity_status'])
            lines.append('| '+' | '.join([str(r['round']),md(r['asset_id']),*dims,score_text(r,t),t.get(r['quality_status'],r['quality_status']),fidelity])+' |')
        lines += ['', '**'+t['domain']+'**', '', '| '+t['check']+' | '+t['status']+' | '+t['evidence']+' |', '|---|---|---|']
        for key,finding in domain.get('checks',{}).items():
            lines.append('| '+t.get(key,key)+' | '+t[finding['status']]+' | '+md(finding['evidence'])+' |')
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
                    language: str = 'zh-CN', title: str | None = None, labels: dict | None = None,
                    face_box: list[int] | None = None, background: str = 'light') -> dict:
    if language not in ('zh-CN','en') or background not in ('light','dark','checker'):
        raise core.StudioError('INVALID_REPORT_OPTIONS','Unsupported report language or preview background.')
    roots = [p.resolve() for p in projects]; output = output.resolve()
    if not roots or len(set(roots)) != len(roots) or (ids is not None and (len(roots)!=1 or not ids or len(ids)!=len(set(ids)))):
        raise core.StudioError('INVALID_REPORT_SCOPE','Use unique projects; explicit asset IDs require one project.')
    if output.exists():
        raise FileExistsError(output)
    t = ZH if language=='zh-CN' else EN
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
            if plan:
                asset=core.get_asset(state,plan['current_asset'])
                history=[core.get_asset(state,h['asset_id']) for h in plan['history']]
            else:
                asset=selected
                history=sorted((a for a in state['assets'] if core.asset_slot(a)==core.asset_slot(asset) and a['version']<=asset['version'] and not a.get('refinement_case')),key=lambda a:a['version'])
            slot=core.asset_slot(asset)
            if slot in slots:
                raise core.StudioError('INVALID_REPORT_SCOPE','Each case may appear once; a tracked asset selects its whole refinement case.')
            slots.add(slot)
            records=[round_record(core,root,state,a,i+1) for i,a in enumerate(history)]
            last=records[-1]
            action=plan['action'] if plan else ('review' if last['quality_status'] in ('pending','unrecorded') or last['fidelity_status']=='pending' else 'failed')
            delivered=None; error=None
            try:
                delivery=core.delivery_assets(root,[asset['id']])['delivery'][0]
                delivered={'path':f'final/{project_index:03d}_{asset["id"]}.png','original_image':str(core.contained(root,asset['path'])),'sha256':asset['sha256'],'canvas':delivery['canvas'],'warnings':delivery['warnings']}
                action='passed'
            except core.StudioError as exc:
                error={'code':exc.code,'message':exc.message}
                if plan and action=='deliver':
                    action='blocked'
                elif last['quality_status']=='stale' or 'ASSET_CHANGED' in last['validation']['errors'] or asset['art_review_status']=='rejected':
                    action='blocked'
                elif action=='failed' and last['quality_status']=='uncertain':
                    action='uncertain'
            cases.append({'project':str(root),'character':state['character_key'],'case_id':case_id or asset['id'],'kind':core.quality_domain(state,asset),
                          'label':label_for(core,asset,labels,language),'status':action,'max_rounds':plan['max_rounds'] if plan else None,
                          'source':str(core.contained(root,state['source'])),'source_sha256':state['source_sha256'],
                          'source_canvas':state['canvas'],'history':records,'final':delivered,'delivery_error':error})
        if state['source_sha256'] not in {s['sha256'] for s in sources}:
            sources.append({'label':labels.get('source',t['source']+' · '+state['character_key']),'image':str(core.contained(root,state['source'])),'sha256':state['source_sha256'],'canvas':state['canvas']})
    if not cases:
        raise core.StudioError('NO_REPORT_ASSETS','No candidates in the requested scope.')
    passed=sum(c['final'] is not None for c in cases)
    data={'schema_version':'1.0','created_at':core.timestamp(),'title':title or t['title'],'language':language,
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
                core.delivery_assets(Path(c['project']),[c['history'][-1]['asset_id']])
        if output.exists():
            raise FileExistsError(output)
        staging.rename(output)
    return {'report':str(output/'report.md'),'manifest':str(output/'report.json'),
            'preview':str(output/'preview.png') if passed else None,
            'images':[str(output/c['final']['path']) for c in cases if c['final']],
            'summary':data['summary']}
