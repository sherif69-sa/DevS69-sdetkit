#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

MANIFEST_SCHEMA = "sdetkit.release_distribution_manifest.v1"
RECORD_SCHEMA = "sdetkit.release_candidate.python_qualification.v1"
VERDICT_SCHEMA = "sdetkit.release_candidate.verdict.v2"
SUPPORTED_PYTHON_VERSIONS = ("3.10", "3.11", "3.12")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON evidence must be an object: {path}")
    return payload


def _file_evidence(name: str, path: Path) -> dict[str, object]:
    data = path.read_bytes()
    payload = _read_json(path)
    if not payload:
        raise ValueError(f"qualification evidence must not be empty: {path}")
    return {
        "name": name,
        "file": path.name,
        "size_bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _wheel_from_manifest(manifest: dict[str, Any]) -> dict[str, object]:
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        raise ValueError("distribution manifest schema mismatch")
    source_sha = str(manifest.get("source_sha", ""))
    if not SHA_RE.fullmatch(source_sha):
        raise ValueError("distribution manifest source SHA is invalid")

    rows = manifest.get("files")
    if not isinstance(rows, list):
        raise ValueError("distribution manifest files must be a list")
    wheels = [
        row for row in rows if isinstance(row, dict) and str(row.get("name", "")).endswith(".whl")
    ]
    if len(wheels) != 1:
        raise ValueError("distribution manifest must contain exactly one wheel")

    wheel = wheels[0]
    name = str(wheel.get("name", ""))
    digest = str(wheel.get("sha256", ""))
    size_bytes = wheel.get("size_bytes")
    if not DIGEST_RE.fullmatch(digest):
        raise ValueError("wheel SHA-256 is invalid")
    if not isinstance(size_bytes, int) or size_bytes <= 0:
        raise ValueError("wheel size must be a positive integer")
    return {"name": name, "sha256": digest, "size_bytes": size_bytes}


def build_python_record(
    *,
    manifest: dict[str, Any],
    python_version: str,
    evidence_paths: dict[str, Path],
    runtime_python_version: str | None = None,
) -> dict[str, object]:
    if python_version not in SUPPORTED_PYTHON_VERSIONS:
        raise ValueError(f"unsupported qualification Python version: {python_version}")
    runtime = runtime_python_version or f"{sys.version_info.major}.{sys.version_info.minor}"
    if runtime != python_version:
        raise ValueError(
            "qualification runtime does not match matrix version: "
            f"runtime={runtime} expected={python_version}"
        )

    source_sha = str(manifest.get("source_sha", ""))
    version = str(manifest.get("version", ""))
    candidate_tag = str(manifest.get("tag", ""))
    if candidate_tag != f"v{version}":
        raise ValueError("candidate tag and version do not match")

    required_evidence = {"gate_fast", "gate_release", "doctor"}
    if set(evidence_paths) != required_evidence:
        raise ValueError(
            "qualification evidence set mismatch: "
            f"expected={sorted(required_evidence)} actual={sorted(evidence_paths)}"
        )

    return {
        "schema_version": RECORD_SCHEMA,
        "status": "exact_wheel_qualification_passed",
        "candidate_tag": candidate_tag,
        "version": version,
        "source_sha": source_sha,
        "python_version": python_version,
        "wheel": _wheel_from_manifest(manifest),
        "evidence_artifacts": [
            _file_evidence(name, evidence_paths[name]) for name in sorted(evidence_paths)
        ],
        "clean_room_install": True,
        "installed_wheel_contract": "passed",
        "external_settings_verified": False,
        "publish_authorized": False,
        "publication_attempted": False,
        "tag_created": False,
    }


def build_verdict(
    *,
    records: list[dict[str, Any]],
    candidate_tag: str,
    version: str,
    source_sha: str,
) -> dict[str, object]:
    if candidate_tag != f"v{version}":
        raise ValueError("candidate tag and version do not match")
    if not SHA_RE.fullmatch(source_sha):
        raise ValueError("source SHA must be a 40-character lowercase hexadecimal value")
    if len(records) != len(SUPPORTED_PYTHON_VERSIONS):
        raise ValueError("qualification verdict requires exactly three Python records")

    observed_versions: list[str] = []
    wheel_identities: set[tuple[str, str, int]] = set()
    for record in records:
        if record.get("schema_version") != RECORD_SCHEMA:
            raise ValueError("qualification record schema mismatch")
        if record.get("status") != "exact_wheel_qualification_passed":
            raise ValueError("qualification record did not pass")
        if record.get("candidate_tag") != candidate_tag:
            raise ValueError("qualification record candidate tag mismatch")
        if record.get("version") != version:
            raise ValueError("qualification record version mismatch")
        if record.get("source_sha") != source_sha:
            raise ValueError("qualification record source SHA mismatch")
        if record.get("external_settings_verified") is not False:
            raise ValueError("qualification record must not claim external settings verification")
        if record.get("publish_authorized") is not False:
            raise ValueError("qualification record must not authorize publication")
        if record.get("publication_attempted") is not False:
            raise ValueError("qualification record must not attempt publication")
        if record.get("tag_created") is not False:
            raise ValueError("qualification record must not claim tag creation")
        if record.get("clean_room_install") is not True:
            raise ValueError("qualification record must prove a clean-room install")
        if record.get("installed_wheel_contract") != "passed":
            raise ValueError("installed-wheel contract did not pass")

        python_version = str(record.get("python_version", ""))
        observed_versions.append(python_version)
        wheel = record.get("wheel")
        if not isinstance(wheel, dict):
            raise ValueError("qualification record wheel evidence is missing")
        name = str(wheel.get("name", ""))
        digest = str(wheel.get("sha256", ""))
        size_bytes = wheel.get("size_bytes")
        if not DIGEST_RE.fullmatch(digest):
            raise ValueError("qualification record wheel digest is invalid")
        if not isinstance(size_bytes, int) or size_bytes <= 0:
            raise ValueError("qualification record wheel size is invalid")
        wheel_identities.add((name, digest, size_bytes))

        artifacts = record.get("evidence_artifacts")
        if not isinstance(artifacts, list):
            raise ValueError("qualification record evidence artifacts are missing")
        names = {str(item.get("name", "")) for item in artifacts if isinstance(item, dict)}
        if names != {"gate_fast", "gate_release", "doctor"}:
            raise ValueError("qualification record evidence artifact set mismatch")

    if sorted(observed_versions) != list(SUPPORTED_PYTHON_VERSIONS):
        raise ValueError(
            "qualified Python version set mismatch: "
            f"expected={list(SUPPORTED_PYTHON_VERSIONS)} actual={sorted(observed_versions)}"
        )
    if len(wheel_identities) != 1:
        raise ValueError("Python qualification records did not test the same exact wheel")

    wheel_name, wheel_sha256, wheel_size = next(iter(wheel_identities))
    return {
        "schema_version": VERDICT_SCHEMA,
        "status": "repository_qualification_passed",
        "candidate_tag": candidate_tag,
        "version": version,
        "source_sha": source_sha,
        "qualified_python_versions": list(SUPPORTED_PYTHON_VERSIONS),
        "qualification_record_count": len(records),
        "exact_wheel": {
            "name": wheel_name,
            "sha256": wheel_sha256,
            "size_bytes": wheel_size,
            "same_digest_across_matrix": True,
        },
        "external_settings_verified": False,
        "publish_authorized": False,
        "publication_attempted": False,
        "tag_created": False,
        "required_external_checks": [
            "GitHub environment pypi protection",
            "PyPI Trusted Publisher binding",
        ],
        "next_action": "verify external publishing settings before creating v1.1.0",
    }


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build release-candidate qualification evidence")
    subparsers = parser.add_subparsers(dest="command", required=True)

    record = subparsers.add_parser("record")
    record.add_argument("--distribution-manifest", type=Path, required=True)
    record.add_argument("--python-version", required=True)
    record.add_argument("--gate-fast", type=Path, required=True)
    record.add_argument("--gate-release", type=Path, required=True)
    record.add_argument("--doctor", type=Path, required=True)
    record.add_argument("--out", type=Path, required=True)

    verdict = subparsers.add_parser("verdict")
    verdict.add_argument("--record", type=Path, action="append", required=True)
    verdict.add_argument("--candidate-tag", required=True)
    verdict.add_argument("--version", required=True)
    verdict.add_argument("--source-sha", required=True)
    verdict.add_argument("--out", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "record":
        payload = build_python_record(
            manifest=_read_json(args.distribution_manifest),
            python_version=args.python_version,
            evidence_paths={
                "gate_fast": args.gate_fast,
                "gate_release": args.gate_release,
                "doctor": args.doctor,
            },
        )
    else:
        payload = build_verdict(
            records=[_read_json(path) for path in args.record],
            candidate_tag=args.candidate_tag,
            version=args.version,
            source_sha=args.source_sha,
        )
    _write_json(args.out, payload)
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
