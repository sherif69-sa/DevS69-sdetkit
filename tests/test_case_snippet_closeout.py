from __future__ import annotations

import json
from pathlib import Path

from sdetkit import case_snippet_closeout_51 as d51
from sdetkit import cli


def _seed_repo(root: Path) -> None:

    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-case-snippet-closeout.md\ncase-snippet-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "impact-51-big-upgrade-report.md\nintegrations-case-snippet-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Cycle 51 — Case snippet #1:** publish mini-case on reliability or quality gate value.\n"
        "- **Cycle 52 — Case snippet #2:** publish mini-case on security/ops workflow value.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-case-snippet-closeout.md").write_text(
        d51._DEFAULT_PAGE_TEMPLATE, encoding="utf-8"
    )
    (root / "docs/impact-51-big-upgrade-report.md").write_text(
        "# Cycle 51 report\n", encoding="utf-8"
    )

    summary = (
        root
        / "docs/artifacts/execution-prioritization-closeout-pack/execution-prioritization-closeout-summary.json"
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
        root
        / "docs/artifacts/execution-prioritization-closeout-pack/execution-prioritization-delivery-board.md"
    )
    board.write_text(
        "\n".join(
            [
                "# Day 50 delivery board",
                "- [ ] Day 50 execution prioritization brief committed",
                "- [ ] Day 50 priorities reviewed with owner + backup",
                "- [ ] Day 50 risk register exported",
                "- [ ] Day 50 KPI scorecard snapshot exported",
                "- [ ] Cycle 51 release priorities drafted from Day 50 learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_case_snippet_closeout_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d51.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "case-snippet-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d51.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/case-snippet-closeout-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/case-snippet-closeout-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (
        tmp_path / "artifacts/case-snippet-closeout-pack/case-snippet-closeout-summary.json"
    ).exists()
    assert (
        tmp_path / "artifacts/case-snippet-closeout-pack/case-snippet-closeout-summary.md"
    ).exists()
    assert (tmp_path / "artifacts/case-snippet-closeout-pack/case-snippet-brief.md").exists()
    assert (tmp_path / "artifacts/case-snippet-closeout-pack/proof-map.csv").exists()
    assert (
        tmp_path / "artifacts/case-snippet-closeout-pack/case-snippet-kpi-scorecard.json"
    ).exists()
    assert (tmp_path / "artifacts/case-snippet-closeout-pack/execution-log.md").exists()
    assert (tmp_path / "artifacts/case-snippet-closeout-pack/delivery-board.md").exists()
    assert (tmp_path / "artifacts/case-snippet-closeout-pack/validation-commands.md").exists()
    assert (
        tmp_path / "artifacts/case-snippet-closeout-pack/evidence/execution-summary.json"
    ).exists()


def test_strict_fails_when_lane50_inputs_missing(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/execution-prioritization-closeout-pack/execution-prioritization-closeout-summary.json"
    ).unlink()
    rc = d51.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["case-snippet-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Case Snippet Closeout summary" in capsys.readouterr().out
