from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import release_prioritization_closeout_85 as d85


def _seed_repo(root: Path) -> None:

    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-release-prioritization-closeout.md\nrelease-prioritization-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "impact-85-big-upgrade-report.md\nintegrations-release-prioritization-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        '- ** — Evidence narrative closeout lane:** convert field objections into deterministic trust upgrades.\n'
        '- ** — Release prioritization closeout lane:** convert trust outcomes into release-ready narrative proof packs.\n',
        encoding="utf-8",
    )
    (root / "docs/integrations-release-prioritization-closeout.md").write_text(
        d85._DEFAULT_PAGE_TEMPLATE, encoding="utf-8"
    )
    (root / "docs/impact-85-big-upgrade-report.md").write_text(
        '#  report\n', encoding="utf-8"
    )

    summary = (
        root
        / "docs/artifacts/evidence-narrative-closeout-pack/evidence-narrative-closeout-summary.json"
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
        root
        / "docs/artifacts/evidence-narrative-closeout-pack/evidence-narrative-delivery-board.md"
    )
    board.write_text(
        "\n".join(
            [
                '#  delivery board',
                '- [ ]  evidence brief committed',
                '- [ ]  evidence narrative plan committed',
                '- [ ]  narrative template upgrade ledger exported',
                '- [ ]  storyline outcomes ledger exported',
                '- [ ]  release priorities drafted from  outcomes',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    plan = root / "docs/roadmap/plans/release-prioritization-plan.json"
    plan.write_text(
        json.dumps(
            {
                "plan_id": "release-prioritization-001",
                "contributors": ["maintainers", "docs-ops"],
                "narrative_channels": ["release-report", "runbook", "faq"],
                "baseline": {"evidence_coverage": 0.64, "narrative_reuse": 0.42},
                "target": {"evidence_coverage": 0.86, "narrative_reuse": 0.67},
                "owner": "docs-ops",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_lane85_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d85.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "release-prioritization-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_lane85_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d85.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/release-prioritization-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/release-prioritization-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (
        tmp_path
        / "artifacts/release-prioritization-pack/release-prioritization-closeout-summary.json"
    ).exists()
    assert (
        tmp_path
        / "artifacts/release-prioritization-pack/release-prioritization-closeout-summary.md"
    ).exists()
    assert (
        tmp_path / "artifacts/release-prioritization-pack/release-prioritization-evidence-brief.md"
    ).exists()
    assert (
        tmp_path / "artifacts/release-prioritization-pack/release-prioritization-plan.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/release-prioritization-pack/release-prioritization-narrative-template-upgrade-ledger.json"
    ).exists()
    assert (
        tmp_path
        / "artifacts/release-prioritization-pack/release-prioritization-storyline-outcomes-ledger.json"
    ).exists()
    assert (
        tmp_path
        / "artifacts/release-prioritization-pack/release-prioritization-narrative-kpi-scorecard.json"
    ).exists()
    assert (
        tmp_path / "artifacts/release-prioritization-pack/release-prioritization-execution-log.md"
    ).exists()
    assert (
        tmp_path / "artifacts/release-prioritization-pack/release-prioritization-delivery-board.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/release-prioritization-pack/release-prioritization-validation-commands.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/release-prioritization-pack/evidence/release-prioritization-execution-summary.json"
    ).exists()


def test_lane85_strict_fails_without_prereq_baseline(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/evidence-narrative-closeout-pack/evidence-narrative-closeout-summary.json"
    ).unlink()
    assert d85.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_lane85_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["release-prioritization-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert ' release prioritization closeout summary' in capsys.readouterr().out
