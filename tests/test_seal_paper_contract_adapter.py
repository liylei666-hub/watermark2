import importlib.util
import json
import hashlib
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "seal_paper_contract_adapter", ROOT / "scripts/seal_paper_contract_adapter.py"
)
ADAPTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ADAPTER)


def packet(distances, kind="synthetic_fixture"):
    return {
        "schema_version": 1,
        "endpoint": "seal_semantic_recaption",
        "distance_definition": "unnormalized_per_patch_euclidean_l2",
        "provenance": {
            "kind": kind,
            "sample_id": "unit-test",
            "distance_source": "independent_synthetic_fixture",
        },
        "distances": distances,
    }


class SealPaperContractAdapterTests(unittest.TestCase):
    def test_exact_boundary_is_not_a_match(self):
        distances = [2.3] * 1024
        distances[0] = 2.299999999
        record = ADAPTER.build_record(packet(distances))
        self.assertEqual(record["decision"]["match_count"], 1)
        self.assertFalse(record["decision"]["accept"])

    def test_eleven_and_twelve_match_boundary(self):
        eleven = [2.0] * 11 + [2.3] + [3.0] * (1024 - 12)
        twelve = [2.0] * 12 + [2.3] + [3.0] * (1024 - 13)
        self.assertFalse(ADAPTER.build_record(packet(eleven))["decision"]["accept"])
        self.assertTrue(ADAPTER.build_record(packet(twelve))["decision"]["accept"])

    def test_rejects_shape_negative_nan_inf_and_non_scalar(self):
        cases = [
            [2.0] * 1023,
            [2.0] * 1025,
            [-1.0] + [2.0] * 1023,
            [float("nan")] + [2.0] * 1023,
            [float("inf")] + [2.0] * 1023,
            [None] + [2.0] * 1023,
            [True] + [2.0] * 1023,
        ]
        for distances in cases:
            with self.subTest(first=distances[0]):
                with self.assertRaises(ValueError):
                    ADAPTER.build_record(packet(distances))

    def test_rejects_wrong_units_and_untrusted_origin_kind(self):
        payload = packet([2.0] * 1024)
        payload["distance_definition"] = "rmse"
        with self.assertRaises(ValueError):
            ADAPTER.build_record(payload)
        payload = packet([2.0] * 1024, kind="official_verified")
        with self.assertRaises(ValueError):
            ADAPTER.build_record(payload)

    def test_roundtrip_persistence_and_refuse_overwrite(self):
        distances = [2.0] * 12 + [2.3] + [3.0] * (1024 - 13)
        record = ADAPTER.build_record(packet(distances))
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "record.json"
            ADAPTER.save_record(path, record)
            loaded = ADAPTER.load_record(path)
            self.assertEqual(loaded, record)
            with self.assertRaises(FileExistsError):
                ADAPTER.save_record(path, record)
            decoded = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(decoded["adapter"]["version"], "1.0.0")
            self.assertEqual(decoded["paper_contract"]["tau"], 2.3)

    def test_record_tampering_is_detected(self):
        record = ADAPTER.build_record(packet([2.0] * 12 + [3.0] * (1024 - 12)))
        record["decision"]["accept"] = False
        with self.assertRaises(ValueError):
            ADAPTER.validate_record(record)

    def test_version_and_source_metadata(self):
        fixture = ROOT / "tests/fixtures/seal_paper_contract_v1.json"
        self.assertEqual(hashlib.sha256(fixture.read_bytes()).hexdigest(),
                         "60df6cf9aacb6898490b399f603d95174fb26041f5f2f9be5a4002f5517b5e07")
        result = ADAPTER.build_record(json.loads(fixture.read_text()))
        self.assertEqual(result["schema_version"], 1)
        self.assertEqual(result["adapter"]["version"], "1.0.0")
        self.assertFalse(result["adapter"]["input_origin_verified"])
        self.assertFalse(result["adapter"]["complete_seal_pipeline"])
        self.assertEqual([r["version"] for r in result["paper_contract"]["sources"]],
                         ["ICCV_2025", "ICCV_2025_supplement", "arxiv_v4_2026-05-18"])
        self.assertEqual(result["paper_contract"]["sources"][0]["locator"], "Algorithm 3")
        self.assertTrue(all(r["url"].startswith("https://") for r in result["paper_contract"]["sources"]))

    def test_wrong_version_or_source_metadata_is_rejected(self):
        import copy
        original = ADAPTER.build_record(packet([2.0] * 12 + [3.0] * 1012))
        mutations = [
            lambda r: r.update(schema_version=2),
            lambda r: r["adapter"].update(version="2.0.0"),
            lambda r: r["paper_contract"]["sources"][0].update(url="https://example.com"),
            lambda r: r["decision"].update(accept=1),
        ]
        for mutate in mutations:
            modified = copy.deepcopy(original)
            mutate(modified)
            with self.assertRaises(ValueError):
                ADAPTER.validate_record(modified)

    def test_independent_fixture_has_expected_shape(self):
        fixture = json.loads(
            (ROOT / "tests/fixtures/seal_paper_contract_v1.json").read_text(encoding="utf-8")
        )
        record = ADAPTER.build_record(fixture)
        self.assertEqual(len(fixture["distances"]), 1024)
        self.assertEqual(record["decision"], {"distance_count": 1024, "match_count": 12, "accept": True})
        self.assertEqual(fixture["provenance"]["kind"], "synthetic_fixture")


if __name__ == "__main__":
    unittest.main()
