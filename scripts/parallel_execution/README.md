# Future experiment launcher

`launcher.py` executes a separately frozen experiment plan using real subprocesses. It integrates the standard-library scheduler with pinned model-worker entry scripts, local model manifests, two idle gates, logs, watchdogs and output seals. Production execution is restricted to Linux user `liyanlei`, a host reporting address `172.18.185.249`, and `/data0/liyanlei/watermark_research`. It has not been deployed or used for a model experiment. Stage27 remains under its original serial controller.

## Frozen plan and worker interface

A plan is JSON with these fields. All paths in `files`, `entry`, `parameters`, `snapshot` and `manifest` are relative to the project. SHA-256 values describe actual bytes; the caller supplies the plan's own hash on the command line.

| Field | Meaning |
| --- | --- |
| `schema` | Integer `1` |
| `run_name` | New name beginning `parallel_` |
| `python_version`, `versions` | Exact Python version and package/version mapping, including every model dependency |
| `devices` | One to four objects with physical `index`, explicit `uuid`, and exact `model`; indices 0,1,2,3,4,5,7 only |
| `methods` | Distinct compared method names, at least two |
| `files` | Relative filename to SHA-256 mapping for launcher.py, worker.py, scheduler.py, all entry/helper sources, input/config files and model manifests |
| `models` | Objects containing `snapshot`, exact 40-character `revision`, and pinned `manifest` filename |
| `resource_wait_seconds` | Maximum wait for an idle selected device before claiming a group |
| `attack_groups`, `evaluation_groups` | Nonempty arrays of objects containing a unique `name` and `jobs` |

Each model manifest maps every file in that local snapshot to SHA-256. The snapshot directory must be named by its revision. Snapshot symlinks may resolve to cached blobs inside the project. Model data are hashed in place; this launcher has no download step. Freeze manifests from the already authorized cache. Hugging Face and Transformers offline flags are set for children.

Each job contains `name`, `method`, `entry`, `parameters`, `argv`, `watchdog_seconds`, `output_limit_bytes` and `completion_marker`. Every attack group must contain exactly one job per declared method, representing the same scientific task; use the frozen design to define its inputs and method order. Method jobs in a group execute serially on one physical GPU. Different groups may execute concurrently on identical GPU models. Evaluation groups can contain one or more evaluation jobs.

The entry is an ordinary Python CLI script, run inside the checked child with its own directory on the import path. `argv` is a string array passed directly to the entry, never to a shell. Exact tokens `{parameters}`, `{output}`, `{project}` and `{run}` are substituted. Every job must include `{parameters}` and `{output}`. Runtime paths can be literal absolute paths on the designated server and must also be pinned in `files`.

For the existing attack interface `main(runtime, job_path, output)`, the relevant job fields are:

```json
{
  "name": "task01_delivery",
  "method": "delivery",
  "entry": "scripts/method_comparison/attack.py",
  "parameters": "protocols/future_task01_delivery.json",
  "argv": ["/data0/liyanlei/watermark_research/protocols/future_attacker_runtime.json", "{parameters}", "{output}"],
  "watchdog_seconds": 1200,
  "output_limit_bytes": 67108864,
  "completion_marker": "COMPLETED_COVER_ATTACK"
}
```

This is an interface example, not an executable scientific plan. A future runtime must pin its own authorized UUIDs and sources. Existing frozen stage27 runtime files remain unchanged. The future evaluator entry must read that experiment's sealed candidate paths and controls, write `summary.json` with `completed: true`, and print its declared completion marker. Current evaluators also require their own input layout and domain delivery seal; `candidates_sealed.json` is the scheduler's barrier, not a replacement for those scientific checks. Supply a frozen evaluator adapter for the new protocol's layout before executing it.

## CLI

Set `CUDA_VISIBLE_DEVICES` to the empty string for the supervisor. Use the pinned model environment's Python. Pass an absolute plan path and its independently recorded hash:

```text
python scripts/parallel_execution/launcher.py --project /data0/liyanlei/watermark_research --plan /data0/liyanlei/watermark_research/protocols/FUTURE_PLAN.json --plan-sha256 PLAN_SHA256 --dry-run
```

