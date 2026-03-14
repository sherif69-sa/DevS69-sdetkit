from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day48_objection_closeout as d48


def _seed_repo(root: Path) -> None:
    (root / "templates/ci/gitlab").mkdir(parents=True, exist_ok=True)
    (root / "templates/ci/jenkins").mkdir(parents=True, exist_ok=True)
    (root / "templates/ci/tekton").mkdir(parents=True, exist_ok=True)
    (root / "docs/roadmap/plans").mkdir(parents=True, exist_ok=True)
    (root / "docs/roadmap/reports").mkdir(parents=True, exist_ok=True)

    (root / "docs/artifacts").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "docs/integrations-objection-closeout.md\nday48-objection-closeout\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "impact-48-big-upgrade-report.md\nintegrations-objection-closeout.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 48 — Objection closeout lock:** convert reliability wins into deterministic objection playbooks.\n"
        "- **Day 49 — Weekly review closeout:** harden the evidence-to-priorities loop.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-objection-closeout.md").write_text(
        d48._DAY48_DEFAULT_PAGE, encoding="utf-8"
    )
    (root / "docs/impact-48-big-upgrade-report.md").write_text("# Day 48 report\n", encoding="utf-8")

    summary = (
        root
        / "docs/artifacts/day47-reliability-closeout-pack/day47-reliability-closeout-summary.json"
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
    board = root / "docs/artifacts/day47-reliability-closeout-pack/day47-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "# Day 47 delivery board",
                "- [ ] Day 47 reliability closeout brief committed",
                "- [ ] Day 47 winners and misses reviewed with owner + backup",
                "- [ ] Day 47 risk register exported",
                "- [ ] Day 47 KPI scorecard snapshot exported",
                "- [ ] Day 48 objection priorities drafted from Day 47 learnings",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_day48_objection_closeout_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d48.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day48-objection-closeout"
    assert out["summary"]["activation_score"] >= 95


def test_day48_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d48.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day48-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day48-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/day48-pack/day48-objection-closeout-summary.json").exists()
    assert (tmp_path / "artifacts/day48-pack/day48-objection-closeout-summary.md").exists()
    assert (tmp_path / "artifacts/day48-pack/day48-objection-plan.md").exists()
    assert (tmp_path / "artifacts/day48-pack/day48-faq-objection-map.csv").exists()
    assert (tmp_path / "artifacts/day48-pack/day48-objection-kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/day48-pack/day48-execution-log.md").exists()
    assert (tmp_path / "artifacts/day48-pack/day48-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day48-pack/day48-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day48-pack/evidence/day48-execution-summary.json").exists()


def test_day48_strict_fails_when_day47_inputs_missing(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (
        tmp_path
        / "docs/artifacts/day47-reliability-closeout-pack/day47-reliability-closeout-summary.json"
    ).unlink()
    rc = d48.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_day48_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["objection-closeout", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 48 objection closeout summary" in capsys.readouterr().out
