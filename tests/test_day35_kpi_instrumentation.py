from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day35_kpi_instrumentation as d35


def _seed_repo(root: Path) -> None:

    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-day35-kpi-instrumentation.md\nday35-kpi-instrumentation\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-35-big-upgrade-report.md\nintegrations-day35-kpi-instrumentation.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 35 — KPI instrumentation:** close attribution gaps and lock weekly review metrics.\n"
        "- **Day 36 — Demo asset #3:** produce/publish `security gate` workflow short video or GIF.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day35-kpi-instrumentation.md").write_text(
        d35._DAY35_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/day-35-big-upgrade-report.md").write_text("# Day 35 report\n", encoding="utf-8")

    summary = root / "docs/artifacts/day34-demo-asset2-pack/day34-demo-asset2-summary.json"
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
    board = root / "docs/artifacts/day34-demo-asset2-pack/day34-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "# Day 34 delivery board",
                "- [ ] Day 34 script draft committed",
                "- [ ] Day 34 first cut rendered",
                "- [ ] Day 34 final cut + caption copy approved",
                "- [ ] Day 35 KPI instrumentation backlog pre-scoped",
                "- [ ] Day 36 community distribution plan updated",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_day35_kpi_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d35.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day35-kpi-instrumentation"
    assert out["summary"]["activation_score"] >= 95


def test_day35_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d35.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day35-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day35-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/day35-pack/day35-kpi-instrumentation-summary.json").exists()
    assert (tmp_path / "artifacts/day35-pack/day35-kpi-instrumentation-summary.md").exists()
    assert (tmp_path / "artifacts/day35-pack/day35-kpi-dictionary.csv").exists()
    assert (tmp_path / "artifacts/day35-pack/day35-alert-policy.md").exists()
    assert (tmp_path / "artifacts/day35-pack/day35-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day35-pack/day35-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day35-pack/evidence/day35-execution-summary.json").exists()


def test_day35_strict_fails_when_day34_inputs_missing(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (tmp_path / "docs/artifacts/day34-demo-asset2-pack/day34-demo-asset2-summary.json").unlink()
    rc = d35.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_day35_strict_fails_when_day34_board_is_not_ready(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (tmp_path / "docs/artifacts/day34-demo-asset2-pack/day34-delivery-board.md").write_text(
        "- [ ] Day 35 KPI instrumentation backlog pre-scoped\n", encoding="utf-8"
    )
    rc = d35.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_day35_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["day35-kpi-instrumentation", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 35 KPI instrumentation summary" in capsys.readouterr().out
