"""CPU audit and descriptive summaries of only the newly bounded codec/bypass runs."""
import argparse, ast, csv, json, os, sys
from pathlib import Path
import numpy as np
from PIL import Image, JpegImagePlugin
from runtime_provenance import array_binding, file_sha

def rmse(a,b):
    return float(np.sqrt(np.mean((a.astype(np.float64)-b.astype(np.float64))**2)))

def patch_l2(a,b):
    delta=a.astype(float)-b.astype(float)
    return np.array([np.linalg.norm(delta[0,:,y:y+2,x:x+2].ravel()) for y in range(0,64,2) for x in range(0,64,2)])

def quantiles(a):
    return dict(zip(['min','p05','p25','median','p75','p95','max'],[float(x) for x in np.percentile(a,[0,5,25,50,75,95,100])]))

def main():
    ap=argparse.ArgumentParser()
    for f in ('run','base-run','trace-run','csi-code'):ap.add_argument('--'+f,required=True)
    args=ap.parse_args();root,base,trace=map(Path,[args.run,args.base_run,args.trace_run])
    cfg=json.loads((root/'inputs/limited_codec_bypass.json').read_text(encoding='utf8'))
    assert cfg['budgets']=={'jpeg_inversions':2,'replay_generations':2,'bypass_inversions':2,'fp32_inversions':0,'new_weight_download_bytes':0,'paid_calls':0}
    assert cfg['thresholds']=={'patch_l2':2,'count_unchecked':10,'calibrated_count':0,'degenerate_operating_point':True}
    backend=Path(args.csi_code)/'csi/backends/sd.py'
    inventory=json.loads((Path(__file__).resolve().parents[1]/'reports/reproduction_audit/csi_code_inventory.json').read_text(encoding='utf8'))
    for item in inventory['files']:assert file_sha(Path(args.csi_code)/item['path'])==item['sha256']
    sys.path.insert(0,args.csi_code)
    from csi.schemes.seal import SealCore
    from csi.types import Key
    core=SealCore(k=1024,b=7,t_patch=2.);key=Key(seed=42)
    os.environ['CUDA_VISIBLE_DEVICES']=''
    import torch
    torch.set_num_threads(4)
    fn=next(n for n in ast.parse(backend.read_text(encoding='utf8')).body if isinstance(n,ast.FunctionDef) and n.name=='_backward_ddim')
    ns={};exec(compile(ast.Module(body=[fn],type_ignores=[]),str(backend),'exec'),ns);update=ns['_backward_ddim']
    runtimes={};frozen={};rows={}
    for phase in ('jpeg','replay','bypass'):
        folder=root/phase
        f=json.loads((folder/'frozen.json').read_text());r=json.loads((folder/'runtime.json').read_text())
        assert file_sha(root/'inputs/limited_codec_bypass.py')==f['script_sha256']
        assert file_sha(root/'inputs/limited_codec_bypass.json')==f['config_sha256']
        assert file_sha(backend)==f['csi_backend_sha256']
        assert file_sha(trace/'frozen.json')==f['trace_frozen_sha256']
        assert file_sha(base/'prepare/frozen.json')==f['prepare_frozen_sha256']
        for name,h in f['source_bindings'].items():assert file_sha(base/'prepare'/name)==h
        for name,h in r['file_hashes'].items():assert file_sha(folder/name)==h
        assert json.loads((folder/'exit_status.json').read_text())['exit_code']==0
        assert r['weights_downloaded_bytes']==0 and r['gpu_uuid']==cfg['physical_gpu_uuid']
        assert f['logical_gpu']==0 and f['preflight']['cuda_visible_devices']==cfg['physical_gpu_uuid']
        runtimes[phase]=r;frozen[phase]=f;rows[phase]=json.loads((folder/'results.json').read_text())
    assert runtimes['jpeg']['inversions']==2 and runtimes['jpeg']['generated_images']==0
    assert runtimes['replay']['inversions']==0 and runtimes['replay']['generated_images']==2
    assert runtimes['bypass']['inversions']==2 and runtimes['bypass']['generated_images']==0
    assert file_sha(root/'replay/frozen.json')==frozen['bypass']['replay_frozen_sha256']
    codec=json.loads((root/'jpeg/codec_control.json').read_text())
    assert codec['baseline_jpeg70_420_bytes_exact'] and codec['baseline_jpeg70_420_decoded_rgb_exact']
    assert codec['prior_jpeg_sha256']==file_sha(base/'prepare/c04_jpeg70.jpg')
    trace_rt=json.loads((trace/'runtime.json').read_text())
    original={};jpeg_data={};bypass_data={};replay_data={}
    for sid in cfg['paired_sources']:
        for name in (sid+'_original.npz',):assert file_sha(trace/name)==trace_rt['file_hashes'][name]
        with np.load(trace/(sid+'_original.npz'),allow_pickle=False) as a:original[sid]={k:a[k].copy() for k in a.files}
    assert file_sha(trace/'c04_jpeg70.npz')==trace_rt['file_hashes']['c04_jpeg70.npz']
    with np.load(trace/'c04_jpeg70.npz',allow_pickle=False) as a:baseline={k:a[k].copy() for k in a.files}
    max_l2=max_step=max_scale=max_decoder=0.;steps_audited=0
    for phase in ('jpeg','bypass'):
        for row in rows[phase]:
            assert row.get('bypass_executed',True)
            with np.load(root/phase/row['arrays_file'],allow_pickle=False) as a:
                data={k:a[k].copy() for k in a.files}
            assert set(data)==set(row['array_bindings'])
            for k,v in data.items():assert np.isfinite(v).all() and array_binding(v)==row['array_bindings'][k]
            assert data['recon'].shape==(1,4,64,64)
            assert data['trajectory'].shape==(51,1,4,64,64)
            assert data['model_inputs'].shape==data['epsilon_predictions'].shape==(50,1,4,64,64)
            assert np.array_equal(data['trajectory'][:-1],data['model_inputs'])
            assert np.array_equal(data['trajectory'][-1].astype(float),data['recon'])
            assert row['unet_calls']==50 and all(s['batch_size']==1 for s in row['steps'])
            assert row['conditioning_binding']==json.loads((trace/'results.json').read_text())[0]['conditioning_binding']
            ref=core.noise_from_embedding(data['feature'],key)
            assert np.array_equal(ref,data['reference'])
            assert np.array_equal(core.bucket_ids(data['feature'],key),data['query_bucket_ids'])
            assert np.array_equal(core.bucket_ids(data['draft_feature'],key),data['draft_bucket_ids'])
            assert np.array_equal(core.noise_from_embedding(data['draft_feature'],key),data['registered_z'])
            nl=patch_l2(data['recon'],ref);ol=patch_l2(data['recon'],data['registered_z'])
            max_l2=max(max_l2,float(np.max(np.abs(nl-data['native_l2']))),float(np.max(np.abs(ol-data['oracle_l2']))))
            assert max_l2<=1e-12
            E=data['query_bucket_ids']==data['draft_bucket_ids'];D=ol<=2.;A=nl<=2.
            for name,mask in [('E',E),('D',D),('A',A)]:assert np.array_equal(mask,data[name])
            assert int(A.sum())==row['match_count'] and int(D.sum())==row['oracle_matches'] and int(E.sum())==row['E']
            assert int((E&D).sum())==row['E_intersect_D'] and int((A&~E).sum())==row['A_outside_E']
            assert np.array_equal(A[E],D[E])
            for i,step in enumerate(row['steps']):
                replay=update(torch.from_numpy(data['trajectory'][i]),torch.tensor(step['alpha_from'],dtype=torch.float32),
                    torch.tensor(step['alpha_to'],dtype=torch.float32),torch.from_numpy(data['epsilon_predictions'][i])).numpy()
                max_step=max(max_step,float(np.max(np.abs(replay.astype(float)-data['trajectory'][i+1].astype(float)))))
                assert np.allclose(replay,data['trajectory'][i+1],rtol=.003,atol=.003);steps_audited+=1
            sid=row['source']
            if phase=='jpeg':
                v=row['variant'];assert v in cfg['jpeg_variants']
                name=sid+'_'+v['id']
                assert file_sha(root/phase/(name+'.png'))==row['input_image_sha256']
                assert file_sha(root/phase/(name+'.jpg'))==row['jpeg_sha256']
                jpg=Image.open(root/phase/(name+'.jpg'));assert JpegImagePlugin.get_sampling(jpg)==v['subsampling']
                assert np.array_equal(np.array(jpg.convert('RGB')),data['input_rgb'])
                assert np.array_equal(np.array(Image.open(root/phase/(name+'.png')).convert('RGB')),data['input_rgb'])
                expected=((data['input_rgb'].astype(np.float32)/255.).transpose(2,0,1)[None]*2.-1.).astype(np.float16)
                assert np.array_equal(expected,data['vae_input_actual'])
                scaled=(torch.from_numpy(data['vae_mode_actual'])*row['latent_scale']).numpy()
                max_scale=max(max_scale,float(np.max(np.abs(scaled.astype(float)-data['initial_update_latent'].astype(float)))))
                assert np.allclose(scaled,data['initial_update_latent'],rtol=.0005,atol=.008)
                jpeg_data[v['id']]=data
            else:
                assert row['vae_bypassed'] and 'vae_mode_actual' not in data and 'vae_input_actual' not in data
                assert file_sha(root/'replay'/(sid+'_replay.npz'))==row['paired_replay_file_sha256']
                for k in ('feature','reference','registered_z','input_rgb','query_bucket_ids','draft_bucket_ids'):
                    assert np.array_equal(data[k],original[sid][k])
                assert np.array_equal(data['old_recon'],original[sid]['recon'])
                assert np.array_equal(data['old_vae_scaled_mode'],original[sid]['initial_update_latent'])
                with np.load(root/'replay'/(sid+'_replay.npz'),allow_pickle=False) as paired:
                    assert np.array_equal(data['initial_update_latent'],paired['terminal_generation_latent'])
                    assert np.array_equal(data['terminal_generation_latent'],paired['terminal_generation_latent'])
                bypass_data[sid]=data
    for row in rows['replay']:
        sid=row['source']
        assert row['paired_old_pixels_exact'] and row['paired_old_png_bytes_exact'] and not any(row['safety_flags'])
        assert row['generation_steps']==50 and row['generation_guidance']==7.5
        assert row['old_image_sha256']==file_sha(base/'prepare'/(sid+'_original.png'))
        assert row['replay_image_sha256']==file_sha(root/'replay'/(sid+'_replay.png'))==row['old_image_sha256']
        with np.load(root/'replay'/row['arrays_file'],allow_pickle=False) as a:data={k:a[k].copy() for k in a.files}
        for k,v in data.items():assert array_binding(v)==row['array_bindings'][k]
        assert np.array_equal(data['old_rgb'],data['replay_rgb']) and np.array_equal(data['old_rgb'],original[sid]['input_rgb'])
        assert np.array_equal(data['old_vae_scaled_mode'],original[sid]['initial_update_latent'])
        expected=(torch.from_numpy(data['terminal_generation_latent'])/row['decoder_scaling_factor']).numpy()
        max_decoder=max(max_decoder,float(np.max(np.abs(expected.astype(float)-data['actual_decoder_input'].astype(float)))))
        assert np.allclose(expected,data['actual_decoder_input'],rtol=.0005,atol=.008)
        replay_data[sid]=data
    codec_summaries=[];bypass_summaries=[];distances=[]
    for label,a in [('original',original['c04']),('jpeg70_420',baseline),*jpeg_data.items()]:
        o=original['c04']
        summary={'source':'c04','variant':label,'native':int(a['A'].sum()),'oracle':int(a['D'].sum()),'E':int(a['E'].sum()),
            'E_intersect_D':int((a['E']&a['D']).sum()),'A_outside_E':int((a['A']&~a['E']).sum()),
            'rgb_code_rmse':rmse(a['input_rgb'],o['input_rgb']),'vae_input_rmse':rmse(a['vae_input_actual'],o['vae_input_actual']),
            'clip_preprocess_rmse':rmse(a['clip_input_float32'],o['clip_input_float32']),
            'vae_mode_rmse':rmse(a['vae_mode_actual'],o['vae_mode_actual']),
            'scaled_initial_rmse':rmse(a['initial_update_latent'],o['initial_update_latent']),
            'final_recon_rmse':rmse(a['recon'],o['recon']),
            'feature_cosine_original':float(np.clip(np.dot(a['feature'],o['feature'])/(np.linalg.norm(a['feature'])*np.linalg.norm(o['feature'])),-1.,1.)),
            'native_l2_quantiles':quantiles(a['native_l2']),'oracle_l2_quantiles':quantiles(a['oracle_l2'])}
        codec_summaries.append(summary)
        for typ in ('native','oracle'):
            for rank,d in enumerate(np.sort(a[typ+'_l2']),1):
                distances.append({'source':'c04','variant':label,'reference':typ,'rank':rank,'l2':float(d),'ecdf':rank/1024})
    for sid,a in bypass_data.items():
        o=original[sid];p=replay_data[sid]
        bypass_summaries.append({'source':sid,'native_before':int(o['A'].sum()),'native_bypass':int(a['A'].sum()),
            'oracle_before':int(o['D'].sum()),'oracle_bypass':int(a['D'].sum()),'E_fixed':int(o['E'].sum()),
            'E_intersect_D_bypass':int((a['E']&a['D']).sum()),'A_outside_E_bypass':int((a['A']&~a['E']).sum()),
            'initial_roundtrip_rmse':rmse(p['terminal_generation_latent'],p['old_vae_scaled_mode']),
            'recon_rmse_from_registered_before':rmse(o['recon'],o['registered_z']),
            'recon_rmse_from_registered_bypass':rmse(a['recon'],a['registered_z']),
            'recon_pair_rmse':rmse(a['recon'],o['recon']),
            'native_l2_quantiles_before':quantiles(o['native_l2']),'native_l2_quantiles_bypass':quantiles(a['native_l2']),
            'oracle_l2_quantiles_before':quantiles(o['oracle_l2']),'oracle_l2_quantiles_bypass':quantiles(a['oracle_l2'])})
    summary={'status':'passed','new_inversions':4,'replay_generations':2,'new_steps_audited':steps_audited,
        'new_model_download_bytes':0,'max_manual_l2_delta':max_l2,'max_step_cpu_replay_delta':max_step,
        'step_replay_tolerance':{'relative':.003,'absolute':.003},'max_scaled_mode_cpu_delta':max_scale,
        'max_decoder_input_cpu_delta':max_decoder,'cpu_torch':torch.__version__,
        'same_pixel_generation_replay_sources':['c04','c02'],'direct_scheduler_latent_capture':True,
        'codec':codec_summaries,'bypass':bypass_summaries,
        'scope':'one cal shoe codec sample; two original-image replay-paired oracle roundtrip controls; no test tuning, deployed repair or statistical security inference',
        'measurement':'all RMSE=float64 sqrt(mean squared coordinate difference); pixel code / normalized input / latent spaces distinct; each L2 is unnormalized norm of16 latent coordinates'}
    (root/'audit.json').write_bytes((json.dumps(summary,indent=2)+'\n').encode())
    with (root/'codec_distances.csv').open('w',newline='',encoding='utf8') as f:
        w=csv.DictWriter(f,fieldnames=list(distances[0]));w.writeheader();w.writerows(distances)
    for label,data in [('codec_summary',codec_summaries),('bypass_summary',bypass_summaries)]:
        flat=[{k:v for k,v in r.items() if not isinstance(v,dict)} for r in data]
        with (root/(label+'.csv')).open('w',newline='',encoding='utf8') as f:
            w=csv.DictWriter(f,fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)
    print(json.dumps({k:v for k,v in summary.items() if k not in ['codec','bypass']},indent=2))
    print(json.dumps(codec_summaries,indent=2));print(json.dumps(bypass_summaries,indent=2))

if __name__=='__main__':main()
