from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day83_trust_faq_expansion_closeout as d83


def _seed_repo(root: Path) -> None:

    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-day83-trust-faq-expansion-closeout.md\nday83-trust-faq-expansion-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-83-big-upgrade-report.md\nintegrations-day83-trust-faq-expansion-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 82 — Integration feedback loop:** fold field feedback into docs/templates.\n"
        "- **Day 83 — Trust FAQ expansion loop:** convert field objections into deterministic trust upgrades.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day83-trust-faq-expansion-closeout.md").write_text(
        d83._DAY83_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/day-83-big-upgrade-report.md").write_text("# Day 83 report\n", encoding="utf-8")

    summary = (
        root
        / "docs/artifacts/day82-integration-feedback-closeout-pack/day82-integration-feedback-closeout-summary.json"
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
    board = root / "docs/artifacts/day82-integration-feedback-closeout-pack/day82-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "# Day 82 delivery board",
                "- [ ] Day 82 integration brief committed",
                "- [ ] Day 82 integration feedback plan committed",
                "- [ ] Day 82 template upgrade ledger exported",
                "- [ ] Day 82 office-hours outcome ledger exported",
                "- [ ] Day 83 trust FAQ priorities drafted from Day 82 feedback",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    plan = root / "docs/roadmap/plans/day83-trust-faq-expansion-plan.json"
    plan.write_text(
        json.dumps(
            {
                "plan_id": "day83-trust-faq-expansion-001",
                "contributors": ["maintainers", "docs-ops"],
                "objection_channels": ["office-hours", "issues", "faq-form"],
                "baseline": {"faq_coverage": 0.61, "deflection_rate": 0.43},
                "target": {"faq_coverage": 0.82, "deflection_rate": 0.62},
                "owner": "docs-ops",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_day83_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d83.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day83-trust-faq-expansion-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_day83_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d83.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day83-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day83-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (
        tmp_path / "artifacts/day83-pack/day83-trust-faq-expansion-closeout-summary.json"
    ).exists()
    assert (
        tmp_path / "artifacts/day83-pack/day83-trust-faq-expansion-closeout-summary.md"
    ).exists()
    assert (tmp_path / "artifacts/day83-pack/day83-trust-faq-brief.md").exists()
    assert (tmp_path / "artifacts/day83-pack/day83-trust-faq-expansion-plan.md").exists()
    assert (tmp_path / "artifacts/day83-pack/day83-trust-template-upgrade-ledger.json").exists()
    assert (tmp_path / "artifacts/day83-pack/day83-escalation-outcomes-ledger.json").exists()
    assert (tmp_path / "artifacts/day83-pack/day83-trust-kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/day83-pack/day83-execution-log.md").exists()
    assert (tmp_path / "artifacts/day83-pack/day83-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day83-pack/day83-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day83-pack/evidence/day83-execution-summary.json").exists()


def test_day83_strict_fails_without_day82(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/day82-integration-feedback-closeout-pack/day82-integration-feedback-closeout-summary.json"
    ).unlink()
    assert d83.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_day83_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(
        ["day83-trust-faq-expansion-closeout", "--root", str(tmp_path), "--format", "text"]
    )
    assert rc == 0
    assert "Day 83 trust FAQ expansion closeout summary" in capsys.readouterr().out
