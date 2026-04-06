from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import demo_asset_33 as d33


def _seed_repo(root: Path) -> None:

    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)

    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)

    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-demo-asset.md\ndemo-asset\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "impact-33-ultra-upgrade-report.md\nintegrations-demo-asset.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- ** — Demo asset #1:** produce/publish `doctor` workflow short video or GIF.\n"
        "- ** — Demo asset #2:** produce/publish `repo audit` workflow short video or GIF.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-demo-asset.md").write_text(
        d33._DEFAULT_PAGE_TEMPLATE, encoding="utf-8"
    )
    (root / "docs/impact-33-ultra-upgrade-report.md").write_text("#  report\n", encoding="utf-8")

    summary = root / "docs/artifacts/release-cadence-pack/release-cadence-summary.json"
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
    board = root / "docs/artifacts/release-cadence-pack/release-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "#  delivery board",
                "- [ ]  cadence calendar committed",
                "- [ ]  changelog template committed",
                "- [ ]  demo asset #1 scope frozen",
                "- [ ]  demo asset #2 scope frozen",
                "- [ ]  weekly review KPI frame locked",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_demo_asset_demo_asset_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d33.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "demo-asset"
    assert out["summary"]["activation_score"] >= 95


def test_demo_asset_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d33.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/demo-asset-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/demo-asset-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/demo-asset-pack/demo-asset-summary.json").exists()
    assert (tmp_path / "artifacts/demo-asset-pack/demo-asset-summary.md").exists()
    assert (tmp_path / "artifacts/demo-asset-pack/demo-asset-plan.json").exists()
    assert (tmp_path / "artifacts/demo-asset-pack/demo-script.md").exists()
    assert (tmp_path / "artifacts/demo-asset-pack/demo-delivery-board.md").exists()
    assert (tmp_path / "artifacts/demo-asset-pack/demo-validation-commands.md").exists()
    assert (tmp_path / "artifacts/demo-asset-pack/evidence/demo-execution-summary.json").exists()


def test_demo_asset_strict_fails_when_lane32_inputs_missing(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (tmp_path / "docs/artifacts/release-cadence-pack/release-cadence-summary.json").unlink()
    rc = d33.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_demo_asset_strict_fails_when_lane32_board_is_not_ready(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (tmp_path / "docs/artifacts/release-cadence-pack/release-delivery-board.md").write_text(
        "- [ ]  demo asset #1 scope frozen\n", encoding="utf-8"
    )
    rc = d33.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_demo_asset_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["demo-asset", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert " demo asset summary" in capsys.readouterr().out
