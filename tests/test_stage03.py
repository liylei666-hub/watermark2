import copy, json, os, tempfile, unittest
from pathlib import Path
import numpy as np
from stage02.core import HOST_GPUS, scores, validate_gpu_config
from stage03.protocol import build_prompts, validate_prompts, generation_jobs, stable_seed, donor_ids, save_once, validate_image_record, validate_manifest

ROOT=Path(__file__).resolve().parents[1]

class Stage03Tests(unittest.TestCase):
    def test_group_family_seed_and_reference(self):
        rows=build_prompts(ROOT);self.assertTrue(validate_prompts(rows))
        for change in ['split','seed','role','family']:
            bad=copy.deepcopy(rows)
            if change=='split':bad[0]['split']='test'
            if change=='seed':bad[0]['seeds'][1]=bad[0]['seeds'][0]
            if change=='role':bad[0]['reference_slot']=1
            if change=='family':bad[0]['family']=bad[20]['family']
            with self.assertRaises(ValueError):validate_prompts(bad)

    def test_preflight_exclusion_and_donors(self):
        rows=build_prompts(ROOT);jobs=generation_jobs(rows);pre=generation_jobs(rows,True)
        self.assertEqual(len(jobs),480);self.assertEqual(len(pre),16)
        self.assertFalse({p['seed'] for p in jobs}&{p['seed'] for p in pre})
        table={p['prompt_id']:p for p in rows}
        for p in rows:
            donors=donor_ids(rows,p);self.assertEqual(len(set(donors)),3)
            for d in donors:
                self.assertEqual(p['split'],table[d]['split']);self.assertNotEqual(p['family'],table[d]['family'])

    def test_resume_rejects_changed_artifact(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'lock.json';save_once(p,{'seed':1});save_once(p,{'seed':1})
            with self.assertRaises(ValueError):save_once(p,{'seed':2})
            self.assertEqual(json.loads(p.read_text()),{'seed':1})

    def test_generation_metadata_contract(self):
        job=generation_jobs(build_prompts(ROOT))[0]
        r=dict(job,generation_config_sha256='cfg',size=[1024,1024],mode='RGB',sha256='sha',pixel_sha256='pix',path='image.png',runtime_sha256='rt',seconds=1.)
        validate_image_record(r,job,'cfg')
        for field,value in [('seed',0),('mode','L'),('generation_config_sha256','other')]:
            bad=dict(r,**{field:value})
            with self.assertRaises(ValueError):validate_image_record(bad,job,'cfg')
        del r['runtime_sha256']
        with self.assertRaises(ValueError):validate_image_record(r,job,'cfg')

    def test_stage02_transform_pixel_regression(self):
        # Compare the shared helper to the saved stage02 output pixels, without rewriting them.
        from PIL import Image
        from stage02.data import allowed_variants
        manifest=json.loads((ROOT/'data/stage02/manifest.json').read_text(encoding='utf-8'));images={im['id']:im for im in manifest['images']};checked=0
        for pair in manifest['pairs']:
            if pair['category']!='A':continue
            left=ROOT/images[pair['left']]['path'];right=ROOT/images[pair['right']]['path']
            if not left.exists() or not right.exists():self.skipTest('Stage02 images available only on server')
            with Image.open(left) as original:
                candidates={name:new for name,new,params in allowed_variants(original)}
                suffix=pair['right'][len(pair['left'])+1:]
                self.assertTrue(np.array_equal(np.asarray(candidates[suffix]),np.asarray(Image.open(right))))
            checked+=1
        self.assertEqual(checked,120)

    def test_comparator_has_no_metadata_input(self):
        import inspect
        self.assertEqual(list(inspect.signature(scores).parameters),['a','b','model'])
        a=np.ones((256,384),dtype=np.float32)/np.sqrt(384);b=a.copy()
        score=scores(a,b,'dinov2')
        metadata={'prompt':'changed','seed':9,'split':'test','label':'B','mask':'irrelevant'}
        self.assertEqual(score,scores(a,b,'dinov2'));self.assertTrue(metadata)

    def test_stage03_gpu_gate_is_cpu_only(self):
        self.assertEqual(os.environ.get('CUDA_VISIBLE_DEVICES'),'')
        cfg=json.loads((ROOT/'configs/stage03.json').read_text())
        self.assertEqual(validate_gpu_config(cfg,HOST_GPUS[7],'dinov2'),7)
        for visible in ['6','GPU-forbidden-mock',HOST_GPUS[5],HOST_GPUS[7]+','+HOST_GPUS[5]]:
            with self.assertRaises(ValueError):validate_gpu_config(cfg,visible,'dinov2')

    def test_threshold_independent_of_test(self):
        from stage03.evaluate import fit_thresholds
        from stage02.core import METHODS
        cal=[dict(split='calibration',category='A',**{m:float(k) for m in METHODS}) for k in range(100)]
        test=[dict(split='test',category='A',**{m:-500. for m in METHODS})]
        self.assertEqual(fit_thresholds(cal,[.05,.01,.10]),fit_thresholds(cal+test,[.05,.01,.10]))

    def test_derived_manifest_checks(self):
        prompts=build_prompts(ROOT);jobs=generation_jobs(prompts)
        images=[dict(j,pixel_sha256=j['id'],transform='identity') for j in jobs]
        ref=images[0];variant=dict(ref,id='variant',transform='jpeg90',pixel_sha256='variant')
        images.append(variant)
        pair=dict(pair_id='a',left=ref['id'],right='variant',category='A',split=ref['split'])
        self.assertTrue(validate_manifest(images,[pair],prompts))
        bad=copy.deepcopy(images);bad[-1]['split']='test'
        with self.assertRaises(ValueError):validate_manifest(bad,[pair],prompts)
        bad=copy.deepcopy(images);bad[-1]['seed']=bad[1]['seed']
        with self.assertRaises(ValueError):validate_manifest(bad,[pair],prompts)

    def test_bootstrap_recalibrates_family_groups(self):
        from stage03.evaluate import bootstrap
        from stage02.core import METHODS
        rows=[]
        for split in ['calibration','test']:
            for k in range(3):
                for category in ['A','B_raw','B_post','D']:
                    rows.append(dict(split=split,family=f'{split}{k}',category=category,**{m:float(k if category=='A' else -1) for m in METHODS}))
        cfg=dict(targets_frr=[.05],bootstrap=dict(seed=1,replicates=20))
        result=bootstrap(rows,cfg)
        self.assertTrue(result['same_indices_all_methods'])
        first=result['intervals']['0.05'][METHODS[0]]
        for m in METHODS:self.assertEqual(first,result['intervals']['0.05'][m])
        self.assertTrue(first['B_raw']['degenerate']);self.assertEqual(first['B_raw']['upper'],0.)

if __name__=='__main__':unittest.main()
