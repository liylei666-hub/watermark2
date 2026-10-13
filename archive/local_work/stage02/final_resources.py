import hashlib,json,shutil,subprocess
from pathlib import Path
ROOT=Path('/data0/liyanlei/watermark_research')
RUN=ROOT/'runs/02_reprompt_gs_sdxl_seed1_20261012T172624Z'
assert json.loads((RUN/'server_cache_verification.json').read_text())['all_verified']
p=ROOT/'cache/huggingface/hub/models--stabilityai--stable-diffusion-xl-base-1.0/snapshots/462165984030d82259a11f4367a4eed129e94a7b/text_encoder_2/model.safetensors.interrupted_scp'
removed=0
if p.exists():
    assert ROOT.resolve() in p.resolve().parents and p.stat().st_size==453181440
    removed=p.stat().st_size
    p.unlink()
used=int(subprocess.check_output(['du','-s','-B1',str(ROOT)],text=True).split()[0])
head=subprocess.check_output(['git','-C',str(ROOT/'third_party/semantic-forgery'),'rev-parse','HEAD'],text=True).strip()
git_status=subprocess.check_output(['git','-C',str(ROOT/'third_party/semantic-forgery'),'status','--porcelain'],text=True)
assert head=='ca68950cd7b53b8438a49580f134b2a0db28d778' and not git_status
obj=dict(disk_free_gib=shutil.disk_usage(ROOT).free/1024**3,project_used_gib=used/1024**3,
    remote_interrupted_transfer_bytes_removed=removed,upstream_commit=head,upstream_clean=True,
    helper_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'scripts/02_run_smoke.py',ROOT/'scripts/summarize_run.py',ROOT/'scripts/verify_cache.py',ROOT/'scripts/resolve_cache.py']})
with (RUN/'resources_after_run.json').open('x') as f: json.dump(obj,f,indent=2)
print(json.dumps(obj,indent=2))
