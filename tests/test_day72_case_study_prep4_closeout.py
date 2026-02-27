from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day72_case_study_prep4_closeout as d72


def _seed_repo(root: Path) -> None:
    (root / "README.md").write_text(
        "docs/integrations-day72-case-study-prep4-closeout.md\nday72-case-study-prep4-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-72-big-upgrade-report.md\nintegrations-day72-case-study-prep4-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 72 — Case-study prep #4:** lock publication-quality evidence and publication readiness handoff.\n"
        "- **Day 73 — Publication launch:** convert Day 72 outputs into externally shareable case study assets.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day72-case-study-prep4-closeout.md").write_text(
        d72._DAY72_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/day-72-big-upgrade-report.md").write_text("# Day 72 report\n", encoding="utf-8")

    summary = (
        root
        / "docs/artifacts/day71-case-study-prep3-closeout-pack/day71-case-study-prep3-closeout-summary.json"
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
    board = root / "docs/artifacts/day71-case-study-prep3-closeout-pack/day71-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "# Day 71 delivery board",
                "- [ ] Day 71 integration brief committed",
                "- [ ] Day 71 triage-speed case-study narrative published",
                "- [ ] Day 71 controls and assumptions log exported",
                "- [ ] Day 71 KPI scorecard snapshot exported",
                "- [ ] Day 73 publication launch priorities drafted from Day 72 learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    case_study = root / ".day72-publication-quality-case-study.json"
    case_study.write_text(
        json.dumps(
            {
                "case_id": "day72-publication-quality-001",
                "metric": "publication-quality-score",
                "baseline": {"score": 61.4},
                "after": {"score": 84.9},
                "confidence": 0.91,
                "owner": "quality-systems",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_day72_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d72.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day72-case-study-prep4-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_day72_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d72.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day72-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day72-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/day72-pack/day72-case-study-prep4-closeout-summary.json").exists()
    assert (tmp_path / "artifacts/day72-pack/day72-case-study-prep4-closeout-summary.md").exists()
    assert (tmp_path / "artifacts/day72-pack/day72-integration-brief.md").exists()
    assert (tmp_path / "artifacts/day72-pack/day72-case-study-narrative.md").exists()
    assert (tmp_path / "artifacts/day72-pack/day72-controls-log.json").exists()
    assert (tmp_path / "artifacts/day72-pack/day72-kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/day72-pack/day72-execution-log.md").exists()
    assert (tmp_path / "artifacts/day72-pack/day72-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day72-pack/day72-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day72-pack/evidence/day72-execution-summary.json").exists()


def test_day72_strict_fails_without_day71(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/day71-case-study-prep3-closeout-pack/day71-case-study-prep3-closeout-summary.json"
    ).unlink()
    assert d72.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_day72_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["day72-case-study-prep4-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 72 case-study prep #4 closeout summary" in capsys.readouterr().out
