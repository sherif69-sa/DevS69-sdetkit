#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.pypi_release_verification.v1"


def compare_distribution_hashes(
    manifest: dict[str, Any],
    pypi_payload: dict[str, Any],
) -> dict[str, object]:
    expected = {
        str(item["name"]): str(item["sha256"])
        for item in manifest.get("files", [])
        if isinstance(item, dict)
    }
    actual = {
        str(item["filename"]): str(item["digests"]["sha256"])
        for item in pypi_payload.get("urls", [])
        if isinstance(item, dict) and isinstance(item.get("digests"), dict)
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": bool(expected) and actual == expected,
        "expected": expected,
        "actual": actual,
        "missing": sorted(set(expected) - set(actual)),
        "unexpected": sorted(set(actual) - set(expected)),
        "digest_mismatches": sorted(
            name for name in set(expected) & set(actual) if expected[name] != actual[name]
        ),
    }


def fetch_sdetkit_release(
    version: str,
    *,
    attempts: int = 12,
    delay_seconds: float = 10.0,
) -> dict[str, Any]:
    url = f"https://pypi.org/pypi/sdetkit/{version}/json"
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(url, timeout=15) as response:
                payload = json.load(response)
            if not isinstance(payload, dict):
                raise ValueError("PyPI response must be a JSON object")
            return payload
        except urllib.error.HTTPError as error:
            if error.code != 404 or attempt == attempts:
                raise
            print(f"PyPI propagation attempt {attempt}/{attempts} did not resolve the release yet")
            time.sleep(delay_seconds)
    raise RuntimeError("PyPI release lookup exhausted without a response")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify PyPI files against a release manifest")
    parser.add_argument("--version", required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    result = compare_distribution_hashes(manifest, fetch_sdetkit_release(args.version))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0 if result["ok"] is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
