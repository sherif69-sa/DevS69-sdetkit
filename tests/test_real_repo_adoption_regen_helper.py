from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
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
    )

    for token in expected_tokens:
        assert token in script_text, f"regeneration helper drifted: missing `{token}`"
