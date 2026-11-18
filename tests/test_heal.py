from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit import auto_fix, cli


@pytest.fixture
def sample_workspace(tmp_path: Path) -> Path:
    src = tmp_path / "src"
    src.mkdir(parents=True)
    tests = tmp_path / "tests"
    tests.mkdir(parents=True)

    (src / "sample.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    (tests / "test_sample.py").write_text(
        "from sample import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n",
        encoding="utf-8",
    )
    return tmp_path


def test_heal_clean_workspace(sample_workspace: Path) -> None:
    report = auto_fix.heal_workspace(sample_workspace, apply=False)

    assert report["schema_version"] == auto_fix.HEAL_SCHEMA_VERSION
    assert report["status"] == "CLEAN"
    assert report["verdict"] == "HEALTHY"
    assert report["heal_score"] == 100.0
    assert report["applied"] is False


def test_heal_mechanical_format_dry_run(sample_workspace: Path) -> None:
    log_text = "ruff format failed\n1 file reformatted\n"
    report = auto_fix.heal_workspace(sample_workspace, apply=False, log_text=log_text)

    assert report["schema_version"] == auto_fix.HEAL_SCHEMA_VERSION
    assert report["status"] == "PREVIEW_READY"
    assert report["verdict"] == "DRY_RUN"
    assert report["heal_score"] == 100.0
    assert report["applied"] is False
    assert len(report["issues_detected"]) >= 1
    assert report["issues_detected"][0]["category"] == "MECHANICAL"


def test_heal_mechanical_format_applied(sample_workspace: Path) -> None:
    log_text = "ruff format failed\n1 file reformatted\n"
    report = auto_fix.heal_workspace(
        sample_workspace,
        apply=True,
        verify=False,
        log_text=log_text,
    )

    assert report["schema_version"] == auto_fix.HEAL_SCHEMA_VERSION
    assert report["status"] == "HEALED"
    assert report["verdict"] == "SHIP"
    assert report["heal_score"] == 100.0
    assert report["applied"] is True
    assert len(report["actions_taken"]) >= 1


def test_heal_logic_failure_human_review(sample_workspace: Path) -> None:
    log_text = "FAILED tests/test_sample.py::test_add - AssertionError: assert 42 == 99"
    report = auto_fix.heal_workspace(sample_workspace, log_text=log_text)

    assert report["schema_version"] == auto_fix.HEAL_SCHEMA_VERSION
    assert report["status"] == "NEEDS_HUMAN_REVIEW"
    assert report["verdict"] == "REVIEW_REQUIRED"
    assert report["heal_score"] == 0.0
    assert "Manual engineer review required" in report["recommendation"]


def test_render_heal_markdown(sample_workspace: Path) -> None:
    report = auto_fix.heal_workspace(sample_workspace, apply=False)
    md = auto_fix.render_heal_markdown(report)

    assert "### [HEAL: HEALTHY (100.0%)]" in md
    assert "SDETKit Autonomous Self-Healing" in md
    assert "Policy Decision" in md


def test_heal_cli_main_json_and_md(
    sample_workspace: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out_file = tmp_path / "heal_report.json"
    rc = auto_fix.heal_main(
        [
            "--repo-root",
            str(sample_workspace),
            "--format",
            "json",
            "--out",
            str(out_file),
        ]
    )
    captured = capsys.readouterr()
    assert rc == 0
    payload = json.loads(captured.out)
    assert payload["schema_version"] == auto_fix.HEAL_SCHEMA_VERSION
    assert out_file.is_file()

    # Markdown format
    rc_md = auto_fix.heal_main(["--repo-root", str(sample_workspace), "--format", "md"])
    captured_md = capsys.readouterr()
    assert rc_md == 0
    assert "### [HEAL:" in captured_md.out


def test_heal_cli_dispatch(sample_workspace: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(
        [
            "heal",
            "--repo-root",
            str(sample_workspace),
            "--format",
            "json",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 0
    data = json.loads(captured.out)
    assert data["schema_version"] == auto_fix.HEAL_SCHEMA_VERSION


def test_heal_verify_cli_dispatch(
    sample_workspace: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = cli.main(
        [
            "verify",
            "heal",
            "--repo-root",
            str(sample_workspace),
            "--format",
            "json",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 0
    data = json.loads(captured.out)
    assert data["schema_version"] == auto_fix.HEAL_SCHEMA_VERSION
