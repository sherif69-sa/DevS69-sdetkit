from __future__ import annotations

from pathlib import Path
import re

import pytest

from sdetkit import docs_qa


def _starter_inventory_text() -> str:
    return Path("docs/starter-work-inventory.md").read_text(encoding="utf-8")


def test_docs_qa_passes_repo_docs() -> None:
    report = docs_qa.run_docs_qa(Path(".").resolve())
    assert report.files_checked >= 2
    assert report.links_checked >= 10
    assert report.ok


def test_docs_qa_detects_missing_anchor(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Title\n\n[bad](#missing)\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    report = docs_qa.run_docs_qa(tmp_path)
    assert not report.ok
    assert any("missing local anchor" in issue.message for issue in report.issues)


def test_docs_qa_handles_reference_links_and_duplicate_headings(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "# Intro\n\n"
        "## Section\n\n"
        "## Section\n\n"
        "[ok-ref][guide]\n\n"
        "[guide]: docs/guide.md#section-1\n",
        encoding="utf-8",
    )
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text("# Guide\n\n## Section\n\n## Section\n", encoding="utf-8")

    report = docs_qa.run_docs_qa(tmp_path)
    assert report.ok


def test_docs_qa_ignores_links_inside_fenced_code_blocks(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "# Intro\n\n```bash\n[broken](docs/missing.md)\n```\n",
        encoding="utf-8",
    )
    (tmp_path / "docs").mkdir()

    report = docs_qa.run_docs_qa(tmp_path)
    assert report.ok


def test_docs_qa_help_describes_product_surface(capsys):
    with pytest.raises(SystemExit) as excinfo:
        docs_qa.main(["--help"])
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    assert "Validate markdown links and heading anchors across README.md and docs/." in out
    assert "--format {text,json,markdown}" in out
    normalized = " ".join(out.split())
    assert "Optional file path to also write the rendered QA report." in normalized


def test_docs_qa_markdown_output_is_structured(tmp_path: Path, capsys) -> None:
    (tmp_path / "README.md").write_text(
        "# Intro\n\n[ok](docs/guide.md#section)\n", encoding="utf-8"
    )
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text("# Guide\n\n## Section\n", encoding="utf-8")

    rc = docs_qa.main(["--root", str(tmp_path), "--format", "markdown"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "# Docs QA report" in out
    assert "## Summary" in out
    assert "- Status: pass" in out
    assert "## Issues" in out


def test_starter_work_inventory_keeps_first_contribution_structure() -> None:
    text = _starter_inventory_text()
    headings = {
        match.group(1).strip().lower()
        for match in re.finditer(r"^##\s+(.+)$", text, flags=re.MULTILINE)
    }

    assert "how to use this inventory" in headings
    assert "starter contribution categories" in headings
    assert "if no starter issue is available" in headings


def test_starter_work_inventory_keeps_contributor_path_references() -> None:
    text = _starter_inventory_text()

    assert "[First contribution quickstart](first-contribution-quickstart.md)" in text
    assert ".github/ISSUE_TEMPLATE/feature_request.yml" in text
    assert "docs/first-contribution-quickstart.md" in text


def test_versioning_and_stability_policy_terms_stay_aligned() -> None:
    versioning = Path("docs/versioning-and-support.md").read_text(encoding="utf-8")
    stability = Path("docs/stability-levels.md").read_text(encoding="utf-8")

    required_tiers = (
        "Public / stable",
        "Advanced but supported",
        "Experimental / incubator",
    )
    for tier in required_tiers:
        assert tier in versioning
        assert tier in stability

    assert "Stable/Core" not in versioning
    assert "Integrations" not in versioning
    assert "Playbooks" not in versioning
    assert "highest compatibility expectation" in stability
    assert "primary compatibility target" in versioning


def test_canonical_visibility_policy_keeps_compatibility_lanes_secondary() -> None:
    versioning = Path("docs/versioning-and-support.md").read_text(encoding="utf-8")

    assert "## Canonical path vs compatibility lanes (visibility policy)" in versioning
    assert "`python -m sdetkit gate fast`" in versioning
    assert "`python -m sdetkit gate release`" in versioning
    assert "`python -m sdetkit doctor`" in versioning
    assert "Compatibility surfaces remain supported" in versioning
    assert "primary first-time recommendation" in versioning
    assert "new deprecation wave" in versioning


def test_command_surface_policy_docs_avoid_legacy_primary_taxonomy() -> None:
    command_surface = Path("docs/command-surface.md").read_text(encoding="utf-8")
    boundary = Path("docs/integrations-and-extension-boundary.md").read_text(encoding="utf-8")

    assert "Stable/Core" not in command_surface
    assert "Integrations" not in command_surface
    assert "| Playbooks |" not in command_surface
    assert "Stable/Core" not in boundary
    assert "## What belongs in Integrations" not in boundary
    assert "## What belongs in Playbooks" not in boundary

    for required in (
        "Public / stable",
        "Advanced but supported",
        "Experimental / incubator",
    ):
        assert required in command_surface
        assert required in boundary

    assert "`python -m sdetkit gate fast`" in command_surface
    assert "`python -m sdetkit gate release`" in command_surface
    assert "`python -m sdetkit doctor`" in command_surface
