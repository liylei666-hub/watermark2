# Stage 27 recovery checkpoint

Snapshot: 2026-10-19 17:39:06 UTC. The continuation is active; this report does not contain final method results.

The running experiment is `runs/27_method_resume_20261019T173017Z`, controlled by PID 21884 and accompanied by CPU postprocessor PID 23796. At the snapshot there were four completed attack tasks, one running task (`2/imprint`, PID 25550), thirty unstarted tasks, and one retained failure (`2/jain`). The latest completed continuation task, `2/delivery`, finished in 412.756438 seconds. At this rate the remaining serial attack work is approximately 3–4 hours, followed by three target-evaluation batches; resource waiting and runtime variation can extend that estimate.

The original run stopped after ten launched worker processes: nine successful processes (six preparation batches and task 1's three attacks) and one preimport idle-gate failure. The failed task produced no candidate. Its recorded 0.498398-second process duration is not evidence of model inference or optimization. The continuation preserves that failure and reuses the successful outputs.

## Checks that affect interpretation

The read-only standard-library audit verified 373/373 original source files, 301/301 inherited copies, 70/70 historical execution records, and 67/67 runtime-pinned code files against their frozen hashes. The original and continuation scientific designs compare equal, including the strict GS threshold and all four go/no-go criteria. The runtime's SHA-256 sidecar, launch binding, device list, storage cap, and inheritance records match. All original process outcomes are accounted for, and the failed task has not been relaunched. See [machine-readable audit](remote_provenance.json) and [auditor](../../tools/audit_stage27_recovery.py).

This is a provenance check plus a non-atomic snapshot of active-run files. It does not establish live-process ownership, model correctness, independent confirmation, or scientific efficacy. Separate SSH process inspection confirmed the named controller, current worker, and postprocessor at the checkpoint. Codex thread inventory and cross-thread messaging returned internal tool errors, so the originating agent could not be identified. No running controller, worker, frozen source, or experiment output was modified by this audit.

## Expected final analysis

The original scientific design has 12 tasks per method and 36 candidate slots. Retaining task 2/Jain as missing leaves at most 35 delivered candidates and 59 target inversions (12 references, 12 covers, 35 candidates). Delivery versus native Imprint still has 12 planned pairs. Report Jain's pass count over all 12 attempts and label numeric summaries conditioned on the 11 delivered images. Do not substitute a replacement task or report a 36/36 completion claim.

Apply the original criteria after all deliverable candidates have been sealed and target scores verified: all twelve reference images valid; at least three additional GS passes; median paired pixel-MSE ratio at most 1.05; median paired core-time ratio at most 1.15. Missing required evidence is inconclusive. Complete evidence that fails the criteria closes the candidate. The screen makes no statistical-significance claim.

## Completed paper work

[Methods and results draft](../../docs/METHOD_COMPARISON_DRAFT.md) defines all three objectives, separates continuous optimization from PNG evaluation, explains the comparator budget and missing-task denominator, and reports the closed eight-pair delivery diagnostic. Its summary was recalculated from saved per-pair rows: baseline message accuracy 0.93701171875, corrected 0.8828125, paired change -0.05419921875; seven pairs worsened and one tied. Ordinary GS passes were 8/8 in both conditions. Stage 27 target endpoints remain pending.

## Resource amendment and coordination

After the checkpoint the user authorized at most four GPUs on server 249, excluding physical GPU6. This changes the resource ceiling, not numerical settings or the prohibition on duplicate work and interference with others. The existing controller remains a serial owner of the experiment lock; launching overlapping workers outside its scheduler is unsafe. Any parallel handover must preserve completed/active task ownership, record the scheduling amendment, retain device identity and idle checks, and maintain the pre-detection candidate seal. No parallel workers were launched by this audit. No password was requested, retrieved, logged, or persisted; the existing SSH identity provided access.

## Validation

Five CPU regression tests passed: tamper/missing-file detection, path containment, read-only byte/timestamp preservation, failed-candidate exclusion, and rejection of relabelled failures. The existing archive verifier also passed: 3,641 published files, 422 remote-source files, six prompt sources, nine recorded runs, and 27 target tensors checked. These historical checks do not cover final stage 27 scores.

The audit and draft were prepared in an isolated Git worktree based on local commit `a68f38e`, preserving the original checkout's uncommitted work. GitHub main was independently observed at `f304de4d64530c8df04a36e1d141c7b08e1af315` before publication. Original user history explicitly requested publication to `liylei666-hub/watermark2`.
