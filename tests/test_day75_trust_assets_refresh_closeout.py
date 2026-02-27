from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day75_trust_assets_refresh_closeout as d75


def _seed_repo(root: Path) -> None:
    (root / "README.md").write_text(
        "docs/integrations-day75-trust-assets-refresh-closeout.md\nday75-trust-assets-refresh-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-75-big-upgrade-report.md\nintegrations-day75-trust-assets-refresh-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 75 — Trust assets refresh:** turn Day 74 outcomes into governance-grade trust proof.\n"
        "- **Day 76 — Contributor recognition board:** publish contributor spotlight and release credits model.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day75-trust-assets-refresh-closeout.md").write_text(
        d75._DAY75_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/day-75-big-upgrade-report.md").write_text("# Day 75 report\n", encoding="utf-8")

    summary = (
        root
        / "docs/artifacts/day74-distribution-scaling-closeout-pack/day74-distribution-scaling-closeout-summary.json"
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
    board = root / "docs/artifacts/day74-distribution-scaling-closeout-pack/day74-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "# Day 74 delivery board",
                "- [ ] Day 74 integration brief committed",
                "- [ ] Day 74 distribution scaling plan committed",
                "- [ ] Day 74 channel controls and assumptions log exported",
                "- [ ] Day 74 KPI scorecard snapshot exported",
                "- [ ] Day 75 trust refresh priorities drafted from Day 74 learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    trust_plan = root / ".day75-trust-assets-refresh-plan.json"
    trust_plan.write_text(
        json.dumps(
            {
                "plan_id": "day75-trust-assets-refresh-001",
                "trust_surfaces": ["README", "SECURITY", "governance"],
                "baseline": {"proof_links": 8, "policy_coverage": 0.67},
                "target": {"proof_links": 14, "policy_coverage": 0.9},
                "confidence": 0.9,
                "owner": "trust-ops",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_day75_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d75.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day75-trust-assets-refresh-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_day75_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d75.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day75-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day75-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (
        tmp_path / "artifacts/day75-pack/day75-trust-assets-refresh-closeout-summary.json"
    ).exists()
    assert (
        tmp_path / "artifacts/day75-pack/day75-trust-assets-refresh-closeout-summary.md"
    ).exists()
    assert (tmp_path / "artifacts/day75-pack/day75-integration-brief.md").exists()
    assert (tmp_path / "artifacts/day75-pack/day75-trust-assets-refresh-plan.md").exists()
    assert (tmp_path / "artifacts/day75-pack/day75-trust-controls-log.json").exists()
    assert (tmp_path / "artifacts/day75-pack/day75-trust-kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/day75-pack/day75-execution-log.md").exists()
    assert (tmp_path / "artifacts/day75-pack/day75-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day75-pack/day75-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day75-pack/evidence/day75-execution-summary.json").exists()


def test_day75_strict_fails_without_day74(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/day74-distribution-scaling-closeout-pack/day74-distribution-scaling-closeout-summary.json"
    ).unlink()
    assert d75.main(["--root", str(tmp_path), "--strict", "--format", "json"]) == 1


def test_day75_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(
        ["day75-trust-assets-refresh-closeout", "--root", str(tmp_path), "--format", "text"]
    )
    assert rc == 0
    assert "Day 75 trust assets refresh closeout summary" in capsys.readouterr().out
