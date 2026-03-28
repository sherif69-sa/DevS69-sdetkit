from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import phase3_wrap_publication_closeout_90 as d90


def _seed_repo(root: Path) -> None:

    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-phase3-wrap-publication-closeout.md\nphase3-wrap-publication-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "impact-90-big-upgrade-report.md\nintegrations-phase3-wrap-publication-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 89 — Governance priorities closeout lane:** convert governance handoff outcomes into governance scale.\n"
        "- **Day 90 — Phase-3 wrap publication closeout lane:** scale governance scale into deterministic execution lanes.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-phase3-wrap-publication-closeout.md").write_text(
        d90._DAY90_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/impact-90-big-upgrade-report.md").write_text(
        "# Day 90 report\n", encoding="utf-8"
    )

    summary = (
        root
        / "docs/artifacts/governance-scale-closeout-pack/governance-scale-closeout-summary.json"
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
        root / "docs/artifacts/governance-scale-closeout-pack/governance-scale-delivery-board.md"
    )
    board.write_text(
        "\n".join(
            [
                "# Day 89 delivery board",
                "- [ ] Day 89 evidence brief committed",
                "- [ ] Day 89 governance scale plan committed",
                "- [ ] Day 89 narrative template upgrade ledger exported",
                "- [ ] Day 89 storyline outcomes ledger exported",
                "- [ ] Day 90 governance scale drafted from Day 89 outcomes",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    plan = root / "docs/roadmap/plans/phase3-wrap-publication-plan.json"
    plan.write_text(
        json.dumps(
            {
                "plan_id": "day90-phase3-wrap-publication-001",
                "contributors": ["maintainers", "release-ops"],
                "narrative_channels": ["launch-brief", "release-report", "faq"],
                "baseline": {"launch_confidence": 0.64, "narrative_reuse": 0.42},
                "target": {"launch_confidence": 0.86, "narrative_reuse": 0.67},
                "owner": "release-ops",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_day90_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d90.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "phase3-wrap-publication-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_day90_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d90.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/phase3-wrap-publication-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/phase3-wrap-publication-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (
        tmp_path
        / "artifacts/phase3-wrap-publication-pack/phase3-wrap-publication-closeout-summary.json"
    ).exists()
    assert (
        tmp_path
        / "artifacts/phase3-wrap-publication-pack/phase3-wrap-publication-closeout-summary.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/phase3-wrap-publication-pack/phase3-wrap-publication-evidence-brief.md"
    ).exists()
    assert (
        tmp_path / "artifacts/phase3-wrap-publication-pack/phase3-wrap-publication-plan.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/phase3-wrap-publication-pack/phase3-wrap-publication-narrative-template-upgrade-ledger.json"
    ).exists()
    assert (
        tmp_path
        / "artifacts/phase3-wrap-publication-pack/phase3-wrap-publication-storyline-outcomes-ledger.json"
    ).exists()
    assert (
        tmp_path
        / "artifacts/phase3-wrap-publication-pack/phase3-wrap-publication-narrative-kpi-scorecard.json"
    ).exists()
    assert (
        tmp_path / "artifacts/phase3-wrap-publication-pack/phase3-wrap-publication-execution-log.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/phase3-wrap-publication-pack/phase3-wrap-publication-delivery-board.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/phase3-wrap-publication-pack/phase3-wrap-publication-validation-commands.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/phase3-wrap-publication-pack/evidence/phase3-wrap-publication-execution-summary.json"
    ).exists()


def test_day90_strict_fails_without_day89(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/governance-scale-closeout-pack/governance-scale-closeout-summary.json"
    ).unlink()
    assert d90.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_day90_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["phase3-wrap-publication-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 90 phase-3 wrap publication closeout summary" in capsys.readouterr().out
