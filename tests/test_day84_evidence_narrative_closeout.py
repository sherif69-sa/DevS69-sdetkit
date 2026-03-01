from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day84_evidence_narrative_closeout as d84


def _seed_repo(root: Path) -> None:

    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-day84-evidence-narrative-closeout.md\nday84-evidence-narrative-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-84-big-upgrade-report.md\nintegrations-day84-evidence-narrative-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 83 — Trust FAQ expansion loop:** convert field objections into deterministic trust upgrades.\n"
        "- **Day 84 — Evidence narrative closeout lane:** convert trust outcomes into release-ready narrative proof packs.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day84-evidence-narrative-closeout.md").write_text(
        d84._DAY84_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/day-84-big-upgrade-report.md").write_text("# Day 84 report\n", encoding="utf-8")

    summary = (
        root
        / "docs/artifacts/day83-trust-faq-expansion-closeout-pack/day83-trust-faq-expansion-closeout-summary.json"
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
    board = root / "docs/artifacts/day83-trust-faq-expansion-closeout-pack/day83-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "# Day 83 delivery board",
                "- [ ] Day 83 trust FAQ brief committed",
                "- [ ] Day 83 trust FAQ expansion plan committed",
                "- [ ] Day 83 trust template upgrade ledger exported",
                "- [ ] Day 83 escalation outcomes ledger exported",
                "- [ ] Day 84 evidence narrative priorities drafted from Day 83 outcomes",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    plan = root / "docs/roadmap/plans/day84-evidence-narrative-plan.json"
    plan.write_text(
        json.dumps(
            {
                "plan_id": "day84-evidence-narrative-001",
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


def test_day84_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d84.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day84-evidence-narrative-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_day84_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d84.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day84-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day84-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (
        tmp_path / "artifacts/day84-pack/day84-evidence-narrative-closeout-summary.json"
    ).exists()
    assert (tmp_path / "artifacts/day84-pack/day84-evidence-narrative-closeout-summary.md").exists()
    assert (tmp_path / "artifacts/day84-pack/day84-evidence-brief.md").exists()
    assert (tmp_path / "artifacts/day84-pack/day84-evidence-narrative-plan.md").exists()
    assert (tmp_path / "artifacts/day84-pack/day84-narrative-template-upgrade-ledger.json").exists()
    assert (tmp_path / "artifacts/day84-pack/day84-storyline-outcomes-ledger.json").exists()
    assert (tmp_path / "artifacts/day84-pack/day84-narrative-kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/day84-pack/day84-execution-log.md").exists()
    assert (tmp_path / "artifacts/day84-pack/day84-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day84-pack/day84-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day84-pack/evidence/day84-execution-summary.json").exists()


def test_day84_strict_fails_without_day83(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/day83-trust-faq-expansion-closeout-pack/day83-trust-faq-expansion-closeout-summary.json"
    ).unlink()
    assert d84.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_day84_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(
        ["day84-evidence-narrative-closeout", "--root", str(tmp_path), "--format", "text"]
    )
    assert rc == 0
    assert "Day 84 evidence narrative closeout summary" in capsys.readouterr().out
