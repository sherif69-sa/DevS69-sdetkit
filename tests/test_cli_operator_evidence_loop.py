from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _failure_bundle(path: Path) -> Path:
    return _write_json(
        path,
        {
            "schema_version": "sdetkit.adaptive.failure_bundle.v1",
            "status": "review_required",
            "review_first": True,
            "safe_to_auto_fix": False,
            "primary_diagnosis_code": "PACKAGE_INSTALL_FAILURE",
            "primary_diagnosis_title": "Dependency resolver failed",
            "diagnosis_count": 1,
            "diagnosis_codes": ["PACKAGE_INSTALL_FAILURE"],
            "diagnoses": [
                {
                    "code": "PACKAGE_INSTALL_FAILURE",
                    "title": "Dependency resolver failed",
                    "diagnosis": "pip could not resolve constraints before proof.",
                    "severity": "high",
                    "confidence": "high",
                    "affected_files": ["constraints-ci.txt", "requirements-test.txt"],
                    "recommended_fix": ["Reproduce the exact install lane."],
                    "proof_commands": [
                        "python -m pip install -c constraints-ci.txt -r requirements-test.txt -e ."
                    ],
                }
            ],
        },
    )


def test_root_help_exposes_operator_loop(capsys) -> None:
    try:
        cli.main(["--help"])
    except SystemExit as exc:
        assert exc.code == 0

    out = capsys.readouterr().out
    assert "operator-loop" in out
    assert "operator evidence loop" in out


def test_operator_loop_help_forwards_to_operator_loop_module(capsys) -> None:
    try:
        cli.main(["operator-loop", "--help"])
    except SystemExit as exc:
        assert exc.code == 0

    out = capsys.readouterr().out
    assert "usage: sdetkit operator-loop" in out
    assert "--failure-bundle" in out
    assert "--quality-log" in out


def test_operator_loop_cli_command_builds_operator_artifacts(tmp_path: Path, capsys) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    quality = _write(
        tmp_path / "quality.log",
        "quality.sh cov passed\nTotal coverage: 96.69%\n",
    )
    failure_bundle = _failure_bundle(tmp_path / "failure-bundle.json")
    out_dir = tmp_path / "operator-loop"

    rc = cli.main(
        [
            "operator-loop",
            "--repo",
            str(repo),
            "--out-dir",
            str(out_dir),
            "--quality-log",
            str(quality),
            "--quality-outcome",
            "success",
            "--failure-bundle",
            str(failure_bundle),
            "--format",
            "json",
        ]
    )

    assert rc == 0
    stdout = capsys.readouterr().out
    assert '"schema_version": ' in stdout
    assert '"classification": ' in stdout

    persisted = json.loads((out_dir / "operator-loop.json").read_text(encoding="utf-8"))
    assert persisted["schema_version"] == "sdetkit.operator.evidence_loop.v1"
    assert persisted["classification"] == "review_required"
    assert persisted["advisory_only"] is True
    assert (out_dir / "operator-loop.json").exists()
    assert (out_dir / "operator-loop.md").exists()
    assert (out_dir / "pr-quality-comment.md").exists()