`--dry-run` validates the plan, source/input/model bytes, versions, GPU selection and method coverage, then prints the exact phase/group/job enumeration. It does not query GPUs, create run directories or launch model processes. It can run in a local project copy with the pinned dependencies and local model snapshots available. Replace `--dry-run` with `--execute` only after the future scientific design, inputs and evaluator adapter are frozen and the existing experiment has relinquished its lock.

The launcher shares `runs/.imprint_delivery.lock` with the existing controller and fails when occupied. The lock encloses final source/storage checks and all phases. Run/task directories are exclusively created. The conservative storage check counts all retained files under `runs` and `reports`, reserves every job's declared maximum plus metadata, and refuses totals over 10 GiB or inadequate free space. It never deletes evidence. Each child is checked every 0.1 seconds for its declared output allowance; this software stop rule may observe an overshoot after a write and is not a filesystem quota.

GPU identity, no compute processes, at most 50 MiB allocated memory, and zero utilization must hold for three consecutive samples. The supervisor checks before claims; the child repeats the gate before model imports. UUID visibility and offline flags precede subprocess startup. Host/IP checks are operational guards used together with the authenticated server session, not independent host attestation. Offline environment variables require the frozen worker to use local loaders; they are not an operating-system network sandbox.

## Records and explicit recovery

Each job retains its claim, process identity, stdout/stderr, child preimport observations, exact entry command, domain outputs, execution record and execution hash seal. Successful attacks require matching candidate PNG hashes. All attacks must complete before candidate sealing and evaluator launch. Candidate hashes are rechecked before each evaluation and at the end. The final seal hashes every execution record and final status. Actual core/load timings remain the worker's responsibility and must be reported separately from process wall time.

Use the same plan/hash with `--resume` for explicit recovery of this launcher's own runs. Recovery verifies schedule identity, execution seals, every recorded artifact, candidate hashes and device affinity. Only successful recorded jobs are inherited. Remaining methods of a partially completed group retain its original GPU. A failed job, missing execution/seal, changed file or existing final result seal stops recovery. An orphaned live child has an ambiguous claim and cannot be duplicated or killed by recovery. Resolve its evidence and ownership separately; a disappeared PID does not imply success. Deleting claims or relabelling failures is not valid recovery.

A clean boundary interruption can resume unclaimed jobs. Original records/status remain intact; a recovery event and separately numbered recovery status are appended. Jobs in flight finish after a peer fails. A watchdog only terminates the subprocess group this runner created. There is no live handover from stage27.

Attack entry arguments contain that attack's pinned parameters/runtime and output. Evaluator inputs are supplied when evaluation jobs launch after the barrier. Launcher and entry share a user account; this is an auditable information boundary, not permission isolation. Review dependency pins and entry input access when freezing the next scientific design.

## CPU validation and remaining evidence

Run `python scripts/parallel_execution/test_scheduler.py -v` and `python scripts/parallel_execution/test_launcher.py -v` with empty CUDA visibility. Kernel tests cover four concurrent threads, unique claims, affinity, busy-device handling and candidate sealing. Integration tests launch real CPU subprocesses through the child wrapper with explicitly replaced test gates and synthetic model files; a four-process rendezvous verifies actual concurrency. They cover CLI dry-run, forbidden GPUs, pinned-file mutations, host/UUID rejection, logs/seals, watchdog/output limits, boundary recovery, live ambiguous children and artifact tampering. Production has no test-mode CLI flag.

These tests establish orchestration behavior. GPU throughput, model numerical equivalence, hardware timing fairness and scientific efficacy remain unmeasured. A new independent scientific protocol and compatible evaluator layout still need freezing; no stage27 task has been submitted to this launcher.

Recorded validation: [28 passing CPU tests and source hashes](../../reports/parallel_launcher_cpu_tests_20261019.json). Background experiment handoff: [checkpoint](../../reports/parallel_launcher_checkpoint_20261019.json).
