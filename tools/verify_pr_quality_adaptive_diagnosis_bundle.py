from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sdetkit.pr_quality_adaptive_diagnosis import (
    ADAPTIVE_DIAGNOSIS_BUNDLE_MANIFEST_SCHEMA_VERSION,
    ADAPTIVE_DIAGNOSIS_EXPORT_SCHEMA_VERSION,
    AUTHORITY_EXPECTATIONS,
)

JsonObject = dict[str, Any]
SCHEMA_VERSION = "sdetkit.adaptive_diagnosis_bundle_verification.v1"
EXPECTED_ARTIFACTS = (
    "adaptive-diagnosis.html",
    "adaptive-diagnosis.md",
    "adaptive-diagnosis.json",
)
DECISION_BOUNDARY = {
    "automation_allowed": False,
    "patch_application_allowed": False,
    "security_dismissal_allowed": False,
    "merge_authorized": False,
    "semantic_equivalence_proven": False,
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, dict) else {}


def _artifact_records(value: object) -> tuple[dict[str, JsonObject], list[str]]:
    records: dict[str, JsonObject] = {}
    mismatches: list[str] = []
    if not isinstance(value, list):
        return records, ["manifest.artifacts must be a list"]
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            mismatches.append(f"manifest.artifacts[{index}] must be an object")
            continue
        name = str(item.get("path") or "").strip()
        if not name:
            mismatches.append(f"manifest.artifacts[{index}].path is required")
            continue
        if name in records:
            mismatches.append(f"duplicate artifact record: {name}")
            continue
        records[name] = item
    return records, mismatches


def verify_bundle(bundle_dir: Path, *, manifest_path: Path | None = None) -> JsonObject:
    root = bundle_dir.resolve()
    manifest_file = (manifest_path or bundle_dir / "manifest.json").resolve()
    mismatches: list[str] = []

    if not manifest_file.is_file():
        mismatches.append("manifest.json is missing")
        manifest: JsonObject = {}
    else:
        loaded = json.loads(manifest_file.read_text(encoding="utf-8"))
        manifest = loaded if isinstance(loaded, dict) else {}
        if not manifest:
            mismatches.append("manifest.json must contain an object")

    if manifest.get("schema_version") != ADAPTIVE_DIAGNOSIS_BUNDLE_MANIFEST_SCHEMA_VERSION:
        mismatches.append("manifest schema_version mismatch")
    if manifest.get("status") != "passed":
        mismatches.append("manifest status must be passed")
    if manifest.get("authority_validated") is not True:
        mismatches.append("manifest authority_validated must be true")
    if _mapping(manifest.get("authority")) != AUTHORITY_EXPECTATIONS:
        mismatches.append("manifest authority boundary mismatch")

    records, record_mismatches = _artifact_records(manifest.get("artifacts"))
    mismatches.extend(record_mismatches)
    expected = set(EXPECTED_ARTIFACTS)
    observed = set(records)
    for missing in sorted(expected - observed):
        mismatches.append(f"missing artifact record: {missing}")
    for unexpected in sorted(observed - expected):
        mismatches.append(f"unexpected artifact record: {unexpected}")

    checked: list[str] = []
    for name in EXPECTED_ARTIFACTS:
        record = records.get(name)
        if record is None:
            continue
        if Path(name).name != name or Path(name).is_absolute():
            mismatches.append(f"unsafe artifact path: {name}")
            continue
        artifact = (root / name).resolve()
        if artifact.parent != root:
            mismatches.append(f"artifact escapes bundle directory: {name}")
            continue
        if not artifact.is_file():
            mismatches.append(f"artifact file is missing: {name}")
            continue
        checked.append(name)
        actual_size = artifact.stat().st_size
        if record.get("size_bytes") != actual_size:
            mismatches.append(f"artifact size mismatch: {name}")
        if record.get("sha256") != _sha256(artifact):
            mismatches.append(f"artifact sha256 mismatch: {name}")

    export_path = root / "adaptive-diagnosis.json"
    if export_path.is_file():
        loaded_export = json.loads(export_path.read_text(encoding="utf-8"))
        export = loaded_export if isinstance(loaded_export, dict) else {}
        if export.get("schema_version") != ADAPTIVE_DIAGNOSIS_EXPORT_SCHEMA_VERSION:
            mismatches.append("adaptive diagnosis export schema_version mismatch")
        if _mapping(export.get("authority")) != AUTHORITY_EXPECTATIONS:
            mismatches.append("adaptive diagnosis export authority boundary mismatch")

    return {
        "schema_version": SCHEMA_VERSION,
        "ok": not mismatches,
        "bundle_dir": bundle_dir.as_posix(),
        "manifest_path": manifest_file.as_posix(),
        "artifact_count": len(records),
        "artifacts_checked": checked,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "decision_boundary": dict(DECISION_BOUNDARY),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify the portable Adaptive Diagnosis evidence bundle."
    )
    parser.add_argument("--bundle-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--out", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = verify_bundle(args.bundle_dir, manifest_path=args.manifest)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.out is None:
        print(rendered, end="")
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8", newline="\n")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
