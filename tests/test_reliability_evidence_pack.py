from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from sdetkit import cli
from sdetkit import reliability_evidence_pack as rep


def _write_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    gha_summary = tmp_path / "gha_summary.json"
    gl_summary = tmp_path / "gl_summary.json"
    cq_summary = tmp_path / "cq_summary.json"
    gha_summary.write_text(
        '{"score": 100.0, "strict": true, "checks_passed": 19, "checks_total": 19}\n',
        encoding="utf-8",
    )
    gl_summary.write_text(
        '{"score": 100.0, "strict": true, "checks_passed": 19, "checks_total": 19}\n',
        encoding="utf-8",
    )
    cq_summary.write_text(
        json.dumps(
            {
                "name": "contribution-quality-report",
                "quality": {"stability_score": 100.0},
                "contributions": {"velocity_score": 92.5},
                "strict_failures": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return gha_summary, gl_summary, cq_summary


def _write_page(root: Path) -> None:
    page = root / "docs/reliability-evidence-pack.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(rep._DEFAULT_PAGE_TEMPLATE, encoding="utf-8")


def test_pack_builds_json(tmp_path: Path, capsys) -> None:
    gha_summary, gl_summary, cq_summary = _write_inputs(tmp_path)
    _write_page(tmp_path)

    rc = rep.main(
        [
            "--root",
            str(tmp_path),
            "--github-actions-summary",
            str(gha_summary.relative_to(tmp_path)),
            "--gitlab-ci-summary",
            str(gl_summary.relative_to(tmp_path)),
            "--contribution-quality-summary",
            str(cq_summary.relative_to(tmp_path)),
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "reliability-evidence-pack"
    assert out["summary"]["strict_all_green"] is True
    assert out["summary"]["reliability_score"] >= 90
    assert out["score"] == 100.0


def test_pack_emits_bundle_and_evidence(tmp_path: Path) -> None:
    gha_summary, gl_summary, cq_summary = _write_inputs(tmp_path)
    _write_page(tmp_path)

    rc = rep.main(
        [
            "--root",
            str(tmp_path),
            "--github-actions-summary",
            str(gha_summary.relative_to(tmp_path)),
            "--gitlab-ci-summary",
            str(gl_summary.relative_to(tmp_path)),
            "--contribution-quality-summary",
            str(cq_summary.relative_to(tmp_path)),
            "--emit-pack-dir",
            "artifacts/reliability-evidence-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/reliability-evidence-pack/evidence",
            "--format",
            "json",
        ]
    )
    assert rc == 0
    assert (
        tmp_path / "artifacts/reliability-evidence-pack/reliability-evidence-summary.json"
    ).exists()
    assert (
        tmp_path / "artifacts/reliability-evidence-pack/reliability-evidence-scorecard.md"
    ).exists()
    assert (
        tmp_path / "artifacts/reliability-evidence-pack/reliability-evidence-checklist.md"
    ).exists()
    assert (
        tmp_path / "artifacts/reliability-evidence-pack/reliability-evidence-validation-commands.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/reliability-evidence-pack/evidence/reliability-evidence-execution-summary.json"
    ).exists()


def test_write_defaults(tmp_path: Path) -> None:
    gha_summary, gl_summary, cq_summary = _write_inputs(tmp_path)
    rc = rep.main(
        [
            "--root",
            str(tmp_path),
            "--write-defaults",
            "--github-actions-summary",
            str(gha_summary.relative_to(tmp_path)),
            "--gitlab-ci-summary",
            str(gl_summary.relative_to(tmp_path)),
            "--contribution-quality-summary",
            str(cq_summary.relative_to(tmp_path)),
            "--format",
            "json",
        ]
    )
    assert rc == 0
    assert (tmp_path / "docs/reliability-evidence-pack.md").exists()


def test_cli_dispatch(tmp_path: Path, capsys) -> None:
    gha_summary, gl_summary, cq_summary = _write_inputs(tmp_path)
    _write_page(tmp_path)

    rc = cli.main(
        [
            "reliability-evidence-pack",
            "--root",
            str(tmp_path),
            "--github-actions-summary",
            str(gha_summary.relative_to(tmp_path)),
            "--gitlab-ci-summary",
            str(gl_summary.relative_to(tmp_path)),
            "--contribution-quality-summary",
            str(cq_summary.relative_to(tmp_path)),
            "--format",
            "text",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "Reliability evidence pack" in out


def test_reliability_pack_help_prefers_canonical_summary_flags() -> None:
    help_text = rep._build_parser().format_help()
    assert "--github-actions-summary" in help_text
    assert "--gitlab-ci-summary" in help_text
    assert "--contribution-quality-summary" in help_text
    assert "--gha_summary-summary" not in help_text
    assert "--gl_summary-summary" not in help_text
    assert "--cq_summary-summary" not in help_text



def test_reliability_pack_load_json_requires_object(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text("[]\n", encoding="utf-8")
    with pytest.raises(ValueError) as e:
        rep._load_json(str(p))
    assert "must contain a JSON object" in str(e.value)


def test_reliability_pack_require_keys_reports_missing_key() -> None:
    with pytest.raises(ValueError) as e:
        rep._require_keys({}, ("score",), "x")
    assert "missing required key: score" in str(e.value)


def test_reliability_pack_normalize_execution_summary_alt_schema_zero_total() -> None:
    out = rep._normalize_execution_summary(
        {"passed_commands": 0, "total_commands": 0, "failed_commands": 0},
        "alt",
    )
    assert out["score"] == 0.0
    assert out["strict"] is True
    assert out["checks_total"] == 0.0


def test_reliability_pack_normalize_execution_summary_rejects_unknown_schema() -> None:
    with pytest.raises(ValueError) as e:
        rep._normalize_execution_summary({"x": 1}, "bad")
    assert "bad summary must include" in str(e.value)


def test_reliability_pack_execute_commands_timeout_records_error(monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=["x"], timeout=1, output="out", stderr="err")

    monkeypatch.setattr(rep.subprocess, "run", boom)
    rows = rep._execute_commands(["python -c 'print(1)'"], timeout_sec=1)
    assert rows[0]["returncode"] == 124
    assert rows[0]["ok"] is False
    assert "timed out after" in rows[0]["error"]


def test_reliability_pack_main_returns_2_on_missing_inputs(tmp_path: Path, capsys) -> None:
    # Missing summary files should be caught and return rc=2.
    rc = rep.main(
        [
            "--root",
            str(tmp_path),
            "--github-actions-summary",
            "missing15.json",
            "--gitlab-ci-summary",
            "missing16.json",
            "--contribution-quality-summary",
            "missing17.json",
            "--format",
            "text",
        ]
    )
    assert rc == 2
    out = capsys.readouterr().out
    assert out.strip() != ""


def test_reliability_pack_main_markdown_writes_output_file(tmp_path: Path) -> None:
    gha_summary, gl_summary, cq_summary = _write_inputs(tmp_path)
    _write_page(tmp_path)

    out_path = tmp_path / "pack.md"
    rc = rep.main(
        [
            "--root",
            str(tmp_path),
            "--github-actions-summary",
            str(gha_summary.relative_to(tmp_path)),
            "--gitlab-ci-summary",
            str(gl_summary.relative_to(tmp_path)),
            "--contribution-quality-summary",
            str(cq_summary.relative_to(tmp_path)),
            "--format",
            "markdown",
            "--output",
            str(out_path.relative_to(tmp_path)),
        ]
    )
    assert rc == 0
    assert out_path.exists()
    assert "Reliability evidence pack" in out_path.read_text(encoding="utf-8")


def test_reliability_pack_strict_fails_when_page_missing_and_score_low(
    tmp_path: Path, capsys
) -> None:
    # Create inputs that produce a very low reliability_score and a page missing required content.
    gha_summary = tmp_path / "gha_summary.json"
    gl_summary = tmp_path / "gl_summary.json"
    cq_summary = tmp_path / "cq_summary.json"
    gha_summary.write_text(
        '{"score": 0.0, "strict": true, "checks_passed": 0, "checks_total": 10}\n', encoding="utf-8"
    )
    gl_summary.write_text(
        '{"score": 0.0, "strict": true, "checks_passed": 0, "checks_total": 10}\n', encoding="utf-8"
    )
    cq_summary.write_text(
        '{"name":"contribution-quality-report","quality":{"stability_score":0.0},"contributions":{"velocity_score":0.0},"strict_failures":[]}\n',
        encoding="utf-8",
    )
    # Write a page that is missing the required header/sections/commands.
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs/reliability-evidence-pack.md").write_text("# empty\n", encoding="utf-8")

    rc = rep.main(
        [
            "--root",
            str(tmp_path),
            "--github-actions-summary",
            str(gha_summary.relative_to(tmp_path)),
            "--gitlab-ci-summary",
            str(gl_summary.relative_to(tmp_path)),
            "--contribution-quality-summary",
            str(cq_summary.relative_to(tmp_path)),
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["strict_failures"]
