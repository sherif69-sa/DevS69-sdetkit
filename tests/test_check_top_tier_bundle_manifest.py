from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_check_top_tier_bundle_manifest_on_generated_manifest(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "bundle"
    manifest = tmp_path / "manifest.json"
    out = tmp_path / "manifest-check.json"

    build_cmd = [
        sys.executable,
        "scripts/build_top_tier_reporting_bundle.py",
        "--input",
        "docs/artifacts/portfolio-input-sample-2026-04-17.jsonl",
        "--out-dir",
        str(bundle_dir),
        "--window-start",
        "2026-04-11",
        "--window-end",
        "2026-04-17",
        "--generated-at",
        "2026-04-17T10:00:00Z",
        "--manifest-out",
        str(manifest),
    ]
    subprocess.run(build_cmd, check=True)

    check_cmd = [
        sys.executable,
        "scripts/check_top_tier_bundle_manifest.py",
        "--manifest",
        str(manifest),
        "--out",
        str(out),
    ]
    subprocess.run(check_cmd, check=True)

    report = json.loads(out.read_text())
    assert report["ok"] is True
    assert report["checked_count"] == 4
    assert report["window"] == {"start": "2026-04-11", "end": "2026-04-17"}
