from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day68_integration_expansion4_closeout as d68


def _seed_repo(root: Path) -> None:
    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)
    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "day68-integration-expansion4-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-68-big-upgrade-report.md\nintegrations-day68-integration-expansion4-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- Day 68 integration expansion\n- Day 69 case study prep\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day68-integration-expansion4-closeout.md").write_text(
        d68._DAY68_DEFAULT_PAGE,
        encoding="utf-8",
    )
    (root / "templates/ci/tekton/day68-self-hosted-reference.yaml").write_text(
        "\n".join(d68._REQUIRED_REFERENCE_LINES) + "\n",
        encoding="utf-8",
    )

    summary = (
        root
        / "docs/artifacts/day67-integration-expansion3-closeout-pack/day67-integration-expansion3-closeout-summary.json"
    )
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(
        json.dumps(
            {
                "summary": {"activation_score": 99, "strict_pass": True},
                "checks": [{"check_id": "ok", "passed": True}],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    board = (
        root / "docs/artifacts/day67-integration-expansion3-closeout-pack/day67-delivery-board.md"
    )
    board.write_text(
        "\n".join(
            [
                "# Day 67 delivery board",
                "- [ ] task 1",
                "- [ ] task 2",
                "- [ ] task 3",
                "- [ ] task 4",
                "- [ ] task 5",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_day68_json_strict(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d68.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["name"] == "integration-expansion4-closeout"
    assert payload["summary"]["activation_score"] >= 95


def test_day68_emit_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d68.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day68-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day68-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (
        tmp_path / "artifacts/day68-pack/day68-integration-expansion4-closeout-summary.json"
    ).exists()
    assert (tmp_path / "artifacts/day68-pack/day68-integration-brief.md").exists()
    assert (tmp_path / "artifacts/day68-pack/day68-self-hosted-blueprint.md").exists()
    assert (tmp_path / "artifacts/day68-pack/day68-policy-plan.json").exists()
    assert (tmp_path / "artifacts/day68-pack/day68-kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/day68-pack/evidence/day68-execution-summary.json").exists()


def test_day68_strict_fails_without_day67_summary(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/day67-integration-expansion3-closeout-pack/day67-integration-expansion3-closeout-summary.json"
    ).unlink()
    rc = d68.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 1


def test_day68_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(
        ["integration-expansion4-closeout", "--root", str(tmp_path), "--format", "text"]
    )
    assert rc == 0
    assert "Integration Expansion4 Closeout summary" in capsys.readouterr().out
