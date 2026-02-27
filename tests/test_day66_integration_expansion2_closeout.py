from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day66_integration_expansion2_closeout as d66


def _seed_repo(root: Path) -> None:
    (root / "README.md").write_text(
        "docs/integrations-day66-integration-expansion2-closeout.md\nday66-integration-expansion2-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-66-big-upgrade-report.md\nintegrations-day66-integration-expansion2-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 66 — Integration expansion #2:** publish advanced GitLab CI implementation path.\n"
        "- **Day 67 — Integration expansion #3:** publish advanced Jenkins implementation path.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day66-integration-expansion2-closeout.md").write_text(
        d66._DAY66_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/day-66-big-upgrade-report.md").write_text("# Day 66 report\n", encoding="utf-8")

    summary = (
        root
        / "docs/artifacts/day65-weekly-review-closeout-pack/day65-weekly-review-closeout-summary.json"
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
    board = root / "docs/artifacts/day65-weekly-review-closeout-pack/day65-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "# Day 65 delivery board",
                "- [ ] Day 65 weekly brief committed",
                "- [ ] Day 65 KPI dashboard snapshot exported",
                "- [ ] Day 65 governance decision register published",
                "- [ ] Day 65 risk and recovery ledger exported",
                "- [ ] Day 66 integration expansion priorities drafted from Day 65 review",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    gitlab = root / ".gitlab-ci.day66-advanced-reference.yml"
    gitlab.write_text(
        "stages:\n"
        "  - lint\n"
        "  - test\n"
        "workflow:\n"
        "  rules:\n"
        "    - if: '$CI_PIPELINE_SOURCE == \"merge_request_event\"'\n"
        "    - if: '$CI_COMMIT_BRANCH'\n"
        "test:matrix:\n"
        "  stage: test\n"
        "  parallel:\n"
        "    matrix:\n"
        "      - PYTHON_VERSION: ['3.10', '3.11']\n"
        "  cache:\n"
        "    key: ${CI_COMMIT_REF_SLUG}\n"
        "    paths:\n"
        "      - .venv/\n",
        encoding="utf-8",
    )


def test_day66_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d66.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day66-integration-expansion2-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_day66_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d66.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day66-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day66-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/day66-pack/day66-integration-expansion2-closeout-summary.json").exists()
    assert (tmp_path / "artifacts/day66-pack/day66-integration-expansion2-closeout-summary.md").exists()
    assert (tmp_path / "artifacts/day66-pack/day66-integration-brief.md").exists()
    assert (tmp_path / "artifacts/day66-pack/day66-pipeline-blueprint.md").exists()
    assert (tmp_path / "artifacts/day66-pack/day66-matrix-plan.json").exists()
    assert (tmp_path / "artifacts/day66-pack/day66-kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/day66-pack/day66-execution-log.md").exists()
    assert (tmp_path / "artifacts/day66-pack/day66-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day66-pack/day66-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day66-pack/evidence/day66-execution-summary.json").exists()


def test_day66_strict_fails_without_day65(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/day65-weekly-review-closeout-pack/day65-weekly-review-closeout-summary.json"
    ).unlink()
    assert d66.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_day66_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["day66-integration-expansion2-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 66 integration expansion #2 closeout summary" in capsys.readouterr().out
