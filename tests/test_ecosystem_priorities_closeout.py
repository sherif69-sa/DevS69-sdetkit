from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import ecosystem_priorities_closeout_78 as d78


def _seed_repo(root: Path) -> None:
    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)
    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-ecosystem-priorities-closeout.md\necosystem-priorities-closeout\n",
        encoding="utf-8",
    )
    (root / "docs/index.md").write_text(
        "impact-78-big-upgrade-report.md\nintegrations-ecosystem-priorities-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "Community touchpoint + ecosystem priorities strategy chain\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-ecosystem-priorities-closeout.md").write_text(
        d78._DEFAULT_PAGE_TEMPLATE, encoding="utf-8"
    )

    summary = (
        root
        / "docs/artifacts/community-touchpoint-closeout-pack/community-touchpoint-closeout-summary.json"
    )
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(
        json.dumps(
            {
                "summary": {"activation_score": 97, "strict_pass": True},
                "checks": [{"passed": True}],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    board = (
        root
        / "docs/artifacts/community-touchpoint-closeout-pack/community-touchpoint-delivery-board.md"
    )
    board.write_text(
        "\n".join(["#  delivery board", *["- [ ]  item" for _ in range(5)]]) + "\n",
        encoding="utf-8",
    )

    (root / "docs/roadmap/plans/ecosystem-priorities-plan.json").write_text(
        json.dumps(
            {
                "plan_id": "ecosystem-priorities-001",
                "contributors": ["platform", "docs"],
                "ecosystem_tracks": ["integrations", "playbooks"],
                "baseline": {"score": 63},
                "target": {"score": 88},
                "owner": "ecosystem-eng",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_lane78_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d78.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "ecosystem-priorities-closeout"
    assert out["summary"]["strict_pass"] is True


def test_lane78_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d78.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/ecosystem-priorities-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/ecosystem-priorities-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (
        tmp_path / "artifacts/ecosystem-priorities-pack/ecosystem-priorities-closeout-summary.json"
    ).exists()
    assert (
        tmp_path / "artifacts/ecosystem-priorities-pack/ecosystem-priorities-delivery-board.md"
    ).exists()
    assert (
        tmp_path / "artifacts/ecosystem-priorities-pack/ecosystem-priorities-workstream-ledger.json"
    ).exists()
    assert (
        tmp_path / "artifacts/ecosystem-priorities-pack/ecosystem-priorities-kpi-scorecard.json"
    ).exists()
    assert any((tmp_path / "artifacts/ecosystem-priorities-pack").iterdir())
    assert (
        tmp_path
        / "artifacts/ecosystem-priorities-pack/evidence/ecosystem-priorities-execution-summary.json"
    ).exists()


def test_lane78_strict_fails_without_lane77_summary(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/community-touchpoint-closeout-pack/community-touchpoint-closeout-summary.json"
    ).unlink()
    assert d78.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_lane78_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["ecosystem-priorities-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Ecosystem Priorities Closeout summary" in capsys.readouterr().out
