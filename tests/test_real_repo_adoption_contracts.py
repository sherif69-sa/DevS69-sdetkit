from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPO_ROOT / "examples" / "adoption" / "real-repo"
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from real_repo_adoption_projection import (  # noqa: E402
    build_lane_proof_summary,
    project_doctor_contract,
    project_gate_contract,
    project_release_contract,
)

GOLDEN_ROOT = REPO_ROOT / "artifacts" / "adoption" / "real-repo-golden"
CANONICAL_REPLAY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "adoption-real-repo-canonical.yml"
CANONICAL_FAST_COMMAND = "python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json"
CANONICAL_RELEASE_COMMAND = "python -m sdetkit gate release --format json --out build/release-preflight.json"
CANONICAL_DOCTOR_COMMAND = "python -m sdetkit doctor --format json --out build/doctor.json"
CANONICAL_SUMMARY_COMMAND = "python ../../../scripts/real_repo_adoption_projection.py --fixture-root . --repo-root ../../.. --build-dir build --out build/adoption-proof-summary.json"
NON_CANONICAL_RELEASE_STABLE_JSON = (
    "python -m sdetkit gate release --format json --stable-json --out build/release-preflight.json"
)


def test_real_repo_fixture_has_canonical_structure() -> None:
    required_fixture_paths = (
        "pyproject.toml",
        "src/app/__init__.py",
        "src/app/main.py",
        "tests/test_main.py",
        "README.md",
    )

    missing = [rel_path for rel_path in required_fixture_paths if not (FIXTURE_ROOT / rel_path).is_file()]
    assert not missing, f"missing canonical fixture files: {missing}"


def test_real_repo_golden_artifacts_exist() -> None:
    required_artifacts = (
        "gate-fast.json",
        "release-preflight.json",
        "doctor.json",
        "gate-fast.rc",
        "release-preflight.rc",
        "doctor.rc",
        "adoption-proof-summary.json",
        "README.md",
    )

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


