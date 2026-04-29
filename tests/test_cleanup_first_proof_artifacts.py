from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path


def test_cleanup_first_proof_artifacts_dry_run_and_delete(tmp_path: Path) -> None:
    artifact = tmp_path / "first-proof"
    artifact.mkdir(parents=True)
    old_file = artifact / "old.json"
    new_file = artifact / "new.json"
    old_file.write_text("{}", encoding="utf-8")
    new_file.write_text("{}", encoding="utf-8")

    old_ts = time.time() - (10 * 24 * 3600)
    os.utime(old_file, (old_ts, old_ts))

    out = artifact / "cleanup.json"
    subprocess.run(
        [
            sys.executable,
            "scripts/cleanup_first_proof_artifacts.py",
            "--artifact-dir",
            str(artifact),
            "--ttl-hours",
            "24",
            "--dry-run",
            "--out",
            str(out),
            "--format",
            "json",
        ],
        check=True,
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["deleted_count"] >= 1
    assert old_file.exists()

    subprocess.run(
        [
            sys.executable,
            "scripts/cleanup_first_proof_artifacts.py",
            "--artifact-dir",
            str(artifact),
            "--ttl-hours",
            "24",
            "--out",
            str(out),
        ],
        check=True,
    )
    assert not old_file.exists()
    assert new_file.exists()
