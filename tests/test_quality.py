"""Internal delivery gates using synthetic fixtures, never claiming visual scores for real art."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

from test_studio import studio, SCRIPT, fixture
from test_outfits import outfits, SCRIPT as OUTFITS_SCRIPT


def assessment(scores=None, defects=None, uncertainties=None, domain="expression"):
    scores = scores or dict.fromkeys(studio.QUALITY_WEIGHTS, 5)
    return {"rubric_version": "1.0", "basis": "assistant", "request": "Synthetic fixture gate exercise only",
            "dimensions": {key: {"score": score, "evidence": "Synthetic test observation; not an artistic evaluation."}
                           for key, score in scores.items()},
            "inspection": dict.fromkeys(studio.QUALITY_INSPECTIONS, True),
            "critical_defects": defects or [], "uncertainties": uncertainties or [],
            "domain_review": {"version": "1.0", "kind": domain, "component": "Synthetic requested component",
                              "checks": {key: {"status": "passed", "evidence": "Synthetic gate fixture only"}
                                         for key in studio.DOMAIN_CHECKS[domain]}}}


class QualityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.source = self.folder/'原图.png'; fixture(self.source)
        self.root = self.folder/'角色项目'
        studio.init_project(self.root, self.source, 'test_character')
        self.prompt = self.folder/'prompt.txt'; self.prompt.write_text('Synthetic change request', encoding='utf-8')

    def candidate(self, size=(64,96)):
        image = self.folder/'generated.png'; fixture(image, size=size, color='#225577')
        return studio.add_asset(self.root, image, 'happy', self.prompt)['asset']

    def review(self, asset, data=None):
        preview = self.root/f'preview/{asset["id"]}-{len(studio.read_state(self.root)["assets"])}.png'
        if not preview.exists(): studio.make_preview(self.root, preview, [asset['id']], [16,10,48,36], 'light')
        return studio.record_quality(self.root, asset['id'], data or assessment(), [preview])

    def code(self, expected, call, *args, **kwargs):
        with self.assertRaises((studio.StudioError, outfits.StudioError)) as caught: call(*args, **kwargs)
        self.assertEqual(caught.exception.code, expected)

    def test_default_new_projects_require_review_before_acceptance_or_delivery(self):
        asset = self.candidate()
        self.assertEqual(asset['quality_required'], '1.0')
        self.code('QUALITY_REVIEW_REQUIRED', studio.review_asset, self.root, asset['id'], 'accepted')
        self.code('QUALITY_CHECK_FAILED', studio.delivery_assets, self.root, [asset['id']])
        self.assertEqual(studio.read_state(self.root)['selected'], {})

    def test_pass_delivers_without_fabricating_user_acceptance_and_exports_evidence(self):
        asset = self.candidate(); original = (self.root/asset['path']).read_bytes()
        result = self.review(asset)
        self.assertEqual((result['quality_status'], result['art_review_status']), ('passed','unreviewed'))
        self.assertEqual(result['selected'], {})
        self.assertEqual(studio.delivery_assets(self.root,[asset['id']])['delivery'][0]['quality_score'], 100)
        self.code('ART_REVIEW_REQUIRED', studio.export_pack, self.root, ids=[asset['id']])
        studio.review_asset(self.root, asset['id'], 'accepted', 'User selected it')
        export = studio.export_pack(self.root)
        with zipfile.ZipFile(export['export']) as z:
            sprite = export['manifest']['sprites'][0]
            self.assertEqual(z.read(sprite['path']), original)
            self.assertEqual(sprite['quality_review']['basis'], 'assistant')

    def test_total_floor_critical_defects_and_uncertainty_are_independent(self):
        cases = [({k:4 for k in studio.QUALITY_WEIGHTS}, [], [], 'failed'),
                 ({'target':5,'identity':5,'protection':5,'rendering':3}, [], [], 'failed'),
                 (None, ['Unrequested iris recoloring'], [], 'failed'),
                 (None, [], ['Protected detail is too small to inspect'], 'uncertain'),
                 ({'target':4,'identity':5,'protection':4,'rendering':4}, [], [], 'passed')]
        for scores,defects,unknown,status in cases:
            with self.subTest(status=status, scores=scores):
                asset=self.candidate(); result=self.review(asset, assessment(scores,defects,unknown))
                self.assertEqual(result['quality_status'], status)
                if status!='passed': self.code('QUALITY_CHECK_FAILED',studio.review_asset,self.root,asset['id'],'accepted')

    def test_uninspected_view_blocks_even_perfect_scores(self):
        asset=self.candidate(); data=assessment(); data['inspection']['normal_display']=False
        self.assertEqual(self.review(asset,data)['quality_status'],'uncertain')

    def test_invalid_scores_or_empty_evidence_do_not_mutate_metadata(self):
        asset=self.candidate(); preview=self.root/'preview/check.png'
        studio.make_preview(self.root,preview,[asset['id']])
        for bad in (True,5.0,float('nan'),6,-1):
            data=assessment();data['dimensions']['identity']['score']=bad
            before=(self.root/'run.json').read_bytes()
            self.code('INVALID_QUALITY_REVIEW',studio.record_quality,self.root,asset['id'],data,[preview])
            self.assertEqual((self.root/'run.json').read_bytes(),before)
        data=assessment();data['dimensions']['identity']['evidence']=''
        self.code('INVALID_QUALITY_REVIEW',studio.record_quality,self.root,asset['id'],data,[preview])
        data=assessment();data['basis']='automatic'
        self.code('INVALID_QUALITY_REVIEW',studio.record_quality,self.root,asset['id'],data,[preview])

    def test_caller_cannot_override_score_or_status(self):
        asset=self.candidate();data=assessment(defects=['Changed weapon geometry'])
        data.update(result={'status':'passed','total':100},asset_sha256='fake')
        result=self.review(asset,data)
        self.assertEqual(result['quality_status'],'failed')
        saved=studio.read_state(self.root)['assets'][0]['quality_review']
        self.assertEqual(saved['asset_sha256'],asset['sha256'])

    def test_canvas_mismatch_does_not_block_visual_review_or_preview_delivery(self):
        asset=self.candidate((32,48)); result=self.review(asset)
        self.assertFalse(result['technical_passed'])
        self.assertEqual(result['quality_status'],'passed')
        delivered=studio.delivery_assets(self.root,[asset['id']])['delivery'][0]
        self.assertIn('CANVAS_MISMATCH',delivered['warnings'])
        self.assertEqual(delivered['canvas'],{'width':32,'height':48})
        self.assertEqual(studio.read_state(self.root)['assets'][0]['validation']['errors'],['CANVAS_MISMATCH'])
        self.code('TECHNICAL_CHECK_FAILED',studio.review_asset,self.root,asset['id'],'accepted')
        self.assertTrue((self.root/asset['path']).is_file())

    def test_canvas_exception_does_not_hide_other_technical_failures(self):
        asset=self.candidate((32,48))
        fixture(self.root/asset['path'],size=(32,48),transparent=False)
        state=studio.read_state(self.root)
        state['assets'][0]['sha256']=studio.digest(self.root/asset['path'])
        studio.write_state(self.root,state)
        result=self.review(state['assets'][0])
        self.assertEqual(result['quality_status'],'failed')
        self.code('TECHNICAL_CHECK_FAILED',studio.delivery_assets,self.root,[asset['id']])

    def test_canvas_exception_never_overrides_visual_defects_or_uncertainty(self):
        asset=self.candidate((32,48))
        self.review(asset,assessment(defects=['Unrequested iris color change']))
        self.code('QUALITY_CHECK_FAILED',studio.delivery_assets,self.root,[asset['id']])
        result=self.review(asset,assessment(uncertainties=['Protected detail unverified']))
        self.assertEqual(result['quality_status'],'uncertain')
        self.code('QUALITY_CHECK_FAILED',studio.delivery_assets,self.root,[asset['id']])

    def test_revision_starts_pending_and_retains_previously_selected_version(self):
        first=self.candidate();self.review(first);studio.review_asset(self.root,first['id'],'accepted')
        second=self.candidate()
        self.assertNotIn('quality_review',second)
        self.assertNotIn('quality_history',second)
        self.assertEqual(second['parent_asset_id'],first['id'])
        self.code('QUALITY_REVIEW_REQUIRED',studio.review_asset,self.root,second['id'],'accepted')
        self.assertEqual(studio.read_state(self.root)['selected'],{'happy':first['id']})

    def test_failed_reassessment_clears_selection_but_retains_user_history(self):
        asset=self.candidate();self.review(asset);studio.review_asset(self.root,asset['id'],'accepted','User liked it')
        self.review(asset,assessment(defects=['Unexpected face redraw']))
        state=studio.read_state(self.root)
        self.assertEqual(state['selected'],{})
        self.assertEqual(state['assets'][0]['art_review_status'],'accepted')
        self.assertEqual(state['assets'][0]['review_note'],'User liked it')
        self.assertEqual(len(state['assets'][0]['quality_history']),2)
        self.code('QUALITY_CHECK_FAILED',studio.select_asset,self.root,asset['id'])
        self.code('QUALITY_CHECK_FAILED',studio.export_pack,self.root,ids=[asset['id']])

    def test_prompt_or_comparison_changes_invalidate_previous_pass(self):
        for kind in ('prompt','comparison'):
            with self.subTest(kind=kind):
                asset=self.candidate();self.review(asset);studio.review_asset(self.root,asset['id'],'accepted')
                saved=studio.read_state(self.root)['assets'][-1]
                path=self.root/(saved['prompt_path'] if kind=='prompt' else saved['quality_review']['comparisons'][0]['path'])
                path.write_bytes(path.read_bytes()+b' changed')
                self.code('QUALITY_CHECK_FAILED',studio.delivery_assets,self.root,[asset['id']])
                self.code('QUALITY_CHECK_FAILED',studio.export_pack,self.root,ids=[asset['id']])

    def test_candidate_change_cannot_reuse_or_replace_review(self):
        asset=self.candidate();self.review(asset)
        fixture(self.root/asset['path'],color='#cc4411')
        self.code('TECHNICAL_CHECK_FAILED',self.review,asset)
        self.code('TECHNICAL_CHECK_FAILED',studio.delivery_assets,self.root,[asset['id']])

    def test_legacy_read_is_unchanged_and_enabling_only_gates_future_candidates(self):
        state=studio.read_state(self.root);state.pop('quality_policy');studio.write_state(self.root,state)
        old=self.candidate();studio.review_asset(self.root,old['id'],'accepted','Prior user choice')
        before=(self.root/'run.json').read_bytes();studio.read_state(self.root)
        self.assertEqual((self.root/'run.json').read_bytes(),before)
        result=studio.enable_quality(self.root)
        self.assertEqual((self.root/'run.before-quality.backup.json').read_bytes(),before)
        self.assertEqual(result['quality_policy']['legacy_asset_ids'],[old['id']])
        enabled=(self.root/'run.json').read_bytes();studio.enable_quality(self.root)
        self.assertEqual((self.root/'run.json').read_bytes(),enabled)
        new=self.candidate();self.assertEqual(new['quality_required'],'1.0')
        self.assertNotIn('quality_review',studio.read_state(self.root)['assets'][0])
        self.code('QUALITY_CHECK_FAILED',studio.delivery_assets,self.root,[old['id']])
        self.assertEqual(studio.export_pack(self.root)['asset_ids'],[old['id']])

    def test_outfits_require_both_fidelity_and_quality(self):
        root=self.folder/'outfits';outfits.init_project(root,self.source,'test_character')
        prepared=outfits.prepare_outfit(root,'coat_navy','coat fabric','navy','Fabric only',['Face and all other parts'],[16,30,48,75])
        asset=outfits.add_asset(root,self.source,'coat_navy','coat fabric','navy',brief_file=Path(prepared['brief_file']))['asset']
        preview=root/'preview/check.png';outfits.make_preview(root,preview,[asset['id']])
        outfits.record_quality(root,asset['id'],assessment(domain='garment_recolor'),[preview])
        self.code('FIDELITY_REVIEW_REQUIRED',outfits.delivery_assets,root,[asset['id']])
        outfits.record_fidelity(root,asset['id'],'passed','passed','Synthetic findings only')
        self.assertEqual(len(outfits.delivery_assets(root,[asset['id']])['delivery']),1)
        outfits.record_fidelity(root,asset['id'],'passed','failed','Synthetic protection failure')
        self.code('FIDELITY_CHECK_FAILED',outfits.delivery_assets,root,[asset['id']])

    def test_delivery_is_atomic_for_mixed_pass_and_pending(self):
        first=self.candidate();self.review(first);second=self.candidate()
        self.code('QUALITY_CHECK_FAILED',studio.delivery_assets,self.root,[first['id'],second['id']])
        self.assertEqual(len(studio.delivery_assets(self.root,[first['id']])['delivery']),1)

    def test_cli_records_and_delivers_and_wrong_module_cannot_write(self):
        asset=self.candidate();preview=self.root/'preview/check.png';studio.make_preview(self.root,preview,[asset['id']])
        data=self.root/'assessment.json';data.write_text(json.dumps(assessment()),encoding='utf-8')
        args=['quality','--project',str(self.root),'--asset',asset['id'],'--assessment-file',str(data),'--comparison',str(preview)]
        before=(self.root/'run.json').read_bytes()
        bad=subprocess.run([sys.executable,str(OUTFITS_SCRIPT),*args],capture_output=True,encoding='utf-8')
        self.assertEqual(json.loads(bad.stderr)['error']['code'],'WRONG_MODULE')
        self.assertEqual((self.root/'run.json').read_bytes(),before)
        good=subprocess.run([sys.executable,str(SCRIPT),*args],capture_output=True,encoding='utf-8')
        self.assertEqual(good.returncode,0,good.stderr)
        result=subprocess.run([sys.executable,str(SCRIPT),'deliver','--project',str(self.root),'--asset',asset['id']],capture_output=True,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['delivery'][0]['art_review_status'],'unreviewed')

    def test_evidence_outside_project_or_standalone_candidate_is_rejected(self):
        asset=self.candidate()
        for path in (self.source,self.root/asset['path']):
            self.code('INVALID_QUALITY_REVIEW',studio.record_quality,self.root,asset['id'],assessment(),[path])

    def test_missing_required_flag_and_forged_total_are_invalid_metadata(self):
        asset=self.candidate();self.review(asset)
        original=json.loads((self.root/'run.json').read_text(encoding='utf-8'))
        for change in ('flag','total'):
            state=copy.deepcopy(original)
            if change=='flag': state['assets'][0].pop('quality_required')
            else: state['assets'][0]['quality_review']['result']['total']=99
            (self.root/'run.json').write_text(json.dumps(state),encoding='utf-8')
            self.code('INVALID_PROJECT',studio.read_state,self.root)
        (self.root/'run.json').write_text(json.dumps(original),encoding='utf-8')

    def test_domain_failure_vetoes_perfect_global_score_without_global_defect_list(self):
        asset=self.candidate();data=assessment()
        data['domain_review']['checks']['face_design']={'status':'failed','evidence':'Synthetic iris preservation failure'}
        result=self.review(asset,data)
        self.assertEqual(result['score']['total'],100)
        self.assertEqual(result['quality_status'],'failed')
        self.code('QUALITY_CHECK_FAILED',studio.delivery_assets,self.root,[asset['id']])

    def test_domain_uncertainty_blocks_delivery_without_global_uncertainty_list(self):
        asset=self.candidate();data=assessment()
        data['domain_review']['checks']['nonface_protection']['status']='uncertain'
        result=self.review(asset,data)
        self.assertEqual(result['quality_status'],'uncertain')
        self.code('QUALITY_CHECK_FAILED',studio.delivery_assets,self.root,[asset['id']])

    def test_new_review_requires_correct_and_complete_domain_with_no_mutation_on_error(self):
        asset=self.candidate();preview=self.root/'preview/domain-check.png';studio.make_preview(self.root,preview,[asset['id']])
        for error,change in [('DOMAIN_REVIEW_REQUIRED','absent'),('INVALID_DOMAIN_REVIEW','wrong'),('INVALID_DOMAIN_REVIEW','incomplete')]:
            data=assessment()
            if change=='absent':data.pop('domain_review')
            elif change=='wrong':data=assessment(domain='garment_recolor')
            else:data['domain_review']['checks'].pop('emotion')
            before=(self.root/'run.json').read_bytes()
            self.code(error,studio.record_quality,self.root,asset['id'],data,[preview])
            self.assertEqual((self.root/'run.json').read_bytes(),before)

    def test_explicit_mouth_state_requires_its_own_check_and_preserved_emotion(self):
        asset=studio.add_asset(self.root,self.source,'happy',mouth_state='open')['asset']
        preview=self.root/'preview/mouth-check.png';studio.make_preview(self.root,preview,[asset['id']])
        self.code('INVALID_DOMAIN_REVIEW',studio.record_quality,self.root,asset['id'],assessment(),[preview])
        data=assessment(domain='mouth_state')
        result=studio.record_quality(self.root,asset['id'],data,[preview]);self.assertEqual(result['quality_status'],'passed')
        data['domain_review']['checks']['emotion']={'status':'failed','evidence':'Synthetic speaking pose turned into surprise'}
        result=studio.record_quality(self.root,asset['id'],data,[preview]);self.assertEqual(result['quality_status'],'failed')

    def test_legacy_quality_reviews_read_without_invented_domain_checks(self):
        asset=self.candidate();self.review(asset)
        state=studio.read_state(self.root)
        state['assets'][0]['quality_review'].pop('domain_review')
        state['assets'][0]['quality_history'][0].pop('domain_review')
        studio.write_state(self.root,state);before=(self.root/'run.json').read_bytes()
        saved=studio.read_state(self.root)
        self.assertNotIn('domain_review',saved['assets'][0]['quality_review'])
        self.assertEqual(studio.quality_status(self.root,saved,saved['assets'][0]),'passed')
        self.assertEqual((self.root/'run.json').read_bytes(),before)


if __name__=='__main__': unittest.main()
