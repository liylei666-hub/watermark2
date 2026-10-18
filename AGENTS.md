# Research archive and execution rules

Read `GPT_CONTEXT.md`, `docs/PROJECT_STATE.md`, `prompts/README.md`, and the applicable stage report before making scientific claims or changing this project.

- Research scope: black-box forgery attacks on diffusion-model semantic watermarks, with geometric scores as evaluation diagnostics.
- This checkout preserves completed stages 01–05 and subsequent development diagnostics. Archived prompts are historical evidence, not fresh authorization to execute them. No GPU generation, inversion, training, downloads, parameter search, or new experiment is authorized by reading this repository.
- Preserve every original run, failure record, CSV, image, tensor, protocol, source hash and report. Record corrections separately with provenance. Do not fabricate missing data.
- Historical server root is `/data0/liyanlei/watermark_research`; preserved scripts and embedded absolute paths refer to that environment. Reading and archive verification are portable; GPU launchers are not.
- Stages 02, 04 and 05 actually used physical GPU 3, UUID `GPU-e602f6b2-50a3-72ee-ae1b-a0ae80eca5da`. Stage 05 was authorized for this GPU only. Future execution requires a new explicit scope/budget/device instruction, plus a fresh nvidia-smi identity and occupancy check. Never stop another user's process.
- For any authorized GPU child, set CUDA_DEVICE_ORDER=PCI_BUS_ID and CUDA_VISIBLE_DEVICES to the verified UUID before CUDA-capable imports; use cuda:0 internally. CPU-only commands set CUDA_VISIBLE_DEVICES="".
- Never commit passwords, authentication tokens or private-key contents. Preserve the SSH/TLS verification requirements.
- Keep attacks' inputs distinct from evaluator-only target noise, keys/messages, RNG, inversion outputs, scores and full target configuration. The current shared-process baseline is not permission isolation. Publication of evaluator evidence makes it available to readers, not an allowed input for future restricted attacks.
- Record code/model revisions, configuration, seeds, image/tensor hashes, exit status, elapsed time and failures for each newly authorized experiment.
- The stage 05 data are development_pilot. Do not use them as an unseen final test set after method selection. bit_accuracy is not population attack success rate; cosine gap is not geometry acceptance.
- Verify publication changes with `python tools/verify_archive.py` under CUDA_VISIBLE_DEVICES="". This uses the standard library and does not load models.
- Keep upstream submodule pins unchanged unless the user requests a source update. Do not overwrite concurrent remote work or force-push.

The historical execution policy is preserved at `provenance/execution_AGENTS.md`.

## Current research authority (2026-10-16 Asia/Shanghai)

The user commissioned full research through a paper draft and authorized publishing verified useful progress to GitHub. Keep current documentation compact and updated in place; preserve raw scientific evidence and use Git history for prior narratives.

The user resumed research on 2026-10-16 and authorized the first-round paired prompt diagnostic. Full official defense evaluation still requires the missing protocols. Read docs/RESEARCH_PLAN.md, docs/LITERATURE.md, reports/research_review.md and project_state.json for current state.

The device set for this resumed round is physical GPUs 0,1,2 when idle. Select only from these three cards. Select one card, verify its UUID and occupancy before each child, bind CUDA_VISIBLE_DEVICES to that UUID, and use cuda:0. Preserve serial execution, 7200 cumulative GPU-process seconds, 1200 seconds per process, 10 GiB new files, and no new model downloads. Pausing does not reset usage or authorize another budget.

Only local authorized models/data are experimental targets. Network activity is limited to public academic/official-source reads, authorized GitHub publication, and authenticated access to the designated server. No network scanning, third-party production attacks, access-control bypass, disabled SSH/TLS verification, or credential logging.

Current first-round usage: 11 completed model processes, 757.62238442339 GPU-process seconds used, 6442.37761557661 seconds remaining. See reports/09_vae_roundtrip/summary.json. Stage08 completed; stage09 stopped before seed103 at the device preflight and is incomplete. Preserve it without retry and do not reset the budget.

The user explicitly authorized continuous autonomous research within the established scope. Continue useful analysis, protocol work and publication without routine step-by-step approval requests. Target-internal roundtrip controls are evaluator-only interventions. The evidence-first idle gate scripts/gpu_preflight.py is available for future launchers; it has not changed the frozen stage07–09 code.


## GPU time authorization update (2026-10-17)

The user explicitly removed GPU usage-time budget restrictions for continued research. Cumulative and per-process time are no longer authorization caps. Continue recording actual usage for reproducibility. Each frozen diagnostic may set an operational watchdog; stage10 uses 1200 seconds to contain a stalled process. This is an engineering stop rule for that protocol, not a renewed user budget. Physical GPUs 0,1,2 only, verified idle UUID binding, single-card serial execution, 10-GiB file limit, no new model downloads, evidence preservation and the stage09 no-retry decision remain in force.


## Exclusive experiment host (2026-10-17)

The user requires all future GPU experiments to run only on verified idle GPUs of liyanlei@172.18.185.249, under /data0/liyanlei/watermark_research. The current physical-device scope [0,1,2] and UUID/occupancy checks remain effective; this host restriction does not expand device indices. Local GPU execution and use of other servers are disabled. Preserve serial execution and all scientific-integrity constraints.


