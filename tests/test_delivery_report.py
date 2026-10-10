"""Report gating, snapshots and provenance using synthetic images, not visual quality tests."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_studio import studio, SCRIPT, fixture
from test_quality import assessment


class DeliveryReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.source = self.folder/'原图.png'; fixture(self.source)
        self.raw = self.folder/'generated.png'; fixture(self.raw,color='#225577')
        self.prompt = self.folder/'prompt.txt'; self.prompt.write_text('Synthetic test edit.',encoding='utf-8')
        self.root = self.folder/'expressions'
        studio.init_project(self.root,self.source,'test_character')

    def candidate(self, expression='happy', root=None, mouth='default'):
        root = root or self.root
        if studio.read_state(root).get('module')=='outfits':
            return studio.add_outfit(root,self.raw,expression,'袜子','白色',self.prompt)['asset']
        return studio.add_asset(root,self.raw,expression,self.prompt,mouth)['asset']

    def review(self, asset, passed=True, root=None):
        root = root or self.root
        kind = studio.quality_domain(studio.read_state(root),asset)
        data=assessment(scores=dict.fromkeys(studio.QUALITY_WEIGHTS,4),domain=kind)
        data['rubric_version']='1.1'
        if not passed:
            key='interfaces' if kind=='garment_recolor' else 'face_design'
            data['domain_review']['checks'][key]={'status':'failed','evidence':'Synthetic protected component changed.'}
        preview=root/'preview'/f'{asset["id"]}.png'
        studio.make_preview(root,preview,[asset['id']])
        if kind=='garment_recolor':
            studio.record_fidelity(root,asset['id'],'passed' if passed else 'failed','passed','Synthetic observations.')
        studio.record_quality(root,asset['id'],data,[preview])

    def report(self, roots=None, name='delivery', **options):
        result=studio.generate_report(roots or [self.root],self.folder/name,**options)
        data=json.loads(Path(result['manifest']).read_text(encoding='utf-8'))
        return result,data

    def revision(self, case):
        plan=studio.refinement_status(self.root,case)
        return studio.add_refinement(self.root,case,self.raw,self.prompt,[Path(p) for p in plan['references'].values()])['asset']

    def test_mixed_modules_copy_only_passed_finals_and_do_not_mutate_inputs(self):
        passed=self.candidate();self.review(passed)
        failed=self.candidate('angry');self.review(failed,False)
        root=self.folder/'outfits';studio.init_project(root,self.source,'test_character',module='outfits')
        outfit=self.candidate('stockings_white',root);self.review(outfit,root=root)
        files=[p for r in (self.root,root) for p in r.rglob('*') if p.is_file()]
        before={p:p.read_bytes() for p in files}
        result,data=self.report([self.root,root],face_box=[10,10,40,40],labels={'happy':'开心','stockings_white':'白丝'})
        self.assertEqual(data['summary'],{'cases':3,'passed':2,'other':1,'images':3})
        self.assertEqual(len(result['images']),2)
        self.assertTrue(Path(result['preview']).is_file())
        self.assertEqual(sum(c['final'] is None for c in data['cases']),1)
        for c in data['cases']:
            if c['final']:
                self.assertEqual((self.folder/'delivery'/c['final']['path']).read_bytes(),Path(c['final']['original_image']).read_bytes())
        for artifact in data['artifacts']:
            self.assertEqual(studio.digest(self.folder/'delivery'/artifact['path']),artifact['sha256'])
        self.assertEqual(before,{p:p.read_bytes() for p in files})

    def test_exhausted_case_produces_report_only_without_promoting_best_failed(self):
        first=self.candidate();self.review(first,False);studio.start_refinement(self.root,first['id'])
        for _ in range(2):self.review(self.revision(first['id']),False)
        result,data=self.report()
        self.assertEqual(data['cases'][0]['status'],'exhausted')
        self.assertEqual(len(data['cases'][0]['history']),3)
        self.assertEqual(result['images'],[]);self.assertIsNone(result['preview'])
        self.assertEqual(list((self.folder/'delivery').rglob('*.png')),[])
        self.assertIsNone(data['cases'][0]['final'])
        self.assertTrue(data['cases'][0]['history'][-1]['issues'])
        self.assertTrue(Path(result['report']).is_file())

    def test_explicit_first_asset_resolves_current_case_and_preserves_budget(self):
        first=self.candidate();self.review(first,False);studio.start_refinement(self.root,first['id'])
        final=self.revision(first['id']);self.review(final)
        other=self.candidate('angry');self.review(other)
        before=(self.root/'run.json').read_bytes()
        result,data=self.report(ids=[first['id']])
        self.assertEqual(data['summary']['cases'],1)
        self.assertEqual(data['cases'][0]['history'][-1]['asset_id'],final['id'])
        self.assertIn(final['id'],result['images'][0])
        self.assertEqual(len(data['cases'][0]['history']),2)
        self.assertEqual((self.root/'run.json').read_bytes(),before)

    def test_latest_failed_version_does_not_fall_back_to_older_pass(self):
        first=self.candidate();self.review(first)
        latest=self.candidate();self.review(latest,False)
        result,data=self.report()
        self.assertEqual(result['images'],[])
        self.assertEqual(data['cases'][0]['history'][-1]['asset_id'],latest['id'])
        self.assertEqual(data['summary']['images'],2)

    def test_pending_quality_or_fidelity_is_not_completed_success(self):
        pending=self.candidate()
        result,data=self.report(name='pending-quality')
        self.assertEqual(data['cases'][0]['status'],'review')
        self.assertIsNone(data['cases'][0]['history'][0]['recorded_score'])
        self.assertEqual(result['images'],[])
        root=self.folder/'outfits';studio.init_project(root,self.source,'test_character',module='outfits')
        asset=self.candidate('white',root)
        data_review=assessment(domain='garment_recolor')
        preview=root/'preview/check.png';studio.make_preview(root,preview,[asset['id']])
        studio.record_quality(root,asset['id'],data_review,[preview])
        studio.start_refinement(root,asset['id'])
        result,data=self.report([root],name='pending-fidelity')
        self.assertEqual(data['cases'][0]['status'],'review')
        self.assertEqual(result['images'],[])

    def test_stale_evidence_changed_candidate_and_user_rejection_block_delivery(self):
        for defect in ('prompt','candidate','rejected'):
            with self.subTest(defect=defect):
                root=self.folder/defect;studio.init_project(root,self.source,'test_character')
                asset=self.candidate(root=root);self.review(asset,root=root)
                if defect=='prompt':(root/asset['prompt_path']).write_text('Changed text',encoding='utf-8')
                elif defect=='candidate':fixture(root/asset['path'],color='#ff0000')
                else:studio.review_asset(root,asset['id'],'rejected','User rejected.')
                result,data=self.report([root],name='report-'+defect)
                self.assertEqual(result['images'],[])
                self.assertEqual(data['cases'][0]['status'],'blocked')
                if defect!='rejected':self.assertFalse(data['cases'][0]['history'][-1]['score_valid'])

    def test_canvas_mismatch_remains_warning_and_png_bytes_are_not_resized(self):
        fixture(self.raw,size=(32,48))
        asset=self.candidate();self.review(asset)
        result,data=self.report()
        self.assertEqual(data['summary']['passed'],1)
        final=data['cases'][0]['final']
        self.assertEqual(final['canvas'],{'width':32,'height':48})
        self.assertIn('CANVAS_MISMATCH',final['warnings'])
        self.assertEqual(Path(result['images'][0]).read_bytes(),self.raw.read_bytes())
        self.assertEqual(studio.read_state(self.root)['selected'],{})

    def test_existing_output_invalid_scope_and_bad_source_are_not_overwritten(self):
        first=self.candidate();self.review(first)
        result,_=self.report();before=Path(result['report']).read_bytes()
        with self.assertRaises(FileExistsError):self.report()
        self.assertEqual(Path(result['report']).read_bytes(),before)
        for roots,options in [([self.root,self.root],{}),([self.root],{'ids':[first['id'],first['id']]}),([self.root],{'face_box':[0,0,999,999]})]:
            with self.assertRaises(studio.StudioError):self.report(roots,name='invalid',**options)
            self.assertFalse((self.folder/'invalid').exists())
        fixture(self.root/'source.png',color='#00ff00')
        with self.assertRaises(studio.StudioError):self.report(name='bad-source')
        self.assertFalse((self.folder/'bad-source').exists())

    def test_cli_supports_english_paths_with_spaces_and_user_labels(self):
        asset=self.candidate();self.review(asset)
        labels=self.folder/'labels.json';labels.write_text(json.dumps({'happy':'Happy / smiling [test]'}),encoding='utf-8')
        result=subprocess.run([sys.executable,str(SCRIPT),'report','--project',str(self.root),'--output',str(self.folder/'报告 output'),'--language','en','--labels-file',str(labels)],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stderr)
        output=json.loads(result.stdout)
        data=json.loads(Path(output['manifest']).read_text(encoding='utf-8'))
        self.assertEqual(data['language'],'en')
        self.assertEqual(data['cases'][0]['label'],'Happy / smiling [test]')
        self.assertTrue(Path(output['preview']).exists())

    def test_changed_evidence_during_assembly_does_not_leave_delivery_output(self):
        asset=self.candidate();self.review(asset)
        original_copy=studio.generate_report.__globals__['copy_exclusive']
        def mutate_after_copy(source,target):
            original_copy(source,target)
            (self.root/asset['prompt_path']).write_text('Changed during assembly',encoding='utf-8')
        with patch.dict(studio.generate_report.__globals__,copy_exclusive=mutate_after_copy):
            with self.assertRaises(studio.StudioError):self.report()
        self.assertFalse((self.folder/'delivery').exists())
        self.assertEqual(list(self.folder.glob('.report-*')),[])


if __name__=='__main__':unittest.main()
