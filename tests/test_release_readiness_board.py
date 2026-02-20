from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import release_readiness_board as rrb


def _write_inputs(tmp_path: Path) -> tuple[Path, Path]:
    day18 = tmp_path / "day18.json"
    day14 = tmp_path / "day14.json"
    day18.write_text(
        json.dumps({"summary": {"reliability_score": 97.5, "gate_status": "pass"}}) + "\n",
        encoding="utf-8",
    )
    day14.write_text(
        json.dumps({"summary": {"score": 96.0, "status": "pass"}}) + "\n",
        encoding="utf-8",
    )
    return day18, day14


def _write_page(root: Path) -> None:
    path = root / "docs/integrations-release-readiness-board.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rrb._DAY19_DEFAULT_PAGE, encoding="utf-8")


def test_day19_board_builds_json(tmp_path: Path, capsys) -> None:
    day18, day14 = _write_inputs(tmp_path)
    _write_page(tmp_path)

    rc = rrb.main(
        [
            "--root",
            str(tmp_path),
            "--day18-summary",
            str(day18.relative_to(tmp_path)),
            "--day14-summary",
            str(day14.relative_to(tmp_path)),
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day19-release-readiness-board"
    assert out["summary"]["strict_all_green"] is True
    assert out["summary"]["release_score"] >= 90


def test_day19_board_emits_bundle_and_evidence(tmp_path: Path) -> None:
    day18, day14 = _write_inputs(tmp_path)
    _write_page(tmp_path)

    rc = rrb.main(
        [
            "--root",
            str(tmp_path),
            "--day18-summary",
            str(day18.relative_to(tmp_path)),
            "--day14-summary",
            str(day14.relative_to(tmp_path)),
            "--emit-pack-dir",
            "artifacts/day19-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day19-pack/evidence",
            "--format",
            "json",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/day19-pack/day19-release-readiness-summary.json").exists()
    assert (tmp_path / "artifacts/day19-pack/day19-release-readiness-scorecard.md").exists()
    assert (tmp_path / "artifacts/day19-pack/day19-release-readiness-checklist.md").exists()
    assert (tmp_path / "artifacts/day19-pack/day19-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day19-pack/evidence/day19-execution-summary.json").exists()


def test_day19_cli_dispatch(tmp_path: Path, capsys) -> None:
    day18, day14 = _write_inputs(tmp_path)
    _write_page(tmp_path)

    rc = cli.main(
        [
            "release-readiness-board",
            "--root",
            str(tmp_path),
            "--day18-summary",
            str(day18.relative_to(tmp_path)),
            "--day14-summary",
            str(day14.relative_to(tmp_path)),
            "--format",
            "text",
        ]
    )
    assert rc == 0
    assert "Day 19 release readiness board" in capsys.readouterr().out


def test_day19_board_supports_day14_kpis_payload(tmp_path: Path, capsys) -> None:
    day18 = tmp_path / "day18.json"
    day14 = tmp_path / "day14.json"
    day18.write_text(
        json.dumps({"summary": {"reliability_score": 92.0, "gate_status": "pass"}}) + "\n",
        encoding="utf-8",
    )
    day14.write_text(json.dumps({"kpis": {"completion_rate_percent": 95}}) + "\n", encoding="utf-8")
    _write_page(tmp_path)

    rc = rrb.main(
        [
            "--root",
            str(tmp_path),
            "--day18-summary",
            str(day18.relative_to(tmp_path)),
            "--day14-summary",
            str(day14.relative_to(tmp_path)),
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["inputs"]["day14"]["status"] == "pass"
    assert out["summary"]["release_score"] == 92.9
