from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_build_first_proof_ops_bundle(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "first-proof"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "first-proof-summary.json").write_text(
        json.dumps({"ok": True, "failed_steps": [], "steps": [{"name": "doctor", "returncode": 0}]}),
        encoding="utf-8",
    )
    (artifact_dir / "first-proof-learning-rollup.json").write_text("{}\n", encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "scripts/build_first_proof_ops_bundle.py",
            "--artifact-dir",
            str(artifact_dir),
            "--format",
            "json",
        ],
        check=True,
    )

    assert (artifact_dir / "health-score.json").exists()
    assert (artifact_dir / "doctor-remediate.json").exists()
    assert (artifact_dir / "artifact-freshness.json").exists()
    assert (artifact_dir / "ops-bundle-manifest.json").exists()
