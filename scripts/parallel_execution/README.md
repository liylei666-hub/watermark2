# Future-run parallel scheduling kernel

This component prepares independent future experiments for the user's authorization of at most four GPUs on server 249, excluding physical GPU6. It is an offline-tested scheduling library. It has no model-launching CLI and has not been deployed to the active stage27 run.

`Scheduler` takes explicit frozen job hashes, task groups, GPU index/UUID/model records, a verified idle-gate callback, and a project-specific runner callback. A task group contains all compared methods for one input task. Groups may run concurrently; methods in a group run serially on the same physical GPU, preserving paired device affinity. The kernel requires one GPU model across the selected cards. Same-model hardware and device affinity do not prove equal computation: core time, load, clocks and thermal state still need recording.

The kernel shares `runs/.imprint_delivery.lock` with the existing project controller. It fails before creating a new run if that lock is occupied. It never terminates the owner or modifies another run. A new run directory and each task directory are exclusively created. Existing, failed and ambiguous directories are refused rather than automatically resumed.

Successful attack callbacks must produce `candidate.png` and its matching SHA-256. All candidates must complete before a single seal is written. Candidate hashes are checked before each evaluation launch and again after the evaluation phase. Any failed attack blocks evaluation. Jobs already in flight finish after a peer fails; new claims stop. An output directory lacking its execution record is classified as `ambiguous_claimed`, not unstarted. It cannot silently be relaunched.

The idle gate requires three consecutive samples with the expected physical index, UUID and model, memory use at most 50 MiB, zero utilization, and no compute process. A busy card cannot reserve a task. Identity mismatch is an error, not a reason to try an unverified identity. GPU6, repeated identities, and selections exceeding four cards are rejected before any runner invocation.

## Project adapter still required before model execution

The caller must provide a frozen, reviewed adapter that verifies actual job/config/source hashes, designated host and root, available storage under the retained 10-GiB cap, and local model revisions. The adapter must start one subprocess per method with UUID binding before CUDA-capable imports, repeat the idle gate inside the child, prohibit model downloads, enforce the declared watchdog, wait for the child to exit, and persist the exact command, process identity, exit code, logs, timings and artifacts. It must preserve the task's existing numerical settings. The kernel does not manufacture those domain-specific guarantees from a returned success flag.

Private evaluator material must remain outside attacker jobs. The candidate barrier is an orchestration boundary, not operating-system permission isolation. Evaluation groups receive their private inputs only through the project adapter after sealing. The next experiment must freeze its own scientific design and adapter; this library does not authorize a new scientific protocol.

Stage27 remains owned by its original serial controller. It cannot be accelerated by simply supplying this library with the same pending job list. A future handover would need a separately recorded task-boundary transfer and validated inheritance of completed, failed and active work. This version intentionally has no automatic live takeover or crash-resume feature.

## CPU validation

Run `python scripts/parallel_execution/test_scheduler.py -v` with `CUDA_VISIBLE_DEVICES` empty. The tests use synthetic bytes and injected runners; no model or GPU is loaded. Tests exercise four real concurrent CPU worker threads, task affinity, unique claims, the global evaluation barrier, busy-device refusal, GPU6 and oversubscription rejection, frozen-list isolation, integrity failures, retained missing outcomes, held project locks, and completion of in-flight jobs after a peer failure. GPU throughput and model numerical equivalence remain unmeasured.
