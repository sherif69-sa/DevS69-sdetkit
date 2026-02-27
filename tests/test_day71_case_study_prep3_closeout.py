from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day71_case_study_prep3_closeout as d71


def _seed_repo(root: Path) -> None:
    (root / "README.md").write_text(
        "docs/integrations-day71-case-study-prep3-closeout.md\nday71-case-study-prep3-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-71-big-upgrade-report.md\nintegrations-day71-case-study-prep3-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 71 — Case-study prep #3:** lock escalation-quality evidence and publication readiness handoff.\n"
        "- **Day 72 — Weekly review #10:** assess integration adoption and feedback quality.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day71-case-study-prep3-closeout.md").write_text(
        d71._DAY71_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/day-71-big-upgrade-report.md").write_text("# Day 71 report\n", encoding="utf-8")

    summary = (
        root
        / "docs/artifacts/day70-case-study-prep2-closeout-pack/day70-case-study-prep2-closeout-summary.json"
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
    board = root / "docs/artifacts/day70-case-study-prep2-closeout-pack/day70-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "# Day 70 delivery board",
                "- [ ] Day 70 integration brief committed",
                "- [ ] Day 70 triage-speed case-study narrative published",
                "- [ ] Day 70 controls and assumptions log exported",
                "- [ ] Day 70 KPI scorecard snapshot exported",
                "- [ ] Day 71 case-study prep priorities drafted from Day 70 learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    case_study = root / ".day71-escalation-quality-case-study.json"
    case_study.write_text(
        json.dumps(
            {
                "case_id": "day71-escalation-quality-001",
                "metric": "escalation-quality-score",
                "baseline": {"score": 61.4},
                "after": {"score": 84.9},
                "confidence": 0.91,
                "owner": "quality-systems",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_day71_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d71.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day71-case-study-prep3-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_day71_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d71.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day71-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day71-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/day71-pack/day71-case-study-prep3-closeout-summary.json").exists()
    assert (tmp_path / "artifacts/day71-pack/day71-case-study-prep3-closeout-summary.md").exists()
    assert (tmp_path / "artifacts/day71-pack/day71-integration-brief.md").exists()
    assert (tmp_path / "artifacts/day71-pack/day71-case-study-narrative.md").exists()
    assert (tmp_path / "artifacts/day71-pack/day71-controls-log.json").exists()
    assert (tmp_path / "artifacts/day71-pack/day71-kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/day71-pack/day71-execution-log.md").exists()
    assert (tmp_path / "artifacts/day71-pack/day71-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day71-pack/day71-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day71-pack/evidence/day71-execution-summary.json").exists()


def test_day71_strict_fails_without_day70(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/day70-case-study-prep2-closeout-pack/day70-case-study-prep2-closeout-summary.json"
    ).unlink()
    assert d71.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_day71_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["day71-case-study-prep3-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 71 case-study prep #3 closeout summary" in capsys.readouterr().out
