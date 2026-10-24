"""CPU tests of real feasibility, gradient composition, stopping and decision behavior."""
import copy,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
os.environ['CUDA_VISIBLE_DEVICES']=''
import numpy as np
import torch
import common as m
import quality as q
import attack,control,analyze,freeze

DESIGN=json.loads((Path(__file__).resolve().parents[2]/'protocols/29_quality_design.json').read_text())
POLICY=DESIGN['policy']


def rows(gain=.04):
    return [dict(task_id=i,kind=k,bit_accuracy=1. if k=='reference' else (.5 if k=='cover' else .65+(gain if k=='pixel10' else 0)),
                 gs_detected=k=='reference',cover_mse_rgb01=POLICY['mse_limit'],core_seconds=365.)
            for i in range(1,17) for k in ('reference','cover')+m.METHODS]


class Numerical(unittest.TestCase):
    def test_quantizer_keeps_exact_cover(self):
        image=np.random.default_rng(1).integers(0,256,(64,64,3),dtype=np.uint8)
        value,cert=q.quantize_feasible(image.astype(np.float32)/255,image,POLICY['mse_limit'],16)
        np.testing.assert_array_equal(value,image);self.assertEqual(cert['squared_byte_error'],0)

    def test_quality_at_boundary_and_deterministic(self):
        cover=np.full((512,512,3),128,dtype=np.uint8)
        value=cover/255+np.sqrt(POLICY['mse_limit'])
        a,cert=q.quantize_feasible(value,cover,POLICY['mse_limit'],16)
        b,_=q.quantize_feasible(value,cover,POLICY['mse_limit'],16)
        np.testing.assert_array_equal(a,b)
        self.assertTrue(cert['feasible']);self.assertGreaterEqual(cert['mse_rgb01']/POLICY['mse_limit'],.999)

    def test_random_and_clipped_images_stay_feasible(self):
        rng=np.random.default_rng(91)
        for mse in (1e-7,1e-4,POLICY['mse_limit']):
            for level in (1,16):
                for repeat in range(5):
                    cover=rng.integers(0,256,(27,39,3),dtype=np.uint8)
                    value=cover/255+rng.normal(0,.3,cover.shape)
                    result,cert=q.quantize_feasible(value,cover,mse,level)
                    self.assertTrue(cert['feasible']);self.assertEqual(result.dtype,np.uint8)
                    self.assertTrue(q.certify(result,cover,mse,level)['feasible'])

    def test_nonfinite_input_rejected(self):
        with self.assertRaises(ValueError):q.quantize_feasible(np.full((2,2,3),np.nan),np.zeros((2,2,3),dtype=np.uint8),.001,16)

    def test_continuous_projection_respects_intersection(self):
        torch.manual_seed(4);cover=torch.rand(1,3,23,27);value=torch.nn.Parameter(torch.randn_like(cover)*10)
        q.project_tensor(value,cover,POLICY['mse_limit'],16)
        self.assertTrue(torch.all((value>=0)&(value<=1)))
        self.assertLessEqual(float((value-cover).abs().max()),16/255+1e-7)
        self.assertLessEqual(float((value-cover).square().mean()),POLICY['mse_limit']+1e-10)

    def test_split_chain_matches_full_nonlinear_gradient(self):
        torch.manual_seed(3);a=torch.randn(7,11,dtype=torch.float64);b=torch.randn(5,7,dtype=torch.float64)
        mapping=lambda x:torch.tanh(a@x)
        inverse=lambda z:(b@z).sin()
        target=torch.randn(5,dtype=torch.float64);x=torch.randn(11,dtype=torch.float64,requires_grad=True)
        expected=torch.autograd.grad((inverse(mapping(x))-target).square().mean(),x)[0]
        got=x.detach().clone().requires_grad_(True);attack.split_gradient(got,mapping,inverse,target)
        torch.testing.assert_close(got.grad,expected,rtol=1e-12,atol=1e-12)

    def test_measured_stop_reserves_finalization(self):
        self.assertTrue(q.enough_time(300,[35,36],50,380,8))
        self.assertFalse(q.enough_time(335,[35,36],50,380,8))
        self.assertFalse(q.enough_time(309,[],50,380,8))

    def test_decision_gates_and_ceiling(self):
        self.assertTrue(m.decide(rows(),DESIGN['decision_rule'])['decision'].startswith('advance_'))
        self.assertTrue(m.decide(rows(-.04),DESIGN['decision_rule'])['decision'].startswith('close_'))
        mixed=rows()
        for row in mixed:
            if row['kind']=='pixel10':row['bit_accuracy']=.85 if row['task_id']<9 else .55
        self.assertTrue(m.decide(mixed,DESIGN['decision_rule'])['decision'].startswith('close_'))
        saturated=rows()
        for row in saturated:
            if row['kind'] in m.METHODS:row['bit_accuracy']=1.
        self.assertEqual(m.decide(saturated,DESIGN['decision_rule'])['decision'],'inconclusive_continuous_endpoint_ceiling')
        self.assertEqual(m.decide(rows()[:-1],DESIGN['decision_rule'])['decision'],'inconclusive_missing_evidence')

    def test_attacker_sources_exclude_secret_and_target_configuration(self):
        pins={'/a/attack.py':'a','/a/target/config.json':'b','/a/proxy/config.json':'c','/a/private_eval/key.bin':'d'}
        self.assertEqual(set(freeze.attack_source_pins(pins,'/a/proxy')),{'/a/attack.py','/a/proxy/config.json'})


