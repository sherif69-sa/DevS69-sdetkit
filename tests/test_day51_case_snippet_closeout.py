from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day51_case_snippet_closeout as d51


def _seed_repo(root: Path) -> None:
    (root / "README.md").write_text(
        "docs/integrations-day51-case-snippet-closeout.md\nday51-case-snippet-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-51-big-upgrade-report.md\nintegrations-day51-case-snippet-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 51 — Case snippet #1:** publish mini-case on reliability or quality gate value.\n"
        "- **Day 52 — Case snippet #2:** publish mini-case on security/ops workflow value.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day51-case-snippet-closeout.md").write_text(
        d51._DAY51_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/day-51-big-upgrade-report.md").write_text("# Day 51 report\n", encoding="utf-8")

    summary = (
        root
        / "docs/artifacts/day50-execution-prioritization-closeout-pack/day50-execution-prioritization-closeout-summary.json"
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
    board = (
        root / "docs/artifacts/day50-execution-prioritization-closeout-pack/day50-delivery-board.md"
    )
    board.write_text(
        "\n".join(
            [
                "# Day 50 delivery board",
                "- [ ] Day 50 execution prioritization brief committed",
                "- [ ] Day 50 priorities reviewed with owner + backup",
                "- [ ] Day 50 risk register exported",
                "- [ ] Day 50 KPI scorecard snapshot exported",
                "- [ ] Day 51 release priorities drafted from Day 50 learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_day51_case_snippet_closeout_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d51.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day51-case-snippet-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_day51_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d51.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day51-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day51-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/day51-pack/day51-case-snippet-closeout-summary.json").exists()
    assert (tmp_path / "artifacts/day51-pack/day51-case-snippet-closeout-summary.md").exists()
    assert (tmp_path / "artifacts/day51-pack/day51-case-snippet-brief.md").exists()
    assert (tmp_path / "artifacts/day51-pack/day51-proof-map.csv").exists()
    assert (tmp_path / "artifacts/day51-pack/day51-case-snippet-kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/day51-pack/day51-execution-log.md").exists()
    assert (tmp_path / "artifacts/day51-pack/day51-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day51-pack/day51-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day51-pack/evidence/day51-execution-summary.json").exists()


def test_day51_strict_fails_when_day50_inputs_missing(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/day50-execution-prioritization-closeout-pack/day50-execution-prioritization-closeout-summary.json"
    ).unlink()
    rc = d51.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_day51_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["day51-case-snippet-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 51 case snippet closeout summary" in capsys.readouterr().out
