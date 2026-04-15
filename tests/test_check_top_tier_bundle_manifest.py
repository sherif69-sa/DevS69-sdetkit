from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_check_top_tier_bundle_manifest_on_sample_manifest(tmp_path: Path) -> None:
    manifest = Path("docs/artifacts/top-tier-bundle-manifest-2026-04-17.json")
    out = tmp_path / "manifest-check.json"

    cmd = [
        sys.executable,
        "scripts/check_top_tier_bundle_manifest.py",
        "--manifest",
        str(manifest),
        "--out",
        str(out),
    ]
    subprocess.run(cmd, check=True)

    report = json.loads(out.read_text())
    assert report["ok"] is True
    assert report["checked_count"] == 4
    assert report["window"] == {"start": "2026-04-11", "end": "2026-04-17"}
