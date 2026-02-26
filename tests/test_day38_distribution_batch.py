from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day38_distribution_batch as d38


def _seed_repo(root: Path) -> None:
    (root / "README.md").write_text(
        "docs/integrations-day38-distribution-batch.md\nday38-distribution-batch\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-38-big-upgrade-report.md\nintegrations-day38-distribution-batch.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 38 — Distribution batch #1:** publish coordinated posts linking demo assets to docs.\n"
        "- **Day 39 — Playbook post #1:** publish Repo Reliability Playbook article #1.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day38-distribution-batch.md").write_text(d38._DAY38_DEFAULT_PAGE, encoding="utf-8")
    (root / "docs/day-38-big-upgrade-report.md").write_text("# Day 38 report\n", encoding="utf-8")

    summary = root / "docs/artifacts/day37-experiment-lane-pack/day37-experiment-lane-summary.json"
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
    board = root / "docs/artifacts/day37-experiment-lane-pack/day37-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "# Day 37 delivery board",
                "- [ ] Day 37 experiment matrix committed",
                "- [ ] Day 37 hypothesis brief reviewed with owner + backup",
                "- [ ] Day 37 scorecard snapshot exported",
                "- [ ] Day 38 distribution batch actions selected from winners",
                "- [ ] Day 38 fallback plan documented for losing variants",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_day38_distribution_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d38.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day38-distribution-batch"
    assert out["summary"]["activation_score"] >= 95


def test_day38_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d38.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day38-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day38-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/day38-pack/day38-distribution-batch-summary.json").exists()
    assert (tmp_path / "artifacts/day38-pack/day38-distribution-batch-summary.md").exists()
    assert (tmp_path / "artifacts/day38-pack/day38-channel-plan.csv").exists()
    assert (tmp_path / "artifacts/day38-pack/day38-post-copy.md").exists()
    assert (tmp_path / "artifacts/day38-pack/day38-kpi-scorecard.json").exists()
    assert (tmp_path / "artifacts/day38-pack/day38-execution-log.md").exists()
    assert (tmp_path / "artifacts/day38-pack/day38-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day38-pack/day38-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day38-pack/evidence/day38-execution-summary.json").exists()


def test_day38_strict_fails_when_day37_inputs_missing(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (tmp_path / "docs/artifacts/day37-experiment-lane-pack/day37-experiment-lane-summary.json").unlink()
    rc = d38.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_day38_strict_fails_when_day37_board_is_not_ready(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (tmp_path / "docs/artifacts/day37-experiment-lane-pack/day37-delivery-board.md").write_text(
        "- [ ] Day 38 distribution batch actions selected from winners\n", encoding="utf-8"
    )
    rc = d38.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_day38_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["day38-distribution-batch", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 38 distribution batch summary" in capsys.readouterr().out
