from __future__ import annotations

from pathlib import Path

import pytest

from sdetkit import triage_templates


def _seed_templates(root: Path) -> None:
    issue_dir = root / ".github" / "ISSUE_TEMPLATE"
    issue_dir.mkdir(parents=True)
    (issue_dir / "bug_report.yml").write_text(
        triage_templates._DEFAULT_BUG_TEMPLATE, encoding="utf-8"
    )
    (issue_dir / "feature_request.yml").write_text(
        triage_templates._DEFAULT_FEATURE_TEMPLATE,
        encoding="utf-8",
    )
    (issue_dir / "config.yml").write_text(triage_templates._DEFAULT_ISSUE_CONFIG, encoding="utf-8")
    (root / ".github" / "PULL_REQUEST_TEMPLATE.md").write_text(
        triage_templates._DEFAULT_PR_TEMPLATE,
        encoding="utf-8",
    )


def test_day9_template_health_payload_is_complete(tmp_path: Path) -> None:
    _seed_templates(tmp_path)
    payload = triage_templates.build_template_health(str(tmp_path))
    assert payload["name"] == "day9-contribution-templates"
    assert payload["score"] == 100.0
    assert payload["passed_checks"] == payload["total_checks"]
    assert len(payload["templates"]) == 4


def test_markdown_export_writes_day9_artifact(tmp_path: Path) -> None:
    _seed_templates(tmp_path)
    out = tmp_path / "day9.md"
    rc = triage_templates.main(
        [
            "--root",
            str(tmp_path),
            "--format",
            "markdown",
            "--output",
            str(out),
            "--strict",
        ]
    )
    assert rc == 0
    text = out.read_text(encoding="utf-8")
    assert "# Contribution templates health" in text
    assert "`config`" in text


def test_write_defaults_repairs_missing_files(tmp_path: Path) -> None:
    rc = triage_templates.main(
        ["--root", str(tmp_path), "--write-defaults", "--strict", "--format", "json"]
    )
    assert rc == 0
    assert (tmp_path / ".github" / "ISSUE_TEMPLATE" / "bug_report.yml").exists()
    assert (tmp_path / ".github" / "ISSUE_TEMPLATE" / "feature_request.yml").exists()
    assert (tmp_path / ".github" / "ISSUE_TEMPLATE" / "config.yml").exists()
    assert (tmp_path / ".github" / "PULL_REQUEST_TEMPLATE.md").exists()


def test_strict_mode_fails_on_missing_requirements(tmp_path: Path) -> None:
    issue_dir = tmp_path / ".github" / "ISSUE_TEMPLATE"
    issue_dir.mkdir(parents=True)
    (issue_dir / "bug_report.yml").write_text("name: Bug report\nbody: []\n", encoding="utf-8")
    (issue_dir / "feature_request.yml").write_text("name: Feature\nbody: []\n", encoding="utf-8")
    (issue_dir / "config.yml").write_text("blank_issues_enabled: true\n", encoding="utf-8")
    (tmp_path / ".github" / "PULL_REQUEST_TEMPLATE.md").write_text("## Summary\n", encoding="utf-8")

    rc = triage_templates.main(["--root", str(tmp_path), "--strict"])
    assert rc == 1


def test_triage_templates_help_describes_product_surface(capsys):
    with pytest.raises(SystemExit) as excinfo:
        triage_templates.main(["--help"])
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    normalized = " ".join(out.split())
    assert "usage: sdetkit triage-templates" in normalized
    assert "--format {text,markdown,json}" in out
    assert (
        "Validate issue, pull request, and config templates for fast maintainer triage."
        in normalized
    )
    assert "Optional file path to also write the rendered triage templates report." in normalized


def test_triage_templates_markdown_output_is_structured(tmp_path: Path, capsys):
    _seed_templates(tmp_path)
    rc = triage_templates.main(["--root", str(tmp_path), "--format", "markdown"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "# Contribution templates health" in out
    assert "| Template | Coverage | Status | Path |" in out
    assert "## Missing checks" in out
    assert "## Triage SLA targets" in out
    assert "## Recovery actions" in out
