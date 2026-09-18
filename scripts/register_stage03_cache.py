"""Verify known cached SD1.5 snapshot against published mirror file identities."""
import os
os.environ['CUDA_VISIBLE_DEVICES']=''
import hashlib, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from stage02.core import dump,sha256
cache=Path('/data0/liyanlei/huggingface/hub/models--runwayml--stable-diffusion-v1-5/snapshots/451f4fe16113bff5a5d2269ed5ad43b0592e9a14')
meta=json.loads((ROOT/'artifacts/stage03_sd15_source.json').read_text());table={f['rfilename']:f for f in meta['siblings']}
files=['model_index.json','scheduler/scheduler_config.json','feature_extractor/preprocessor_config.json']
for comp in ['unet','vae','text_encoder','safety_checker']:
    files += [comp+'/config.json',comp+('/diffusion_pytorch_model.safetensors' if comp in ['unet','vae'] else '/model.safetensors')]
for f in ['merges.txt','vocab.json','special_tokens_map.json','tokenizer_config.json']:files.append('tokenizer/'+f)
records=[]
for f in files:
    path=cache/f;actual=sha256(path);source=table[f];expected=source.get('lfs',{}).get('sha256')
    if path.stat().st_size!=source['size'] or (expected and actual!=expected):raise ValueError('Cached file differs from pinned public snapshot: '+f)
    if not expected and source.get('blobId'):
        blob=hashlib.sha1(b'blob '+str(path.stat().st_size).encode()+b'\0'+path.read_bytes()).hexdigest()
        if blob!=source['blobId']:raise ValueError('Cached config Git blob mismatch: '+f)
    records.append(dict(rfilename=f,path=str(path),size=path.stat().st_size,sha256=actual,published_lfs_sha256=expected))
    print('verified',f,flush=True)
out=ROOT/'outputs/stage03';archive=out/'asset_selection';archive.mkdir(exist_ok=True)
# There must be no generated pixels when resolving this engineering-only model selection.
if (out/'generation_records').exists() and list((out/'generation_records').glob('*.json')):raise RuntimeError('Generation already started; cannot replace model selection')
lock=out/'protocol_lock.json'
if lock.exists():
    prior=json.loads(lock.read_text())
    if prior['config']['generator']['pipeline']=='StableDiffusionXLPipeline':lock.rename(archive/'sdxl_protocol_lock.json')
dump(out/'generator_files.json',dict(model_id=meta['id'],revision=meta['sha'],status='complete',local_path=str(cache),selected_bytes=sum(f['size'] for f in records),files=records,
     source='Published SD1.5 community mirror at fixed revision; cached LFS files verified against API SHA256, not claimed as Runway attestation',new_download_bytes=0))
dump(archive/'selection.json',dict(selected=meta['id'],revision=meta['sha'],reason='SDXL official HTTPS unavailable directly on server; local resumed UNet transfer about 70 KB/s (~2 GB remaining). Complete SD1.5 cache matches pinned public mirror LFS identities.',generated_before_selection=0,parameters='1024x1024,30 steps,CFG5 retained',limitation='SD1.5 fine-tuned at 512x512; 1024 output may have repeated or malformed content; inspect fixed grids without sample filtering'))
