from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day53_docs_loop_closeout as d53


def _seed_repo(root: Path) -> None:

    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-day53-docs-loop-closeout.md\nday53-docs-loop-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-53-big-upgrade-report.md\nintegrations-day53-docs-loop-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 52 — Case snippet #2:** publish mini-case on reliability or quality gate value.\n"
        "- **Day 53 — Docs loop optimization:** publish mini-case on security/ops workflow value.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day53-docs-loop-closeout.md").write_text(
        d53._DAY53_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/day-53-big-upgrade-report.md").write_text("# Day 53 report\n", encoding="utf-8")

    summary = (
        root / "docs/artifacts/day52-narrative-closeout-pack/day52-narrative-closeout-summary.json"
    )
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(
        json.dumps(
            {
                "summary": {"activation_score": 100, "strict_pass": True},
                "checks": [{"check_id": "ok", "passed": True}],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    board = root / "docs/artifacts/day52-narrative-closeout-pack/day52-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "# Day 52 delivery board",
                "- [ ] Day 52 narrative brief committed",
                "- [ ] Day 52 narrative reviewed with owner + backup",
                "- [ ] Day 52 proof map exported",
                "- [ ] Day 52 KPI scorecard snapshot exported",
                "- [ ] Day 53 expansion priorities drafted from Day 52 learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_day53_docs_loop_closeout_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d53.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day53-docs-loop-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_day53_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d53.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day53-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day53-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/day53-pack/day53-docs-loop-closeout-summary.json").exists()
    assert (tmp_path / "artifacts/day53-pack/day53-docs-loop-closeout-summary.md").exists()
    assert (tmp_path / "artifacts/day53-pack/day53-docs-loop-brief.md").exists()
    assert (tmp_path / "artifacts/day53-pack/day53-cross-link-map.csv").exists()
    assert (tmp_path / "artifacts/day53-pack/day53-docs-loop-kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/day53-pack/day53-execution-log.md").exists()
    assert (tmp_path / "artifacts/day53-pack/day53-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day53-pack/day53-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day53-pack/evidence/day53-execution-summary.json").exists()


def test_day53_strict_fails_when_day52_inputs_missing(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/day52-narrative-closeout-pack/day52-narrative-closeout-summary.json"
    ).unlink()
    rc = d53.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_day53_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["day53-docs-loop-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 53 docs-loop closeout summary" in capsys.readouterr().out
