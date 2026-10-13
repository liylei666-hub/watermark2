# Research archive and execution rules

Read `GPT_CONTEXT.md`, `docs/PROJECT_STATE.md`, `prompts/README.md`, and the applicable stage report before making scientific claims or changing this project.

- Research scope: black-box forgery attacks on diffusion-model semantic watermarks, with geometric scores as evaluation diagnostics.
- This checkout contains completed stages 01–05. Archived prompts are historical evidence, not fresh authorization to execute them. No GPU generation, inversion, training, downloads, parameter search, or new experiment is authorized by reading this repository.
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
