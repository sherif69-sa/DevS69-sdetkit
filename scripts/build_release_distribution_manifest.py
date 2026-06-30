#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

TAG_RE = re.compile(r"^v\d+\.\d+\.\d+$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SCHEMA_VERSION = "sdetkit.release_distribution_manifest.v1"


def build_manifest(
    *,
    dist_dir: Path,
    tag: str,
    version: str,
    source_sha: str,
) -> dict[str, object]:
    if not TAG_RE.fullmatch(tag):
        raise ValueError("release tag must match vX.Y.Z")
    if tag.removeprefix("v") != version:
        raise ValueError("release tag and package version do not match")
    if not SHA_RE.fullmatch(source_sha):
        raise ValueError("source SHA must be a 40-character lowercase hexadecimal value")

    files = [
        {
            "name": path.name,
            "size_bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in sorted(dist_dir.iterdir())
        if path.is_file()
    ]
    if not any(str(item["name"]).endswith(".whl") for item in files):
        raise ValueError("release build did not produce a wheel")
    if not any(str(item["name"]).endswith(".tar.gz") for item in files):
        raise ValueError("release build did not produce an sdist")

    return {
        "schema_version": SCHEMA_VERSION,
        "source_sha": source_sha,
        "tag": tag,
        "version": version,
        "files": files,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the release distribution manifest")
    parser.add_argument("--dist-dir", type=Path, default=Path("dist"))
    parser.add_argument("--tag", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    payload = build_manifest(
        dist_dir=args.dist_dir,
        tag=args.tag,
        version=args.version,
        source_sha=args.source_sha,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
