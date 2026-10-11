"""Shared reference lineage and gates using synthetic images, not visual-quality scores."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

from test_studio import studio, fixture
from test_outfits import outfits, builder, REPO
from test_candidate_review import contract
from test_quality import assessment


class EditReferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name) / '共享参考测试'
        self.folder.mkdir()
        self.source = self.folder / '原图.png'; fixture(self.source)
        self.ref = self.folder / '参考.png'; fixture(self.ref, color='#887766')
        self.raw = self.folder / '生成.png'; fixture(self.raw, color='#336699')
        self.prompt = self.folder / '提示词.txt'
        self.prompt.write_text('合成工作流测试：仅参考指定属性，保护原图其他内容。', encoding='utf-8')
        self.inputs = self.folder / '参考输入.json'

    def setup_mode(self, mode='expression', mouth='default'):
        self.mode = mode
        self.root = self.folder / (mode + '_' + mouth)
        self.c = studio if mode == 'expression' else outfits
        self.c.init_project(self.root, self.source, 'test_character')
        scope = ['expression', 'mouth'] if mode == 'expression' and mouth != 'default' else ['expression'] if mode == 'expression' else ['upper', 'lower'] if mode == 'outfit_replace' else ['target']
        self.inputs = self.folder / '参考输入.json'
        self.inputs.write_text(json.dumps([dict(id='design_ref', path=self.ref.name, scope=scope, notes='仅参考指定编辑属性')], ensure_ascii=False), encoding='utf-8')
        self.prepared = self.c.reference_call('prepare', self.root, self.inputs)
        self.refs = [Path(p) for p in self.prepared['reference_paths']]
        self.add_kwargs = dict(prompt_file=self.prompt)
        if mode == 'expression':
            self.add_args = [self.root, self.raw, 'happy']
            self.add_kwargs.update(mouth_state=mouth, reference_file=Path(self.prepared['reference_file']))
        else:
            options = dict(edit_type=mode, replacement='参考设计')
            color = None
            if mode == 'recolor':
                options.pop('replacement'); color = '白色'
            if mode == 'outfit_replace':
                options['outfit_components'] = [dict(id='upper', source='上衣', replacement='参考上衣'), dict(id='lower', source='裙子', replacement='参考裙子')]
            if mode.startswith('prop_'):
                options.update(edit_type='prop_edit', prop_action=mode.removeprefix('prop_'))
                if mode == 'prop_remove': options['replacement'] = None
            brief = outfits.prepare_outfit(self.root, 'option', '测试目标', color, '仅修改授权目标及必要交界', ['身份、姿势、其他内容'], [1, 1, 60, 90], reference_file=Path(self.prepared['reference_file']), **options)
            self.add_args = [self.root, self.raw, 'option', '测试目标', color]
            self.add_kwargs.update(brief_file=Path(brief['brief_file']), **options)
        return self

    def add(self, refs=None):
        return self.c.add_asset(*self.add_args, **self.add_kwargs, references=self.refs if refs is None else refs)['asset']

    def call(self, name, *args, **kwargs):
        return self.c.workflow_call(name, *args, **kwargs)

    def code(self, expected, fn, *args, **kwargs):
        with self.assertRaises(self.c.StudioError) as error:
            fn(*args, **kwargs)
        self.assertEqual(error.exception.code, expected)

    def checks(self, asset):
        checks = contract()
        if asset.get('edit_type') == 'prop_edit': checks[0]['component'] = asset['target']
        if asset.get('outfit_components'):
            checks += [dict(id='component_'+x['id'], dimension='target', component=x['source'], property='设计', expected=x['replacement'], view='target_detail') for x in asset['outfit_components']]
        checks += [dict(id='reference_design' if ref['id']=='design_ref' else 'reference_'+ref['id'], dimension='target', component=ref['id'], property='指定参考属性', expected=ref['notes'], view='target_detail') for ref in asset['edit_references']]
        return checks

    def start(self, asset, budget=3):
        self.key = asset['id']
        self.call('pool_start', self.root, self.key, self.checks(asset), budget)

    def review(self, asset, fail=False):
        sheet = self.call('review_sheet', self.root, [asset['id']], 'assistant')
        state = self.c.read_state(self.root)
        asset = self.c.get_asset(state, asset['id'])
        data = assessment(scores=dict.fromkeys(studio.QUALITY_WEIGHTS_V12, 5), domain=self.c.quality_domain(state, asset))
        data.update(rubric_version='1.2', criteria=copy.deepcopy(state['candidate_pools'][asset['candidate_pool']]['contract']), normal_display_height=420, blind_packet=sheet['packet'])
        for item in data['criteria']: item.update(observed='合成可见依据', status='passed', score=5)
        if asset.get('outfit_components'):
            data['domain_review']['component_checks'] = {x['id']: dict(status='passed', evidence='合成部件检查') for x in asset['outfit_components']}
        if asset.get('prop_action'): data['domain_review']['prop_action'] = asset['prop_action']
        if fail:
            data['dimensions']['target']['score'] = 3
            data['criteria'][-1].update(status='failed', score=3, observed='参考属性尚未达成')
        if self.mode != 'expression': self.c.record_fidelity(self.root, asset['id'], 'passed', 'passed', '合成保真依据')
        preview = self.root / 'preview' / (asset['id']+'.png')
        self.c.make_preview(self.root, preview, [asset['id']])
        return self.c.record_quality(self.root, asset['id'], data, [preview])

    def compare(self, preferred):
        state = self.c.read_state(self.root)
        ids = [a['id'] for a in state['assets'] if a.get('candidate_pool') == self.key]
        sheet = self.call('review_sheet', self.root, ids, 'assistant')
        packet = self.c.read_state(self.root)['review_packets'][sheet['packet']]
        label = next(k for k, v in packet['items'].items() if v['asset_id'] == preferred['id'])
        return self.call('compare', self.root, self.key, dict(packet=sheet['packet'], basis='assistant', preferred=label, repairable=True, evidence='合成择优依据', repair_plan='修正指定参考属性'))

    def feedback(self, asset, decision='accept'):
        sheet = self.call('review_sheet', self.root, [asset['id']], 'user')
        packet = self.c.read_state(self.root)['review_packets'][sheet['packet']]
        alias = next(k for k,v in packet['items'].items() if v['asset_id']==asset['id'])
        self.call('human_feedback', self.root, dict(packet=sheet['packet'], basis='user', candidate=alias, decision=decision, note='调整目标细节' if decision == 'revise' else '采用'))
        return sheet

    def test_all_current_modes_preserve_references_through_review_and_zip(self):
        for mode, mouth in [('expression','default'), ('expression','open'), ('recolor','default'), ('replace','default'), ('outfit_replace','default'), ('prop_add','default'), ('prop_remove','default'), ('prop_replace','default')]:
            with self.subTest(mode=mode, mouth=mouth):
                self.setup_mode(mode, mouth)
                before = (self.root/'run.json').read_bytes()
                asset = self.add()
                self.assertEqual((self.root/('run.schema-'+json.loads(before)['schema_version']+'.backup.json')).read_bytes(), before)
                self.assertEqual((self.root/asset['path']).read_bytes(), self.raw.read_bytes())
                self.start(asset)
                self.review(asset)
                self.assertEqual(self.call('pool_status', self.root, self.key)['action'], 'human_review')
                self.feedback(asset)
                archive = self.c.export_pack(self.root, self.root/'delivery.zip', [asset['id']])
                with zipfile.ZipFile(self.root/'delivery.zip') as pack:
                    manifest = json.loads(pack.read('manifest.json'))
                    ref = manifest['sprites'][0]['edit_references'][0]
                    self.assertEqual(pack.read(ref['path']), self.ref.read_bytes())
                    self.assertEqual(len(manifest['sprites']), 1)
                    self.assertEqual(manifest['sprites'][0]['generation_inputs']['references'][1]['role'], 'edit_reference')

    def test_snapshot_preparation_is_read_only_and_external_file_can_change(self):
        self.setup_mode()
        before = (self.root/'run.json').read_bytes()
        original = self.ref.read_bytes()
        self.assertEqual(self.c.reference_call('prepare', self.root, self.inputs), self.prepared)
        self.assertEqual(before, (self.root/'run.json').read_bytes())
        self.ref.unlink()
        asset = self.add()
        self.assertEqual((self.root/asset['edit_references'][0]['path']).read_bytes(), original)

    def test_all_modes_redraw_from_failures_without_losing_scopes_or_mouth_state(self):
        for mode, mouth in [('expression','default'), ('expression','closed'), ('recolor','default'), ('replace','default'), ('outfit_replace','default'), ('prop_add','default'), ('prop_remove','default'), ('prop_replace','default')]:
            with self.subTest(mode=mode, mouth=mouth):
                self.setup_mode(mode, mouth); asset = self.add(); self.start(asset); self.review(asset, fail=True)
                attempt = self.call('pool_reserve', self.root, self.key)
                new = self.call('pool_import', self.root, self.key, attempt['token'], self.raw, self.prompt, [Path(p) for p in attempt['reference_paths']])['asset']
                self.assertEqual(new['edit_references'], asset['edit_references'])
                self.assertEqual(new.get('mouth_state'), asset.get('mouth_state'))
                self.assertEqual(new.get('outfit_components'), asset.get('outfit_components'))
                self.assertEqual(new.get('prop_action'), asset.get('prop_action'))
                self.review(new); self.compare(new)
                self.assertEqual(self.call('pool_status', self.root, self.key)['action'], 'human_review')
                self.assertEqual(len(self.c.read_state(self.root)['candidate_pools'][self.key]['attempts']), 2)

    def test_three_references_survive_redraw_and_tool_failure_still_consumes_attempt(self):
        self.setup_mode()
        payload = json.loads(self.inputs.read_text(encoding='utf-8'))
        for index, color in [(2,'#cc5577'),(3,'#dd6633')]:
            ref = self.folder/('参考'+str(index)+'.png'); fixture(ref, color=color)
            payload.append(dict(id='ref_'+str(index), path=ref.name, scope=['expression'], notes='授权表情线索'+str(index)))
        self.inputs.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
        prepared = studio.reference_call('prepare', self.root, self.inputs)
        self.add_kwargs['reference_file'] = Path(prepared['reference_file'])
        self.refs = [Path(p) for p in prepared['reference_paths']]
        asset = self.add(); self.start(asset); self.review(asset, fail=True)
        attempt = self.call('pool_reserve', self.root, self.key)
        self.assertEqual(len(attempt['reference_paths']), 5)
        self.assertEqual(attempt['references'][2:], asset['edit_references'])
        self.call('pool_import', self.root, self.key, attempt['token'], None, None, [], failure='合成工具失败')
        last = self.call('pool_reserve', self.root, self.key)
        self.assertEqual(last['number'], 3)
        self.assertEqual(last['references'], attempt['references'])
        revised = self.call('pool_import', self.root, self.key, last['token'], self.raw, self.prompt, [Path(p) for p in last['reference_paths']])['asset']
        self.review(revised, fail=True); self.compare(revised)
        self.assertEqual(self.call('pool_status', self.root, self.key)['action'], 'exhausted')
        self.code('POOL_NOT_READY', self.call, 'pool_reserve', self.root, self.key)

    def test_missing_reordered_or_extra_actual_inputs_rejected_before_import(self):
        self.setup_mode('replace')
        before = (self.root/'run.json').read_bytes()
        for refs in [[], self.refs[:1], list(reversed(self.refs)), self.refs+[self.ref]]:
            self.code('INVALID_GENERATION_REFERENCES', self.add, refs)
            self.assertEqual(before, (self.root/'run.json').read_bytes())
            self.assertFalse((self.root/'run.schema-1.2.backup.json').exists())

    def test_reference_scope_cannot_authorize_protected_content(self):
        self.setup_mode()
        payload = json.loads(self.inputs.read_text(encoding='utf-8')); payload[0]['scope'] = ['pose']
        self.inputs.write_text(json.dumps(payload), encoding='utf-8')
        prepared = studio.reference_call('prepare', self.root, self.inputs)
        self.add_kwargs['reference_file'] = Path(prepared['reference_file'])
        self.code('INVALID_EDIT_REFERENCES', self.add)

    def test_invalid_input_shapes_do_not_copy_any_snapshots(self):
        self.setup_mode()
        for scope in [[{}], ['expression','expression'], []]:
            payload = json.loads(self.inputs.read_text(encoding='utf-8')); payload[0]['scope'] = scope
            self.inputs.write_text(json.dumps(payload), encoding='utf-8')
            paths = set((self.root/'references').rglob('*'))
            self.code('INVALID_EDIT_REFERENCES', studio.reference_call, 'prepare', self.root, self.inputs)
            self.assertEqual(paths, set((self.root/'references').rglob('*')))

    def test_every_reference_needs_a_contract_check(self):
        self.setup_mode('outfit_replace'); asset = self.add()
        self.code('INVALID_CANDIDATE_REVIEW', self.call, 'pool_start', self.root, asset['id'], self.checks(asset)[:-1])
        self.assertNotIn('candidate_pools', self.c.read_state(self.root))

    def test_over_80_with_failed_reference_redraws_and_keeps_all_inputs_for_three_rounds(self):
        self.setup_mode('replace'); asset = self.add(); self.start(asset)
        original = copy.deepcopy(asset['edit_references'])
        for number in range(1, 4):
            self.review(asset, fail=True)
            saved = self.c.get_asset(self.c.read_state(self.root), asset['id'])
            self.assertGreaterEqual(saved['quality_review']['result']['total'], 80)
            if number > 1: self.compare(asset)
            action = self.call('pool_status', self.root, self.key)['action']
            if number == 3:
                self.assertEqual(action, 'exhausted'); break
            self.assertEqual(action, 'redraw')
            self.code('INTERNAL_REVIEW_INCOMPLETE', self.call, 'review_sheet', self.root, [asset['id']], 'user')
            attempt = self.call('pool_reserve', self.root, self.key)
            self.assertEqual([r['role'] for r in attempt['references']], ['immutable_source','edit_target','edit_reference'])
            self.assertEqual(attempt['references'][1]['sha256'], asset['sha256'])
            self.assertIn('reference_design', [x['id'] for x in attempt['blocking_findings']])
            result = self.call('pool_import', self.root, self.key, attempt['token'], self.raw, self.prompt, [Path(p) for p in attempt['reference_paths']])
            asset = result['asset']
            self.assertEqual(asset['edit_references'], original)
            self.assertNotIn('quality_review', asset)
        self.call('review_sheet', self.root, [asset['id']], 'user')
        self.code('POOL_NOT_READY', self.call, 'pool_reserve', self.root, self.key)
        self.assertEqual(len(self.c.read_state(self.root)['candidate_pools'][self.key]['attempts']), 3)

    def test_changed_snapshot_blocks_generation_and_keeps_budget_and_history(self):
        self.setup_mode(); asset = self.add(); self.start(asset); self.review(asset, fail=True)
        snapshot = self.root/asset['edit_references'][0]['path']; original = snapshot.read_bytes()
        before = (self.root/'run.json').read_bytes()
        fixture(snapshot, color='#aa3344')
        saved = self.c.get_asset(self.c.read_state(self.root), asset['id'])
        self.assertEqual(self.c.quality_status(self.root, self.c.read_state(self.root), saved), 'stale')
        self.assertEqual(self.call('pool_status', self.root, self.key)['action'], 'blocked')
        self.code('POOL_NOT_READY', self.call, 'pool_reserve', self.root, self.key)
        self.assertEqual(before, (self.root/'run.json').read_bytes())
        snapshot.write_bytes(original)
        self.assertEqual(self.call('pool_status', self.root, self.key)['action'], 'redraw')

    def test_changed_snapshot_blocks_already_accepted_export(self):
        self.setup_mode('recolor'); asset = self.add(); self.start(asset); self.review(asset); self.feedback(asset)
        (self.root/asset['edit_references'][0]['path']).unlink()
        self.assertFalse(self.c.check_asset(self.root, self.c.read_state(self.root), asset)['passed'])
        with self.assertRaises(self.c.StudioError): self.c.export_pack(self.root, self.root/'blocked.zip', [asset['id']])
        self.assertFalse((self.root/'blocked.zip').exists())

    def test_human_revision_keeps_reference_scopes_parent_and_fresh_review(self):
        self.setup_mode('prop_add'); asset = self.add(); self.start(asset); self.review(asset)
        sheet = self.feedback(asset, 'revise')
        before = (self.root/'run.json').read_bytes()
        plan = self.call('revision_prepare', self.root, sheet['packet'], self.checks(asset))
        self.assertEqual([x['role'] for x in plan['references']], ['immutable_source','edit_target','edit_reference'])
        self.assertEqual(plan['references'][1]['sha256'], asset['sha256'])
        revised = self.call('revision_import', self.root, sheet['packet'], self.raw, self.prompt, [Path(p) for p in plan['reference_paths']])['asset']
        self.assertEqual(revised['edit_references'], asset['edit_references'])
        self.assertEqual(revised['parent_asset_id'], asset['id'])
        self.assertNotIn('quality_review', revised)
        self.assertEqual(self.call('pool_status', self.root, revised['id'])['action'], 'review')
        self.key = revised['id']; self.review(revised)
        page = self.call('review_sheet', self.root, [revised['id']], 'user')
        self.assertEqual(page['revision_note'], '调整目标细节')
        self.assertEqual(Path(page['edit_references'][0]['path']).read_bytes(), self.ref.read_bytes())

    def test_review_reference_cards_are_localized_not_selectable_and_tamper_bound(self):
        self.setup_mode(); asset = self.add(); self.start(asset); self.review(asset)
        page = self.call('review_sheet', self.root, [asset['id']], 'user', 'en-US')
        html = Path(page['page']).read_text(encoding='utf-8')
        self.assertIn('Edit reference', html)
        self.assertNotIn('value="design_ref"', html)
        self.assertEqual(set(page['candidates']), {'A'})
        refreshed = self.call('refresh_review_sheet', self.root, page['packet'])
        self.assertEqual(refreshed['edit_references'], page['edit_references'])
        fixture(Path(page['edit_references'][0]['path']), color='#aa3344')
        self.code('STALE_REVIEW_PACKET', self.call, 'human_feedback', self.root, dict(packet=page['packet'], basis='user', candidate='A', decision='accept', note='采用'))

    def test_reference_aware_edits_cannot_use_legacy_refinement(self):
        self.setup_mode(); asset = self.add()
        self.code('POOL_IMPORT_REQUIRED', studio.start_refinement, self.root, asset['id'])

    def test_old_custom_language_pages_do_not_require_unused_reference_labels(self):
        spec = importlib.util.spec_from_file_location('reference_renderer', REPO/'plugins/charakit/lib/candidate_review.py')
        renderer = importlib.util.module_from_spec(spec); spec.loader.exec_module(renderer)
        old = {k: 'localized '+v for k,v in renderer.PREVIEW_EN.items() if k not in ('参考图','仅参考指定修改内容')}
        revision = dict(source='parent.png', note='Original correction')
        html = renderer.render_sheet('packet', ['A'], 'request', contract(), 'user', 'ja', old, revision)
        self.assertIn('localized Before revision', html)
        self.assertNotIn('__UI_', html)
        old.pop('修订前'); old.pop('本次修改')
        html = renderer.render_sheet('packet', ['A'], 'request', contract(), 'user', 'ja', old)
        self.assertNotIn('__UI_', html)

    def test_packaged_cli_supports_both_modules_outside_repo(self):
        archive = self.folder/'charakit.zip'; builder.build(REPO, archive)
        unpacked = self.folder/'独立安装'
        with zipfile.ZipFile(archive) as pack: pack.extractall(unpacked)
        for module in ('expressions', 'outfits'):
            script = next(unpacked.rglob('charakit-'+module+'/scripts/studio.py'))
            root = self.folder/('CLI_'+module)
            subprocess.run([sys.executable,str(script),'init','--project',str(root),'--source',str(self.source),'--character','test_character'],cwd=self.folder,check=True,capture_output=True)
            self.inputs.write_text(json.dumps([dict(id='ref',path=self.ref.name,scope=['expression'] if module=='expressions' else ['target'],notes='指定属性')],ensure_ascii=False),encoding='utf-8')
            result = subprocess.run([sys.executable,str(script),'reference-prepare','--project',str(root),'--references-file',str(self.inputs)],cwd=self.folder,check=True,capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(json.loads(result.stdout)['edit_references'][0]['role'], 'edit_reference')

    def test_final_report_records_reference_metadata_only_after_human_feedback(self):
        self.setup_mode(); asset = self.add(); self.start(asset); self.review(asset)
        options = dict(projects=[self.root], output=self.root/'report', language='zh-CN')
        self.code('HUMAN_REVIEW_REQUIRED', studio.generate_report, **options, stage='final')
        self.feedback(asset)
        studio.generate_report(**options, stage='final')
        report = json.loads((self.root/'report/report.json').read_text(encoding='utf-8'))
        self.assertEqual(report['cases'][0]['edit_references'][0]['sha256'], asset['edit_references'][0]['sha256'])
        self.assertEqual(report['cases'][0]['history'][0]['generation_inputs']['references'][1]['role'], 'edit_reference')
        self.assertIn('参考图与适用范围', (self.root/'report/report.md').read_text(encoding='utf-8'))


if __name__ == '__main__': unittest.main()
