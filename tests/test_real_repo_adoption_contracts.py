from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPO_ROOT / "examples" / "adoption" / "real-repo"
GOLDEN_ROOT = REPO_ROOT / "artifacts" / "adoption" / "real-repo-golden"


def test_real_repo_fixture_has_canonical_structure() -> None:
    required_fixture_paths = (
        "pyproject.toml",
        "src/app/__init__.py",
        "src/app/main.py",
        "tests/test_main.py",
    )

    missing = [rel_path for rel_path in required_fixture_paths if not (FIXTURE_ROOT / rel_path).is_file()]
    assert not missing, f"missing canonical fixture files: {missing}"


def test_real_repo_golden_artifacts_exist() -> None:
    required_artifacts = ("gate-fast.json", "release-preflight.json", "doctor.json", "README.md")

    missing = [name for name in required_artifacts if not (GOLDEN_ROOT / name).is_file()]
    assert not missing, f"missing canonical golden artifacts: {missing}"


def test_real_repo_gate_artifacts_preserve_contract_keys() -> None:
    expected_profiles = {
        "gate-fast.json": "fast",
        "release-preflight.json": "release",
    }

    for artifact_name, expected_profile in expected_profiles.items():
        payload = json.loads((GOLDEN_ROOT / artifact_name).read_text(encoding="utf-8"))
        assert {"ok", "failed_steps", "profile", "steps"}.issubset(payload)
        assert isinstance(payload["ok"], bool)
        assert isinstance(payload["failed_steps"], list)
        assert payload["profile"] == expected_profile
        assert isinstance(payload["steps"], list)


def test_real_repo_doctor_artifact_preserves_contract_keys() -> None:
    payload = json.loads((GOLDEN_ROOT / "doctor.json").read_text(encoding="utf-8"))

    assert {"ok", "quality", "recommendations"}.issubset(payload)
    assert isinstance(payload["ok"], bool)
    assert isinstance(payload["quality"], dict)
    assert "failed_check_ids" in payload["quality"]
    assert isinstance(payload["quality"]["failed_check_ids"], list)
    assert isinstance(payload["recommendations"], list)
