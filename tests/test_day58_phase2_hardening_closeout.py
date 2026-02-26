from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day58_phase2_hardening_closeout as d58


def _seed_repo(root: Path) -> None:
    (root / "README.md").write_text(
        "docs/integrations-day58-phase2-hardening-closeout.md\nday58-phase2-hardening-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-58-big-upgrade-report.md\nintegrations-day58-phase2-hardening-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 58 — Phase-2 hardening:** polish highest-traffic pages and remove top friction points.\n"
        "- **Day 59 — Phase-3 pre-plan:** convert Phase-2 learnings into Phase-3 priorities.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day58-phase2-hardening-closeout.md").write_text(
        d58._DAY58_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/day-58-big-upgrade-report.md").write_text("# Day 58 report\n", encoding="utf-8")

    summary = (
        root
        / "docs/artifacts/day57-kpi-deep-audit-closeout-pack/day57-kpi-deep-audit-closeout-summary.json"
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
    board = root / "docs/artifacts/day57-kpi-deep-audit-closeout-pack/day57-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "# Day 57 delivery board",
                "- [ ] Day 57 KPI deep audit brief committed",
                "- [ ] Day 57 deep-audit plan reviewed with owner + backup",
                "- [ ] Day 57 risk ledger exported",
                "- [ ] Day 57 KPI scorecard snapshot exported",
                "- [ ] Day 58 execution priorities drafted from Day 57 learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_day58_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d58.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day58-phase2-hardening-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_day58_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d58.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day58-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day58-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/day58-pack/day58-phase2-hardening-closeout-summary.json").exists()
    assert (tmp_path / "artifacts/day58-pack/day58-phase2-hardening-closeout-summary.md").exists()
    assert (tmp_path / "artifacts/day58-pack/day58-phase2-hardening-brief.md").exists()
    assert (tmp_path / "artifacts/day58-pack/day58-risk-ledger.csv").exists()
    assert (tmp_path / "artifacts/day58-pack/day58-kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/day58-pack/day58-execution-log.md").exists()
    assert (tmp_path / "artifacts/day58-pack/day58-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day58-pack/day58-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day58-pack/evidence/day58-execution-summary.json").exists()


def test_day58_strict_fails_without_day57(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/day57-kpi-deep-audit-closeout-pack/day57-kpi-deep-audit-closeout-summary.json"
    ).unlink()
    assert d58.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_day58_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["day58-phase2-hardening-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 58 Phase-2 hardening closeout summary" in capsys.readouterr().out
