from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day64_integration_expansion_closeout as d64


def _seed_repo(root: Path) -> None:
    (root / "README.md").write_text(
        "docs/integrations-day64-integration-expansion-closeout.md\nday64-integration-expansion-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-64-big-upgrade-report.md\nintegrations-day64-integration-expansion-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 64 — Integration expansion #1:** add advanced GitHub Actions reference workflow.\n"
        "- **Day 65 — Weekly review #9:** report baseline movement and community signal quality.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day64-integration-expansion-closeout.md").write_text(
        d64._DAY64_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/day-64-big-upgrade-report.md").write_text("# Day 64 report\n", encoding="utf-8")

    summary = (
        root
        / "docs/artifacts/day63-onboarding-activation-closeout-pack/day63-onboarding-activation-closeout-summary.json"
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
        root / "docs/artifacts/day63-onboarding-activation-closeout-pack/day63-delivery-board.md"
    )
    board.write_text(
        "\n".join(
            [
                "# Day 63 delivery board",
                "- [ ] Day 63 onboarding launch brief committed",
                "- [ ] Day 63 orientation script + ownership matrix published",
                "- [ ] Day 63 roadmap voting brief exported",
                "- [ ] Day 63 KPI scorecard snapshot exported",
                "- [ ] Day 64 contributor pipeline priorities drafted from Day 63 learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    workflow = root / ".github/workflows/day64-advanced-github-actions-reference.yml"
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_text(
        "\n".join(
            [
                "name: Day64 Advanced GitHub Actions Reference",
                "on:",
                "  workflow_dispatch:",
                "  workflow_call:",
                "jobs:",
                "  validate:",
                "    runs-on: ubuntu-latest",
                "    strategy:",
                "      matrix:",
                "        python-version: ['3.11']",
                "    concurrency:",
                "      group: day64-${{ github.ref }}",
                "      cancel-in-progress: true",
                "    steps:",
                "      - uses: actions/cache@v4",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_day64_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d64.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day64-integration-expansion-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_day64_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d64.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day64-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day64-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (
        tmp_path / "artifacts/day64-pack/day64-integration-expansion-closeout-summary.json"
    ).exists()
    assert (
        tmp_path / "artifacts/day64-pack/day64-integration-expansion-closeout-summary.md"
    ).exists()
    assert (tmp_path / "artifacts/day64-pack/day64-integration-brief.md").exists()
    assert (tmp_path / "artifacts/day64-pack/day64-workflow-blueprint.md").exists()
    assert (tmp_path / "artifacts/day64-pack/day64-matrix-plan.csv").exists()
    assert (tmp_path / "artifacts/day64-pack/day64-kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/day64-pack/day64-execution-log.md").exists()
    assert (tmp_path / "artifacts/day64-pack/day64-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day64-pack/day64-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day64-pack/evidence/day64-execution-summary.json").exists()


def test_day64_strict_fails_without_day63(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/day63-onboarding-activation-closeout-pack/day63-onboarding-activation-closeout-summary.json"
    ).unlink()
    assert d64.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_day64_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(
        ["day64-integration-expansion-closeout", "--root", str(tmp_path), "--format", "text"]
    )
    assert rc == 0
    assert "Day 64 integration expansion closeout summary" in capsys.readouterr().out
