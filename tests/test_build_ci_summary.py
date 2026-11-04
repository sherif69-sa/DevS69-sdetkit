from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_build_ci_summary_writes_json_and_markdown(tmp_path: Path) -> None:
    _write_json(tmp_path / "gate-fast.json", {"ok": True, "failed_steps": []})
    _write_json(tmp_path / "doctor.json", {"ok": True, "score": 93})
    _write_json(
        tmp_path / "security-enforce.json",
        {
            "ok": True,
            "counts": {"error": 0, "warn": 0, "info": 194},
            "limits": {"error": 0, "warn": 0},
        },
    )
    _write_json(tmp_path / "package-validate.json", {"ok": True})

    out_json = tmp_path / "ci-summary.json"
    out_md = tmp_path / "ci-summary.md"
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/build_ci_summary.py",
            "--artifact-dir",
            str(tmp_path),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    assert out_json.is_file()
    assert out_md.is_file()

    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["status"] == "pass"
    assert payload["checks"]["gate_fast"]["ok"] is True
    assert payload["checks"]["doctor"]["score"] == 93
    assert payload["checks"]["package_validate"]["present"] is True
    assert payload["checks"]["package_validate"]["ok"] is True
    # Info findings are counted, not limited: they do not fail the summary.
    assert payload["checks"]["security"]["counts"]["info"] == 194
    markdown = out_md.read_text(encoding="utf-8")
    assert "# CI Operator Summary" in markdown
    assert "gate_fast" in markdown
    assert "| security | True | True | error=0 (max 0), warn=0 (max 0), info=194 |" in markdown


def test_build_ci_summary_marks_failure_when_gate_or_security_fails(tmp_path: Path) -> None:
    _write_json(tmp_path / "gate-fast.json", {"ok": False, "failed_steps": ["lint"]})
    _write_json(
        tmp_path / "security-enforce.json",
        {
            "ok": True,
            "counts": {"error": 0, "warn": 0, "info": 194},
            "limits": {"error": 0, "warn": 0},
        },
    )
    out_json = tmp_path / "ci-summary.json"
    out_md = tmp_path / "ci-summary.md"
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/build_ci_summary.py",
            "--artifact-dir",
            str(tmp_path),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    summary = json.loads(out_json.read_text(encoding="utf-8"))
    assert summary["status"] == "fail"
    assert summary["checks"]["gate_fast"]["failed_steps"] == ["lint"]


def _summary(tmp_path: Path) -> dict[str, object]:
    out_json = tmp_path / "ci-summary.json"
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/build_ci_summary.py",
            "--artifact-dir",
            str(tmp_path),
            "--out-json",
            str(out_json),
            "--out-md",
            str(tmp_path / "ci-summary.md"),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(out_json.read_text(encoding="utf-8"))


def test_a_security_finding_over_its_limit_fails_the_summary(tmp_path: Path) -> None:
    _write_json(tmp_path / "gate-fast.json", {"ok": True, "failed_steps": []})
    # The shape `security enforce --format json` writes.
    _write_json(
        tmp_path / "security-enforce.json",
        {
            "ok": False,
            "counts": {"error": 0, "warn": 1, "info": 3, "total": 4},
            "limits": {"error": 0, "warn": 0, "info": None},
            "exceeded": [{"metric": "warn", "count": 1, "limit": 0}],
        },
    )

    summary = _summary(tmp_path)

    assert summary["status"] == "fail"
    assert summary["checks"]["security"]["counts"]["warn"] == 1
    markdown = (tmp_path / "ci-summary.md").read_text(encoding="utf-8")
    assert "error=0 (max 0), warn=1 (max 0), info=3 |" in markdown


def test_no_security_report_reads_as_not_present(tmp_path: Path) -> None:
    _write_json(tmp_path / "gate-fast.json", {"ok": True, "failed_steps": []})

    summary = _summary(tmp_path)

    assert summary["status"] == "pass"
    assert summary["checks"]["security"] == {
        "present": False,
        "ok": None,
        "counts": {},
        "limits": {},
    }
    assert "| security | False | None |  |" in (tmp_path / "ci-summary.md").read_text(
        encoding="utf-8"
    )
