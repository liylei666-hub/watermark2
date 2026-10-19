"""CPU-only adversarial and concurrent integration tests for future scheduling."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import scheduler as s

os.environ["CUDA_VISIBLE_DEVICES"] = ""
HASH = hashlib.sha256(b"frozen synthetic configuration").hexdigest()
DEVICES = tuple(s.Device(i, "GPU-test-" + str(i), "test-model") for i in (0, 1, 2, 4))


def groups(count=1, methods=1):
    return tuple(s.Group("task" + str(i), tuple(s.Job(f"attack{i}_{m}", HASH) for m in range(methods))) for i in range(count))


EVALUATION = (s.Group("evaluation", (s.Job("eval0", HASH),)),)


class Runner:
    def __init__(self, fail=None, barrier=None):
        self.calls, self.active, self.peak = [], 0, 0
        self.lock = threading.Lock()
        self.fail, self.barrier = fail, barrier

    def __call__(self, job, device, output, environment):
        with self.lock:
            self.calls.append((job.name, device.index))
            self.active += 1
            self.peak = max(self.peak, self.active)
        try:
            assert environment["CUDA_VISIBLE_DEVICES"] == device.uuid
            assert environment["HF_HUB_OFFLINE"] == "1"
            if self.barrier and job.name.endswith("_0"):
                self.barrier.wait(timeout=5)
            if job.name == self.fail:
                return dict(completed=False, exit_code=1)
            if job.name.startswith("eval"):
                seal = json.loads((output.parent / "candidates_sealed.json").read_text())
                assert seal["candidates"]
                assert all((output.parent / name / "execution.json").exists() for name in seal["candidates"])
                return dict(completed=True, exit_code=0)
            raw = job.name.encode()
            (output / "candidate.png").write_bytes(raw)  # Synthetic bytes: no image/model claim.
            time.sleep(0.005)
            return dict(completed=True, exit_code=0, candidate_sha256=hashlib.sha256(raw).hexdigest())
        finally:
            with self.lock:
                self.active -= 1


class Scheduling(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def make(self, runner=None, devices=DEVICES[:1], attacks=None, gate=None):
        return s.Scheduler(self.root, "new_run", devices, attacks or groups(), EVALUATION,
            runner or Runner(), gate or (lambda device: True), resource_wait_seconds=0, poll_seconds=.001)

    def test_four_workers_affinity_unique_claim_and_detection_barrier(self):
        runner = Runner(barrier=threading.Barrier(4))
        result = self.make(runner, DEVICES, groups(4, 2)).run()
        self.assertTrue(result["completed"])
        self.assertEqual(runner.peak, 4)
        self.assertEqual(len(runner.calls), len(set(name for name, _ in runner.calls)))
        assigned = dict(runner.calls)
        for i in range(4):
            self.assertEqual(assigned[f"attack{i}_0"], assigned[f"attack{i}_1"])
        events = [json.loads(line) for line in (self.root / "runs/new_run/events.jsonl").read_text().splitlines()]
        barrier = next(i for i, e in enumerate(events) if e["event"] == "candidate_barrier_passed")
        self.assertTrue(all(i > barrier for i, e in enumerate(events) if e.get("phase") == "evaluation"))

    def test_gpu6_rejected_before_runner_or_gate(self):
        with self.assertRaises(ValueError):
            self.make(devices=(s.Device(6, "GPU-excluded", "test-model"),))
        self.assertFalse((self.root / "runs").exists())

    def test_more_than_four_or_duplicate_devices_rejected(self):
        with self.assertRaises(ValueError):
            self.make(devices=DEVICES + (s.Device(5, "GPU-test-5", "test-model"),))
        with self.assertRaises(ValueError):
            self.make(devices=(DEVICES[0], DEVICES[0]))

    def test_duplicate_jobs_rejected_before_any_write(self):
        with self.assertRaises(ValueError):
            self.make(attacks=(s.Group("one", (s.Job("same", HASH),)), s.Group("two", (s.Job("same", HASH),))))
        self.assertFalse((self.root / "runs").exists())

    def test_failed_job_keeps_failure_and_blocks_evaluation_and_retry(self):
        runner = Runner(fail="attack0_0")
        plan = self.make(runner, attacks=groups(2))
        result = plan.run()
        self.assertFalse(result["completed"])
        self.assertEqual(result["failed_jobs"], ["attack0_0"])
        self.assertEqual(runner.calls, [("attack0_0", 0)])
        self.assertFalse((plan.root / "candidates_sealed.json").exists())
        before = (plan.root / "attack0_0/execution.json").read_bytes()
        with self.assertRaises(FileExistsError):
            self.make().run()
        self.assertEqual((plan.root / "attack0_0/execution.json").read_bytes(), before)

    def test_busy_device_never_claims_task_or_launches(self):
        runner = Runner()
        result = self.make(runner, gate=lambda device: False).run()
        self.assertFalse(result["completed"])
        self.assertEqual(runner.calls, [])
        self.assertEqual(result["unstarted_jobs"], ["attack0_0", "eval0"])
        self.assertEqual(result["ambiguous_claimed_jobs"], [])

    def test_busy_device_skipped_for_an_idle_device(self):
        runner = Runner()
        result = self.make(runner, devices=DEVICES[:2], gate=lambda d: d.index == 1).run()
        self.assertTrue(result["completed"])
        self.assertEqual({device for _, device in runner.calls}, {1})

    def test_candidate_tamper_blocks_evaluator(self):
        runner = Runner()
        def gate(device):
            run = self.root / "runs/new_run"
            if (run / "candidates_sealed.json").exists():
                (run / "attack0_0/candidate.png").write_bytes(b"tampered")
            return True
        result = self.make(runner, gate=gate).run()
        self.assertFalse(result["completed"])
        self.assertEqual(runner.calls, [("attack0_0", 0)])

    def test_partial_execution_record_is_ambiguous_not_unstarted(self):
        original = s.write_once
        def write(path, value):
            if Path(path).name == "execution.json":
                raise OSError("simulated recording failure")
            return original(path, value)
        with patch.object(s, "write_once", write):
            result = self.make().run()
        self.assertEqual(result["ambiguous_claimed_jobs"], ["attack0_0"])
        self.assertNotIn("attack0_0", result["unstarted_jobs"])

    def test_existing_project_lock_blocks_entire_run(self):
        runner = Runner()
        with s.project_lock(self.root / "runs/.imprint_delivery.lock"):
            with self.assertRaises(OSError):
                self.make(runner).run()
        self.assertFalse((self.root / "runs/new_run").exists())
        self.assertEqual(runner.calls, [])

    def test_inflight_job_finishes_after_peer_failure(self):
        runner = Runner()
        barrier = threading.Barrier(2)
        def concurrent(job, device, output, environment):
            if job.name in ("attack0_0", "attack1_0"):
                barrier.wait(timeout=5)
            if job.name == "attack0_0":
                return dict(completed=False, exit_code=1)
            if job.name == "attack1_0":
                time.sleep(.1)
            return runner(job, device, output, environment)
        result = self.make(concurrent, devices=DEVICES[:2], attacks=groups(3)).run()
        self.assertFalse(result["completed"])
        self.assertEqual(result["completed_jobs"], ["attack1_0"])
        self.assertEqual(result["failed_jobs"], ["attack0_0"])
        self.assertIn("attack2_0", result["unstarted_jobs"])

    def test_caller_cannot_mutate_scheduled_job_list(self):
        jobs = [s.Job("attack0_0", HASH)]
        plan = self.make(attacks=(s.Group("task0", jobs),))
        jobs.append(s.Job("injected", HASH))
        result = plan.run()
        self.assertTrue(result["completed"])
        self.assertNotIn("injected", result["completed_jobs"])


class IdleGate(unittest.TestCase):
    def observation(self, index=0, busy=False, uuid="GPU-test-0", util=0):
        return dict(index=index, uuid=uuid, model="test-model", memory_used_mib=4,
                    utilization_percent=util, compute_apps=[{"pid": 123}] if busy else [])

    def test_three_idle_samples_required_after_transient(self):
        samples = iter([self.observation(util=v) for v in (0, 1, 0, 0, 0)])
        events = []
        self.assertTrue(s.verify_idle(DEVICES[0], lambda _: next(samples), events.append, sleep=lambda _: None))
        self.assertEqual(events[-1]["samples"], 5)

    def test_foreign_process_rejected(self):
        self.assertFalse(s.verify_idle(DEVICES[0], lambda _: self.observation(busy=True), lambda _: None, sleep=lambda _: None))

    def test_identity_mismatch_is_not_resource_wait(self):
        with self.assertRaises(ValueError):
            s.verify_idle(DEVICES[0], lambda _: self.observation(uuid="GPU-other"), lambda _: None, sleep=lambda _: None)


if __name__ == "__main__":
    unittest.main()
