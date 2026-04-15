#!/usr/bin/env python3
"""Validate top-tier bundle manifest file integrity and required fields."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


_REQUIRED_ARTIFACT_KEYS = (
    "portfolio_scorecard",
    "kpi_weekly",
    "kpi_contract_check",
    "top_tier_contract_check",
)


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _validate(manifest: dict[str, Any]) -> dict[str, Any]:
    _expect(manifest.get("ok") is True, "manifest.ok must be true")
    _expect(isinstance(manifest.get("window"), dict), "manifest.window must be object")

    artifacts = manifest.get("artifacts")
    _expect(isinstance(artifacts, dict), "manifest.artifacts must be object")

    checked = []
    for key in _REQUIRED_ARTIFACT_KEYS:
        _expect(key in artifacts, f"missing artifact entry: {key}")
        entry = artifacts[key]
        _expect(isinstance(entry, dict), f"artifact entry {key} must be object")

        path = Path(str(entry.get("path", "")))
        _expect(path.is_file(), f"artifact path missing: {path}")

        expected = str(entry.get("sha256", ""))
        actual = _sha256(path)
        _expect(expected == actual, f"sha256 mismatch for {key}: expected {expected}, got {actual}")
        checked.append({"key": key, "path": str(path), "sha256": actual})

    return {
        "ok": True,
        "checked_count": len(checked),
        "window": manifest.get("window"),
        "artifacts": checked,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Check top-tier bundle manifest")
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out", default="", help="Optional JSON report output path")
    args = ap.parse_args()

    manifest = json.loads(Path(args.manifest).read_text())
    report = _validate(manifest)

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2) + "\n")

    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
