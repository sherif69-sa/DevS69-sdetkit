from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day67_integration_expansion3_closeout as d67


def _seed_repo(root: Path) -> None:
    (root / "README.md").write_text(
        "docs/integrations-day67-integration-expansion3-closeout.md\nday67-integration-expansion3-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-67-big-upgrade-report.md\nintegrations-day67-integration-expansion3-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 67 — Integration expansion #3:** publish advanced Jenkins implementation path.\n"
        "- **Day 68 — Integration expansion #4:** publish self-hosted enterprise implementation path.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day67-integration-expansion3-closeout.md").write_text(
        d67._DAY67_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/day-67-big-upgrade-report.md").write_text("# Day 67 report\n", encoding="utf-8")

    summary = (
        root
        / "docs/artifacts/day66-integration-expansion2-closeout-pack/day66-integration-expansion2-closeout-summary.json"
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
        root / "docs/artifacts/day66-integration-expansion2-closeout-pack/day66-delivery-board.md"
    )
    board.write_text(
        "\n".join(
            [
                "# Day 66 delivery board",
                "- [ ] Day 66 integration brief committed",
                "- [ ] Day 66 advanced GitLab pipeline blueprint published",
                "- [ ] Day 66 matrix and cache strategy exported",
                "- [ ] Day 66 KPI scorecard snapshot exported",
                "- [ ] Day 67 integration expansion priorities drafted from Day 66 learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    jenkins = root / ".jenkins.day67-advanced-reference.Jenkinsfile"
    jenkins.write_text(
        "pipeline {\n"
        "  agent any\n"
        "  stages {\n"
        "    stage('test') {\n"
        "      matrix {\n"
        "        stages {\n"
        "          stage('unit') {\n"
        "            steps { echo 'ok' }\n"
        "          }\n"
        "        }\n"
        "      }\n"
        "    }\n"
        "  }\n"
        "  parallel {\n"
        "    stage('contract') { steps { echo 'x' } }\n"
        "  }\n"
        "  post {\n"
        "    always { echo 'archive' }\n"
        "  }\n"
        "}\n",
        encoding="utf-8",
    )


def test_day67_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d67.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day67-integration-expansion3-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_day67_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d67.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day67-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day67-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (
        tmp_path / "artifacts/day67-pack/day67-integration-expansion3-closeout-summary.json"
    ).exists()
    assert (
        tmp_path / "artifacts/day67-pack/day67-integration-expansion3-closeout-summary.md"
    ).exists()
    assert (tmp_path / "artifacts/day67-pack/day67-integration-brief.md").exists()
    assert (tmp_path / "artifacts/day67-pack/day67-jenkins-blueprint.md").exists()
    assert (tmp_path / "artifacts/day67-pack/day67-matrix-plan.json").exists()
    assert (tmp_path / "artifacts/day67-pack/day67-kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/day67-pack/day67-execution-log.md").exists()
    assert (tmp_path / "artifacts/day67-pack/day67-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day67-pack/day67-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day67-pack/evidence/day67-execution-summary.json").exists()


def test_day67_strict_fails_without_day66(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/day66-integration-expansion2-closeout-pack/day66-integration-expansion2-closeout-summary.json"
    ).unlink()
    assert d67.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_day67_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(
        ["day67-integration-expansion3-closeout", "--root", str(tmp_path), "--format", "text"]
    )
    assert rc == 0
    assert "Day 67 integration expansion #3 closeout summary" in capsys.readouterr().out
