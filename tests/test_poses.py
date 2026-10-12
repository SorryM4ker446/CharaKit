"""Static pose workflow tests with synthetic images; no generated-art quality claims."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

from test_outfits import REPO, builder, fixture, outfits
from test_studio import studio
from test_candidate_review import contract
from test_quality import assessment

SCRIPT = REPO / 'plugins/charakit/skills/charakit-poses/scripts/studio.py'
spec = importlib.util.spec_from_file_location('poses', SCRIPT)
poses = importlib.util.module_from_spec(spec)
spec.loader.exec_module(poses)


class PoseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name) / '姿势测试'
        self.folder.mkdir()
        self.root = self.folder / '项目'
        self.source = self.folder / '原图.png'
        self.raw = self.folder / '候选.png'
        fixture(self.source)
        fixture(self.raw, '#334477')
        self.prompt = self.folder / 'prompt.txt'
        self.prompt.write_text('Synthetic pose request, retain expression and clothing design.', encoding='utf-8')
        poses.init_project(self.root, self.source, 'test_character')

    def call(self, name, *args, **kwargs):
        return poses.workflow_call(name, *args, **kwargs)

    def code(self, expected, fn, *args, **kwargs):
        with self.assertRaises(poses.StudioError) as error:
            fn(*args, **kwargs)
        self.assertEqual(error.exception.code, expected)

    def prepare(self, preset='wave', side='right', option=None, **kwargs):
        option = option or preset + '_' + side
        return poses.prepare_pose(self.root, option, preset, side,
                                  '自然站立' if preset == 'natural_standing' else '角色自身' + side + '手的' + preset,
                                  '手臂动作及必要衣褶、关节、接触、遮挡；其余设计保留',
                                  ['五官表情、嘴形、服装设计、道具、原画风、画布'],
                                  [10, 30, 85, 120], **kwargs)

    def candidate(self, preset='wave', side='right', option=None, budget=1, reference_file=None, image=None):
        brief = self.prepare(preset, side, option, reference_file=reference_file, anchors=['保持脚底基线'])
        asset = poses.add_asset(self.root, image or self.raw, brief['edit_brief']['pose_id'], self.prompt,
                                Path(brief['brief_file']), [Path(p) for p in brief['reference_paths']])['asset']
        checks = contract()
        checks[0].update(component=asset['target'], expected='按已记录侧别、手形和幅度完成动作')
        for ref in asset.get('edit_references', []):
            checks.append(dict(id='ref_'+ref['id'], dimension='target', component=ref['id'],
                               property='动作结构', expected=ref['notes'], view='target_detail'))
        self.call('pool_start', self.root, asset['id'], checks, budget)
        return asset

    def evidence(self, asset):
        page = self.call('review_sheet', self.root, [asset['id']], 'assistant')
        state = poses.read_state(self.root)
        current = poses.get_asset(state, asset['id'])
        data = assessment(scores=dict.fromkeys(poses.QUALITY_WEIGHTS_V12, 5), domain='pose_edit')
        data.update(rubric_version='1.2', criteria=copy.deepcopy(state['candidate_pools'][current['candidate_pool']]['contract']),
                    normal_display_height=420, blind_packet=page['packet'])
        data['domain_review'].update(pose=asset['pose'], side=asset['side'], component=asset['target'])
        for check in data['criteria']:
            check.update(observed='Synthetic fixture observation only.', status='passed', score=5)
        preview = self.root / 'preview' / (asset['id']+'.png')
        poses.make_preview(self.root, preview, [asset['id']])
        return data, preview

    def review(self, asset, mutate=None, protection='passed'):
        data, preview = self.evidence(asset)
        if mutate:
            mutate(data)
        poses.record_fidelity(self.root, asset['id'], 'passed', protection, 'Synthetic target and design protection finding.')
        return poses.record_quality(self.root, asset['id'], data, [preview])

    def feedback(self, asset, decision='accept', inspection=None):
        page = self.call('review_sheet', self.root, [asset['id']], 'user', inspection=inspection)
        packet = poses.read_state(self.root)['review_packets'][page['packet']]
        alias = next(k for k, v in packet['items'].items() if v['asset_id'] == asset['id'])
        result = self.call('human_feedback', self.root, dict(packet=page['packet'], basis='user', candidate=alias,
                          decision=decision, note='修正手指，保留姿势' if decision == 'revise' else '采用这个版本'))
        return page, result

    def reference(self, scope='pose'):
        image = self.folder / 'reference.png'
        fixture(image, '#884422')
        raw = self.folder / 'refs.json'
        raw.write_text(json.dumps([dict(id='gesture', path=str(image), scope=[scope], notes='仅手掌朝向和动作结构')]), encoding='utf-8')
        return Path(poses.reference_call('prepare', self.root, raw)['reference_file'])

    def compare(self, case_id, preferred):
        state = poses.read_state(self.root)
        ids = [a['id'] for a in state['assets'] if a.get('candidate_pool') == case_id]
        page = self.call('review_sheet', self.root, ids, 'assistant')
        packet = poses.read_state(self.root)['review_packets'][page['packet']]
        alias = next(k for k, v in packet['items'].items() if v['asset_id'] == preferred)
        return self.call('compare', self.root, case_id, dict(packet=page['packet'], basis='assistant',
                         preferred=alias, repairable=False, evidence='Synthetic comparison of actual fixture gates.'))

    def test_all_presets_and_both_sides_end_to_end_raw_exports_and_bilingual_reports(self):
        for preset in poses.POSES:
            for side in (('none',) if preset == 'natural_standing' else ('left', 'right')):
                with self.subTest(preset=preset, side=side):
                    asset = self.candidate(preset, side)
                    self.review(asset)
                    self.code('HUMAN_REVIEW_REQUIRED', poses.review_asset, self.root, asset['id'], 'accepted')
                    draft = poses.generate_report([self.root], self.folder / (asset['id']+'_draft'), ids=[asset['id']])
                    self.assertEqual((draft['stage'], draft['images']), ('draft', []))
                    page, result = self.feedback(asset)
                    self.assertEqual(result['next_action'], 'export')
                    self.assertEqual(page['inspection']['regions'], [])
                    export = poses.export_pack(self.root, ids=[asset['id']])
                    self.assertEqual(export['manifest']['asset_kind'], 'full_character_pose')
                    self.assertEqual(export['manifest']['schema_version'], '3.0')
                    sprite = export['manifest']['sprites'][0]
                    self.assertEqual((sprite['pose'], sprite['side']), (preset, side))
                    self.assertEqual(sprite['generation_inputs']['references'][0]['role'], 'immutable_source')
                    self.assertIn('/poses/', sprite['path'])
                    with zipfile.ZipFile(export['export']) as archive:
                        self.assertEqual(archive.read(sprite['path']), self.raw.read_bytes())
                    for language in ('zh-CN', 'en'):
                        report = poses.generate_report([self.root], self.folder / (asset['id']+'_'+language), ids=[asset['id']], language=language, stage='final')
                        self.assertEqual(Path(report['images'][0]).read_bytes(), self.raw.read_bytes())
                        text = Path(report['report']).read_text(encoding='utf-8')
                        self.assertIn('肢体与关节' if language == 'zh-CN' else 'Limbs and joints', text)
                        self.assertIn('脚底基线', text)

    def test_scope_side_and_coordinates_fail_before_writing(self):
        before = (self.root / 'run.json').read_bytes()
        for preset, side in [('wave', 'none'), ('natural_standing', 'left'), ('combat', 'right'), ('wave', 'screen_right')]:
            self.code('INVALID_POSE', self.prepare, preset, side)
        self.code('INVALID_EDIT_BRIEF', poses.prepare_pose, self.root, 'wave', 'wave', 'right', 'wave', 'arms', ['face'], [0, 0, 1000, 1000])
        self.assertFalse((self.root / 'briefs').exists())
        self.assertEqual((self.root / 'run.json').read_bytes(), before)

    def test_prompt_brief_and_actual_input_bindings_are_required(self):
        brief = self.prepare()
        args = (self.root, self.raw, 'wave_right')
        self.code('INVALID_EDIT_BRIEF', poses.add_asset, *args, self.prompt)
        self.code('INVALID_GENERATION_REFERENCES', poses.add_asset, *args, self.prompt, Path(brief['brief_file']))
        self.code('POSE_PROMPT_REQUIRED', poses.add_asset, *args, None, Path(brief['brief_file']), [self.root/'source.png'])
        self.code('INVALID_EDIT_BRIEF', poses.add_asset, self.root, self.raw, 'wrong_id', self.prompt, Path(brief['brief_file']), [self.root/'source.png'])
        self.assertEqual(poses.read_state(self.root)['assets'], [])

    def test_definition_is_immutable_and_projects_remain_independent(self):
        asset = self.candidate()
        self.code('POSE_DEFINITION_CHANGED', self.prepare, 'wave', 'left', 'wave_right')
        self.code('WRONG_MODULE', poses.prepare_outfit, self.root, 'coat', 'coat', 'red', 'fabric', ['face'], [10,30,85,120])
        self.code('WRONG_MODULE', poses.add_outfit, self.root, self.raw, 'coat', 'coat', 'red')
        self.code('WRONG_MODULE', poses.add_asset.__globals__['_core'].add_asset, self.root, self.raw, 'happy')
        for module in ('expressions', 'outfits'):
            root = self.folder / module
            poses.init_project.__globals__['_core'].init_project(root, self.source, 'test_character', module=module)
            self.code('WRONG_MODULE', poses.prepare_pose, root, 'wave', 'wave', 'left', 'wave', 'arms', ['face'], [10,30,85,120])
        self.assertEqual(poses.read_state(self.root)['assets'][0]['id'], asset['id'])

    def test_wrong_domain_side_or_old_rubric_cannot_pass(self):
        asset = self.candidate()
        original, preview = self.evidence(asset)
        for mutation in ('side', 'pose', 'missing_check', 'old_rubric', 'domain'):
            data = copy.deepcopy(original)
            if mutation == 'side': data['domain_review']['side'] = 'left'
            elif mutation == 'pose': data['domain_review']['pose'] = 'palm_up'
            elif mutation == 'missing_check': data['domain_review']['checks'].pop('contacts')
            elif mutation == 'old_rubric': data.update(rubric_version='1.1', dimensions=assessment()['dimensions'])
            else: data['domain_review'] = assessment()['domain_review']
            self.code('INVALID_DOMAIN_REVIEW', poses.record_quality, self.root, asset['id'], data, [preview])

    def test_every_pose_domain_failure_and_uncertainty_vetoes_high_total(self):
        for key in poses.DOMAIN_CHECKS['pose_edit']:
            for status in ('failed', 'uncertain'):
                with self.subTest(check=key, status=status):
                    asset = self.candidate(option='check_'+key+'_'+status)
                    result = self.review(asset, lambda data: data['domain_review']['checks'][key].update(status=status))
                    self.assertNotEqual(result['quality_status'], 'passed')
                    self.assertEqual(result['score']['total'], 100)
                    _, feedback = self.feedback(asset)
                    self.assertEqual(feedback['next_action'], 'blocked')
                    self.assertNotIn(asset['pose_id'], poses.read_state(self.root)['selected'])

    def test_failed_protection_overrides_quality_and_user_preference(self):
        asset = self.candidate()
        self.review(asset, protection='failed')
        _, feedback = self.feedback(asset)
        self.assertEqual(feedback['next_action'], 'blocked')
        self.assertEqual(poses.read_state(self.root)['selected'], {})

    def test_redraw_retains_pose_and_fixed_budget_and_shows_failed_rounds(self):
        asset = self.candidate(budget=2)
        self.review(asset, lambda data: data['domain_review']['checks']['limbs_joints'].update(status='failed'))
        plan = self.call('pool_reserve', self.root, asset['id'])
        next_asset = self.call('pool_import', self.root, asset['id'], plan['token'], self.raw, self.prompt, [Path(p) for p in plan['reference_paths']])['asset']
        self.assertEqual(next_asset['pose'], asset['pose'])
        self.assertEqual(next_asset['edit_brief'], asset['edit_brief'])
        self.review(next_asset)
        self.compare(asset['id'], next_asset['id'])
        page = self.call('review_sheet', self.root, [next_asset['id']], 'user')
        self.assertEqual(len(page['candidates']), 2)
        self.code('POOL_NOT_READY', self.call, 'pool_reserve', self.root, asset['id'])
        self.assertEqual(poses.read_state(self.root)['candidate_pools'][asset['id']]['budget'], 2)

    def test_reference_scope_inputs_and_revision_continuity(self):
        asset = self.candidate(reference_file=self.reference())
        self.review(asset)
        page, _ = self.feedback(asset, 'revise')
        state = poses.read_state(self.root)
        old_pool = copy.deepcopy(state['candidate_pools'][asset['id']])
        revision = self.call('revision_prepare', self.root, page['packet'], old_pool['contract'], 2)
        self.assertEqual([r['role'] for r in revision['references']], ['edit_target', 'immutable_source', 'edit_reference'])
        self.assertEqual(revision['edit']['side'], 'right')
        imported = self.call('revision_import', self.root, page['packet'], self.raw, self.prompt, [Path(p) for p in revision['reference_paths']])['asset']
        self.assertEqual(imported['edit_brief'], asset['edit_brief'])
        self.assertEqual(imported['edit_references'], asset['edit_references'])
        data, comparison = self.evidence(imported)
        self.assertTrue({'revision_continuity','source_protection_recheck'} <= {x['id'] for x in data['criteria']})
        poses.record_fidelity(self.root, imported['id'], 'passed', 'passed', 'Synthetic continuity.')
        poses.record_quality(self.root, imported['id'], data, [comparison])
        detail = [dict(id='hand', box=[5,20,90,130], label='手与关节', reason='当前动作及前后版本中可见位置')]
        final_page, result = self.feedback(imported, inspection=detail)
        self.assertEqual(final_page['inspection']['comparison_base'], 'parent')
        self.assertEqual(result['next_action'], 'export')
        report = poses.generate_report([self.root], self.folder/'revision_final', ids=[imported['id']], stage='final')
        manifest = json.loads(Path(report['manifest']).read_text(encoding='utf-8'))
        self.assertEqual(manifest['cases'][0]['inspection_regions'], detail)
        self.assertEqual(manifest['cases'][0]['detail_previews'][0]['box'], detail[0]['box'])
        state = poses.read_state(self.root)
        self.assertEqual(state['candidate_pools'][asset['id']], old_pool)
        self.assertEqual(state['candidate_pools'][imported['id']]['budget'], 2)

    def test_references_cannot_authorize_face_clothes_or_wrong_input_order(self):
        for scope in ('expression', 'target', 'face'):
            self.code('INVALID_EDIT_REFERENCES', self.prepare, reference_file=self.reference(scope))
        brief = self.prepare(reference_file=self.reference())
        refs = [Path(p) for p in brief['reference_paths']]
        self.code('INVALID_GENERATION_REFERENCES', poses.add_asset, self.root, self.raw, 'wave_right', self.prompt, Path(brief['brief_file']), list(reversed(refs)))
        self.assertEqual(poses.read_state(self.root)['assets'], [])

    def test_source_only_human_revision_and_its_redraw_keep_chosen_baseline(self):
        asset = self.candidate()
        self.review(asset)
        page, _ = self.feedback(asset, 'revise')
        checks = poses.read_state(self.root)['candidate_pools'][asset['id']]['contract']
        revision = self.call('revision_prepare', self.root, page['packet'], checks, 2)
        child = self.call('revision_import', self.root, page['packet'], self.raw, self.prompt, [Path(p) for p in revision['reference_paths']])['asset']
        self.review(child, lambda data: data['domain_review']['checks']['contacts'].update(status='failed'))
        plan = self.call('pool_reserve', self.root, child['id'])
        self.assertEqual([r['role'] for r in plan['references']], ['edit_target', 'immutable_source'])
        corrected = self.call('pool_import', self.root, child['id'], plan['token'], self.raw, self.prompt, [Path(p) for p in plan['reference_paths']])['asset']
        self.assertEqual(corrected['pose'], asset['pose'])
        self.review(corrected)
        self.compare(child['id'], corrected['id'])
        _, result = self.feedback(corrected)
        self.assertEqual(result['next_action'], 'export')
        self.assertEqual(poses.read_state(self.root)['candidate_pools'][child['id']]['budget'], 2)

    def test_failed_tool_call_consumes_remaining_budget_without_inventing_candidate(self):
        asset = self.candidate(budget=2)
        self.review(asset, lambda data: data['domain_review']['checks']['target_pose'].update(status='failed'))
        plan = self.call('pool_reserve', self.root, asset['id'])
        result = self.call('pool_import', self.root, asset['id'], plan['token'], None, None, [], failure='Synthetic tool failure.')
        self.assertEqual((result['used'], result['budget'], result['action']), (2, 2, 'exhausted'))
        self.assertEqual(len(poses.read_state(self.root)['assets']), 1)
        page = self.call('review_sheet', self.root, [asset['id']], 'user')
        self.assertEqual(len(page['review_summary']['failed_calls']), 1)
        self.code('POOL_NOT_READY', self.call, 'pool_reserve', self.root, asset['id'])

    def test_changed_source_detail_or_pose_reference_blocks_reliance_on_it(self):
        ref_file = self.reference()
        brief = self.prepare(reference_file=ref_file)
        detail = Path(brief['detail_reference'])
        original = detail.read_bytes()
        detail.write_bytes(b'changed')
        self.code('REFERENCE_CHANGED', poses.add_asset, self.root, self.raw, 'wave_right', self.prompt, Path(brief['brief_file']), [Path(p) for p in brief['reference_paths']])
        detail.write_bytes(original)
        asset = poses.add_asset(self.root, self.raw, 'wave_right', self.prompt, Path(brief['brief_file']), [Path(p) for p in brief['reference_paths']])['asset']
        reference = self.root / asset['edit_references'][0]['path']
        reference.write_bytes(b'changed')
        self.assertIn('EDIT_REFERENCE_CHANGED', poses.check_asset(self.root, poses.read_state(self.root), asset)['errors'])

    def test_no_legacy_refinement_or_untracked_quality_bypass(self):
        brief = self.prepare()
        asset = poses.add_asset(self.root, self.raw, 'wave_right', self.prompt, Path(brief['brief_file']), [self.root/'source.png'])['asset']
        self.code('POOL_IMPORT_REQUIRED', poses.start_refinement, self.root, asset['id'])
        checks = contract()
        self.code('INVALID_CANDIDATE_REVIEW', self.call, 'pool_start', self.root, asset['id'], checks)
        data = assessment(scores=dict.fromkeys(poses.QUALITY_WEIGHTS_V12, 5), domain='pose_edit')
        data.update(rubric_version='1.2', criteria=checks, normal_display_height=420, blind_packet='not_real')
        data['domain_review'].update(pose='wave', side='right')
        for check in checks: check.update(score=5, status='passed', observed='Synthetic finding.')
        self.code('POOL_IMPORT_REQUIRED', poses.record_quality, self.root, asset['id'], data, [])

    def test_raw_canvas_mismatch_is_reviewable_but_never_exported(self):
        wrong = self.folder / 'wrong.png'
        fixture(wrong, size=(110,160))
        asset = self.candidate(image=wrong)
        self.assertIn('CANVAS_MISMATCH', asset['validation']['errors'])
        self.review(asset)
        _, result = self.feedback(asset)
        self.assertEqual(result['next_action'], 'blocked')
        self.assertEqual((self.root / asset['path']).read_bytes(), wrong.read_bytes())

    def test_source_reuse_stays_reviewed_and_attributable(self):
        asset = self.candidate('natural_standing', 'none', image=self.source)
        self.assertEqual(asset['origin'], 'source_reuse')
        self.review(asset)
        _, result = self.feedback(asset)
        self.assertEqual(result['next_action'], 'export')

    def test_tampered_pose_and_provenance_metadata_are_rejected(self):
        asset = self.candidate()
        state = poses.read_state(self.root)
        for field, value in [('side','left'), ('pose','palm_up'), ('expression','happy'), ('generation_inputs',{})]:
            changed = copy.deepcopy(state)
            changed['assets'][0][field] = value
            poses.write_state(self.root, changed)
            self.code('INVALID_PROJECT', poses.read_state, self.root)
        poses.write_state(self.root, state)
        self.assertEqual(poses.read_state(self.root)['assets'][0]['id'], asset['id'])

    def test_packaged_entrypoint_operates_away_from_repository(self):
        archive = self.folder / 'plugin.zip'
        builder.build(REPO, archive)
        installed = self.folder / '独立安装'
        with zipfile.ZipFile(archive) as package:
            package.extractall(installed)
        script = installed / 'skills/charakit-poses/scripts/studio.py'
        def run(*args):
            result = subprocess.run([sys.executable, str(script), *map(str,args)], cwd=self.folder, capture_output=True, encoding='utf-8')
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)
        self.assertEqual(len(run('presets')['presets']), 4)
        root = self.folder / 'CLI 项目'
        run('init','--project',root,'--source',self.source,'--character','test_character')
        brief = run('prepare','--project',root,'--pose-id','wave_right','--pose','wave','--side','right',
                    '--target','右手招呼','--boundary','手臂及衣褶','--protect','五官服装设计','--target-box',10,30,85,120)
        added = run('add','--project',root,'--pose-id','wave_right','--image',self.raw,'--prompt-file',self.prompt,
                    '--brief-file',brief['brief_file'],'--reference',root/'source.png')
        self.assertEqual(added['asset']['pose'], 'wave')
        self.assertEqual(run('status','--project',root)['assets'][0]['fidelity_status'], 'pending')


if __name__ == '__main__':
    unittest.main()
