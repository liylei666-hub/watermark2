"""CPU audit of six recorded native inversions and cal-only perturbation trajectories."""
import argparse,json,os
from pathlib import Path
import sys
import numpy as np
from runtime_provenance import file_sha,array_binding
def rms(a,b):
    return float(np.sqrt(np.mean((a.astype(np.float64)-b.astype(np.float64))**2)))
def main():
    ap=argparse.ArgumentParser()
    for f in ('run','base-run','csi-code','output'):ap.add_argument('--'+f,required=True)
    args=ap.parse_args();root=Path(args.run);base=Path(args.base_run)
    inventory=json.loads((Path(__file__).resolve().parents[1]/'reports/reproduction_audit/csi_code_inventory.json').read_text(encoding='utf8'))
    assert inventory['commit']=='8723e362835a6a61efd11b61f677b3321face3fa'
    for entry in inventory['files']:assert file_sha(Path(args.csi_code)/entry['path'])==entry['sha256']
    sys.path.insert(0,args.csi_code)
    from csi.schemes.seal import SealCore
    from csi.types import Key
    core=SealCore(k=1024,b=7,t_patch=2.);key=Key(seed=42)
    frozen=json.loads((root/'gpu/frozen.json').read_text());runtime=json.loads((root/'gpu/runtime.json').read_text())
    assert file_sha(root/'inputs/focused_inversion_trace.py')==frozen['script_sha256']
    assert file_sha(root/'inputs/focused_stability.json')==frozen['config_sha256']
    assert file_sha(root/'cpu/cpu_results.json')==frozen['cpu_controls_sha256']
    cf=json.loads((root/'cpu/frozen.json').read_text())
    assert file_sha(root/'inputs/focused_cpu_controls.py')==cf['script_sha256']
    for name,digest in cf['input_hashes'].items():assert file_sha(base/name.replace('\\', '/'))==digest
    for name,digest in runtime['file_hashes'].items():assert file_sha(root/'gpu'/name)==digest
    assert json.loads((root/'gpu/exit_status.json').read_text())['exit_code']==0
    assert runtime['inversions']==6 and runtime['generated_images']==runtime['weights_downloaded_bytes']==0
    rows=json.loads((root/'gpu/results.json').read_text())
    assert {(r['source'],r['variant']) for r in rows}=={(s,v) for s in ('c04','c02') for v in ('original','lossless_pixel_identity','jpeg70')}
    cached={};max_l2=0.;max_normalize=0.
    os.environ['CUDA_VISIBLE_DEVICES']=''
    import torch
    torch.set_num_threads(4)
    # CPU step replay can differ by rounding across torch builds; report and bound it.
    source=Path(args.csi_code)/'csi/backends/sd.py'
    import ast
    fn=next(n for n in ast.parse(source.read_text(encoding="utf8")).body if isinstance(n,ast.FunctionDef) and n.name=='_backward_ddim')
    ns={};exec(compile(ast.Module(body=[fn],type_ignores=[]),str(source),'exec'),ns)
    update=ns['_backward_ddim']
    max_step_replay_delta=0.;max_scaled_delta=0.
    for row in rows:
        a=np.load(root/'gpu'/row['arrays_file'],allow_pickle=False)
        assert set(a.files)==set(row['array_bindings'])
        for k in a.files:assert array_binding(a[k])==row['array_bindings'][k]
        assert a['trajectory'].shape==(51,1,4,64,64) and a['model_inputs'].shape==a['epsilon_predictions'].shape==(50,1,4,64,64)
        assert np.array_equal(a['trajectory'][:-1],a['model_inputs'])
        assert np.array_equal(a['trajectory'][-1].astype(np.float64),a['recon'])
        assert row['unet_calls']==50 and row['classifier_free_guidance_branch'] is False
        assert all(s['batch_size']==1 for s in row['steps'])
        assert row['conditioning_binding']['shape'][0]==1
        expected=(a['input_rgb'].astype(np.float32)/255.).transpose(2,0,1)[None]*2.-1.
        delta=float(np.max(np.abs(expected.astype(np.float16)-a['vae_input_actual'])))
        max_normalize=max(max_normalize,delta);assert delta==0
        scaled=(torch.from_numpy(a['vae_mode_actual'])*row['latent_scale']*row['init_noise_sigma']).numpy()
        scaled_delta=float(np.max(np.abs(scaled.astype(float)-a['initial_update_latent'].astype(float))))
        max_scaled_delta=max(max_scaled_delta,scaled_delta);assert scaled_delta<=0.008
        for i,step in enumerate(row['steps']):
            actual=update(torch.from_numpy(a['trajectory'][i]),torch.tensor(step['alpha_from'],dtype=torch.float32),
                torch.tensor(step['alpha_to'],dtype=torch.float32),torch.from_numpy(a['epsilon_predictions'][i])).numpy()
            d=float(np.max(np.abs(actual.astype(float)-a['trajectory'][i+1].astype(float))))
            max_step_replay_delta=max(max_step_replay_delta,d)
            assert np.allclose(actual,a['trajectory'][i+1],rtol=0.003,atol=0.003)
        reference=core.noise_from_embedding(a['feature'],key)
        assert np.array_equal(reference,a['reference'])
        assert np.array_equal(core.bucket_ids(a['feature'],key),a['query_bucket_ids'])
        assert np.array_equal(core.bucket_ids(a['draft_feature'],key),a['draft_bucket_ids'])
        l2=core.patch_l2(a['recon'],reference);oracle=core.patch_l2(a['recon'],a['registered_z'])
        d=float(np.max(np.abs(l2-a['native_l2'])));max_l2=max(max_l2,d);assert d<=1e-12
        assert np.max(np.abs(oracle-a['oracle_l2']))<=1e-12
        E=a['query_bucket_ids']==a['draft_bucket_ids'];D=oracle<=2.;A=l2<=2.
        for k,mask in [('E',E),('D',D),('A',A)]:assert np.array_equal(a[k],mask)
        assert np.array_equal(A[E],D[E])
        assert row['match_count']==int(A.sum()) and row['E_intersect_D']==int((E&D).sum()) and row['A_outside_E']==int((A&~E).sum())
        prior=np.load(base/'calibration'/(row['source']+'_arrays.npz'),allow_pickle=False)
        v='original' if row['variant']=='lossless_pixel_identity' else row['variant']
        assert np.array_equal(a['feature'],prior[v+'_feature']) and np.array_equal(a['recon'],prior[v+'_recon'])
        assert row['feature_max_delta_from_prior']==row['recon_max_delta_from_prior']==row['reference_max_delta_from_prior']==0.
        image=root/'cpu'/(row['source']+'_lossless_pixel_identity.png') if row['variant']=='lossless_pixel_identity' else base/'prepare'/(row['source']+'_'+v+'.png')
        assert file_sha(image)==row['image_file_sha256']
        cached[(row['source'],row['variant'])]=a
    diagnostics={}
    for sid in ('c04','c02'):
        original=cached[(sid,'original')];identity=cached[(sid,'lossless_pixel_identity')];jpeg=cached[(sid,'jpeg70')]
        for k in original.files:assert np.array_equal(original[k],identity[k]),k
        trajectory=[rms(original['trajectory'][i],jpeg['trajectory'][i]) for i in range(51)]
        diagnostic={k:rms(original[k],jpeg[k]) for k in ('input_rgb','vae_input_actual','clip_input_float32','vae_mode_actual','initial_update_latent','recon')}
        diagnostic['trajectory_pair_rmse']=trajectory
        diagnostic['trajectory_final_to_initial_ratio']=trajectory[-1]/trajectory[0]
        diagnostic['model_input_pair_rmse']=[rms(original['model_inputs'][i],jpeg['model_inputs'][i]) for i in range(50)]
        diagnostic['epsilon_pair_rmse']=[rms(original['epsilon_predictions'][i],jpeg['epsilon_predictions'][i]) for i in range(50)]
        diagnostic['identity_all_arrays_exactly_equal']=True
        diagnostics[sid]=diagnostic
    result={'status':'passed','native_inversions':6,'steps_audited':300,'same_pixel_all_stages_exact':True,
        'same_input_matches_prior_run_exact':True,'max_native_l2_delta':max_l2,'max_vae_normalize_delta':max_normalize,
        'max_vae_scaled_cpu_replay_delta':max_scaled_delta,'max_step_cpu_replay_delta':max_step_replay_delta,
        'step_replay_tolerance':{'relative':0.003,'absolute':0.003},'cpu_torch':torch.__version__,
        'diagnostics':diagnostics,'scope':'same native implementation rerun with hooks, followed by CPU state/hash/math audit; cal-only mechanism exploration'}
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in result.items() if k!='diagnostics'},indent=2))
    print(json.dumps({s:{k:v for k,v in d.items() if not isinstance(v,list)} for s,d in diagnostics.items()},indent=2))
if __name__=='__main__':main()
