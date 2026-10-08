#!/usr/bin/env bash
set -u
cd /data0/liyanlei/watermark2_instance_authenticity
phase=${1:?prepare or score}
case "$phase" in prepare|score) ;; *) exit 2;; esac
run_dir="runs/mechanical-v1/phase-$phase"
if [ -e "$run_dir" ]; then echo 'Refuse overwrite'; exit 2; fi
mkdir -p "$run_dir"
printf '%s\n' "$$" > "$run_dir/runner.pid"
timeout --signal=TERM 900s env CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=GPU-9644fb82-cb6f-7311-8017-eaee41409bb7 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 DIFFUSERS_OFFLINE=1 /data0/liyanlei/envs/stego_attack/bin/python scripts/sd15_clip_mechanical.py "$phase" --config configs/sd15_clip_mechanical.json --base-run runs/smoke-v1/attempt1 --sd-cache /data0/liyanlei/huggingface/hub/models--runwayml--stable-diffusion-v1-5/snapshots/451f4fe16113bff5a5d2269ed5ad43b0592e9a14 --clip-code /data0/liyanlei/instance_authentication_research/third_party/clip --clip-weight /data0/liyanlei/instance_authentication_research/weights/ViT-B-32.pt --csi-code source-csi --source-run runs/mechanical-v1/phase-prepare --variants runs/mechanical-v1/variants --output "$run_dir" > "$run_dir/execution.log" 2>&1
run_status=$?
printf '{"exit_code":%s}\n' "$run_status" > "$run_dir/exit_status.json"
tail -12 "$run_dir/execution.log"
exit "$run_status"
