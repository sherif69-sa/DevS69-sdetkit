from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import integration_expansion_closeout_64 as d64


def _seed_repo(root: Path) -> None:

    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-integration-expansion-closeout.md\nintegration-expansion-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "impact-64-big-upgrade-report.md\nintegrations-integration-expansion-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Cycle 64 — Integration expansion #1:** add advanced GitHub Actions reference workflow.\n"
        "- **Day 65 — Weekly review #9:** report baseline movement and community signal quality.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-integration-expansion-closeout.md").write_text(
        d64._DEFAULT_PAGE_TEMPLATE, encoding="utf-8"
    )
    (root / "docs/impact-64-big-upgrade-report.md").write_text(
        "# Cycle 64 report\n", encoding="utf-8"
    )

    summary = (
        root
        / "docs/artifacts/onboarding-activation-closeout-pack/onboarding-activation-closeout-summary.json"
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
    board = root / "docs/artifacts/onboarding-activation-closeout-pack/delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "# Cycle 63 delivery board",
                "- [ ] Cycle 63 onboarding launch brief committed",
                "- [ ] Cycle 63 orientation script + ownership matrix published",
                "- [ ] Cycle 63 roadmap voting brief exported",
                "- [ ] Cycle 63 KPI scorecard snapshot exported",
                "- [ ] Cycle 64 contributor pipeline priorities drafted from Cycle 63 learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    workflow = root / ".github/workflows/advanced-github-actions-reference-64.yml"
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_text(
        "\n".join(
            [
                "name: Cycle64 Advanced GitHub Actions Reference",
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
                "      group: integration-expansion-64-${{ github.ref }}",
                "      cancel-in-progress: true",
                "    steps:",
                "      - uses: actions/cache@v4",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d64.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "integration-expansion-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d64.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/integration-expansion-closeout-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/integration-expansion-closeout-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (
        tmp_path
        / "artifacts/integration-expansion-closeout-pack/integration-expansion-closeout-summary.json"
    ).exists()
    assert (
        tmp_path
        / "artifacts/integration-expansion-closeout-pack/integration-expansion-closeout-summary.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/integration-expansion-closeout-pack/integration-expansion-integration-brief.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/integration-expansion-closeout-pack/integration-expansion-workflow-blueprint.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/integration-expansion-closeout-pack/integration-expansion-matrix-plan.csv"
    ).exists()
    assert (
        tmp_path
        / "artifacts/integration-expansion-closeout-pack/integration-expansion-kpi-scorecard.json"
    ).exists()
    assert (
        tmp_path
        / "artifacts/integration-expansion-closeout-pack/integration-expansion-execution-log.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/integration-expansion-closeout-pack/integration-expansion-delivery-board.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/integration-expansion-closeout-pack/integration-expansion-validation-commands.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/integration-expansion-closeout-pack/evidence/integration-expansion-execution-summary.json"
    ).exists()


def test_strict_fails_without_cycle63(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/onboarding-activation-closeout-pack/onboarding-activation-closeout-summary.json"
    ).unlink()
    assert d64.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["integration-expansion-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Integration Expansion Closeout summary" in capsys.readouterr().out
