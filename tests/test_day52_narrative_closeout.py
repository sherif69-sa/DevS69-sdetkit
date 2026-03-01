from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day52_narrative_closeout as d52


def _seed_repo(root: Path) -> None:

    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-day52-narrative-closeout.md\nday52-narrative-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-52-big-upgrade-report.md\nintegrations-day52-narrative-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 52 — Narrative #1:** publish mini-case on reliability or quality gate value.\n"
        "- **Day 53 — Narrative #2:** publish mini-case on security/ops workflow value.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day52-narrative-closeout.md").write_text(
        d52._DAY52_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/day-52-big-upgrade-report.md").write_text("# Day 52 report\n", encoding="utf-8")

    summary = (
        root
        / "docs/artifacts/day51-case-snippet-closeout-pack/day51-case-snippet-closeout-summary.json"
    )
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(
        json.dumps(
            {
                "summary": {"activation_score": 99, "strict_pass": True},
                "checks": [{"check_id": "ok", "passed": True}],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    board = root / "docs/artifacts/day51-case-snippet-closeout-pack/day51-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "# Day 51 delivery board",
                "- [ ] Day 51 case snippet brief committed",
                "- [ ] Day 51 snippet reviewed with owner + backup",
                "- [ ] Day 51 proof map exported",
                "- [ ] Day 51 KPI scorecard snapshot exported",
                "- [ ] Day 52 narrative priorities drafted from Day 51 learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_day52_narrative_closeout_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d52.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day52-narrative-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_day52_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d52.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day52-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day52-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/day52-pack/day52-narrative-closeout-summary.json").exists()
    assert (tmp_path / "artifacts/day52-pack/day52-narrative-closeout-summary.md").exists()
    assert (tmp_path / "artifacts/day52-pack/day52-narrative-brief.md").exists()
    assert (tmp_path / "artifacts/day52-pack/day52-proof-map.csv").exists()
    assert (tmp_path / "artifacts/day52-pack/day52-narrative-kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/day52-pack/day52-execution-log.md").exists()
    assert (tmp_path / "artifacts/day52-pack/day52-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day52-pack/day52-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day52-pack/evidence/day52-execution-summary.json").exists()


def test_day52_strict_fails_when_day51_inputs_missing(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/day51-case-snippet-closeout-pack/day51-case-snippet-closeout-summary.json"
    ).unlink()
    rc = d52.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_day52_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["day52-narrative-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 52 narrative closeout summary" in capsys.readouterr().out
