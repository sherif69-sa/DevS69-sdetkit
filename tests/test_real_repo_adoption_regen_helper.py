from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPO_ROOT / "examples" / "adoption" / "real-repo"
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from real_repo_adoption_projection import (  # noqa: E402
    CANONICAL_LANE_SPEC,
    build_lane_proof_summary,
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
        "adoption-proof-summary.json",
        "--check",
    )

    for token in expected_tokens:
        assert token in script_text, f"regeneration helper drifted: missing `{token}`"

    artifacts = {spec["artifact"] for spec in CANONICAL_LANE_SPEC}
    rc_files = {spec["rc_file"] for spec in CANONICAL_LANE_SPEC}
    assert artifacts == {"gate-fast.json", "release-preflight.json", "doctor.json"}
    assert rc_files == {"gate-fast.rc", "release-preflight.rc", "doctor.rc"}
    gate_fast_spec = next(spec for spec in CANONICAL_LANE_SPEC if spec["id"] == "gate_fast")
    assert "--stable-json" in gate_fast_spec["args"]


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
            f"/home/runner/work/{REPO_ROOT.name}/{REPO_ROOT.name}/scripts/run.py",
        ],
        fixture_root=FIXTURE_ROOT,
        repo_root=REPO_ROOT,
    )
    assert normalized == [
        "<repo>",
        "<repo>",
        "python",
        "<repo>/subdir",
        "<repo>/scripts/run.py",
        "<repo>/scripts/run.py",
    ]


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


def test_projection_helper_projects_gate_contract_with_stable_ordering() -> None:
    payload = {
        "ok": False,
        "failed_steps": ["pytest", "doctor"],
        "profile": "fast",
        "steps": [
            {"id": "pytest", "ok": False, "rc": 4, "cmd": ["/tmp/venv/bin/python", "-m", "pytest"]},
            {
                "id": "doctor",
                "ok": False,
                "rc": 2,
                "cmd": [
                    f"/home/runner/work/{REPO_ROOT.name}/{REPO_ROOT.name}/.venv/bin/python",
                    "-m",
                    "sdetkit",
                    "doctor",
                ],
            },
        ],
    }
    projected = project_contract_for_artifact(
        "gate-fast.json",
        payload,
        fixture_root=FIXTURE_ROOT,
        repo_root=REPO_ROOT,
    )
    assert projected == {
        "ok": False,
        "failed_steps": ["doctor", "pytest"],
        "profile": "fast",
        "steps": [
            {"id": "doctor", "ok": False, "rc": 2, "cmd": ["python", "-m", "sdetkit", "doctor"]},
            {"id": "pytest", "ok": False, "rc": 4, "cmd": ["python", "-m", "pytest"]},
        ],
    }


def test_projection_helper_canonical_truth_model_is_explicit() -> None:
    expected = {
        "gate_fast": (2, False),
        "gate_release": (2, False),
        "doctor": (0, True),
    }
    observed = {
        spec["id"]: (spec["expected_rc"], spec["expected_ok"]) for spec in CANONICAL_LANE_SPEC
    }
    assert observed == expected


def test_projection_summary_marks_all_expectations_met_for_current_golden_set() -> None:
    golden_dir = REPO_ROOT / "artifacts" / "adoption" / "real-repo-golden"
    generated = build_lane_proof_summary(
        fixture_root=FIXTURE_ROOT, repo_root=REPO_ROOT, build_dir=golden_dir
    )
    saved = json.loads((golden_dir / "adoption-proof-summary.json").read_text(encoding="utf-8"))
    assert generated == saved
    assert saved["all_expectations_met"] is True
