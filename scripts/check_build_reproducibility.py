#!/usr/bin/env python3
"""Compare two distribution directories without treating errors as passing evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
import zipfile
from pathlib import Path


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def members(path: Path) -> dict[str, str]:
    """Read member content only, never extract archives onto the filesystem."""
    if path.name.endswith(".whl"):
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                raise ValueError("duplicate archive member")
            return {name: digest(archive.read(name)) for name in names if not name.endswith("/")}
    with tarfile.open(path, "r:gz") as archive:
        entries = archive.getmembers()
        names = [entry.name for entry in entries]
        if len(names) != len(set(names)):
            raise ValueError("duplicate archive member")
        result = {}
        for entry in entries:
            if entry.isfile():
                stream = archive.extractfile(entry)
                if stream is None:
                    raise ValueError("unreadable archive member")
                with stream:
                    result[entry.name] = digest(stream.read())
            elif not entry.isdir():
                raise ValueError("unsupported archive member type")
        return result


def compare(left: Path, right: Path) -> dict:
    def inventory(directory: Path) -> dict[str, Path]:
        if not directory.is_dir():
            raise ValueError("distribution directory does not exist")
        return {
            path.name: path
            for path in directory.iterdir()
            if path.is_file() and (path.name.endswith(".whl") or path.name.endswith(".tar.gz"))
        }

    a, b = inventory(left), inventory(right)
    if not a or not b:
        raise ValueError("no distributions found")
    names = sorted(a.keys() | b.keys())
    artifacts = []
    for name in names:
        if name not in a or name not in b:
            artifacts.append({"name": name, "status": "missing", "byte_identical": False})
            continue
        left_hash, right_hash = digest(a[name].read_bytes()), digest(b[name].read_bytes())
        am, bm = members(a[name]), members(b[name])
        added = sorted(bm.keys() - am.keys())
        removed = sorted(am.keys() - bm.keys())
        changed = sorted(key for key in am.keys() & bm.keys() if am[key] != bm[key])
        artifacts.append(
            {
                "name": name,
                "status": "compared",
                "byte_identical": left_hash == right_hash,
                "left_sha256": left_hash,
                "right_sha256": right_hash,
                "member_content_identical": am == bm,
                "added_members": added,
                "removed_members": removed,
                "changed_members": changed,
                "note": "Equal member content is not proof of byte or metadata reproducibility.",
            }
        )
    return {
        "schema": "sdetkit.build_reproducibility.v1",
        "status": "completed",
        "report_only": True,
        "reproducible": all(item["byte_identical"] for item in artifacts),
        "artifacts": artifacts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--left", type=Path, required=True)
    parser.add_argument("--right", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = compare(args.left, args.right)
    except (OSError, EOFError, ValueError, tarfile.TarError, zipfile.BadZipFile) as error:
        report = {
            "schema": "sdetkit.build_reproducibility.v1",
            "status": "tool_error",
            "report_only": True,
            "reproducible": None,
            "error": str(error),
        }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
