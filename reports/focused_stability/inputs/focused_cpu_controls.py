"""Frozen two-source CPU binding/criterion controls and reference/recon cross-swaps."""
import argparse,ast,io,json
from pathlib import Path
import sys,time
import numpy as np
from PIL import Image
from runtime_provenance import file_sha,array_binding

def manual_patches(a):
    return a[0].reshape(4,32,2,32,2).transpose(1,3,0,2,4).reshape(1024,16)

def main():
    ap=argparse.ArgumentParser()
    for f in ('config','run','csi-code','csi-inventory','output'):ap.add_argument('--'+f,required=True)
    args=ap.parse_args();cfg=json.loads(Path(args.config).read_text());base=Path(args.run);out=Path(args.output)
    assert not out.exists();out.mkdir(parents=True)
    metrics=json.loads((base/'audit.json').read_text())['metrics']['source_profiles']['calibration']
    candidates=[sid for sid,p in metrics.items() if sid!=cfg['unstable_source'] and p['minimum']>=10]
    chosen=sorted(candidates,key=lambda sid:(-metrics[sid]['minimum'],sid))[0];assert chosen==cfg['stable_source']=='c02'
    inv=json.loads(Path(args.csi_inventory).read_text());assert inv['commit']=='8723e362835a6a61efd11b61f677b3321face3fa'
    for f in inv['files']:assert file_sha(Path(args.csi_code)/f['path'])==f['sha256']
    backend=Path(args.csi_code)/'csi/backends/sd.py';tree=ast.parse(backend.read_text(encoding='utf8'))
    klass=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='StableDiffusionBackend')
    invert=next(n for n in klass.body if isinstance(n,ast.FunctionDef) and n.name=='invert')
    assignment=next(n for n in invert.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='guidance' for t in n.targets))
    after=invert.body[invert.body.index(assignment)+1:]
    assert not any(isinstance(n,ast.Name) and n.id=='guidance' for stmt in after for n in ast.walk(stmt))
    unet_calls=[n for n in ast.walk(invert) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='unet']
    assert len(unet_calls)==1
    prompt_calls=[n for n in ast.walk(invert) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='_text_embedding']
    assert len(prompt_calls)==1 and isinstance(prompt_calls[0].args[0],ast.Constant) and prompt_calls[0].args[0].value==''
    sys.path.insert(0,args.csi_code)
    from csi.schemes.seal import SealCore
    from csi.types import Key
    core=SealCore(k=1024,b=7,t_patch=2.0);key=Key(seed=42)
    checks={}
    zero=np.zeros((1,4,64,64))
    assert np.array_equal(core.patch_l2(zero,zero),np.zeros(1024));checks['identical_latents_all_1024_match']=True
    for offset,expected in [(0.49,1024),(0.5,1024),(0.50000001,0)]:
        dist=core.patch_l2(zero,zero+offset);assert int((dist<=2.).sum())==expected
        assert np.allclose(dist,4*offset,rtol=0,atol=1e-12)
    checks['inclusive_threshold_boundary_2_and_above']=True
    one=zero.copy();one[0,0,0,0]=3
    l2=core.patch_l2(one,zero);assert l2[0]==3 and int((l2<=2).sum())==1023
    checks['single_pixel_maps_to_first_patch']=True
    sentinel=np.arange(16384).reshape(1,4,64,64).astype(float)
    for n,ys,xs in core._patch_slices():assert np.array_equal(manual_patches(sentinel)[n],sentinel[:,:,ys,xs].ravel())
    checks['NCHW_manual_patch_axis_mapping']=True
    source_files={};rows=[];arrays={};calrows=json.loads((base/'calibration/scores.json').read_text())
    rt=json.loads((base/'calibration/runtime.json').read_text())
    for sid in (cfg['unstable_source'],chosen):
        arrfile=base/'calibration'/(sid+'_arrays.npz')
        assert file_sha(arrfile)==rt['file_hashes'][arrfile.name]
        a=np.load(arrfile,allow_pickle=False);registered=a['registered_z'];draft=a['draft_feature']
        assert registered.shape==(1,4,64,64) and draft.shape==(512,)
        assert np.array_equal(core.noise_from_embedding(draft,key),registered)
        dids=core.bucket_ids(draft,key);arrays[sid+'_draft_bucket_ids']=dids
        source_files[str(arrfile.relative_to(base))]=file_sha(arrfile)
        for v in cfg['variants_cpu']:
            imagefile=base/'prepare'/(sid+'_'+v+'.png')
            r=next(r for r in calrows if r['source']==sid and r['variant']==v)
            image=Image.open(imagefile).convert('RGB');pixels=np.array(image)
            assert image.size==(512,512) and pixels.shape==(512,512,3) and pixels.dtype==np.uint8
            assert file_sha(imagefile)==r['input_image_sha256'] and array_binding(pixels)==r['decoded_rgb']
            assert np.array_equal(np.array(image.resize((512,512))),pixels)
            for k in ('feature','reference','recon','l2'):assert array_binding(a[v+'_'+k])==r['stage_bindings'][k]
            assert np.array_equal(core.noise_from_embedding(a[v+'_feature'],key),a[v+'_reference'])
            assert abs(np.linalg.norm(a[v+'_feature'])-1)<1e-6
            assert a[v+'_recon'].shape==(1,4,64,64)
            assert np.all(np.isfinite(a[v+'_recon']))
            x=(pixels.astype(np.float32)/255.).transpose(2,0,1)[None]*2.-1.
            assert x.shape==(1,3,512,512) and x.min()>=-1 and x.max()<=1
            source_files[str(imagefile.relative_to(base))]=file_sha(imagefile)
            arrays[sid+'_'+v+'_vae_input_normalized_cpu']=x
        original=Image.open(base/'prepare'/(sid+'_original.png')).convert('RGB')
        buf=io.BytesIO();original.save(buf,format='PNG',compress_level=9)
        lossless=Image.open(io.BytesIO(buf.getvalue())).convert('RGB')
        assert np.array_equal(np.array(lossless),np.array(original))
        (out/(sid+'_lossless_pixel_identity.png')).write_bytes(buf.getvalue())
        checks[sid+'_pixel_identical_lossless_roundtrip']=True
        arrays[sid+'_registered_z']=registered
        for rv in cfg['variants_cpu']:
            recon=a[rv+'_recon'];oracle_l2=core.patch_l2(recon,registered);D=oracle_l2<=2.
            for sv in cfg['variants_cpu']:
                reference=a[sv+'_reference'];qids=core.bucket_ids(a[sv+'_feature'],key);E=qids==dids
                native_l2=core.patch_l2(recon,reference);A=native_l2<=2.
                assert np.array_equal(A[E],D[E])
                manual=np.linalg.norm(manual_patches(recon)-manual_patches(reference),axis=1)
                assert np.max(np.abs(manual-native_l2))<=1e-12
                name=sid+'_'+rv+'_recon_'+sv+'_semantic'
                arrays.update({name+'_E':E,name+'_D':D,name+'_A':A,name+'_l2':native_l2,name+'_oracle_l2':oracle_l2,name+'_query_bucket_ids':qids})
                rows.append({'source':sid,'recon_input':rv,'semantic_input':sv,
                    'E':int(E.sum()),'D':int(D.sum()),'E_intersect_D':int((E&D).sum()),
                    'A':int(A.sum()),'A_outside_E':int((A&~E).sum()),
                    'fallback10_accepted':int(A.sum())>=10,
                    'native_l2_binding':array_binding(native_l2),'oracle_l2_binding':array_binding(oracle_l2)})
    np.savez_compressed(out/'cross_swap_arrays.npz',**arrays)
    write={'config':cfg,'config_sha256':file_sha(args.config),'script_sha256':file_sha(__file__),
        'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'selection_minima':{sid:p['minimum'] for sid,p in metrics.items()},
        'selected_control':chosen,'input_hashes':source_files,'backend_sha256':file_sha(backend),
        'effective_inversion':{'condition':'empty prompt','unet_calls_per_step':1,'guidance_assignment_unused':True}}
    (out/'frozen.json').write_text(json.dumps(write,indent=2)+'\n',encoding='utf8')
    result={'status':'passed','controls':checks,'source_binding_controls':True,'shape_scaling_controls':True,
        'rows':rows,'gpu_inversions_triggered':False,'scope':'cal-only stored-array engineering control; no independent semantic encoder validation or test tuning'}
    (out/'cpu_results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
