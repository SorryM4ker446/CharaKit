"""Assemble reviewed deliverables and an evidence-based report; never generate or regrade art."""
from __future__ import annotations

import json
import math
from pathlib import Path
import tempfile

from PIL import Image, ImageDraw


ZH = {
    'prop_edit': '配饰／道具编辑', 'prop_action': '物件操作', 'prop_add': '添加', 'prop_remove': '移除', 'prop_replace': '替换',
    'target_object': '目标物件符合度', 'placement_contacts': '位置与接触关系',
    'occlusion_reconstruction': '遮挡与移除补全', 'anatomy_pose': '人体结构与姿势',
    'outfit_replace': '整套替换', 'outfit_design': '整套设计符合度', 'component_completion': '部件完成度',
    'ensemble_coherence': '整套搭配一致性', 'outfit_components': '服装部件清单', 'component_checks': '逐件检查',
    'user_revision': '按人工意见修订', 'revision_parent': '修订所依据版本', 'revision_note': '原始修改意见',
    'revision_attempt': '人工修订执行状态', 'revision_failed': '本次人工修订生成失败',
    'next_revision_failed': '保留失败原因；本次额度已用，新的生成需要具体的新修订请求。',
    'reserved': '已记录一次修订，待执行', 'imported': '修订图已保存，需重新评审', 'cancelled': '已被新的人工决定取消',
    'draft_title': '内部检查草稿', 'final_title': '最终评审报告',
    'draft_note': '尚有情况未完成人工评图。这是内部检查记录，不是最终评审报告，不含成品或打包输出。',
    'final_note': '本次候选池已记录实际人工意见；以下汇总人工选择、内部检查和 Codex 处理结果。',
    'awaiting_report': '已完成人评，等待汇总', 'next_awaiting_report': '其余情况完成人评后生成最终报告。',
    'user_declined': '用户未采用', 'next_user_declined': '保留评审记录，停止本批次，不打包。',
    'human_action': 'Codex 处理结果', 'accept': '采用', 'reject': '都不采用', 'revision_request': '按人工意见等待修订',
    'export': '满足交付条件，可打包', 'stopped': '已停止本批次', 'feedback_blocked': '保留人工意见，检查未通过，暂不能交付',
    'human_facets': '人工评价', 'fit': '需求符合度', 'preservation': '人物与细节保留', 'usability': '实际使用意愿',
    'title': '角色图像交付报告', 'overview': '结果概览', 'case': '情况', 'module': '模块',
    'rounds': '轮数', 'scores': '逐轮评分', 'status': '结果', 'final': '成品图',
    'passed': '通过', 'exhausted': '达到上限，未通过', 'blocked': '记录或文件失效',
    'review': '待评审', 'revise': '待修订', 'failed': '未通过', 'uncertain': '存在不确定项',
    'unrecorded': '未记录', 'pending': '待评审', 'stale': '证据失效',
    'expression': '表情', 'mouth_state': 'mouth', 'garment_recolor': 'outfits · 改色', 'garment_replace': 'outfits · 替换',
    'details': '评审与修订记录', 'round': '轮次', 'asset': '版本', 'quality': '质量',
    'target': '需求达成', 'identity': '角色一致性', 'protection': '非目标保留', 'integration': '结构与衔接', 'rendering': '画面完成度',
    'source_sample': '原图独立采样', 'repair_best': '修订择优候选', 'review_redraw': '按内部失败项重绘', 'redraw': '内部修订待生成', 'human_review': '等待人工评图',
    'next_redraw': '按本轮失败项在剩余轮次内重绘，重新检查全部五维及专项；通过或用完预算后再进入人工评图。',
    'compare': '内部候选比较待完成', 'generate_reserved': '已计次，等待本轮生成',
    'tool_failure': '出图调用失败', 'attempt_budget': '已用调用／上限',
    'next_exhausted_human': '停止生成，说明剩余失败项及调用失败原因，进入人工评图；不合格候选不能作为成品打包。',
    'human': '人工评审', 'next_human_review': '展示匿名评图页，记录用户采用、修改或拒绝的实际反馈，再处理交付。',
    'issues': '未通过项', 'component': '编辑部位', 'request': '请求', 'source': '原图',
    'domain': '最终专项检查', 'check': '检查项', 'evidence': '观察依据',
    'limits': '检查范围与限制', 'preview': '最终版预览', 'history': '过程证据（供查看）',
    'prompt': '实际提示词', 'comparison': '对照', 'none': '无', 'report_only': '无合格成品，仅报告',
    'next': '后续处理', 'next_exhausted': '停止自动生成；根据上述未通过项调整编辑策略，后续尝试需另行明确授权。',
    'next_blocked': '先检查缺失或变更的文件及评审证据，不能复用失效分数作为通过依据。',
    'next_review': '完成本轮评审与适用的保真检查；尚未形成合格成品。',
    'next_revise': '按 refine-status 返回的策略与参考图角色，在剩余授权轮数内修订并重新评审。',
    'next_failed': '保留当前候选及问题记录；需要修订时另行明确尝试次数。',
    'note': '分数与观察来自已保存的助手或用户评审；本命令只核对记录和门禁，不进行视觉评分。通过表示可供用户验收，不代表用户已接受。报告仅覆盖所列项目与情况。',
    'scope_note': '全图、目标细节、保护细节、正常展示和背景边缘的检查完成情况见下方记录；具体展示尺寸以原评审记录为准，本命令不新增游戏内验证。',
    'canvas_note': '画布差异仅作为预览交付警告；正式验收、选择及ZIP导出仍保留原画布要求。成品PNG按原字节复制，预览缩放仅用于展示。',
    'snapshot': '报告是生成时的快照；后续项目或文件变化需重新生成。过程图不作为验收标准。',
    'summary': '情况：{cases}；通过：{passed}；未交付：{other}；本报告范围内候选图：{images}。',
    'emotion': '情绪', 'face_design': '面部设计', 'nonface_protection': '非面部保护',
    'target_color': '目标颜色', 'garment_invariants': '衣物构造与材质', 'interfaces': '接口与排除区域',
    'target_garment': '替换款式与材质', 'fit_interfaces': '合身与交界', 'coverage_anatomy': '覆盖范围与人体结构',
    'edit_definition': '编辑方案', 'replace': '单件替换', 'recolor': '单件改色',
    'face_expression': '面部与表情', 'non_target_protection': '非目标保护',
    'full_image': '全图', 'target_detail': '目标细节', 'protected_details': '保护细节',
    'normal_display': '正常展示', 'background_edges': '背景与边缘', 'inspection': '检查完成情况',
    'dimensions': '尺寸', 'technical': '文件检查', 'fidelity': '保真', 'checked': '已检查', 'unchecked': '未检查',
    'round_unit': '轮', 'canvas_warning': '尺寸与原图不同（预览允许）', 'not_applicable': '不适用',
    'quality_stale': '提示词或对照证据已变更，原评分不能作为当前通过依据。',
    'quality_pending': '本轮质量评审尚未完成。', 'quality_unrecorded': '尚未记录质量评审。',
    'fidelity_pending': '本轮保真检查尚未完成。', 'user_rejected': '用户已拒绝此版本。',
    'blockers': '阻塞原因', 'threshold': '总分门槛', 'dimension_floor': '分项下限',
    'gate_note': '总分达标不等于通过：还需各分项达标、专项检查全部通过，以及评审证据和适用的保真／文件检查有效。轻微笔触变化可接受；身份或结构误改仍须修复。',
    'strategy': '生成策略', 'initial': '首版', 'continue_previous': '修订上一版', 'source_rebase': '从原图重做目标衣物',
}
EN = {
    'prop_edit': 'Accessory/prop editing', 'prop_action': 'Object operation', 'prop_add': 'Add', 'prop_remove': 'Remove', 'prop_replace': 'Replace',
    'target_object': 'Target object adherence', 'placement_contacts': 'Placement and contacts',
    'occlusion_reconstruction': 'Occlusion and reconstruction', 'anatomy_pose': 'Anatomy and pose',
    'outfit_replace': 'Full outfit replacement', 'outfit_design': 'Outfit design adherence', 'component_completion': 'Component completion',
    'ensemble_coherence': 'Ensemble coherence', 'outfit_components': 'Clothing component inventory', 'component_checks': 'Component findings',
    'user_revision': 'Revise from human feedback', 'revision_parent': 'Revision parent', 'revision_note': 'Original correction request',
    'revision_attempt': 'Human revision execution', 'revision_failed': 'Human revision generation failed',
    'next_revision_failed': 'Retain the failure; the attempt is spent. Another image requires a specific new revision request.',
    'reserved': 'One revision recorded; awaiting execution', 'imported': 'Revision saved; fresh review required', 'cancelled': 'Cancelled by a newer human decision',
    'draft_title': 'Internal inspection draft', 'final_title': 'Final review report',
    'draft_note': 'Some cases await actual human feedback. This internal inspection draft is not a final report and contains no final assets or package.',
    'final_note': 'Actual human decisions have been recorded for the candidate pools. This report combines their feedback, internal findings and Codex disposition.',
    'awaiting_report': 'Reviewed; awaiting remaining cases', 'next_awaiting_report': 'Complete human review of remaining cases before the final report.',
    'user_declined': 'User declined', 'next_user_declined': 'Retain feedback and stop this batch without packaging.',
    'human_action': 'Codex disposition', 'accept': 'Accept', 'reject': 'Reject all', 'revision_request': 'Revision requested',
    'export': 'Eligible for packaging', 'stopped': 'Batch stopped', 'feedback_blocked': 'Feedback retained; checks block delivery',
    'human_facets': 'Human ratings', 'fit': 'Request fit', 'preservation': 'Character/detail preservation', 'usability': 'Usability',
    'title': 'Character image delivery report', 'overview': 'Results', 'case': 'Case', 'module': 'Module',
    'rounds': 'Rounds', 'scores': 'Scores by round', 'status': 'Result', 'final': 'Final PNG',
    'passed': 'Passed', 'exhausted': 'Limit reached; failed', 'blocked': 'Invalid records or files',
    'review': 'Review pending', 'revise': 'Revision pending', 'failed': 'Failed', 'uncertain': 'Uncertain',
    'unrecorded': 'Unrecorded', 'pending': 'Pending', 'stale': 'Stale evidence',
    'expression': 'Expressions', 'mouth_state': 'Mouth', 'garment_recolor': 'Outfits',
    'details': 'Review and revision history', 'round': 'Round', 'asset': 'Version', 'quality': 'Quality',
    'target': 'Target', 'identity': 'Identity', 'protection': 'Protection', 'integration': 'Integration', 'rendering': 'Rendering',
    'source_sample': 'Independent source sample', 'repair_best': 'Repair preferred candidate', 'review_redraw': 'Redraw from internal findings', 'redraw': 'Internal redraw pending', 'human_review': 'Human review pending',
    'next_redraw': 'Correct recorded failures within the remaining rounds and reassess all five dimensions and domain checks before human review.',
    'compare': 'Internal comparison pending', 'generate_reserved': 'Attempt reserved; generation pending',
    'tool_failure': 'Image-tool failure', 'attempt_budget': 'Attempts used / limit',
    'next_exhausted_human': 'Stop generation, explain unresolved checks and failed calls, then present anonymous human review. Failed candidates cannot be packaged as final artwork.',
    'human': 'Human review', 'next_human_review': 'Present anonymous review and record the actual user decision before delivery.',
    'issues': 'Unmet criteria', 'component': 'Component', 'request': 'Request', 'source': 'Source',
    'domain': 'Final domain checks', 'check': 'Check', 'evidence': 'Observation',
    'limits': 'Inspection scope and limitations', 'preview': 'Final preview', 'history': 'Process evidence (inspection only)',
    'prompt': 'Submitted prompt', 'comparison': 'Comparison', 'none': 'None', 'report_only': 'No qualified final; report only',
    'next': 'Next step', 'next_exhausted': 'Stop generation. Change the editing strategy using these findings; further attempts require explicit authorization.',
    'next_blocked': 'Resolve missing or changed files/evidence before relying on the recorded scores.',
    'next_review': 'Complete this round’s quality and applicable fidelity review; no qualified final yet.',
    'next_revise': 'Follow refine-status strategy and reference roles within the remaining authorized rounds, then review again.',
    'next_failed': 'Retain the candidate and findings; obtain an explicit attempt budget for a further revision.',
    'note': 'Scores and observations are from saved assistant/user reviews. This command validates records and gates, not visual quality. Passed images are ready for user review, not automatically accepted. Only listed projects and cases are covered.',
    'scope_note': 'Recorded full-image, target, protected-detail, normal-display and edge inspection flags appear below. Display size follows the original assessment; this command does not add game integration testing.',
    'canvas_note': 'Canvas mismatch is a preview-delivery warning; formal acceptance, selection and ZIP export retain the source-canvas requirement. Final PNG bytes are copied unchanged; preview scaling is for display only.',
    'snapshot': 'This report is a snapshot. Regenerate after subsequent file/project changes. Process images are not acceptance criteria.',
    'summary': 'Cases: {cases}; passed: {passed}; not delivered: {other}; candidates within scope: {images}.',
    'emotion': 'Emotion', 'face_design': 'Facial design', 'nonface_protection': 'Non-face protection',
    'target_color': 'Target color', 'garment_invariants': 'Garment construction/material', 'interfaces': 'Interfaces/exclusions',
    'garment_replace': 'Outfits · replacement', 'target_garment': 'Replacement design/material',
    'fit_interfaces': 'Fit/interfaces', 'coverage_anatomy': 'Coverage/anatomy',
    'edit_definition': 'Edit definition', 'replace': 'Single-garment replacement', 'recolor': 'Single-garment recolor',
    'face_expression': 'Face/expression', 'non_target_protection': 'Non-target protection',
    'full_image': 'Full image', 'target_detail': 'Target detail', 'protected_details': 'Protected details',
    'normal_display': 'Normal display', 'background_edges': 'Background/edges', 'inspection': 'Inspection coverage',
    'dimensions': 'Dimensions', 'technical': 'File validation', 'fidelity': 'Fidelity', 'checked': 'Checked', 'unchecked': 'Not checked',
    'round_unit': ' rounds', 'canvas_warning': 'Canvas differs (preview allowed)', 'not_applicable': 'N/A',
    'quality_stale': 'Prompt/comparison evidence changed; recorded scores cannot establish current passage.',
    'quality_pending': 'Quality review is incomplete.', 'quality_unrecorded': 'No quality review recorded.',
    'fidelity_pending': 'Fidelity review is incomplete.', 'user_rejected': 'The user rejected this version.',
    'blockers': 'Blocking reasons', 'threshold': 'Total threshold', 'dimension_floor': 'Dimension floor',
    'gate_note': 'Meeting the total threshold alone does not pass: each dimension, all domain checks, current review evidence and applicable fidelity/file gates must also pass. Minor brushwork variation is acceptable; identity or structural changes still require correction.',
    'strategy': 'Generation strategy', 'initial': 'Initial image', 'continue_previous': 'Revise previous image', 'source_rebase': 'Reapply garment edit to source',
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
        if asset['edit_type'] == 'prop_edit':
            t = ZH if language == 'zh-CN' else EN
            name = t['prop_'+asset['prop_action']]+' · '+asset['target']
            if 'replacement' in asset:
                name += ' → '+asset['replacement']
            return labels.get(asset['outfit_id'], name)
        change = asset['color'] if asset['edit_type'] == 'recolor' else asset['replacement']
        return labels.get(asset['outfit_id'], f"{asset['target']} → {change}")
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
    issues += record['validation']['errors'] if not record['score_valid'] else []
    if not issues and record['fidelity_status'] in ('failed','uncertain'):
        issues.append((record['fidelity_review'] or {}).get('note', record['fidelity_status']))
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
    reasons.extend(code for code in record['validation']['errors'] if code != 'CANVAS_MISMATCH')
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
    for c in data['cases']:
        if not c['final']:
            lines += ['',f"**{md(c['label'])} — {t[c['status']]}**", '']
            issues = display_issues(case_record(c),t)
            lines += ['- '+md(issue) for issue in issues]
            if not issues and c.get('delivery_error'):
                lines.append('- '+md(c['delivery_error']['code']))
            next_step = ('按实际人工意见处理修订请求；本报告不自动新增生成次数。' if data['language']=='zh-CN' else 'Handle the actual revision request; this report does not authorize additional generation.') if (c.get('human_result') or {}).get('next_action')=='revision_request' and c['status']!='revision_failed' else t.get('next_'+c['status'],t['next_failed'])
            if c['status']=='exhausted' and (c.get('candidate_pool') or {}).get('version')=='1.1' and not c.get('human_result'):
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
            change = t['prop_remove'] if edit.get('prop_action') == 'remove' else edit.get('replacement', edit.get('color', '—'))
            lines += [t['edit_definition']+'：'+t[edit['edit_type']]+' · '+md(edit['target'])+' → '+md(change), '']
            if edit.get('prop_action'):
                lines += [t['prop_action']+'：'+t['prop_'+edit['prop_action']], '']
            if edit.get('outfit_components'):
                lines += ['**'+t['outfit_components']+'**', '']
                lines += ['- '+md(item['source'])+' → '+md(item['replacement']) for item in edit['outfit_components']]
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
                    language: str = 'zh-CN', title: str | None = None, labels: dict | None = None,
                    face_box: list[int] | None = None, background: str = 'light', stage: str = 'auto') -> dict:
    if language not in ('zh-CN','en') or background not in ('light','dark','checker') or stage not in ('auto','final'):
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
            internal_plan = core.workflow_call('pool_status',root,pool_id) if pool_id and pool['version']=='1.1' else None
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
            cases.append({'project':str(root),'character':state['character_key'],'case_id':pool_id or case_id or asset['id'],'kind':core.quality_domain(state,asset),
                          'requested_revision':requested_revision,
                          'human_revision':state.get('human_revisions',{}).get(asset.get('human_revision')),
                          'revision_parent_image':str(core.contained(root,core.get_asset(state,state['human_revisions'][asset['human_revision']]['parent_asset'])['path'])) if asset.get('human_revision') else None,
                          'human_feedback':feedback or asset.get('human_feedback'), 'human_result':human_result,
                          'assessed_asset_id':asset['id'], 'candidate_pool':state.get('candidate_pools',{}).get(pool_id),
                          'label':label_for(core,asset,labels,language),'status':action,'max_rounds':pool['budget'] if pool_id else plan['max_rounds'] if plan else None,
                          'attempt_count':len(pool['attempts']) if pool_id else len(records),
                          'edit':{key:asset[key] for key in ('edit_type','target','color','replacement','outfit_components','prop_action','edit_brief') if key in asset} if 'outfit_id' in asset else None,
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
            'images':[str(output/c['final']['path']) for c in cases if c['final']],
            'summary':data['summary']}
