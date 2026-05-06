from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from sdetkit import investigate
from sdetkit.investigation_evidence import build_investigation_evidence


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = "src"
    return env


def test_build_investigation_evidence_writes_expected_files(tmp_path):
    out_dir = tmp_path / "build" / "investigate" / "netclient"

    payload = build_investigation_evidence(
        "MISSING_PUBLIC_API_PARITY",
        "netclient",
        out_dir,
        root=tmp_path,
    )

    assert payload["schema_version"] == "sdetkit.investigation.evidence.v1"
    assert payload["diagnostic_only"] is True
    assert payload["automation_allowed"] is False
    assert payload["safe_to_auto_fix"] is False
    assert payload["requires_human_review"] is True
    assert payload["classification"] == "MISSING_PUBLIC_API_PARITY"
    assert payload["surface"] == "netclient"
    assert payload["proof_status"] == "missing"
    assert payload["candidate_status"] == "review_required"
    assert payload["proof_commands"] == [
        "python -m sdetkit investigate surface --root . --surface netclient --format json",
        "python -m pytest -q tests/test_netclient.py",
    ]

    expected_files = {
        "CANDIDATE_FREEZE.md",
        "AUDIT_RESULT.md",
        "proof-commands.md",
        "investigation.json",
    }
    assert {path.name for path in out_dir.iterdir()} == expected_files
    written = json.loads((out_dir / "investigation.json").read_text(encoding="utf-8"))
    assert written == payload
    assert "# Investigation candidate freeze" in (out_dir / "CANDIDATE_FREEZE.md").read_text(
        encoding="utf-8"
    )
    assert "# Investigation audit result" in (out_dir / "AUDIT_RESULT.md").read_text(
        encoding="utf-8"
    )
    assert "python -m pytest -q tests/test_netclient.py" in (
        out_dir / "proof-commands.md"
    ).read_text(encoding="utf-8")


def test_evidence_writer_uses_default_review_commands_for_unknown_class(tmp_path):
    payload = build_investigation_evidence(
        "UNKNOWN_REVIEW_REQUIRED",
        "mystery",
        tmp_path / "evidence",
    )

    assert payload["proof_commands"] == [
        "python -m sdetkit investigate failure --log <log> --format markdown",
        "./scripts/pr_preflight.sh",
    ]


def test_investigate_evidence_json_cli_writes_output(tmp_path, capsys):
    out_dir = tmp_path / "bundle"
    out = tmp_path / "evidence.json"

    rc = investigate.main(
        [
            "evidence",
            "--classification",
            "MISSING_PUBLIC_API_PARITY",
            "--surface",
            "netclient",
            "--out-dir",
            str(out_dir),
            "--root",
            str(tmp_path),
            "--format",
            "json",
            "--out",
            str(out),
        ]
    )

    assert rc == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    printed = json.loads(capsys.readouterr().out)
    assert written["schema_version"] == "sdetkit.investigation.evidence.v1"
    assert printed["command"] == "investigate evidence"
    assert written["files"]["investigation_json"].endswith("investigation.json")
    assert (out_dir / "CANDIDATE_FREEZE.md").exists()
    assert (out_dir / "AUDIT_RESULT.md").exists()
    assert (out_dir / "proof-commands.md").exists()
    assert (out_dir / "investigation.json").exists()


def test_investigate_evidence_markdown_cli(tmp_path, capsys):
    rc = investigate.main(
        [
            "evidence",
            "--classification",
            "PRODUCT_LOGIC_FAILURE",
            "--surface",
            "release_room",
            "--out-dir",
            str(tmp_path / "evidence"),
            "--format",
            "markdown",
        ]
    )

    assert rc == 0
    rendered = capsys.readouterr().out
    assert "# Investigation evidence" in rendered
    assert "classification: **PRODUCT_LOGIC_FAILURE**" in rendered
    assert "surface: **release_room**" in rendered
    assert "automation allowed: **False**" in rendered
    assert "python -m pytest -q" in rendered


def test_investigate_evidence_blank_classification_returns_2(tmp_path, capsys):
    rc = investigate.main(
        [
            "evidence",
            "--classification",
            " ",
            "--surface",
            "netclient",
            "--out-dir",
            str(tmp_path / "evidence"),
        ]
    )

    assert rc == 2
    assert "classification is required" in capsys.readouterr().err


def test_investigate_evidence_blank_surface_returns_2(tmp_path, capsys):
    rc = investigate.main(
        [
            "evidence",
            "--classification",
            "MISSING_PUBLIC_API_PARITY",
            "--surface",
            " ",
            "--out-dir",
            str(tmp_path / "evidence"),
        ]
    )

    assert rc == 2
    assert "surface is required" in capsys.readouterr().err


def test_python_m_sdetkit_investigate_evidence_outputs_json(tmp_path):
    out_dir = tmp_path / "bundle"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sdetkit",
            "investigate",
            "evidence",
            "--classification",
            "MISSING_PUBLIC_API_PARITY",
            "--surface",
            "netclient",
            "--out-dir",
            str(out_dir),
            "--format",
            "json",
        ],
        cwd=Path.cwd(),
        env=_env(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "sdetkit.investigation.evidence.v1"
    assert payload["classification"] == "MISSING_PUBLIC_API_PARITY"
    assert payload["automation_allowed"] is False
    assert (out_dir / "investigation.json").exists()
