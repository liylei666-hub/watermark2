"""Evaluator-only target self-roundtrip. No imports of CUDA libraries at module load."""
import hashlib, json, os, sys
from pathlib import Path

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path, data):
    with Path(path).open('x', encoding='utf-8') as f: json.dump(data, f, indent=2, ensure_ascii=False)

def generate_and_measure(provider, recovered, prompts, freeze, measure):
    """The same recovered input supplies both fixed arms; freeze precedes evaluation."""
    results={}
    for arm,prompt in prompts.items():
        generated=provider.generate(prompts=prompt,num_inference_steps=50,guidance_scale=7.5,
                                    latents=recovered.clone())
        image=generated['images_PIL'][0]
        freeze(arm,image)
        inverted=provider.invert_images(image,num_inference_steps=50)['zT_torch']
        results[arm]=measure(arm,image,inverted)
    return results

def main(case):
    cfg=json.loads((case/'config.json').read_text())
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==cfg['gpu_uuid']
    assert os.environ.get('CUDA_DEVICE_ORDER')=='PCI_BUS_ID'
    assert os.environ.get('HF_HUB_OFFLINE')=='1'
    for p,h in cfg['input_hashes'].items(): assert sha(p)==h
    sys.path.insert(0,cfg['upstream_path'])
    # Device binding is checked before CUDA-capable imports.
    import numpy as np
    import torch
    from PIL import Image
    from diffusers import DiffusionPipeline
    from utils.pipe import pipe_utils
    from utils.wm.gs_provider import GsProvider
    from utils.utils import set_random_seed,check_if_detection_successful
    assert torch.cuda.device_count()==1
    torch.cuda.set_device(0)
    write(case/'device.json',dict(uuid=cfg['gpu_uuid'],visible_count=1,logical_device='cuda:0',name=torch.cuda.get_device_name(0)))
    loads=[]; original_download=DiffusionPipeline.download.__func__
    def checked_download(cls,model_id,*args,**kwargs):
        assert model_id==cfg['model_id']
        result=original_download(cls,model_id,*args,**kwargs)
        assert str(Path(result).resolve())==cfg['model_snapshot']
        loads.append(dict(model_id=model_id,snapshot=str(Path(result).resolve())))
        return result
    DiffusionPipeline.download=classmethod(checked_download)
    set_random_seed(cfg['seed'])
    provider=pipe_utils.get_pipe_provider(pretrained_model_name_or_path=cfg['model_id'],resolution=512,
                device='cuda:0',eager_loading=False,schedulers_name='DDIM',disable_tqdm=True)
    wm=GsProvider(latent_shape=(1,4,64,64),device='cuda:0',**cfg['gs_parameters'])
    reference=Image.open(cfg['reference_png']).convert('RGB')
    original=np.load(cfg['original_latent'],allow_pickle=False)
    saved_reference=np.load(cfg['reference_inversion'],allow_pickle=False)
    assert original.shape==saved_reference.shape==(1,4,64,64)
    arrays={};image_records={}
    def capture(name,tensor):
        arr=tensor.detach().to(device='cpu',copy=True).contiguous().numpy()
        assert arr.shape==(1,4,64,64) and arr.dtype==np.float32 and np.isfinite(arr).all()
        path=case/(name+'.npy')
        with path.open('xb') as f: np.save(f,arr,allow_pickle=False)
        assert np.array_equal(np.load(path,allow_pickle=False),arr)
        arrays[name]=dict(path=str(path),sha256=sha(path),shape=list(arr.shape),dtype=str(arr.dtype))
        return arr
    def cosine(a,b):
        a=a.astype(np.float64).ravel(); b=b.astype(np.float64).ravel()
        return float(np.dot(a,b)/(np.linalg.norm(a)*np.linalg.norm(b)))
    def freeze(arm,image):
        path=case/(arm+'.png')
        with path.open('xb') as f:image.save(f,format='PNG')
        assert np.array_equal(np.asarray(Image.open(path)),np.asarray(image))
        image_records[arm]=dict(path=str(path),sha256=sha(path),size=list(image.size),event='before_target_inversion')
        write(case/(arm+'_frozen.json'),image_records[arm])
    def measure(arm,image,tensor):
        assert sha(image_records[arm]['path'])==image_records[arm]['sha256']
        array=capture(arm+'_inverted_zT',tensor)
        accuracy=float(wm.get_accuracies(tensor)['bit_accuracies'][0])
        return dict(bit_accuracy=accuracy,gs_detected=check_if_detection_successful('GS',.70703125,accuracy),
                    cosine_to_original=cosine(original,array),cosine_to_reference_inverse=cosine(saved_reference,array))
    with torch.no_grad():
        print('REINVERT_REFERENCE',flush=True)
        recovered=provider.invert_images(reference,num_inference_steps=50)['zT_torch']
        actual=capture('recomputed_reference_zT',recovered)
        match=np.array_equal(actual,saved_reference)
        write(case/'reference_replay.json',dict(bitwise_equal=bool(match),
            max_abs_error=float(np.max(np.abs(actual-saved_reference))),
            archived_sha256=sha(cfg['reference_inversion']),recomputed_sha256=sha(case/'recomputed_reference_zT.npy')))
        assert match, 'Archived reference inversion did not reproduce exactly; stop before generation'
        ref_accuracy=float(wm.get_accuracies(recovered)['bit_accuracies'][0])
        assert ref_accuracy==cfg['reference_bit_accuracy']
        print('REFERENCE_INVERSION_MATCHED',flush=True)
        results=generate_and_measure(provider,recovered,cfg['prompts'],freeze,measure)
    assert len(loads)==1
    write(case/'actual_model_loads.json',loads)
    write(case/'tensor_manifest.json',dict(arrays=arrays,images=image_records,config_sha256=sha(case/'config.json')))
    write(case/'metrics.json',dict(seed=cfg['seed'],results=results,reference_bit_accuracy=ref_accuracy,
          evaluation_only=True,geometry_threshold=None,geometry_accepted=None))
    print('COMPLETED_TARGET_ROUNDTRIP',flush=True)

if __name__=='__main__':main(Path(sys.argv[1]))
