from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day73_case_study_launch_closeout as d73


def _seed_repo(root: Path) -> None:
    (root / "README.md").write_text(
        "docs/integrations-day73-case-study-launch-closeout.md\nday73-case-study-launch-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-73-big-upgrade-report.md\nintegrations-day73-case-study-launch-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 73 — Case-study launch:** lock publication-quality evidence and publication readiness handoff.\n"
        "- **Day 74 — Distribution scaling:** convert Day 73 learnings into scaled distribution operations.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day73-case-study-launch-closeout.md").write_text(
        d73._DAY73_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/day-73-big-upgrade-report.md").write_text("# Day 73 report\n", encoding="utf-8")

    summary = (
        root
        / "docs/artifacts/day72-case-study-prep4-closeout-pack/day72-case-study-prep4-closeout-summary.json"
    )
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(
        json.dumps(
            {
                "summary": {"activation_score": 100, "strict_pass": True},
                "checks": [{"passed": True}],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    board = root / "docs/artifacts/day72-case-study-prep4-closeout-pack/day72-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "# Day 72 delivery board",
                "- [ ] Day 72 integration brief committed",
                "- [ ] Day 72 publication-quality case-study narrative published",
                "- [ ] Day 72 controls and assumptions log exported",
                "- [ ] Day 72 KPI scorecard snapshot exported",
                "- [ ] Day 74 distribution scaling priorities drafted from Day 73 learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    case_study = root / ".day73-published-case-study.json"
    case_study.write_text(
        json.dumps(
            {
                "case_id": "day73-published-case-study-001",
                "metric": "incident-triage-mttr",
                "baseline": {"hours": 6.2},
                "after": {"hours": 3.1},
                "confidence": 0.91,
                "owner": "incident-ops",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_day73_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d73.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day73-case-study-launch-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_day73_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d73.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day73-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day73-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (
        tmp_path / "artifacts/day73-pack/day73-case-study-launch-closeout-summary.json"
    ).exists()
    assert (tmp_path / "artifacts/day73-pack/day73-case-study-launch-closeout-summary.md").exists()
    assert (tmp_path / "artifacts/day73-pack/day73-integration-brief.md").exists()
    assert (tmp_path / "artifacts/day73-pack/day73-case-study-narrative.md").exists()
    assert (tmp_path / "artifacts/day73-pack/day73-controls-log.json").exists()
    assert (tmp_path / "artifacts/day73-pack/day73-kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/day73-pack/day73-execution-log.md").exists()
    assert (tmp_path / "artifacts/day73-pack/day73-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day73-pack/day73-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day73-pack/evidence/day73-execution-summary.json").exists()


def test_day73_strict_fails_without_day72(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/day72-case-study-prep4-closeout-pack/day72-case-study-prep4-closeout-summary.json"
    ).unlink()
    assert d73.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_day73_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["day73-case-study-launch-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 73 case-study launch closeout summary" in capsys.readouterr().out
