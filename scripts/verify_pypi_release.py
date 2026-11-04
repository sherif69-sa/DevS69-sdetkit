#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.pypi_release_verification.v1"
# Right after an upload, PyPI's JSON API and its simple index can each lag: a release that is
# not found yet, or that lists only some of its files. Wait up to 5 minutes for both.
ATTEMPTS = 20
DELAY_SECONDS = 15.0


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
    attempts: int = ATTEMPTS,
    delay_seconds: float = DELAY_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
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
            # Not there yet (404), or PyPI itself failing (5xx): ask again. Anything else is final.
            if (error.code != 404 and error.code < 500) or attempt == attempts:
                raise
            why = (
                "did not resolve the release yet" if error.code == 404 else f"returned {error.code}"
            )
        except urllib.error.URLError as error:
            if attempt == attempts:
                raise
            why = f"was not reachable ({error.reason})"
        print(f"PyPI propagation attempt {attempt}/{attempts}: PyPI {why}")
        sleep(delay_seconds)
    raise RuntimeError("PyPI release lookup exhausted without a response")


def verify_release(
    manifest: dict[str, Any],
    fetch: Callable[[], dict[str, Any]],
    *,
    attempts: int = ATTEMPTS,
    delay_seconds: float = DELAY_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, object]:
    """Compare PyPI's files with the manifest until PyPI lists all of them. A file whose digest
    differs, or a file the manifest does not have, is not a delay: that fails at once."""

    for attempt in range(1, attempts + 1):
        result = compare_distribution_hashes(manifest, fetch())
        if result["ok"] or result["digest_mismatches"] or result["unexpected"]:
            return result
        if attempt == attempts:
            return result
        print(
            f"PyPI propagation attempt {attempt}/{attempts}: not listed yet: "
            + ", ".join(result["missing"])  # type: ignore[arg-type]
        )
        sleep(delay_seconds)
    raise RuntimeError("unreachable")


def install_from_index(
    version: str,
    *,
    attempts: int = ATTEMPTS,
    delay_seconds: float = DELAY_SECONDS,
    run: Callable[[list[str]], int] = lambda argv: subprocess.run(argv, check=False).returncode,
    sleep: Callable[[float], None] = time.sleep,
) -> bool:
    """Install `sdetkit==version` from PyPI's simple index, as a user would, waiting for the
    index to serve it."""

    argv = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--no-cache-dir",
        "--index-url",
        "https://pypi.org/simple/",
        f"sdetkit=={version}",
    ]
    for attempt in range(1, attempts + 1):
        if run(argv) == 0:
            return True
        if attempt < attempts:
            print(f"PyPI's index does not serve sdetkit=={version} yet ({attempt}/{attempts})")
            sleep(delay_seconds)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify PyPI files against a release manifest")
    parser.add_argument("--version", required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--install",
        action="store_true",
        help="Then install the release from PyPI's simple index, as a user would",
    )
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    result = verify_release(manifest, lambda: fetch_sdetkit_release(args.version))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    if result["ok"] is not True:
        return 1
    if args.install and not install_from_index(args.version):
        print(f"sdetkit=={args.version} did not install from PyPI's index", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