class Workflow(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='quality_test_',dir=Path(__file__).resolve().parents[2]);self.root=Path(self.temp.name)
        for name in ('runs','private_eval','protocols'):(self.root/name).mkdir()
        self.runtime=self.root/'protocols/runtime.json';self.runtime.write_text('{}')
        self.cfg=dict(device=dict(index=0,uuid='GPU-test-0',model='CPU fixture'),run_dir='runs/test',private_folder='private_eval/test',
            runtime_paths={k:'protocols/runtime.json' for k in ('attacker','evaluator','controller')},
            runtime_sha256={k:m.c.sha(self.runtime) for k in ('attacker','evaluator')},source_commit='fixture',
            max_new_bytes=10*1024**3,watchdog_seconds=1200,design=DESIGN,policy=POLICY,proxy=DESIGN['proxy'])
        self.calls=[]
    def tearDown(self):self.temp.cleanup()
    def run_fixture(self,fail=None,bad_cost=False,bad_quality=False):
        cfg=self.cfg;calls=self.calls
        class Runner(control.PilotRunner):
            def __call__(self,job,device,output,environment):
                from PIL import Image
                calls.append(job.name)
                if environment['CUDA_VISIBLE_DEVICES']!=device.uuid:raise AssertionError('Device binding')
                if job.name==fail:return dict(completed=False,exit_code=1)
                if job.name.startswith('prepare_'):
                    role=job.name.removeprefix('prepare_')
                    for sid in range(1,17):
                        folder=output/str(sid);folder.mkdir();Image.new('RGB',(512,512),(128,128,128)).save(folder/(role+'.png'))
                elif job.name.startswith('attack_'):
                    path=Path(self.commands[job.name][1][0]);data=m.validate_job(path,cfg)
                    if any(k in data for k in ('target','key','message','private_folder')):raise AssertionError('Information boundary')
                    cover=np.asarray(Image.open(path.parent/'cover.png')).copy()
                    pixels,cert=q.quantize_feasible(cover/255+(0 if bad_quality else np.sqrt(POLICY['mse_limit'])),cover,POLICY['mse_limit'],16)
                    Image.fromarray(pixels).save(output/'candidate.png')
                    m.c.write(output/'candidate_frozen.json',dict(task_id=data['task_id'],method=data['method'],job_sha256=m.c.sha(path),image=m.c.png_record(output/'candidate.png')))
                    m.c.write(output/'summary.json',dict(quality=cert,core_seconds=790 if bad_cost else 730))
                elif job.name=='evaluate':
                    if len(calls)!=36:raise AssertionError('Early target evaluation')
                    m.verify_seal(output.parent)
                return dict(completed=True,exit_code=0)
        def finish(*args):
            value=dict(decision={'decision':'fixture'});m.c.write(args[0]/'analysis.json',value);return value
        with patch.object(control,'ROOT',self.root),patch.object(control.launch,'check_host',lambda _:None),patch.object(control.r,'verify_runtime',lambda _:cfg),patch.object(control.sched,'verify_idle',lambda *args:True),patch.object(control,'PilotRunner',Runner),patch.object(analyze,'analyze',finish):
            control.run(self.runtime)
    def test_complete_unique_claims_and_order(self):
        self.run_fixture();self.assertEqual(len(self.calls),36);self.assertEqual(len(set(self.calls)),36)
        self.assertEqual(self.calls[:3],['qualification','prepare_reference','prepare_cover'])
        self.assertEqual(self.calls[-1],'evaluate')
    def test_qualification_failure_stops_all_benchmark_work(self):
        with self.assertRaises(RuntimeError):self.run_fixture(fail='qualification')
        self.assertEqual(self.calls,['qualification'])
    def test_attack_failure_no_retry_or_target(self):
        with self.assertRaises(RuntimeError):self.run_fixture(fail='attack_1_pixel10')
        self.assertNotIn('evaluate',self.calls);before=list(self.calls)
        with self.assertRaises(ValueError):self.run_fixture()
        self.assertEqual(before,self.calls)
    def test_cost_mismatch_blocks_target(self):
        with self.assertRaisesRegex(RuntimeError,'prerequisites'):self.run_fixture(bad_cost=True)
        self.assertNotIn('evaluate',self.calls)
    def test_underused_quality_blocks_target(self):
        with self.assertRaisesRegex(RuntimeError,'prerequisites'):self.run_fixture(bad_quality=True)
        self.assertNotIn('evaluate',self.calls)
    def test_existing_owner_blocks_claims(self):
        with m.sched.project_lock(self.root/'runs/.imprint_delivery.lock'):
            with self.assertRaises(OSError):self.run_fixture()
        self.assertFalse((self.root/'runs/test').exists())


if __name__=='__main__':unittest.main()
