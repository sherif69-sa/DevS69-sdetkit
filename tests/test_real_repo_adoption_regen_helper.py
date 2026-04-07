from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPO_ROOT / "examples" / "adoption" / "real-repo"
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from real_repo_adoption_projection import (
    normalize_cmd,
    project_contract_for_artifact,
)
SCRIPT_PATH = REPO_ROOT / "scripts" / "regenerate_real_repo_adoption_goldens.py"


def test_regen_helper_script_targets_canonical_paths_and_artifacts() -> None:
    assert SCRIPT_PATH.is_file(), "missing real-repo golden regeneration helper"

    script_text = SCRIPT_PATH.read_text(encoding="utf-8")

    expected_tokens = (
        "examples",
        "adoption",
        "real-repo",
        "artifacts",
        "real-repo-golden",
        "build/gate-fast.json",
        "build/release-preflight.json",
        "build/doctor.json",
        "gate-fast.json",
        "release-preflight.json",
        "doctor.json",
        "--stable-json",
        "--check",
    )

    for token in expected_tokens:
        assert token in script_text, f"regeneration helper drifted: missing `{token}`"


def test_regen_helper_check_mode_succeeds_when_goldens_match() -> None:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--check"],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, (
        "expected --check to succeed when canonical fixture output matches checked-in goldens\n"
        f"stdout:\n{proc.stdout}\n"
        f"stderr:\n{proc.stderr}"
    )


def test_projection_helper_normalizes_repo_paths_and_python_binary() -> None:
    normalized = normalize_cmd(
        [
            str(FIXTURE_ROOT),
            str(REPO_ROOT),
            "/tmp/venv/bin/python",
            f"{FIXTURE_ROOT}/subdir",
            f"{REPO_ROOT}/scripts/run.py",
        ],
        fixture_root=FIXTURE_ROOT,
        repo_root=REPO_ROOT,
    )
    assert normalized == ["<repo>", "<repo>", "python", "<repo>/subdir", "<repo>/scripts/run.py"]


def test_projection_helper_projects_doctor_contract_with_sorted_failed_checks() -> None:
    payload = {
        "ok": False,
        "quality": {"failed_check_ids": ["b", "a"], "score": 91},
        "recommendations": [{"id": "fix-1"}],
        "noise": "ignored",
    }

    projected = project_contract_for_artifact(
        "doctor.json",
        payload,
        fixture_root=FIXTURE_ROOT,
        repo_root=REPO_ROOT,
    )

    assert projected == {
        "ok": False,
        "quality": {"failed_check_ids": ["a", "b"], "score": 91},
        "recommendations": [{"id": "fix-1"}],
    }
