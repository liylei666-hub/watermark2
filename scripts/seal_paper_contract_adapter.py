"""Original CPU paper-contract adapter for already computed semantic patch L2.

This module does not compute captions, embeddings, image inversion or watermark
authenticity. Input provenance and distance units are caller declarations.
Only the Python standard library is used.
"""
import argparse
import hashlib
import json
import math
from collections.abc import Sequence
from numbers import Real
from pathlib import Path

SCHEMA_VERSION = 1
ADAPTER_VERSION = "1.0.0"
ENDPOINT = "seal_semantic_recaption"
DISTANCE_DEFINITION = "unnormalized_per_patch_euclidean_l2"
PATCHES = 1024
BITS = 7
TAU = 2.3
MINIMUM_MATCHES = 12


def paper_contract():
    """Return fresh source metadata and the fixed paper rule."""
    return {
        "k": PATCHES,
        "b": BITS,
        "distance_definition": DISTANCE_DEFINITION,
        "patch_comparison": "strict_lt",
        "tau": TAU,
        "count_comparison": "gte",
        "minimum_matches": MINIMUM_MATCHES,
        "sources": [
            {
                "version": "ICCV_2025",
                "locator": "Algorithm 3",
                "url": "https://www.openaccess.thecvf.com/content/ICCV2025/papers/"
                       "Arabi_SEAL_Semantic_Aware_Image_Watermarking_ICCV_2025_paper.pdf",
            },
            {
                "version": "ICCV_2025_supplement",
                "locator": "9.1 Key Parameters",
                "url": "https://www.openaccess.thecvf.com/content/ICCV2025/supplemental/"
                       "Arabi_SEAL_Semantic_Aware_ICCV_2025_supplemental.pdf",
            },
            {
                "version": "arxiv_v4_2026-05-18",
                "locator": "Algorithm 3 and 9.1",
                "url": "https://arxiv.org/html/2503.12172v4",
            },
        ],
    }


def canonical_bytes(value):
    """Stable JSON bytes for local consistency checks, not authentication."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def validate_distances(values):
    """Require a one-dimensional sequence of exactly 1024 finite nonnegative reals."""
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes, bytearray)):
        raise ValueError("distances must be a one-dimensional numeric sequence")
    if len(values) != PATCHES:
        raise ValueError(f"expected {PATCHES} distances, got {len(values)}")
    result = []
    for index, value in enumerate(values):
        if isinstance(value, bool) or not isinstance(value, Real):
            raise ValueError(f"distance {index} must be a real scalar")
        try:
            scalar = float(value)
        except (ValueError, TypeError, OverflowError) as exc:
            raise ValueError(f"distance {index} cannot be represented as a finite float") from exc
        if not math.isfinite(scalar) or scalar < 0:
            raise ValueError(f"distance {index} must be finite and nonnegative")
        result.append(scalar)
    return result


def validate_input(payload):
    """Validate declared units/endpoint/provenance without verifying their origin."""
    required = {"schema_version", "endpoint", "distance_definition", "provenance", "distances"}
    if not isinstance(payload, dict) or set(payload) != required:
        raise ValueError("input must contain exactly schema_version, endpoint, distance_definition, provenance, distances")
    if type(payload["schema_version"]) is not int or payload["schema_version"] != SCHEMA_VERSION:
        raise ValueError("unsupported input schema_version")
    if payload["endpoint"] != ENDPOINT:
        raise ValueError("input endpoint must declare semantic recaption distances")
    if payload["distance_definition"] != DISTANCE_DEFINITION:
        raise ValueError("input must declare unnormalized per-patch Euclidean L2")
    provenance = payload["provenance"]
    fields = {"kind", "sample_id", "distance_source"}
    if not isinstance(provenance, dict) or set(provenance) != fields:
        raise ValueError("provenance must contain exactly kind, sample_id, distance_source")
    if any(not isinstance(v, str) or not v.strip() for v in provenance.values()):
        raise ValueError("provenance fields must be nonempty strings")
    if provenance["kind"] not in {"synthetic_fixture", "caller_supplied_distances"}:
        raise ValueError("unsupported provenance kind")
    return {
        "schema_version": SCHEMA_VERSION,
        "endpoint": ENDPOINT,
        "distance_definition": DISTANCE_DEFINITION,
        "provenance": dict(provenance),
        "distances": validate_distances(payload["distances"]),
    }


def build_record(payload):
    """Apply strict L2<2.3 and count>=12 to validated precomputed distances."""
    normalized = validate_input(payload)
    count = sum(distance < TAU for distance in normalized["distances"])
    return {
        "schema_version": SCHEMA_VERSION,
        "adapter": {
            "name": "seal_semantic_paper_contract_adapter",
            "version": ADAPTER_VERSION,
            "implementation": "original_python_standard_library_cpu",
            "scope": "decision_and_persistence_for_precomputed_distances",
            "complete_seal_pipeline": False,
            "input_origin_verified": False,
            "security_calibrated": False,
        },
        "paper_contract": paper_contract(),
        "input": normalized,
        "input_sha256": hashlib.sha256(canonical_bytes(normalized)).hexdigest(),
        "decision": {
            "distance_count": PATCHES,
            "match_count": count,
            "accept": count >= MINIMUM_MATCHES,
        },
    }


def validate_record(record):
    """Recompute a packet and check rule, metadata, values, digest and decision."""
    if not isinstance(record, dict) or "input" not in record:
        raise ValueError("record must contain an input packet")
    expected = build_record(record["input"])
    try:
        matches = canonical_bytes(record) == canonical_bytes(expected)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError("record is not a valid finite JSON packet") from exc
    if not matches:
        raise ValueError("record metadata, rule, digest or decision is inconsistent")
    return expected


def save_record(path, record):
    """Validate and create one UTF-8 JSON packet, refusing to overwrite a file."""
    checked = validate_record(record)
    text = json.dumps(checked, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(text)


def load_record(path):
    """Load and validate a saved packet, including its fixed version and sources."""
    return validate_record(json.loads(Path(path).read_text(encoding="utf-8")))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="JSON input packet containing 1024 precomputed distances")
    parser.add_argument("--output", required=True, type=Path, help="new JSON record path; existing files are refused")
    args = parser.parse_args()
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        record = build_record(payload)
        save_record(args.output, record)
    except (ValueError, OSError, TypeError, OverflowError) as exc:
        parser.exit(2, f"paper-contract adapter: {exc}\n")
    print(json.dumps({
        "adapter_version": ADAPTER_VERSION,
        "scope": record["adapter"]["scope"],
        "sample_id": record["input"]["provenance"]["sample_id"],
        "decision": record["decision"],
        "output": str(args.output),
    }, indent=2))


if __name__ == "__main__":
    main()