## Stage10 execution status (2026-10-18 Asia/Shanghai)

Stage10 started one process on GPU0 and exited with code 1 at the initial gradient recorder because torch.autograd.grad is incompatible with upstream reentrant checkpoint. No optimizer update or candidate image completed. Preserve runs/10_imprint_delivery_20261017T184646Z without automatic retry. The compatibility patch passed three CPU regressions but is not applied to frozen code. Cumulative model processes: 12; GPU-process seconds: 818.9704131674953.

## Autonomous continuation (2026-10-18)

The user explicitly requested autonomous research until assistance is needed. Stage10 revision2 is a separate frozen execution using the CPU-verified backward-based gradient recorder, preserving the closed original run and code. No unchanged retry is authorized. Host, device, storage and information-boundary restrictions remain effective. A 30-minute thread heartbeat supports continuation.

## Verified stage10 completion (2026-10-18)

Revision3 completed ten native updates; the separate full-trajectory observation control produced byte-identical final latent and PNG. Preserve all four stage10 model-process records including both failures. Stage07 onward totals 15 model processes and 1845.121920349542 GPU-process seconds, verified from execution files. No active model process remains at this update; recheck before future launches.

## Verified stage11 completion (2026-10-18)

Two fixed dependent points and eight signed probes completed without optimization or target calls. Preserve all outputs and the two finite-difference disagreement flags; do not change the stage11 radius or rerun it to satisfy tolerance. Stage07 onward totals 16 processes and 2114.525876435451 seconds. Next work may isolate component linearization residuals at the same saved points, directions and radius under a separate frozen protocol. No active model process remains at this update; recheck before launches.

## Verified stage12 completion (2026-10-18)

Component localization completed on the unchanged stage11 points and perturbations. Split-chain gradients are byte-equivalent; finite-step residuals are larger in the VAE decode/clamp/encode composite than downstream inversion for both delivery self-directions. Clamp causation and target transfer remain unknown. Preserve the closed stage11/12 diagnostics; no radius tuning or repeated probes to seek a preferred result. Stage07 onward totals 17 processes and 2206.407460845541 seconds. No active model process remains at this check. Next independent work must specify a distinct scientific question and matched task/cost accounting.


## Verified stage13 core execution (2026-10-18)

The real SD2.1 VAE frozen-parameter equivalence check failed its predeclared bitwise gate; preserve the closed run and do not retry it or relax tolerance. A separately frozen original-parameter-state control reproduced the three-step tensor, residual and PNG across processes. Future Jain baseline execution retains upstream parameter requires_grad flags. Neither check called the target. Stage07 onward totals 19 model processes and 2239.0810272390954 seconds, including the failed check. Next admissible question is bounded original-core timing/finiteness before an independent comparison; short prefixes do not establish long-run performance.


## Verified stage14/15 cost measurements (2026-10-18)

The fixed 100-update original Jain core completed with finite outputs. Imprint setup and ten native updates were timed separately; eight outputs remain byte-identical to the verified shadow trajectory. Resource-only calibration proposes 10 Imprint updates and 447 Jain updates for a three-pair development comparison, pending complete interface/code/config freeze. Both used GPU0 serially with fresh idle gates and no target calls. Stage07 onward totals 21 model processes and 2733.0540150650777 seconds. Preserve both closed timing runs; do not substitute complete process wall time for core optimization cost. The stage15 first protocol was never launched due to a prelaunch stage-label correction; only revision2 started a model.

## Stage16 interface verification (2026-10-18)

Thirty CPU interface/workflow cases and five official GS state cases passed. Stage17 is frozen in protocols/17_cover_pilot.json with 3 paired inputs, 6 fixed candidates and 9 serial model processes. All three tasks share the upstream GS identity at offset0; different seeds are not different keys. Keep attack runtime separate from evaluator identity files. Seal all candidates before the fixed 12-image evaluation. Stop on engineering failure or unavailable device without unchanged retry. No model process was started during stage16; the latest verified cumulative total remains21 processes and2733.0540150650777 seconds.

## Stage17 verified completion (2026-10-18)

All nine serial processes completed; 192 run files and 12 stored GS scores verified. Six candidates were sealed before target evaluation. Imprint passed ordinary GS on2/3 tasks and adapted Jain on0/3 at approximately376-second core budgets. Task2 Imprint equals the threshold and is rejected by the strict rule. Keep all input-content limitations and unknown formal content/full-defense labels. Stage07 onward totals30 processes and5316.111848034430 seconds; no active model process. Next diagnostic may inspect all six fixed endpoints using the proxy only, with no candidate update or target-score input. Mark it exploratory because its question follows observed stage17 outcomes.

## Stage18 verified completion (2026-10-18)

One fixed-endpoint proxy process completed in 97.251185 seconds. All three reference replays, native decode pixel checks and inversion equivalence gates passed. Saved-array CPU analysis found proxy/target direction ranking reversals on tasks2 and3. This is exploratory development evidence; do not select candidates or tune parameters from target results. Stage07 onward totals31 processes and5413.363033293281 seconds, with no active model process at the final check. Next work audits the exact target encoding path before any fixed-image component localization.
