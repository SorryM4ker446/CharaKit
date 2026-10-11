"""Full outfit mechanics using synthetic PNGs; these tests do not assess real artwork."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

from test_outfits import outfits, fixture, builder, REPO
from test_quality import assessment
from test_candidate_review import contract


class FullOutfitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name) / '整套测试'
        self.folder.mkdir()
        self.root = self.folder / '项目'
        self.source = self.folder / 'source.png'; fixture(self.source)
        self.raw = self.folder / 'raw.png'; fixture(self.raw, '#556677')
        self.prompt = self.folder / 'prompt.txt'
        self.prompt.write_text('Synthetic outfit replacement fixture.', encoding='utf-8')
        outfits.init_project(self.root, self.source, 'test_character')
        self.components = [
            {'id': 'upper', 'source': '现有上衣', 'replacement': '蓝色短外套'},
            {'id': 'lower', 'source': '现有短裙', 'replacement': '同色长裙'},
        ]
        self.target = '上衣和裙子'
        self.design = '统一蓝色休闲套装，保留鞋袜和装备'

    def call(self, name, *args, **kwargs):
        return outfits.workflow_call(name, *args, **kwargs)

    def code(self, code, fn, *args, **kwargs):
        with self.assertRaises(outfits.StudioError) as error:
            fn(*args, **kwargs)
        self.assertEqual(error.exception.code, code)

    def prepare(self, option='blue_set', **kwargs):
        options = dict(edit_type='outfit_replace', replacement=self.design, outfit_components=self.components)
        options.update(kwargs)
        return outfits.prepare_outfit(self.root, option, self.target, None,
                                      '仅清单内服装及必要的接缝、覆盖变化',
                                      ['面部、表情、头发、姿势、鞋袜、装备'], [10, 30, 85, 120], **options)

    def candidate(self, option='blue_set', pool=True, budget=1):
        brief = self.prepare(option)
        asset = outfits.add_asset(self.root, self.raw, option, self.target,
                                 prompt_file=self.prompt, brief_file=Path(brief['brief_file']),
                                 replacement=self.design)['asset']
        if pool:
            self.call('pool_start', self.root, asset['id'], self.outfit_contract(), budget)
        return asset

    def outfit_contract(self):
        return contract() + [dict(id='component_'+x['id'], dimension='target', component=x['source'],
                                 property='替换设计', expected=x['replacement'], view='target_detail')
                             for x in self.components]

    def assessment(self, asset):
        packet = self.call('review_sheet', self.root, [asset['id']], 'assistant')
        state = outfits.read_state(self.root)
        current = outfits.get_asset(state, asset['id'])
        data = assessment(scores=dict.fromkeys(outfits.QUALITY_WEIGHTS_V12, 5), domain='outfit_replace')
        data.update(rubric_version='1.2', criteria=copy.deepcopy(state['candidate_pools'][current['candidate_pool']]['contract']),
                    normal_display_height=420, blind_packet=packet['packet'])
        for item in data['criteria']:
            item.update(observed='Synthetic visible finding.', status='passed', score=5)
        data['domain_review']['component_checks'] = {
            item['id']: {'status': 'passed', 'evidence': 'Synthetic per-component finding.'}
            for item in self.components}
        comparison = self.root / 'preview' / (asset['id'] + '.png')
        outfits.make_preview(self.root, comparison, [asset['id']], detail_box=[10,30,85,120])
        return data, comparison

    def review(self, asset, mutate=None):
        data, comparison = self.assessment(asset)
        if mutate: mutate(data)
        outfits.record_fidelity(self.root, asset['id'], 'passed', 'passed', 'Synthetic target and protection finding.')
        return outfits.record_quality(self.root, asset['id'], data, [comparison])

    def feedback(self, asset, decision='accept'):
        page = self.call('review_sheet', self.root, [asset['id']], 'user')
        packet = outfits.read_state(self.root)['review_packets'][page['packet']]
        alias = next(k for k,v in packet['items'].items() if v['asset_id']==asset['id'])
        result = self.call('human_feedback', self.root, dict(packet=page['packet'], basis='user', candidate=alias,
                                                            decision=decision, note='下摆需要调整' if decision=='revise' else '采用这个版本'))
        return page, result

    def test_read_only_prepare_and_exact_legacy_migration(self):
        state = outfits.read_state(self.root); state.pop('quality_policy'); outfits.write_state(self.root, state)
        old = outfits.add_asset(self.root, self.raw, 'old_coat', 'coat', 'blue')['asset']
        outfits.review_asset(self.root, old['id'], 'accepted', 'Synthetic user selection.')
        before = (self.root/'run.json').read_bytes()
        prepared = self.prepare()
        self.assertEqual(prepared['edit_brief']['schema_version'], '1.2')
        self.assertEqual(before, (self.root/'run.json').read_bytes())
        new = self.candidate()
        state = outfits.read_state(self.root)
        self.assertEqual(state['schema_version'], '1.4')
        self.assertEqual((self.root/'run.schema-1.2.backup.json').read_bytes(), before)
        self.assertEqual(state['assets'][0], json.loads(before)['assets'][0])
        self.assertEqual(state['selected'], {'old_coat': old['id']})
        self.assertEqual((self.root/new['path']).read_bytes(), self.raw.read_bytes())
        self.assertEqual(new['outfit_components'], self.components)
        self.assertNotIn('color', new)

    def test_single_replacement_project_upgrades_and_never_downgrades(self):
        state = outfits.read_state(self.root); state['schema_version']='1.3'; outfits.write_state(self.root,state)
        before = (self.root/'run.json').read_bytes()
        self.candidate()
        self.assertEqual((self.root/'run.schema-1.3.backup.json').read_bytes(), before)
        brief = outfits.prepare_outfit(self.root,'shoes','shoes',None,'shoe edges',['face'],[10,90,80,140],
                                      edit_type='replace',replacement='low shoes')
        outfits.add_asset(self.root,self.raw,'shoes','shoes',prompt_file=self.prompt,
                         brief_file=Path(brief['brief_file']),edit_type='replace',replacement='low shoes')
        self.assertEqual(outfits.read_state(self.root)['schema_version'],'1.4')

    def test_invalid_inventories_leave_no_artifacts(self):
        invalid = [None, [], self.components*2, [{'id':'upper','source':'coat'}],
                   [dict(self.components[0], mask='invented')], [dict(self.components[0], id='../coat')],
                   [dict(self.components[0], source='')],
                   [self.components[0], dict(self.components[1], source=self.components[0]['source'])]]
        before = (self.root/'run.json').read_bytes()
        for items in invalid:
            with self.subTest(items=items):
                self.code('INVALID_OUTFIT_COMPONENTS', self.prepare, outfit_components=items)
        self.assertEqual(before,(self.root/'run.json').read_bytes())
        self.assertFalse((self.root/'briefs').exists())

    def test_components_forbidden_in_single_garment_modes(self):
        for mode, change in [('recolor',dict(color='blue')),('replace',dict(replacement='jacket'))]:
            with self.subTest(mode=mode):
                self.code('INVALID_RECOLOR' if mode=='recolor' else 'INVALID_REPLACEMENT',
                          outfits.outfit_fields,'coat','coat',change.get('color'),mode,change.get('replacement'),self.components)

    def test_missing_brief_prompt_and_conflicting_backup_do_not_import(self):
        before = (self.root/'run.json').read_bytes()
        args = (self.root,self.raw,'blue_set',self.target)
        options = dict(edit_type='outfit_replace',replacement=self.design,outfit_components=self.components)
        self.code('EDIT_BRIEF_REQUIRED',outfits.add_asset,*args,prompt_file=self.prompt,**options)
        brief=self.prepare()
        self.code('REPLACEMENT_PROMPT_REQUIRED',outfits.add_asset,*args,brief_file=Path(brief['brief_file']),**options)
        backup=self.root/'run.schema-1.2.backup.json'; backup.write_bytes(b'existing backup')
        self.code('MIGRATION_BACKUP_EXISTS',outfits.add_asset,*args,prompt_file=self.prompt,brief_file=Path(brief['brief_file']),**options)
        self.assertEqual(before,(self.root/'run.json').read_bytes())
        self.assertEqual(backup.read_bytes(),b'existing backup')
        self.assertFalse((self.root/'candidates').exists())

    def test_definition_and_inventory_cannot_drift_between_versions(self):
        first=self.candidate(pool=False)
        second=outfits.add_asset(self.root,self.raw,'blue_set',self.target,replacement=self.design,prompt_file=self.prompt)['asset']
        self.assertEqual(second['outfit_components'],first['outfit_components'])
        self.assertEqual(second['edit_brief'],first['edit_brief'])
        changed=copy.deepcopy(self.components); changed[0]['replacement']='different coat'
        self.code('OUTFIT_DEFINITION_CHANGED',outfits.add_asset,self.root,self.raw,'blue_set',self.target,
                  replacement=self.design,prompt_file=self.prompt,outfit_components=changed)

    def test_full_outfit_requires_new_pool_and_per_component_contract(self):
        asset=self.candidate(pool=False)
        self.code('POOL_IMPORT_REQUIRED',outfits.start_refinement,self.root,asset['id'])
        self.code('INVALID_CANDIDATE_REVIEW',self.call,'pool_start',self.root,asset['id'],contract())
        self.code('HUMAN_REVIEW_REQUIRED',self.call,'require_user_feedback',self.root,outfits.read_state(self.root),asset)
        self.call('pool_start',self.root,asset['id'],self.outfit_contract(),1)
        self.review(asset)
        self.code('HUMAN_REVIEW_REQUIRED',outfits.review_asset,self.root,asset['id'],'accepted')
        self.code('POOL_NOT_READY',self.call,'pool_reserve',self.root,asset['id'])

    def test_every_domain_and_component_vetoes_perfect_total(self):
        for key in outfits.DOMAIN_CHECKS['outfit_replace']:
            with self.subTest(check=key):
                asset=self.candidate('case_'+key)
                result=self.review(asset,lambda data: data['domain_review']['checks'][key].update(status='failed'))
                self.assertEqual(result['score']['total'],100)
                self.assertEqual(result['quality_status'],'failed')
        for status in ('failed','uncertain'):
            asset=self.candidate('component_'+status)
            result=self.review(asset,lambda data: data['domain_review']['component_checks']['lower'].update(status=status))
            self.assertEqual(result['quality_status'],status)

    def test_missing_or_extra_component_evidence_cannot_be_saved(self):
        asset=self.candidate()
        data,comparison=self.assessment(asset)
        for missing in (True,False):
            altered=copy.deepcopy(data)
            checks=altered['domain_review']['component_checks']
            if missing: checks.pop('lower')
            else: checks['shoe']=copy.deepcopy(checks['upper'])
            self.code('INVALID_DOMAIN_REVIEW',outfits.record_quality,self.root,asset['id'],altered,[comparison])
        self.assertNotIn('quality_review',outfits.read_state(self.root)['assets'][0])

    def test_human_revision_keeps_inventory_and_requires_fresh_review(self):
        parent=self.candidate(); self.review(parent)
        draft=outfits.generate_report([self.root],self.folder/'draft')
        self.assertEqual(draft['stage'],'draft')
        page,_=self.feedback(parent,'revise')
        plan=self.call('revision_prepare',self.root,page['packet'],self.outfit_contract())
        self.assertEqual(plan['edit']['outfit_components'],self.components)
        child=self.call('revision_import',self.root,plan['revision'],self.raw,self.prompt,
                        [Path(p) for p in plan['reference_paths']])['asset']
        self.assertEqual(child['parent_asset_id'],parent['id'])
        self.assertEqual(child['outfit_components'],self.components)
        self.assertEqual(child['edit_brief'],parent['edit_brief'])
        self.assertNotIn('quality_review',child)
        self.assertNotIn('human_feedback',child)
        self.assertEqual(outfits.read_state(self.root)['candidate_pools'][child['id']]['budget'],3)
        self.review(child); self.feedback(child)
        exported=outfits.export_pack(self.root)
        record=exported['manifest']['sprites'][0]
        self.assertEqual(record['outfit_components'],self.components)
        self.assertEqual(record['parent_asset_id'],parent['id'])
        with zipfile.ZipFile(exported['export']) as archive:
            self.assertEqual(archive.read(record['path']),self.raw.read_bytes())
        for language in ('zh-CN','en'):
            report=outfits.generate_report([self.root],self.folder/language,stage='final',language=language)
            rendered=Path(report['report']).read_text(encoding='utf-8')
            self.assertIn('逐件检查' if language=='zh-CN' else 'Component findings',rendered)
            self.assertIn(self.components[1]['replacement'],rendered)
            self.assertEqual(report['stage'],'final')

    def test_mixed_legacy_and_full_outfit_exports_preserve_bytes(self):
        state=outfits.read_state(self.root); state.pop('quality_policy'); outfits.write_state(self.root,state)
        old=outfits.add_asset(self.root,self.raw,'old_coat','coat','blue')['asset']
        outfits.review_asset(self.root,old['id'],'accepted','Synthetic user selection.')
        full=self.candidate(); self.review(full); self.feedback(full)
        exported=outfits.export_pack(self.root)
        self.assertEqual(exported['manifest']['schema_version'],'1.4')
        self.assertEqual(len(exported['manifest']['sprites']),2)
        with zipfile.ZipFile(exported['export']) as archive:
            for record in exported['manifest']['sprites']:
                self.assertEqual(archive.read(record['path']),self.raw.read_bytes())

    def test_pool_import_preserves_full_scope_and_fixed_attempt_budget(self):
        first=self.candidate(budget=2)
        self.review(first,lambda data: data['domain_review']['checks']['ensemble_coherence'].update(status='failed'))
        attempt=self.call('pool_reserve',self.root,first['id'])
        child=self.call('pool_import',self.root,first['id'],attempt['token'],self.raw,self.prompt,
                        [Path(p) for p in attempt['reference_paths']])['asset']
        self.assertEqual(child['outfit_components'],self.components)
        self.assertEqual(child['parent_asset_id'],first['id'])
        self.review(child,lambda data: data['domain_review']['checks']['ensemble_coherence'].update(status='failed'))
        self.code('POOL_NOT_READY',self.call,'pool_reserve',self.root,first['id'])

    def test_component_id_cannot_hide_failed_domain_from_redraw_findings(self):
        self.components[0]['id']='rendering'
        first=self.candidate(budget=3)
        self.review(first,lambda data:data['domain_review']['checks']['rendering'].update(status='failed',evidence='Synthetic rendering defect.'))
        attempt=self.call('pool_reserve',self.root,first['id'])
        findings=[x for x in attempt['blocking_findings'] if x['id']=='rendering']
        self.assertTrue(findings)
        self.assertEqual(findings[0]['evidence'],'Synthetic rendering defect.')
        self.assertEqual(self.call('pool_status',self.root,first['id'])['action'],'generate_reserved')

    def test_packaged_cli_handles_inventory_bom_and_unicode_outside_repo(self):
        archive=self.folder/'plugin.zip'; builder.build(REPO,archive)
        installed=self.folder/'installed'
        with zipfile.ZipFile(archive) as package: package.extractall(installed)
        script=installed/'skills/charakit-outfits/scripts/studio.py'
        inventory=self.folder/'部件.json'; inventory.write_text(json.dumps(self.components,ensure_ascii=False),encoding='utf-8-sig')
        args=[sys.executable,str(script),'prepare','--project',str(self.root),'--outfit','blue_set',
              '--edit-type','outfit_replace','--target',self.target,'--replacement',self.design,
              '--components-file',str(inventory),'--boundary','服装交界','--protect','脸部和装备',
              '--target-box','10','30','85','120']
        run=subprocess.run(args,cwd=self.folder,capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(run.returncode,0,run.stderr)
        brief=json.loads(run.stdout)
        run=subprocess.run([sys.executable,str(script),'add','--project',str(self.root),'--outfit','blue_set',
                            '--target',self.target,'--replacement',self.design,'--image',str(self.raw),
                            '--prompt-file',str(self.prompt),'--brief-file',brief['brief_file']],
                           cwd=self.folder,capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(run.returncode,0,run.stderr)
        self.assertEqual(json.loads(run.stdout)['asset']['outfit_components'],self.components)

    def test_single_piece_mapping_is_supported_without_forced_layers(self):
        self.components=[dict(id='dress',source='上衣和裙子合并范围',replacement='完整连衣长裙')]
        asset=self.candidate(); self.review(asset); self.feedback(asset)
        self.assertEqual(outfits.export_pack(self.root)['manifest']['sprites'][0]['outfit_components'],self.components)

    def test_canvas_mismatch_allows_review_but_keeps_formal_export_gate(self):
        fixture(self.raw,'#556677',size=(100,150))
        asset=self.candidate(); self.review(asset)
        _,feedback=self.feedback(asset)
        self.assertEqual(feedback['next_action'],'blocked')
        state=outfits.read_state(self.root)
        self.assertEqual(state['selected'],{})
        self.assertIn('CANVAS_MISMATCH',outfits.check_asset(self.root,state,state['assets'][0])['errors'])
        self.assertEqual((self.root/asset['path']).read_bytes(),self.raw.read_bytes())

    def test_human_revision_uses_chosen_earlier_full_outfit(self):
        first=self.candidate(budget=2)
        self.review(first,lambda data: data['domain_review']['checks']['ensemble_coherence'].update(status='failed'))
        attempt=self.call('pool_reserve',self.root,first['id'])
        second=self.call('pool_import',self.root,first['id'],attempt['token'],self.raw,self.prompt,
                         [Path(p) for p in attempt['reference_paths']])['asset']
        self.review(second)
        internal=self.call('review_sheet',self.root,[first['id'],second['id']],'assistant')
        state=outfits.read_state(self.root)
        preferred=next(k for k,v in state['review_packets'][internal['packet']]['items'].items() if v['asset_id']==second['id'])
        self.call('compare',self.root,first['id'],dict(packet=internal['packet'],basis='assistant',preferred=preferred,
                  repairable=False,evidence='Synthetic comparison prefers the internally passed candidate.'))
        page=self.call('review_sheet',self.root,[first['id'],second['id']],'user')
        state=outfits.read_state(self.root)
        alias=next(k for k,v in state['review_packets'][page['packet']]['items'].items() if v['asset_id']==first['id'])
        self.call('human_feedback',self.root,dict(packet=page['packet'],basis='user',candidate=alias,decision='revise',note='修订早期版下摆'))
        plan=self.call('revision_prepare',self.root,page['packet'],self.outfit_contract())
        child=self.call('revision_import',self.root,plan['revision'],self.raw,self.prompt,
                        [Path(p) for p in plan['reference_paths']])['asset']
        self.assertEqual(child['parent_asset_id'],first['id'])
        self.assertNotEqual(child['parent_asset_id'],second['id'])
        self.assertEqual(child['outfit_components'],first['outfit_components'])

    def test_tampered_schema_inventory_or_findings_invalidates_project(self):
        asset=self.candidate(); self.review(asset)
        original=(self.root/'run.json').read_bytes()
        for corrupt in ('schema','inventory','findings'):
            with self.subTest(corrupt=corrupt):
                state=json.loads(original)
                if corrupt=='schema': state['schema_version']='1.3'
                elif corrupt=='inventory': state['assets'][0]['outfit_components'][0]['replacement']='different design'
                else: state['assets'][0]['quality_review']['domain_review']['component_checks'].pop('lower')
                outfits.write_state(self.root,state)
                self.code('INVALID_PROJECT',outfits.read_state,self.root)
        (self.root/'run.json').write_bytes(original)


if __name__ == '__main__':
    unittest.main()
