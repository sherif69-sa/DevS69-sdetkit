from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day33_demo_asset as d33


def _seed_repo(root: Path) -> None:

    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-day33-demo-asset.md\nday33-demo-asset\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-33-ultra-upgrade-report.md\nintegrations-day33-demo-asset.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 33 — Demo asset #1:** produce/publish `doctor` workflow short video or GIF.\n"
        "- **Day 34 — Demo asset #2:** produce/publish `repo audit` workflow short video or GIF.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day33-demo-asset.md").write_text(
        d33._DAY33_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/day-33-ultra-upgrade-report.md").write_text("# Day 33 report\n", encoding="utf-8")

    summary = root / "docs/artifacts/day32-release-cadence-pack/day32-release-cadence-summary.json"
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(
        json.dumps(
            {
                "summary": {"activation_score": 98, "strict_pass": True},
                "checks": [{"check_id": "ok", "passed": True}],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    board = root / "docs/artifacts/day32-release-cadence-pack/day32-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "# Day 32 delivery board",
                "- [ ] Day 32 cadence calendar committed",
                "- [ ] Day 32 changelog template committed",
                "- [ ] Day 33 demo asset #1 scope frozen",
                "- [ ] Day 34 demo asset #2 scope frozen",
                "- [ ] Day 35 weekly review KPI frame locked",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_day33_demo_asset_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d33.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day33-demo-asset"
    assert out["summary"]["activation_score"] >= 95


def test_day33_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d33.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day33-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day33-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/day33-pack/day33-demo-asset-summary.json").exists()
    assert (tmp_path / "artifacts/day33-pack/day33-demo-asset-summary.md").exists()
    assert (tmp_path / "artifacts/day33-pack/day33-demo-asset-plan.json").exists()
    assert (tmp_path / "artifacts/day33-pack/day33-demo-script.md").exists()
    assert (tmp_path / "artifacts/day33-pack/day33-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day33-pack/day33-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day33-pack/evidence/day33-execution-summary.json").exists()


def test_day33_strict_fails_when_day32_inputs_missing(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path / "docs/artifacts/day32-release-cadence-pack/day32-release-cadence-summary.json"
    ).unlink()
    rc = d33.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_day33_strict_fails_when_day32_board_is_not_ready(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (tmp_path / "docs/artifacts/day32-release-cadence-pack/day32-delivery-board.md").write_text(
        "- [ ] Day 33 demo asset #1 scope frozen\n", encoding="utf-8"
    )
    rc = d33.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_day33_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["day33-demo-asset", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 33 demo asset summary" in capsys.readouterr().out
