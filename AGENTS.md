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
