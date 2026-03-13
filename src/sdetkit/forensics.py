from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

from .atomicio import canonical_json_bytes, canonical_json_dumps
from .report import diff_runs, load_run_record
from .security import SecurityError, safe_path


def _compare(from_path: Path, to_path: Path) -> dict[str, Any]:
    from_run = load_run_record(from_path)
    to_run = load_run_record(to_path)
    payload = diff_runs(from_run, to_run)
    new_error = [x for x in payload.get("new", []) if x.get("severity") == "error"]
    payload["schema_version"] = "sdetkit.forensics.compare.v1"
    payload["regression_summary"] = {
        "new_failures": payload.get("counts", {}).get("new", 0),
        "resolved_failures": payload.get("counts", {}).get("resolved", 0),
        "changed_failures": payload.get("counts", {}).get("changed", 0),
        "regression": bool(new_error),
    }
    payload["next_step"] = (
        "Block release and open failure-forensics triage lane."
        if new_error
        else "No new error regressions detected."
    )
    return payload


def _bundle(run_path: Path, output_path: Path, include: list[str]) -> dict[str, Any]:
    run = load_run_record(run_path)
    extras: list[dict[str, Any]] = []
    manifest = {
        "schema_version": "sdetkit.forensics.bundle-manifest.v1",
        "run_sha256": hashlib.sha256(canonical_json_bytes(run)).hexdigest(),
        "included_files": sorted(include),
        "extras": extras,
    }

    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        info = zipfile.ZipInfo("manifest.json")
        info.date_time = (1980, 1, 1, 0, 0, 0)
        info.compress_type = zipfile.ZIP_DEFLATED
        zf.writestr(info, canonical_json_dumps(manifest))

        run_info = zipfile.ZipInfo("run.json")
        run_info.date_time = (1980, 1, 1, 0, 0, 0)
        run_info.compress_type = zipfile.ZIP_DEFLATED
        zf.writestr(run_info, canonical_json_dumps(run))

        for file_name in sorted(include):
            path = safe_path(Path.cwd(), file_name, allow_absolute=True)
            if not path.exists() or not path.is_file():
                extras.append(
                    {
                        "requested": file_name,
                        "stored": None,
                        "status": "missing",
                    }
                )
                continue
            data = path.read_bytes()
            if path.is_absolute():
                sanitized = "_".join(path.parts[1:])
            else:
                sanitized = "_".join(path.parts)
            archive_name = f"extras/{sanitized}"
            extra = zipfile.ZipInfo(archive_name)
            extra.date_time = (1980, 1, 1, 0, 0, 0)
            extra.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(extra, data)
            extras.append(
                {
                    "requested": file_name,
                    "stored": archive_name,
                    "status": "included",
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "size_bytes": len(data),
                }
            )

    return {
        "schema_version": "sdetkit.forensics.bundle.v1",
        "bundle": str(output_path),
        "manifest": manifest,
    }


def _bundle_diff(from_bundle: Path, to_bundle: Path) -> dict[str, Any]:
    with (
        zipfile.ZipFile(from_bundle, "r") as left_zip,
        zipfile.ZipFile(to_bundle, "r") as right_zip,
    ):
        left_names = set(left_zip.namelist())
        right_names = set(right_zip.namelist())
        added = sorted(right_names - left_names)
        removed = sorted(left_names - right_names)
        shared = sorted(left_names & right_names)
        changed = sorted(
            name
            for name in shared
            if hashlib.sha256(left_zip.read(name)).hexdigest()
            != hashlib.sha256(right_zip.read(name)).hexdigest()
        )

    return {
        "schema_version": "sdetkit.forensics.bundle-diff.v1",
        "from_bundle": str(from_bundle),
        "to_bundle": str(to_bundle),
        "added": added,
        "removed": removed,
        "changed": changed,
        "summary": {
            "added": len(added),
            "removed": len(removed),
            "changed": len(changed),
            "passed": not (added or removed or changed),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sdetkit forensics", description="Failure Forensics Kit")
    sub = parser.add_subparsers(dest="cmd", required=True)

    compare = sub.add_parser("compare", help="Compare two run records")
    compare.add_argument("--from", dest="from_run", required=True)
    compare.add_argument("--to", dest="to_run", required=True)
    compare.add_argument("--fail-on", choices=["none", "warn", "error"], default="none")

    bundle = sub.add_parser("bundle", help="Create deterministic repro/evidence bundle")
    bundle.add_argument("--run", required=True)
    bundle.add_argument("--output", required=True)
    bundle.add_argument("--include", nargs="*", default=[])

    bundle_diff = sub.add_parser("bundle-diff", help="Diff two forensics bundles")
    bundle_diff.add_argument("--from-bundle", required=True)
    bundle_diff.add_argument("--to-bundle", required=True)

    ns = parser.parse_args(argv)
    try:
        if ns.cmd == "compare":
            payload = _compare(
                safe_path(Path.cwd(), ns.from_run, allow_absolute=True),
                safe_path(Path.cwd(), ns.to_run, allow_absolute=True),
            )
            sys.stdout.write(canonical_json_dumps(payload))
            new_error = [x for x in payload.get("new", []) if x.get("severity") == "error"]
            new_warn = [x for x in payload.get("new", []) if x.get("severity") in {"warn", "error"}]
            if ns.fail_on == "error" and new_error:
                return 1
            if ns.fail_on == "warn" and new_warn:
                return 1
            return 0

        if ns.cmd == "bundle-diff":
            payload = _bundle_diff(
                safe_path(Path.cwd(), ns.from_bundle, allow_absolute=True),
                safe_path(Path.cwd(), ns.to_bundle, allow_absolute=True),
            )
            sys.stdout.write(canonical_json_dumps(payload))
            return 0 if payload["summary"]["passed"] else 1

        payload = _bundle(
            safe_path(Path.cwd(), ns.run, allow_absolute=True),
            safe_path(Path.cwd(), ns.output, allow_absolute=True),
            list(ns.include),
        )
        sys.stdout.write(canonical_json_dumps(payload))
        return 0
    except (ValueError, OSError, SecurityError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"forensics error: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
