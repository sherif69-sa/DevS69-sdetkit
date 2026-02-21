from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import external_contribution_push as ecp


def _seed(root: Path) -> None:
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text("day-26-ultra-upgrade-report.md\n", encoding="utf-8")
    (root / "README.md").write_text(
        "docs/integrations-external-contribution-push.md\nexternal-contribution-push\n", encoding="utf-8"
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 26 — External contribution push:** spotlight open starter tasks publicly.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-external-contribution-push.md").write_text(
        ecp._DAY26_DEFAULT_PAGE, encoding="utf-8"
    )


def test_day26_external_contribution_push_json(tmp_path: Path, capsys) -> None:
    _seed(tmp_path)

    rc = ecp.main(["--root", str(tmp_path), "--format", "json"])

    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day26-external-contribution-push"
    assert out["summary"]["activation_score"] == 100.0


def test_day26_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed(tmp_path)

    rc = ecp.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day26-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day26-pack/evidence",
            "--format",
            "json",
        ]
    )

    assert rc == 0
    assert (tmp_path / "artifacts/day26-pack/day26-external-contribution-summary.json").exists()
    assert (tmp_path / "artifacts/day26-pack/day26-external-contribution-scorecard.md").exists()
    assert (tmp_path / "artifacts/day26-pack/day26-starter-task-spotlight.md").exists()
    assert (tmp_path / "artifacts/day26-pack/day26-external-contribution-triage-board.md").exists()
    assert (tmp_path / "artifacts/day26-pack/day26-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day26-pack/evidence/day26-execution-summary.json").exists()


def test_day26_strict_fails_when_sections_missing(tmp_path: Path) -> None:
    _seed(tmp_path)
    (tmp_path / "docs/integrations-external-contribution-push.md").write_text(
        "# External contribution push (Day 26)\n", encoding="utf-8"
    )

    rc = ecp.main(["--root", str(tmp_path), "--strict", "--format", "json"])

    assert rc == 1


def test_day26_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed(tmp_path)

    rc = cli.main(["external-contribution-push", "--root", str(tmp_path), "--format", "text"])

    assert rc == 0
    assert "Day 26 external contribution push summary" in capsys.readouterr().out
