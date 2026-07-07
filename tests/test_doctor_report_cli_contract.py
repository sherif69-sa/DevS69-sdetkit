from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


def _run_sdetkit(
    repo_root: Path, cwd: Path, *args: str
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root / "src")
    return subprocess.run(
        [sys.executable, "-m", "sdetkit", *args],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _write_failure_vector_bundle(path: Path) -> None:
    payload = {
        "schema_version": "sdetkit.failure_vector.bundle.v1",
        "vector_schema_version": "sdetkit.failure_vector.v1",
        "environment": "ci",
        "failure_vector_count": 1,
        "summary": {
            "by_failure_class": {"format": 1},
            "by_risk": {"low": 1},
            "safe_fix_candidate_count": 1,
            "review_first_count": 0,
        },
        "failure_vectors": [
            {
                "check": "ruff_format",
                "failure_class": "format",
                "failure_type": "format",
                "risk": "low",
                "headline_signal": "ruff format would reformat one file",
                "local_repro_command": (
                    "python -m ruff format --check src/sdetkit/cli/__init__.py"
                ),
                "safe_fix_candidate": True,
                "safe_fix_allowed": False,
            }
        ],
    }
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def test_sdetkit_doctor_report_contract_json_is_review_first(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]

    proc = _run_sdetkit(
        repo_root,
        tmp_path,
        "doctor",
        "--report-contract",
        "--format",
        "json",
        "--no-workspace",
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["schema_version"] == "sdetkit.doctor_report.v1"
    assert payload["status"] == "green"
    assert payload["safety_decision"]["review_first"] is True
    assert payload["safety_decision"]["automation_allowed"] is False
    assert payload["safety_decision"]["patch_application_allowed"] is False
    assert payload["safety_decision"]["merge_authorized"] is False
    assert payload["proof_commands"] == ["python -m sdetkit doctor --all --format json"]


def test_sdetkit_doctor_report_contract_markdown_respects_out_path(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    out_path = tmp_path / "doctor-report.md"

    proc = _run_sdetkit(
        repo_root,
        tmp_path,
        "doctor",
        "--report-contract",
        "--format",
        "md",
        "--ci",
        "--out",
        str(out_path),
        "--no-workspace",
    )

    assert proc.returncode == 2
    assert proc.stderr == ""
    assert proc.stdout.startswith("# SDETKit Doctor Report")
    assert "## Safety Decision" in proc.stdout
    assert "automation_allowed: `false`" in proc.stdout
    assert "patch_application_allowed: `false`" in proc.stdout
    assert "merge_authorized: `false`" in proc.stdout
    assert out_path.read_text(encoding="utf-8") == proc.stdout


def test_sdetkit_doctor_report_contract_writes_artifact_bundle(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    artifact_dir = tmp_path / "doctor-artifacts"

    proc = _run_sdetkit(
        repo_root,
        tmp_path,
        "doctor",
        "--report-contract",
        "--format",
        "json",
        "--report-artifact-dir",
        str(artifact_dir),
        "--no-workspace",
    )

    assert proc.returncode == 0, proc.stderr
    json_path = artifact_dir / "doctor-report.json"
    markdown_path = artifact_dir / "doctor-report.md"
    manifest_path = artifact_dir / "doctor-report-manifest.json"
    assert json_path.read_text(encoding="utf-8") == proc.stdout
    assert markdown_path.read_text(encoding="utf-8").startswith(
        "# SDETKit Doctor Report"
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest == {
        "outputs": {
            "json": {
                "path": "doctor-report.json",
                "sha256": _sha256_text(json_path.read_text(encoding="utf-8")),
            },
            "markdown": {
                "path": "doctor-report.md",
                "sha256": _sha256_text(markdown_path.read_text(encoding="utf-8")),
            },
        },
        "report_schema_version": "sdetkit.doctor_report.v1",
        "schema_version": "sdetkit.doctor_report_artifact_bundle.v1",
        "status": "green",
    }


def test_sdetkit_doctor_report_contract_loads_failure_vector_bundle(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    bundle_path = tmp_path / "failure-vector.json"
    artifact_dir = tmp_path / "doctor-artifacts"
    _write_failure_vector_bundle(bundle_path)

    proc = _run_sdetkit(
        repo_root,
        tmp_path,
        "doctor",
        "--report-contract",
        "--format",
        "json",
        "--failure-vector-bundle",
        str(bundle_path),
        "--report-artifact-dir",
        str(artifact_dir),
        "--no-workspace",
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["status"] == "review_required"
    assert payload["summary"]["failure_vector_count"] == 1
    assert payload["failure_vector_evidence"]["available"] is True
    assert payload["failure_vector_evidence"]["failure_vector_count"] == 1
    assert payload["failure_vector_evidence"]["top_failure"] == {
        "check": "ruff_format",
        "failure_type": "format",
        "headline_signal": "ruff format would reformat one file",
        "local_repro_command": (
            "python -m ruff format --check src/sdetkit/cli/__init__.py"
        ),
        "risk": "low",
    }
    assert payload["safety_decision"]["automation_allowed"] is False
    assert payload["safety_decision"]["patch_application_allowed"] is False
    assert payload["safety_decision"]["merge_authorized"] is False

    markdown = (artifact_dir / "doctor-report.md").read_text(encoding="utf-8")
    assert "## Failure Vector Evidence" in markdown
    assert "failure_vector_count: `1`" in markdown
    assert "top_failure_type: `format`" in markdown

    manifest = json.loads(
        (artifact_dir / "doctor-report-manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["status"] == "review_required"
