from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import community_activation as ca


def _seed(root: Path) -> None:
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text("day-25-ultra-upgrade-report.md\n", encoding="utf-8")
    (root / "README.md").write_text(
        "docs/integrations-community-activation.md\ncommunity-activation\n", encoding="utf-8"
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 25 — Community activation:** open roadmap-voting discussion and collect feedback.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-community-activation.md").write_text(ca._DAY25_DEFAULT_PAGE, encoding="utf-8")


def test_day25_community_activation_json(tmp_path: Path, capsys) -> None:
    _seed(tmp_path)

    rc = ca.main(["--root", str(tmp_path), "--format", "json"])

    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day25-community-activation"
    assert out["summary"]["activation_score"] == 100.0


def test_day25_community_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed(tmp_path)

    rc = ca.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day25-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day25-pack/evidence",
            "--format",
            "json",
        ]
    )

    assert rc == 0
    assert (tmp_path / "artifacts/day25-pack/day25-community-summary.json").exists()
    assert (tmp_path / "artifacts/day25-pack/day25-community-scorecard.md").exists()
    assert (tmp_path / "artifacts/day25-pack/day25-roadmap-vote-discussion-template.md").exists()
    assert (tmp_path / "artifacts/day25-pack/day25-feedback-triage-board.md").exists()
    assert (tmp_path / "artifacts/day25-pack/day25-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day25-pack/evidence/day25-execution-summary.json").exists()


def test_day25_community_strict_fails_when_sections_missing(tmp_path: Path) -> None:
    _seed(tmp_path)
    (tmp_path / "docs/integrations-community-activation.md").write_text(
        "# Community activation (Day 25)\n", encoding="utf-8"
    )

    rc = ca.main(["--root", str(tmp_path), "--strict", "--format", "json"])

    assert rc == 1


def test_day25_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed(tmp_path)

    rc = cli.main(["community-activation", "--root", str(tmp_path), "--format", "text"])

    assert rc == 0
    assert "Day 25 community activation summary" in capsys.readouterr().out
