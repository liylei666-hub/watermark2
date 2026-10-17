"""Integrity and denominator checks using synthetic bookkeeping fixtures."""
import copy
import hashlib
import os
from pathlib import Path
import tempfile
import unittest

from summarize_evaluation_events import summarize


class EventTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "candidate.bin").write_bytes(b"synthetic unit fixture, not an image")
        self.doc = {"schema_version": 1, "scope": "single_output", "full_defense_protocol_complete": True,
                    "planned_tasks": [{"task_id": "a", "group": "test"}],
                    "records": [{"task_id": "a", "group": "test", "run_status": "completed",
                        "candidate": {"path": "candidate.bin", "sha256": hashlib.sha256((self.root / "candidate.bin").read_bytes()).hexdigest()},
                        "reference_valid": True, "content_met": True, "forgery_in_scope": True,
                        "watermark_pass": True, "full_defense_accept": True}]}

    def summary(self):
        return summarize(self.doc, self.root)["groups"]["test"]

    def test_hash_tampering_rejected(self):
        (self.root / "candidate.bin").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
            self.summary()

    def test_path_traversal_rejected(self):
        self.doc["records"][0]["candidate"]["path"] = "../outside"
        with self.assertRaisesRegex(ValueError, "escapes"):
            self.summary()

    def test_missing_task_cannot_reduce_denominator(self):
        self.doc["planned_tasks"].append({"task_id": "b", "group": "test"})
        with self.assertRaisesRegex(ValueError, "Missing planned"):
            self.summary()

    def test_duplicate_cannot_create_any_of_k(self):
        self.doc["records"].append(copy.deepcopy(self.doc["records"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate task"):
            self.summary()

    def test_unknown_content_kept_unknown(self):
        self.doc["records"][0]["content_met"] = None
        s = self.summary()
        self.assertIsNone(s["full_defense_joint_rate"])
        self.assertEqual(s["joint_success_unknown"], 1)
        self.assertEqual(s["descriptive_identification_bounds"], [0, 1])

    def test_content_failure_is_not_detector_bypass(self):
        self.doc["records"][0]["content_met"] = False
        self.doc["records"][0]["full_defense_accept"] = None
        self.assertEqual(self.summary()["full_defense_joint_rate"], 0)

    def test_missing_protocol_suppresses_rate_and_bounds(self):
        self.doc["full_defense_protocol_complete"] = False
        self.doc["records"][0]["full_defense_accept"] = None
        s = self.summary()
        self.assertIsNone(s["full_defense_joint_rate"])
        self.assertIsNone(s["descriptive_identification_bounds"])
        self.assertEqual(s["watermark_task_rate_among_valid_references"], 1)

    def test_unknown_protocol_cannot_accept(self):
        self.doc["full_defense_protocol_complete"] = None
        with self.assertRaisesRegex(ValueError, "complete protocol"):
            self.summary()

    def test_failed_run_stays_in_denominator(self):
        failed = copy.deepcopy(self.doc["records"][0])
        failed.update(task_id="b", run_status="failed", candidate=None,
                      content_met=None, forgery_in_scope=None, watermark_pass=None, full_defense_accept=None)
        self.doc["planned_tasks"].append({"task_id": "b", "group": "test"})
        self.doc["records"].append(failed)
        s = self.summary()
        self.assertEqual(s["reference_valid"], 2)
        self.assertEqual(s["failed"], 1)
        self.assertEqual(s["full_defense_joint_rate"], .5)

    def test_reference_unknown_separately_counted(self):
        self.doc["records"][0]["reference_valid"] = None
        s = self.summary()
        self.assertEqual(s["reference_unknown"], 1)
        self.assertIsNone(s["full_defense_joint_rate"])

    def test_strings_and_integers_are_not_boolean_labels(self):
        for value in ("False", "True", 0, 1):
            self.doc["records"][0]["content_met"] = value
            with self.assertRaisesRegex(ValueError, "bool or null"):
                self.summary()

    def test_unrecognized_fields_rejected(self):
        self.doc["records"][0]["target_key"] = "synthetic"
        with self.assertRaisesRegex(ValueError, "Invalid record fields"):
            self.summary()


if __name__ == "__main__":
    if os.environ.get("CUDA_VISIBLE_DEVICES") != "":
        raise SystemExit('Set CUDA_VISIBLE_DEVICES=""')
    unittest.main()
