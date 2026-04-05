from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import external_contribution as ecp


def _seed(root: Path) -> None:
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "impact-26-ultra-upgrade-report.md\ndocs/external-contribution.md\nExternal contribution\n",
        encoding="utf-8",
    )
    (root / "README.md").write_text(
        "External contribution\ndocs/external-contribution.md\nexternal-contribution\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **External contribution:** spotlight open starter tasks publicly.\n",
        encoding="utf-8",
    )
    (root / "docs/external-contribution.md").write_text(
        ecp._DEFAULT_PAGE_TEMPLATE, encoding="utf-8"
    )


def test_external_contribution_json(tmp_path: Path, capsys) -> None:
    _seed(tmp_path)

    rc = ecp.main(["--root", str(tmp_path), "--format", "json"])

    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "external-contribution"
    assert out["summary"]["activation_score"] == 100.0


def test_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed(tmp_path)

    rc = ecp.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/external-contribution-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/external-contribution-pack/evidence",
            "--format",
            "json",
        ]
    )

    assert rc == 0
    assert (
        tmp_path / "artifacts/external-contribution-pack/external-contribution-summary.json"
    ).exists()
    assert (
        tmp_path / "artifacts/external-contribution-pack/external-contribution-scorecard.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/external-contribution-pack/external-contribution-starter-task-spotlight.md"
    ).exists()
    assert (
        tmp_path / "artifacts/external-contribution-pack/external-contribution-triage-board.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/external-contribution-pack/external-contribution-validation-commands.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/external-contribution-pack/evidence/external-contribution-execution-summary.json"
    ).exists()


def test_strict_fails_when_sections_missing(tmp_path: Path) -> None:
    _seed(tmp_path)
    (tmp_path / "docs/external-contribution.md").write_text(
        "# External contribution\n", encoding="utf-8"
    )

    rc = ecp.main(["--root", str(tmp_path), "--strict", "--format", "json"])

    assert rc == 1


def test_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed(tmp_path)

    rc = cli.main(["external-contribution", "--root", str(tmp_path), "--format", "text"])

    assert rc == 0
    assert "External contribution summary" in capsys.readouterr().out
