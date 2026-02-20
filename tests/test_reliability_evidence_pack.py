from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import reliability_evidence_pack as rep


def _write_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    day15 = tmp_path / "day15.json"
    day16 = tmp_path / "day16.json"
    day17 = tmp_path / "day17.json"
    day15.write_text(
        '{"score": 100.0, "strict": true, "checks_passed": 19, "checks_total": 19}\n',
        encoding="utf-8",
    )
    day16.write_text(
        '{"score": 100.0, "strict": true, "checks_passed": 19, "checks_total": 19}\n',
        encoding="utf-8",
    )
    day17.write_text(
        json.dumps(
            {
                "name": "day17-quality-contribution-delta",
                "quality": {"stability_score": 100.0},
                "contributions": {"velocity_score": 92.5},
                "strict_failures": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return day15, day16, day17


def _write_page(root: Path) -> None:
    page = root / "docs/integrations-reliability-evidence-pack.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(rep._DAY18_DEFAULT_PAGE, encoding="utf-8")


def test_day18_pack_builds_json(tmp_path: Path, capsys) -> None:
    day15, day16, day17 = _write_inputs(tmp_path)
    _write_page(tmp_path)

    rc = rep.main(
        [
            "--root",
            str(tmp_path),
            "--day15-summary",
            str(day15.relative_to(tmp_path)),
            "--day16-summary",
            str(day16.relative_to(tmp_path)),
            "--day17-summary",
            str(day17.relative_to(tmp_path)),
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day18-reliability-evidence-pack"
    assert out["summary"]["strict_all_green"] is True
    assert out["summary"]["reliability_score"] >= 90
    assert out["score"] == 100.0


def test_day18_pack_emits_bundle_and_evidence(tmp_path: Path) -> None:
    day15, day16, day17 = _write_inputs(tmp_path)
    _write_page(tmp_path)

    rc = rep.main(
        [
            "--root",
            str(tmp_path),
            "--day15-summary",
            str(day15.relative_to(tmp_path)),
            "--day16-summary",
            str(day16.relative_to(tmp_path)),
            "--day17-summary",
            str(day17.relative_to(tmp_path)),
            "--emit-pack-dir",
            "artifacts/day18-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day18-pack/evidence",
            "--format",
            "json",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/day18-pack/day18-reliability-summary.json").exists()
    assert (tmp_path / "artifacts/day18-pack/day18-reliability-scorecard.md").exists()
    assert (tmp_path / "artifacts/day18-pack/day18-reliability-checklist.md").exists()
    assert (tmp_path / "artifacts/day18-pack/day18-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day18-pack/evidence/day18-execution-summary.json").exists()


def test_day18_write_defaults(tmp_path: Path) -> None:
    day15, day16, day17 = _write_inputs(tmp_path)
    rc = rep.main(
        [
            "--root",
            str(tmp_path),
            "--write-defaults",
            "--day15-summary",
            str(day15.relative_to(tmp_path)),
            "--day16-summary",
            str(day16.relative_to(tmp_path)),
            "--day17-summary",
            str(day17.relative_to(tmp_path)),
            "--format",
            "json",
        ]
    )
    assert rc == 0
    assert (tmp_path / "docs/integrations-reliability-evidence-pack.md").exists()


def test_day18_cli_dispatch(tmp_path: Path, capsys) -> None:
    day15, day16, day17 = _write_inputs(tmp_path)
    _write_page(tmp_path)

    rc = cli.main(
        [
            "reliability-evidence-pack",
            "--root",
            str(tmp_path),
            "--day15-summary",
            str(day15.relative_to(tmp_path)),
            "--day16-summary",
            str(day16.relative_to(tmp_path)),
            "--day17-summary",
            str(day17.relative_to(tmp_path)),
            "--format",
            "text",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "Day 18 reliability evidence pack" in out
