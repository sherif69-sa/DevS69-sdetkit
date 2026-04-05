from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import phase3_preplan_closeout_59 as d59


def _seed_repo(root: Path) -> None:

    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-phase3-preplan-closeout.md\nphase3-preplan-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "impact-59-big-upgrade-report.md\nintegrations-phase3-preplan-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 59 — Phase-3 pre-plan:** convert Phase-2 learnings into Phase-3 priorities.\n"
        "- **Day 60 — Phase-2 wrap + handoff:** publish full Phase-2 report and lock Phase-3 execution board.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-phase3-preplan-closeout.md").write_text(
        d59._DEFAULT_PAGE_TEMPLATE, encoding="utf-8"
    )
    (root / "docs/impact-59-big-upgrade-report.md").write_text(
        "# Day 59 report\n", encoding="utf-8"
    )

    summary = (
        root
        / "docs/artifacts/phase2-hardening-closeout-pack/phase2-hardening-closeout-summary.json"
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
    board = (
        root / "docs/artifacts/phase2-hardening-closeout-pack/phase2-hardening-delivery-board.md"
    )
    board.write_text(
        "\n".join(
            [
                "# Day 58 delivery board",
                "- [ ] Day 58 Phase-2 hardening brief committed",
                "- [ ] Day 58 hardening plan reviewed with owner + backup",
                "- [ ] Day 58 risk ledger exported",
                "- [ ] Day 58 KPI scorecard snapshot exported",
                "- [ ] Day 59 pre-plan priorities drafted from Day 58 learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_lane59_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d59.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "phase3-preplan-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_lane59_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d59.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/phase3-preplan-closeout-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/phase3-preplan-closeout-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (
        tmp_path / "artifacts/phase3-preplan-closeout-pack/phase3-preplan-closeout-summary.json"
    ).exists()
    assert (
        tmp_path / "artifacts/phase3-preplan-closeout-pack/phase3-preplan-closeout-summary.md"
    ).exists()
    assert (tmp_path / "artifacts/phase3-preplan-closeout-pack/phase3-preplan-brief.md").exists()
    assert (
        tmp_path / "artifacts/phase3-preplan-closeout-pack/phase3-preplan-risk-ledger.csv"
    ).exists()
    assert (
        tmp_path / "artifacts/phase3-preplan-closeout-pack/phase3-preplan-kpi-scorecard.json"
    ).exists()
    assert (
        tmp_path / "artifacts/phase3-preplan-closeout-pack/phase3-preplan-execution-log.md"
    ).exists()
    assert (
        tmp_path / "artifacts/phase3-preplan-closeout-pack/phase3-preplan-delivery-board.md"
    ).exists()
    assert (
        tmp_path / "artifacts/phase3-preplan-closeout-pack/phase3-preplan-validation-commands.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/phase3-preplan-closeout-pack/evidence/phase3-preplan-execution-summary.json"
    ).exists()


def test_lane59_strict_fails_without_phase2_hardening(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/phase2-hardening-closeout-pack/phase2-hardening-closeout-summary.json"
    ).unlink()
    assert d59.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_lane59_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["phase3-preplan-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Phase3 Preplan Closeout summary" in capsys.readouterr().out
