from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day60_phase2_wrap_handoff_closeout as d60


def _seed_repo(root: Path) -> None:
    (root / "README.md").write_text(
        "docs/integrations-day60-phase2-wrap-handoff-closeout.md\nday60-phase2-wrap-handoff-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-60-big-upgrade-report.md\nintegrations-day60-phase2-wrap-handoff-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 60 — Phase-2 wrap + handoff:** publish full Phase-2 report and lock Phase-3 execution board.\n"
        "- **Day 61 — Phase-3 kickoff:** set Phase-3 baseline and define ecosystem/trust KPIs.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day60-phase2-wrap-handoff-closeout.md").write_text(d60._DAY60_DEFAULT_PAGE, encoding="utf-8")
    (root / "docs/day-60-big-upgrade-report.md").write_text("# Day 60 report\n", encoding="utf-8")

    summary = root / "docs/artifacts/day59-phase3-preplan-closeout-pack/day59-phase3-preplan-closeout-summary.json"
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(json.dumps({"summary": {"activation_score": 100, "strict_pass": True}, "checks": [{"passed": True}]}, indent=2), encoding="utf-8")
    board = root / "docs/artifacts/day59-phase3-preplan-closeout-pack/day59-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "# Day 59 delivery board",
                "- [ ] Day 59 Phase-3 pre-plan brief committed",
                "- [ ] Day 59 pre-plan reviewed with owner + backup",
                "- [ ] Day 59 risk ledger exported",
                "- [ ] Day 59 KPI scorecard snapshot exported",
                "- [ ] Day 60 execution priorities drafted from Day 59 learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_day60_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d60.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day60-phase2-wrap-handoff-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_day60_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d60.main(["--root", str(tmp_path), "--emit-pack-dir", "artifacts/day60-pack", "--execute", "--evidence-dir", "artifacts/day60-pack/evidence", "--format", "json", "--strict"])
    assert rc == 0
    assert (tmp_path / "artifacts/day60-pack/day60-phase2-wrap-handoff-closeout-summary.json").exists()
    assert (tmp_path / "artifacts/day60-pack/day60-phase2-wrap-handoff-closeout-summary.md").exists()
    assert (tmp_path / "artifacts/day60-pack/day60-phase2-wrap-handoff-brief.md").exists()
    assert (tmp_path / "artifacts/day60-pack/day60-risk-ledger.csv").exists()
    assert (tmp_path / "artifacts/day60-pack/day60-kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/day60-pack/day60-execution-log.md").exists()
    assert (tmp_path / "artifacts/day60-pack/day60-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day60-pack/day60-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day60-pack/evidence/day60-execution-summary.json").exists()


def test_day60_strict_fails_without_day59(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (tmp_path / "docs/artifacts/day59-phase3-preplan-closeout-pack/day59-phase3-preplan-closeout-summary.json").unlink()
    assert d60.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_day60_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["day60-phase2-wrap-handoff-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 60 Phase-2 wrap + handoff closeout summary" in capsys.readouterr().out
