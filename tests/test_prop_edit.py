"""Accessory/prop workflow tests with synthetic PNGs, not visual-quality claims."""
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


class PropEditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name) / '道具测试'
        self.folder.mkdir()
        self.root = self.folder / '项目'
        self.source = self.folder / 'source.png'; fixture(self.source)
        self.raw = self.folder / 'raw.png'; fixture(self.raw, '#556677')
        self.prompt = self.folder / 'prompt.txt'
        self.prompt.write_text('Synthetic requested prop edit.', encoding='utf-8')
        outfits.init_project(self.root, self.source, 'test_character')
        self.target = '右手物件位置'
        self.design = '闭合雨伞，原握持方向和比例'

    def call(self, name, *args, **kwargs):
        return outfits.workflow_call(name, *args, **kwargs)

    def code(self, code, fn, *args, **kwargs):
        with self.assertRaises(outfits.StudioError) as error:
            fn(*args, **kwargs)
        self.assertEqual(error.exception.code, code)

    def prepare(self, action='remove', option=None, **kwargs):
        options = dict(edit_type='prop_edit', prop_action=action,
                       replacement=None if action == 'remove' else self.design)
        options.update(kwargs)
        return outfits.prepare_outfit(self.root, option or 'prop_'+action, self.target, None,
                                      '仅物件及必要的接触、遮挡、原占位补全；身体姿势不变',
                                      ['面部、表情、头发、服装、身体比例和构图'],
                                      [10, 30, 85, 120], **options)

    def prop_contract(self):
        result = contract()
        result[0].update(component=self.target, expected='符合实际添加、移除或替换要求')
        return result

    def candidate(self, action='remove', option=None, pool=True, budget=1):
        brief = self.prepare(action, option)
        asset = outfits.add_asset(self.root, self.raw, option or 'prop_'+action, self.target,
                                 replacement=None if action == 'remove' else self.design,
                                 prompt_file=self.prompt, brief_file=Path(brief['brief_file']))['asset']
        if pool:self.call('pool_start', self.root, asset['id'], self.prop_contract(), budget)
        return asset

    def evidence(self, asset):
        packet = self.call('review_sheet', self.root, [asset['id']], 'assistant')
        state = outfits.read_state(self.root)
        current = outfits.get_asset(state, asset['id'])
        data = assessment(scores=dict.fromkeys(outfits.QUALITY_WEIGHTS_V12, 5), domain='prop_edit')
        data.update(rubric_version='1.2', criteria=copy.deepcopy(state['candidate_pools'][current['candidate_pool']]['contract']),
                    normal_display_height=420, blind_packet=packet['packet'])
        data['domain_review']['prop_action'] = asset['prop_action']
        for check in data['criteria']:check.update(observed='Synthetic inspected finding.',status='passed',score=5)
        comparison = self.root / 'preview' / (asset['id']+'.png')
        outfits.make_preview(self.root, comparison, [asset['id']], detail_box=[10,30,85,120])
        return data, comparison

    def review(self, asset, mutate=None):
        data, comparison = self.evidence(asset)
        if mutate:mutate(data)
        outfits.record_fidelity(self.root, asset['id'], 'passed', 'passed', 'Synthetic target and protection finding.')
        return outfits.record_quality(self.root, asset['id'], data, [comparison])

    def feedback(self, asset, decision='accept'):
        page = self.call('review_sheet', self.root, [asset['id']], 'user')
        packet = outfits.read_state(self.root)['review_packets'][page['packet']]
        alias = next(k for k,v in packet['items'].items() if v['asset_id']==asset['id'])
        result = self.call('human_feedback', self.root, dict(packet=page['packet'],basis='user',candidate=alias,
                          decision=decision,note='修订物件接触位置' if decision=='revise' else '采用这个版本'))
        return page, result

    def test_all_operations_review_adoption_report_and_raw_export(self):
        for action in outfits.PROP_ACTIONS:
            with self.subTest(action=action):
                asset=self.candidate(action); self.review(asset)
                self.assertEqual(asset['edit_type'],'prop_edit')
                self.assertEqual(asset['edit_brief']['schema_version'],'1.3')
                self.assertEqual(asset['prop_action'],action)
                self.assertEqual('replacement' in asset,action!='remove')
                self.code('HUMAN_REVIEW_REQUIRED',outfits.review_asset,self.root,asset['id'],'accepted')
                draft=outfits.generate_report([self.root],self.folder/('draft_'+action),ids=[asset['id']])
                self.assertEqual(draft['stage'],'draft'); self.assertEqual(draft['images'],[])
                _,feedback=self.feedback(asset)
                self.assertEqual(feedback['next_action'],'export')
                exported=outfits.export_pack(self.root,ids=[asset['id']])
                record=exported['manifest']['sprites'][0]
                self.assertEqual(exported['manifest']['schema_version'],'1.5')
                self.assertEqual(record['prop_action'],action)
                self.assertEqual('replacement' in record,action!='remove')
                with zipfile.ZipFile(exported['export']) as archive:self.assertEqual(archive.read(record['path']),self.raw.read_bytes())
                for language in ('zh-CN','en'):
                    report=outfits.generate_report([self.root],self.folder/(action+'_'+language),ids=[asset['id']],stage='final',language=language)
                    rendered=Path(report['report']).read_text(encoding='utf-8')
                    self.assertIn('物件操作' if language=='zh-CN' else 'Object operation',rendered)
                    self.assertIn('遮挡与移除补全' if language=='zh-CN' else 'Occlusion and reconstruction',rendered)
                    self.assertEqual(len(report['images']),1)
                    self.assertEqual(Path(report['images'][0]).read_bytes(),self.raw.read_bytes())

    def test_legacy_schema_migrations_backup_exact_metadata_and_keep_selection(self):
        for schema in ('1.2','1.3','1.4'):
            with self.subTest(schema=schema):
                self.root=self.folder/('project_'+schema); outfits.init_project(self.root,self.source,'test_character')
                state=outfits.read_state(self.root);state.pop('quality_policy');state['schema_version']=schema
                outfits.write_state(self.root,state)
                old=outfits.add_asset(self.root,self.raw,'old_coat','coat','blue')['asset']
                outfits.review_asset(self.root,old['id'],'accepted','Synthetic selection.')
                before=(self.root/'run.json').read_bytes()
                prepared=self.prepare()
                self.assertEqual(before,(self.root/'run.json').read_bytes())
                prop=outfits.add_asset(self.root,self.raw,'prop_remove',self.target,prompt_file=self.prompt,brief_file=Path(prepared['brief_file']))['asset']
                state=outfits.read_state(self.root)
                self.assertEqual(state['schema_version'],'1.5')
                self.assertEqual((self.root/f'run.schema-{schema}.backup.json').read_bytes(),before)
                self.assertEqual(state['assets'][0],json.loads(before)['assets'][0])
                self.assertEqual(state['selected'],{'old_coat':old['id']})
                self.assertEqual((self.root/prop['path']).read_bytes(),self.raw.read_bytes())

    def test_invalid_actions_and_conflicting_fields_leave_no_artifacts(self):
        invalid=[dict(prop_action=None),dict(prop_action='move'),dict(prop_action='remove',replacement='umbrella'),
                 dict(prop_action='add',replacement=None),dict(prop_action='replace',replacement=''),
                 dict(outfit_components=[{'id':'hat','source':'hat','replacement':'cap'}])]
        before=(self.root/'run.json').read_bytes()
        for kwargs in invalid:
            with self.subTest(kwargs=kwargs):self.code('INVALID_PROP_EDIT',self.prepare,**kwargs)
        self.code('INVALID_PROP_EDIT',outfits.outfit_fields,'prop','object','blue','prop_edit',None,None,'remove')
        for mode in ('recolor','replace','outfit_replace'):
            with self.subTest(mode=mode):
                self.assertFalse(outfits.valid_outfit_definition(dict(edit_type=mode,target='coat',color='blue',prop_action='add')))
        self.assertEqual(before,(self.root/'run.json').read_bytes());self.assertFalse((self.root/'briefs').exists())

    def test_missing_brief_prompt_and_conflicting_backup_block_import(self):
        args=(self.root,self.raw,'prop_remove',self.target)
        options=dict(edit_type='prop_edit',prop_action='remove')
        self.code('EDIT_BRIEF_REQUIRED',outfits.add_asset,*args,prompt_file=self.prompt,**options)
        brief=self.prepare()
        self.code('REPLACEMENT_PROMPT_REQUIRED',outfits.add_asset,*args,brief_file=Path(brief['brief_file']),**options)
        before=(self.root/'run.json').read_bytes()
        backup=self.root/'run.schema-1.2.backup.json';backup.write_bytes(b'prior backup')
        self.code('MIGRATION_BACKUP_EXISTS',outfits.add_asset,*args,prompt_file=self.prompt,brief_file=Path(brief['brief_file']),**options)
        self.assertEqual(before,(self.root/'run.json').read_bytes());self.assertFalse((self.root/'candidates').exists())

    def test_action_and_design_cannot_drift_between_versions(self):
        first=self.candidate('replace',pool=False)
        second=outfits.add_asset(self.root,self.raw,'prop_replace',self.target,replacement=self.design,prompt_file=self.prompt)['asset']
        self.assertEqual(first['prop_action'],second['prop_action'])
        self.assertEqual(first['edit_brief'],second['edit_brief'])
        self.code('OUTFIT_DEFINITION_CHANGED',outfits.add_asset,self.root,self.raw,'prop_replace',self.target,
                  prop_action='remove',prompt_file=self.prompt)
        self.code('OUTFIT_DEFINITION_CHANGED',outfits.add_asset,self.root,self.raw,'prop_replace',self.target,
                  replacement='different object',prompt_file=self.prompt)

    def test_prepared_brief_must_match_actual_action(self):
        brief=self.prepare('add')
        self.code('INVALID_EDIT_BRIEF',outfits.add_asset,self.root,self.raw,'prop_add',self.target,
                  edit_type='prop_edit',prop_action='replace',replacement=self.design,
                  prompt_file=self.prompt,brief_file=Path(brief['brief_file']))

    def test_props_require_pool_target_contract_and_actual_human_feedback(self):
        asset=self.candidate(pool=False)
        self.code('POOL_IMPORT_REQUIRED',outfits.start_refinement,self.root,asset['id'])
        self.code('INVALID_CANDIDATE_REVIEW',self.call,'pool_start',self.root,asset['id'],contract())
        self.code('HUMAN_REVIEW_REQUIRED',self.call,'require_user_feedback',self.root,outfits.read_state(self.root),asset)
        data=assessment(scores=dict.fromkeys(outfits.QUALITY_WEIGHTS_V12,5),domain='prop_edit')
        data.update(rubric_version='1.2',criteria=self.prop_contract(),normal_display_height=420,blind_packet='not-scored')
        for item in data['criteria']:item.update(observed='Synthetic finding.',status='passed',score=5)
        data['domain_review']['prop_action']='remove'
        self.code('POOL_IMPORT_REQUIRED',outfits.record_quality,self.root,asset['id'],data,[])

    def test_wrong_action_missing_check_or_garment_checklist_cannot_be_saved(self):
        asset=self.candidate();data,comparison=self.evidence(asset)
        for change in ('wrong_action','missing_action','missing_check','garment'):
            altered=copy.deepcopy(data)
            if change=='wrong_action':altered['domain_review']['prop_action']='add'
            elif change=='missing_action':altered['domain_review'].pop('prop_action')
            elif change=='missing_check':altered['domain_review']['checks'].pop('occlusion_reconstruction')
            else:altered['domain_review']=assessment(domain='garment_replace')['domain_review']
            self.code('INVALID_DOMAIN_REVIEW',outfits.record_quality,self.root,asset['id'],altered,[comparison])
        self.assertNotIn('quality_review',outfits.read_state(self.root)['assets'][0])

    def test_all_prop_checks_veto_perfect_total_and_user_acceptance(self):
        for key in outfits.DOMAIN_CHECKS['prop_edit']:
            for status in ('failed','uncertain'):
                with self.subTest(check=key,status=status):
                    asset=self.candidate(option='case_'+key+'_'+status)
                    result=self.review(asset,lambda data:data['domain_review']['checks'][key].update(status=status))
                    self.assertEqual(result['score']['total'],100)
                    self.assertEqual(result['quality_status'],status)
                    _,feedback=self.feedback(asset)
                    self.assertEqual(feedback['next_action'],'blocked')
                    self.assertEqual(outfits.read_state(self.root)['selected'],{})

    def test_fidelity_failure_blocks_otherwise_passed_prop(self):
        asset=self.candidate();data,comparison=self.evidence(asset)
        outfits.record_fidelity(self.root,asset['id'],'passed','failed','Synthetic unrequested clothing change.')
        outfits.record_quality(self.root,asset['id'],data,[comparison])
        _,feedback=self.feedback(asset)
        self.assertEqual(feedback['blockers']['fidelity'],'failed')
        report=outfits.generate_report([self.root],self.folder/'blocked',stage='final')
        self.assertEqual(report['images'],[])

    def test_pool_import_retains_action_and_budget(self):
        first=self.candidate('add',budget=2)
        self.review(first,lambda data:data['domain_review']['checks']['placement_contacts'].update(status='failed'))
        attempt=self.call('pool_reserve',self.root,first['id'])
        second=self.call('pool_import',self.root,first['id'],attempt['token'],self.raw,self.prompt,
                         [Path(p) for p in attempt['reference_paths']])['asset']
        self.assertEqual(second['prop_action'],'add');self.assertEqual(second['replacement'],self.design)
        self.assertEqual(second['edit_brief'],first['edit_brief'])
        self.review(second);self.code('POOL_NOT_READY',self.call,'pool_reserve',self.root,first['id'])

    def test_failed_fidelity_redraws_before_human_review_even_with_full_score(self):
        first=self.candidate('add',budget=3)
        data,comparison=self.evidence(first)
        outfits.record_fidelity(self.root,first['id'],'passed','failed','Synthetic protected-region deviation.')
        result=outfits.record_quality(self.root,first['id'],data,[comparison])
        self.assertEqual(result['score']['total'],100)
        self.assertEqual(self.call('pool_status',self.root,first['id'])['action'],'redraw')
        self.code('INTERNAL_REVIEW_INCOMPLETE',self.call,'review_sheet',self.root,[first['id']],'user')
        attempt=self.call('pool_reserve',self.root,first['id'])
        self.assertIn('fidelity',[x['id'] for x in attempt['blocking_findings']])
        child=self.call('pool_import',self.root,first['id'],attempt['token'],self.raw,self.prompt,
                        [Path(p) for p in attempt['reference_paths']])['asset']
        self.assertEqual(child['prop_action'],'add')
        self.assertNotIn('fidelity_review',child)

    def test_human_revision_retains_operation_and_needs_fresh_review(self):
        for action in outfits.PROP_ACTIONS:
            with self.subTest(action=action):
                parent=self.candidate(action);self.review(parent)
                page,_=self.feedback(parent,'revise')
                plan=self.call('revision_prepare',self.root,page['packet'],self.prop_contract())
                self.assertEqual(plan['edit']['prop_action'],action)
                child=self.call('revision_import',self.root,plan['revision'],self.raw,self.prompt,[Path(p) for p in plan['reference_paths']])['asset']
                self.assertEqual(child['parent_asset_id'],parent['id'])
                self.assertEqual(child['prop_action'],action);self.assertEqual(child['edit_brief'],parent['edit_brief'])
                self.assertNotIn('human_feedback',child);self.assertNotIn('quality_review',child)
                self.assertEqual(outfits.read_state(self.root)['candidate_pools'][child['id']]['budget'],3)
                self.review(child);self.feedback(child)
                export=outfits.export_pack(self.root,ids=[child['id']])
                self.assertEqual(export['manifest']['sprites'][0]['prop_action'],action)

    def test_canvas_mismatch_keeps_raw_image_and_blocks_formal_adoption(self):
        fixture(self.raw,'#556677',size=(100,150))
        asset=self.candidate();self.review(asset)
        _,feedback=self.feedback(asset)
        self.assertEqual(feedback['blockers']['technical'],['CANVAS_MISMATCH'])
        self.assertEqual((self.root/asset['path']).read_bytes(),self.raw.read_bytes())
        self.assertEqual(outfits.read_state(self.root)['selected'],{})

    def test_props_cannot_enter_expression_projects(self):
        state=outfits.read_state(self.root);state['module']='expressions';state['schema_version']='1.0'
        outfits.write_state(self.root,state)
        self.code('WRONG_MODULE',self.prepare)

    def test_mixed_garment_and_prop_project_never_downgrades(self):
        prop=self.candidate();self.review(prop);self.feedback(prop)
        brief=outfits.prepare_outfit(self.root,'coat','coat',None,'collar',['face'],[10,30,85,120],edit_type='replace',replacement='jacket')
        outfits.add_asset(self.root,self.raw,'coat','coat',replacement='jacket',prompt_file=self.prompt,brief_file=Path(brief['brief_file']))
        self.assertEqual(outfits.read_state(self.root)['schema_version'],'1.5')
        export=outfits.export_pack(self.root,ids=[prop['id']]);self.assertEqual(export['manifest']['schema_version'],'1.5')

    def test_packaged_cli_handles_all_actions_and_languages_outside_repo(self):
        archive=self.folder/'plugin.zip';builder.build(REPO,archive)
        installed=self.folder/'installed'
        with zipfile.ZipFile(archive) as package:
            self.assertFalse(any(name.endswith('.html') for name in package.namelist()))
            package.extractall(installed)
        script=installed/'skills/charakit-outfits/scripts/studio.py'
        for action in outfits.PROP_ACTIONS:
            options=['--replacement',self.design] if action!='remove' else []
            args=[sys.executable,str(script),'prepare','--project',str(self.root),'--outfit','cli_'+action,
                  '--edit-type','prop_edit','--prop-action',action,'--target',self.target,
                  '--boundary','必要的接触和遮挡补全','--protect','人物、服装、头发和姿势','--target-box','10','30','85','120',*options]
            run=subprocess.run(args,cwd=self.folder,capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(run.returncode,0,run.stderr);brief=json.loads(run.stdout)
            run=subprocess.run([sys.executable,str(script),'add','--project',str(self.root),'--outfit','cli_'+action,
                                '--target',self.target,'--image',str(self.raw),'--prompt-file',str(self.prompt),
                                '--brief-file',brief['brief_file'],*options],cwd=self.folder,capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(run.returncode,0,run.stderr);asset=json.loads(run.stdout)['asset']
            self.assertEqual(asset['prop_action'],action)
            for language in ('zh-CN','en'):
                page=self.call('review_sheet',self.root,[asset['id']],'assistant',language)
                public=json.loads(Path(page['public_packet']).read_text(encoding='utf-8'))
                expected={'add':'添加','remove':'移除','replace':'替换'}[action] if language=='zh-CN' else action.capitalize()
                self.assertTrue(public['request'].startswith(expected));self.assertIn(self.target,public['request'])


if __name__=='__main__':unittest.main()
