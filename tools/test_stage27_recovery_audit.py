"""Adversarial checks for evidence integrity and missing-task accounting."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from audit_stage27_recovery import inside, verify_map, inheritance_check


class EvidenceAudit(unittest.TestCase):
    def test_tampered_and_missing_files_are_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data").write_bytes(b"changed")
            expected = {"data": hashlib.sha256(b"original").hexdigest(), "missing": "0" * 64}
            result = verify_map(root, expected)
            self.assertEqual(result["verified"], 0)
            self.assertEqual({r["error"] for r in result["errors"]}, {"hash_mismatch", "missing"})

    def test_escape_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                inside(directory, "../outside")

    def test_read_only_check_preserves_bytes_and_timestamp(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "raw"
            path.write_bytes(b"evidence")
            before = path.stat().st_mtime_ns
            result = verify_map(directory, {"raw": hashlib.sha256(b"evidence").hexdigest()})
            self.assertEqual(result["verified"], 1)
            self.assertEqual(path.stat().st_mtime_ns, before)
            self.assertEqual(path.read_bytes(), b"evidence")

    def test_failure_retained_and_successful_candidate_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / "failed"
            folder.mkdir()
            raw = json.dumps({"completed": False, "exit_code": 1, "timed_out": False, "elapsed_seconds": 0.5}).encode()
            (folder / "execution.json").write_bytes(raw)
            meta = {"completed": {}, "failed": {"attack_outputs/2/jain": {"path": "failed", "sha256": hashlib.sha256(raw).hexdigest()}}}
            self.assertEqual(inheritance_check(directory, meta)["errors"], [])
            (folder / "candidate.png").write_bytes(b"not allowed")
            self.assertEqual(inheritance_check(directory, meta)["errors"][0]["error"], "failed_task_has_success_or_candidate")

    def test_relabelled_failure_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / "failed"
            folder.mkdir()
            raw = json.dumps({"completed": False, "exit_code": 1, "elapsed_seconds": 0.5}).encode()
            (folder / "execution.json").write_bytes(raw)
            meta = {"failed": {}, "completed": {"task": {"path": "failed", "sha256": hashlib.sha256(raw).hexdigest()}}}
            self.assertEqual(inheritance_check(directory, meta)["errors"][0]["error"], "completion_classification_mismatch")


if __name__ == "__main__":
    unittest.main()
