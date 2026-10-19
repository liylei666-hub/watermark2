# Stage 27 recovery checkpoint

Final update, 2026-10-19 21:30:45 UTC: stage27 is complete, with 35 delivered candidates, one preserved preimport failure, no pending/unknown tasks and 59 target evaluations. The original controller and postprocessor have finished. The original owner published complete evidence in [main commit 6784879](https://github.com/liylei666-hub/watermark2/commit/678487991fab34650cc5b16e5e96a008fb38bcf4).

Native Imprint passed ordinary GS on 8/12 attempts, delivery-path Imprint on 6/12, and adapted Jain on 3/12 (11 delivered). All twelve references passed. The delivery/native median paired MSE ratio was 0.90897063 and the core-time ratio 1.05165976, but the pass gain was -2 instead of the required minimum +3. The fixed candidate closes under the unchanged scientific rule. Full-defense acceptance and formal human content labels remain unknown.

A targeted local rerun of the published public analyzer checked all 59 images, source associations, sealing order, failures, pixel metrics and timing summaries. It agrees with the published analysis within the existing 1e-12 readback tolerance; the maximum floating-point difference was 7.105427357601002e-15. A separate CSV calculation reproduced the method counts and paired summaries. The server had independently decoded all 59 scores; this local rerun did not decrypt messages. See [final closeout](final_closeout.json), [public recheck](final_public_recheck.json), [task rows](final_task_results.csv) and the updated [paper draft](../../docs/METHOD_COMPARISON_DRAFT.md). No new GPU job or repeated whole-repository audit was performed. The earlier checkpoint below is historical.

## Original recovery snapshot

Snapshot: 2026-10-19 17:39:06 UTC. The continuation was active at this historical checkpoint; the following paragraphs preserve its recovery context.

The running experiment is `runs/27_method_resume_20261019T173017Z`, controlled by PID 21884 and accompanied by CPU postprocessor PID 23796. At the snapshot there were four completed attack tasks, one running task (`2/imprint`, PID 25550), thirty unstarted tasks, and one retained failure (`2/jain`). The latest completed continuation task, `2/delivery`, finished in 412.756438 seconds. At this rate the remaining serial attack work is approximately 3–4 hours, followed by three target-evaluation batches; resource waiting and runtime variation can extend that estimate.

The original run stopped after ten launched worker processes: nine successful processes (six preparation batches and task 1's three attacks) and one preimport idle-gate failure. The failed task produced no candidate. Its recorded 0.498398-second process duration is not evidence of model inference or optimization. The continuation preserves that failure and reuses the successful outputs.

## Checks that affect interpretation

The read-only standard-library audit verified 373/373 original source files, 301/301 inherited copies, 70/70 historical execution records, and 67/67 runtime-pinned code files against their frozen hashes. The original and continuation scientific designs compare equal, including the strict GS threshold and all four go/no-go criteria. The runtime's SHA-256 sidecar, launch binding, device list, storage cap, and inheritance records match. All original process outcomes are accounted for, and the failed task has not been relaunched. See [machine-readable audit](remote_provenance.json) and [auditor](../../tools/audit_stage27_recovery.py).

This is a provenance check plus a non-atomic snapshot of active-run files. It does not establish live-process ownership, model correctness, independent confirmation, or scientific efficacy. Separate SSH process inspection confirmed the named controller, current worker, and postprocessor at the checkpoint. Codex thread inventory and cross-thread messaging returned internal tool errors. A subsequent read-only check of local thread metadata and the latest assistant progress messages identified the original project thread `01a130e6-8d03-76a1-a3c0-e57a13c6b13d` (title: `ciallo`) as still in progress and tracking this exact run. Its reported task counts match the server. User messages and credentials were not read during that ownership check. No running controller, worker, frozen source, or experiment output was modified by this audit.

## Expected final analysis

The original scientific design has 12 tasks per method and 36 candidate slots. Retaining task 2/Jain as missing leaves at most 35 delivered candidates and 59 target inversions (12 references, 12 covers, 35 candidates). Delivery versus native Imprint still has 12 planned pairs. Report Jain's pass count over all 12 attempts and label numeric summaries conditioned on the 11 delivered images. Do not substitute a replacement task or report a 36/36 completion claim.

Apply the original criteria after all deliverable candidates have been sealed and target scores verified: all twelve reference images valid; at least three additional GS passes; median paired pixel-MSE ratio at most 1.05; median paired core-time ratio at most 1.15. Missing required evidence is inconclusive. Complete evidence that fails the criteria closes the candidate. The screen makes no statistical-significance claim.

## Completed paper work

[Methods and results draft](../../docs/METHOD_COMPARISON_DRAFT.md) defines all three objectives, separates continuous optimization from PNG evaluation, explains the comparator budget and missing-task denominator, and reports the closed eight-pair delivery diagnostic. Its summary was recalculated from saved per-pair rows: baseline message accuracy 0.93701171875, corrected 0.8828125, paired change -0.05419921875; seven pairs worsened and one tied. Ordinary GS passes were 8/8 in both conditions. Stage 27 target endpoints remain pending.

The draft includes a visually checked paired-score figure exported as [PNG](delivery_endpoint.png), [SVG](delivery_endpoint.svg), and [PDF](delivery_endpoint.pdf). Its [manifest](figure_manifest.json) binds the figure to the saved verification rows and plotting script. There are no fitted curves or invented uncertainty intervals.

## Resource amendment and coordination

After the checkpoint the user authorized at most four GPUs on server 249, excluding physical GPU6. This changes the resource ceiling, not numerical settings or the prohibition on duplicate work and interference with others. The existing controller remains a serial owner of the experiment lock; launching overlapping workers outside its scheduler is unsafe. Any parallel handover must preserve completed/active task ownership, record the scheduling amendment, retain device identity and idle checks, and maintain the pre-detection candidate seal. No parallel workers were launched by this audit. No password was requested, retrieved, logged, or persisted; the existing SSH identity provided access.

## Validation

Five CPU regression tests passed: tamper/missing-file detection, path containment, read-only byte/timestamp preservation, failed-candidate exclusion, and rejection of relabelled failures. At the initial checkpoint, the original working checkout's archive verifier also passed: 3,641 published files, 422 remote-source files, six prompt sources, nine recorded runs, and 27 target tensors checked. The separate publication branch has its own current inventory and fresh result in [provenance/verification.json](../../provenance/verification.json); its tracked-file population differs from that working checkout. These historical checks do not cover final stage 27 scores.

The audit and draft were prepared in an isolated Git worktree based on local commit `a68f38e`, preserving the original checkout's uncommitted work. GitHub main was independently observed at `f304de4d64530c8df04a36e1d141c7b08e1af315` before publication. Original user history explicitly requested publication to `liylei666-hub/watermark2`. The first audit/draft commit `a8facbd697656302a206e292319298bc6b046d12` was pushed to `research/stage27-recovery-20261019` and verified using `git ls-remote`.
