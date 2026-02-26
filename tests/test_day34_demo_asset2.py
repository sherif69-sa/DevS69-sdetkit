from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import day34_demo_asset2 as d34


def _seed_repo(root: Path) -> None:
    (root / "README.md").write_text(
        "docs/integrations-day34-demo-asset2.md\nday34-demo-asset2\n",
        encoding="utf-8",
    )
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "day-34-ultra-upgrade-report.md\nintegrations-day34-demo-asset2.md\n",
        encoding="utf-8",
    )
    (root / "docs/top-10-github-strategy.md").write_text(
        "- **Day 34 — Demo asset #2:** produce/publish `repo audit` workflow short video or GIF.\n"
        "- **Day 35 — KPI instrumentation:** tighten signal loops and close attribution gaps.\n",
        encoding="utf-8",
    )
    (root / "docs/integrations-day34-demo-asset2.md").write_text(d34._DAY34_DEFAULT_PAGE, encoding="utf-8")
    (root / "docs/day-34-ultra-upgrade-report.md").write_text("# Day 34 report\n", encoding="utf-8")

    summary = root / "docs/artifacts/day33-demo-asset-pack/day33-demo-asset-summary.json"
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
    board = root / "docs/artifacts/day33-demo-asset-pack/day33-delivery-board.md"
    board.write_text(
        "\n".join(
            [
                "# Day 33 delivery board",
                "- [ ] Day 33 script draft committed",
                "- [ ] Day 33 first cut rendered",
                "- [ ] Day 33 final cut + caption copy approved",
                "- [ ] Day 34 demo asset #2 backlog pre-scoped",
                "- [ ] Day 35 KPI instrumentation plan updated",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_day34_demo_asset2_json(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = d34.main(["--root", str(tmp_path), "--format", "json", "--strict"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day34-demo-asset2"
    assert out["summary"]["activation_score"] >= 95


def test_day34_emit_pack_and_execute(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    rc = d34.main(
        [
            "--root",
            str(tmp_path),
            "--emit-pack-dir",
            "artifacts/day34-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day34-pack/evidence",
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/day34-pack/day34-demo-asset2-summary.json").exists()
    assert (tmp_path / "artifacts/day34-pack/day34-demo-asset2-summary.md").exists()
    assert (tmp_path / "artifacts/day34-pack/day34-demo-asset2-plan.json").exists()
    assert (tmp_path / "artifacts/day34-pack/day34-demo-script.md").exists()
    assert (tmp_path / "artifacts/day34-pack/day34-delivery-board.md").exists()
    assert (tmp_path / "artifacts/day34-pack/day34-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day34-pack/evidence/day34-execution-summary.json").exists()


def test_day34_strict_fails_when_day33_inputs_missing(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (tmp_path / "docs/artifacts/day33-demo-asset-pack/day33-demo-asset-summary.json").unlink()
    rc = d34.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_day34_strict_fails_when_day33_board_is_not_ready(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    (tmp_path / "docs/artifacts/day33-demo-asset-pack/day33-delivery-board.md").write_text(
        "- [ ] Day 34 demo asset #2 backlog pre-scoped\n", encoding="utf-8"
    )
    rc = d34.main(["--root", str(tmp_path), "--strict", "--format", "json"])
    assert rc == 1


def test_day34_cli_dispatch(tmp_path: Path, capsys) -> None:
    _seed_repo(tmp_path)
    rc = cli.main(["day34-demo-asset2", "--root", str(tmp_path), "--format", "text"])
    assert rc == 0
    assert "Day 34 demo asset #2 summary" in capsys.readouterr().out
