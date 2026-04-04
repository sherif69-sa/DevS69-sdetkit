from __future__ import annotations

import json
from pathlib import Path

from sdetkit import first_contribution as fc


def test_write_defaults_and_main_markdown_output(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / ".github" / "ISSUE_TEMPLATE").mkdir(parents=True)
    (tmp_path / "docs" / "starter-work-inventory.md").write_text("# starter\n", encoding="utf-8")
    (tmp_path / "docs" / "first-contribution-quickstart.md").write_text(
        "# quickstart\n", encoding="utf-8"
    )
    (tmp_path / ".github" / "PULL_REQUEST_TEMPLATE.md").write_text("template\n", encoding="utf-8")
    (tmp_path / ".github" / "ISSUE_TEMPLATE" / "feature_request.yml").write_text(
        "name: feature\n", encoding="utf-8"
    )
    out = tmp_path / "artifacts/first-contribution.md"
    rc = fc.main(
        [
            "--root",
            str(tmp_path),
            "--write-defaults",
            "--format",
            "markdown",
            "--output",
            str(out),
            "--strict",
        ]
    )
    assert rc == 0
    assert out.exists()
    assert (tmp_path / "CONTRIBUTING.md").exists()


def test_write_defaults_noop_when_header_present(tmp_path: Path) -> None:
    c = tmp_path / "CONTRIBUTING.md"
    c.write_text(fc._DAY10_DEFAULT_BLOCK, encoding="utf-8")
    assert fc._write_defaults(tmp_path) == []


def test_main_json_strict_fail(tmp_path: Path, capsys) -> None:
    (tmp_path / "CONTRIBUTING.md").write_text("# Contributing\n", encoding="utf-8")
    rc = fc.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["missing"]


def test_build_status_exposes_starter_profiles(tmp_path: Path) -> None:
    (tmp_path / "CONTRIBUTING.md").write_text(fc._DAY10_DEFAULT_BLOCK, encoding="utf-8")
    payload = fc.build_first_contribution_status(str(tmp_path))
    assert payload["starter_profiles"]["docs-polish"]["label"] == "Docs polish"
    assert "mkdocs build" in payload["starter_profiles"]["docs-polish"]["validation"]
    assert payload["trust_assets"]["starter_inventory"]["path"] == "docs/starter-work-inventory.md"
    assert payload["good_first_issue_labels"][0] == "good first issue"


def test_markdown_render_lists_starter_profiles(tmp_path: Path, capsys) -> None:
    (tmp_path / "CONTRIBUTING.md").write_text(fc._DAY10_DEFAULT_BLOCK, encoding="utf-8")
    rc = fc.main(["--root", str(tmp_path), "--format", "markdown"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "## Starter profiles" in out
    assert "Automation upgrade" in out
    assert "## Contributor trust assets" in out


def test_profile_filter_focuses_single_starter_profile(tmp_path: Path) -> None:
    (tmp_path / "CONTRIBUTING.md").write_text(fc._DAY10_DEFAULT_BLOCK, encoding="utf-8")
    payload = fc.build_first_contribution_status(str(tmp_path), profile="test-hardening")

    assert list(payload["starter_profiles"]) == ["test-hardening"]
    assert payload["selected_profile"] == "test-hardening"
    assert payload["recommended_profile"] == "test-hardening"


def test_strict_mode_fails_when_trust_assets_are_missing(tmp_path: Path, capsys) -> None:
    (tmp_path / "CONTRIBUTING.md").write_text(fc._DAY10_DEFAULT_BLOCK, encoding="utf-8")

    rc = fc.main(["--root", str(tmp_path), "--format", "json", "--strict"])

    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert "docs/starter-work-inventory.md" in payload["missing_assets"]
