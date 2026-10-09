#!/usr/bin/env bash
set -u
cd /data0/liyanlei/watermark2_instance_authenticity
run_dir=runs/limited-v1/input_cast
if [ -e "$run_dir" ]; then echo 'Refuse overwrite'; exit 2; fi
mkdir -p "$run_dir"
timeout --signal=TERM 120s env CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=GPU-9644fb82-cb6f-7311-8017-eaee41409bb7 /data0/liyanlei/envs/stego_attack/bin/python scripts/replay_generation_input_cast.py --prepare-run runs/calibration-v1/prepare --csi-code source-csi --output "$run_dir" > "$run_dir/execution.log" 2>&1
run_status=$?
printf '{"exit_code":%s}\n' "$run_status" > "$run_dir/exit_status.json"
cat "$run_dir/execution.log"
exit "$run_status"