def _run_fixture_command(args: list[str], out_path: Path, rc_path: Path) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "src")

    proc = subprocess.run(
        [sys.executable, "-m", "sdetkit", *args, "--format", "json", "--out", str(out_path)],
        cwd=FIXTURE_ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    rc_path.write_text(f"{proc.returncode}\n", encoding="utf-8")
    assert out_path.is_file(), (
        f"expected fixture command to emit {out_path.name} (rc={proc.returncode})\n"
        f"stdout:\n{proc.stdout}\n"
        f"stderr:\n{proc.stderr}"
    )
    return json.loads(out_path.read_text(encoding="utf-8"))


def test_real_repo_fixture_output_matches_golden_contract_projection(tmp_path: Path) -> None:
    actual_gate = _run_fixture_command(["gate", "fast", "--stable-json"], tmp_path / "gate-fast.json", tmp_path / "gate-fast.rc")
    actual_release = _run_fixture_command(["gate", "release"], tmp_path / "release-preflight.json", tmp_path / "release-preflight.rc")
    actual_doctor = _run_fixture_command(["doctor"], tmp_path / "doctor.json", tmp_path / "doctor.rc")

    golden_gate = json.loads((GOLDEN_ROOT / "gate-fast.json").read_text(encoding="utf-8"))
    golden_release = json.loads((GOLDEN_ROOT / "release-preflight.json").read_text(encoding="utf-8"))
    golden_doctor = json.loads((GOLDEN_ROOT / "doctor.json").read_text(encoding="utf-8"))

    assert project_gate_contract(actual_gate, fixture_root=FIXTURE_ROOT, repo_root=REPO_ROOT) == project_gate_contract(golden_gate, fixture_root=FIXTURE_ROOT, repo_root=REPO_ROOT)
    assert project_release_contract(actual_release, fixture_root=FIXTURE_ROOT, repo_root=REPO_ROOT) == project_release_contract(golden_release, fixture_root=FIXTURE_ROOT, repo_root=REPO_ROOT)
    assert project_doctor_contract(actual_doctor) == project_doctor_contract(golden_doctor)


def test_real_repo_summary_matches_golden_projection(tmp_path: Path) -> None:
    _run_fixture_command(["gate", "fast", "--stable-json"], tmp_path / "gate-fast.json", tmp_path / "gate-fast.rc")
    _run_fixture_command(["gate", "release"], tmp_path / "release-preflight.json", tmp_path / "release-preflight.rc")
    _run_fixture_command(["doctor"], tmp_path / "doctor.json", tmp_path / "doctor.rc")

    generated = build_lane_proof_summary(fixture_root=FIXTURE_ROOT, repo_root=REPO_ROOT, build_dir=tmp_path)
    golden = json.loads((GOLDEN_ROOT / "adoption-proof-summary.json").read_text(encoding="utf-8"))
    assert generated == golden


def test_canonical_replay_workflow_contract_is_stable() -> None:
    assert CANONICAL_REPLAY_WORKFLOW.is_file(), "missing canonical replay workflow"

    workflow = yaml.safe_load(CANONICAL_REPLAY_WORKFLOW.read_text(encoding="utf-8"))
    replay_steps = workflow["jobs"]["replay"]["steps"]
    run_scripts = "\n".join(step.get("run", "") for step in replay_steps if isinstance(step, dict))

    expected_commands = (
        "python scripts/regenerate_real_repo_adoption_goldens.py --check",
        "python -m sdetkit gate fast",
        "python -m sdetkit gate release",
        "python -m sdetkit doctor",
        "python ../../../scripts/real_repo_adoption_projection.py",
    )
    for cmd in expected_commands:
        assert cmd in run_scripts, f"workflow drifted: missing canonical command `{cmd}`"

    expected_build_files = (
        "build/gate-fast.json",
        "build/release-preflight.json",
        "build/doctor.json",
        "build/gate-fast.rc",
        "build/release-preflight.rc",
        "build/doctor.rc",
        "build/adoption-proof-summary.json",
    )
    for rel_path in expected_build_files:
        assert rel_path in run_scripts, f"workflow drifted: missing output write `{rel_path}`"

    upload_step = next(
        (
            step
            for step in replay_steps
            if isinstance(step, dict) and str(step.get("uses", "")).startswith("actions/upload-artifact@")
        ),
        None,
    )
    assert upload_step is not None, "workflow drifted: missing artifact upload step"
    upload_with = upload_step.get("with", {})
    assert upload_with.get("name") == "adoption-real-repo-canonical"

    upload_paths = str(upload_with.get("path", ""))
    for rel_path in expected_build_files:
        assert (
            f"examples/adoption/real-repo/{rel_path}" in upload_paths
        ), f"workflow drifted: missing uploaded artifact path for `{rel_path}`"


def test_real_repo_proof_docs_and_goldens_match_canonical_command_contract() -> None:
    real_repo_doc = (REPO_ROOT / "docs" / "real-repo-adoption.md").read_text(encoding="utf-8")
    ci_walkthrough_doc = (REPO_ROOT / "docs" / "ci-artifact-walkthrough.md").read_text(encoding="utf-8")
    fixture_readme = (FIXTURE_ROOT / "README.md").read_text(encoding="utf-8")
    golden_readme = (GOLDEN_ROOT / "README.md").read_text(encoding="utf-8")

    for text in (real_repo_doc, fixture_readme, golden_readme):
        assert CANONICAL_FAST_COMMAND in text
        assert CANONICAL_RELEASE_COMMAND in text
        assert CANONICAL_DOCTOR_COMMAND in text
        assert CANONICAL_SUMMARY_COMMAND in text
        assert NON_CANONICAL_RELEASE_STABLE_JSON not in text

    assert "adoption-real-repo-canonical" in ci_walkthrough_doc
    assert "build/adoption-proof-summary.json" in ci_walkthrough_doc
    assert "build/adoption-proof-summary.json" in real_repo_doc


def test_canonical_rc_truth_model_matches_goldens() -> None:
    expected = {
        "gate-fast.rc": "2",
        "release-preflight.rc": "2",
        "doctor.rc": "0",
    }
    for name, value in expected.items():
        assert (GOLDEN_ROOT / name).read_text(encoding="utf-8").strip() == value
