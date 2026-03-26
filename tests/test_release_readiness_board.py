from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import release_readiness_board as rrb


def _write_inputs(tmp_path: Path) -> tuple[Path, Path]:
    reliability_summary_path = tmp_path / "reliability-summary.json"
    weekly_review_summary_path = tmp_path / "weekly-review-summary.json"
    reliability_summary_path.write_text(
        json.dumps({"summary": {"reliability_score": 97.5, "gate_status": "pass"}}) + "\n",
        encoding="utf-8",
    )
    weekly_review_summary_path.write_text(
        json.dumps({"summary": {"score": 96.0, "status": "pass"}}) + "\n",
        encoding="utf-8",
    )
    return reliability_summary_path, weekly_review_summary_path


def _write_page(root: Path) -> None:
    path = root / "docs/release-readiness.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rrb._RELEASE_READINESS_DEFAULT_PAGE, encoding="utf-8")


def test_board_builds_json(tmp_path: Path, capsys) -> None:
    reliability_summary_path, weekly_review_summary_path = _write_inputs(tmp_path)
    _write_page(tmp_path)

    rc = rrb.main(
        [
            "--root",
            str(tmp_path),
            "--reliability-summary",
            str(reliability_summary_path.relative_to(tmp_path)),
            "--weekly-review-summary",
            str(weekly_review_summary_path.relative_to(tmp_path)),
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "release-readiness"
    assert out["summary"]["strict_all_green"] is True
    assert out["summary"]["release_score"] >= 90


def test_board_emits_bundle_and_evidence(tmp_path: Path) -> None:
    reliability_summary_path, weekly_review_summary_path = _write_inputs(tmp_path)
    _write_page(tmp_path)

    rc = rrb.main(
        [
            "--root",
            str(tmp_path),
            "--reliability-summary",
            str(reliability_summary_path.relative_to(tmp_path)),
            "--weekly-review-summary",
            str(weekly_review_summary_path.relative_to(tmp_path)),
            "--emit-pack-dir",
            "artifacts/release-readiness-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/release-readiness-pack/evidence",
            "--format",
            "json",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/release-readiness-pack/release-readiness-summary.json").exists()
    assert (tmp_path / "artifacts/release-readiness-pack/release-readiness-scorecard.md").exists()
    assert (tmp_path / "artifacts/release-readiness-pack/release-readiness-checklist.md").exists()
    assert (
        tmp_path / "artifacts/release-readiness-pack/release-readiness-validation-commands.md"
    ).exists()
    assert (
        tmp_path
        / "artifacts/release-readiness-pack/evidence/release-readiness-execution-summary.json"
    ).exists()


def test_cli_dispatch(tmp_path: Path, capsys) -> None:
    reliability_summary_path, weekly_review_summary_path = _write_inputs(tmp_path)
    _write_page(tmp_path)

    rc = cli.main(
        [
            "release-readiness",
            "--root",
            str(tmp_path),
            "--reliability-summary",
            str(reliability_summary_path.relative_to(tmp_path)),
            "--weekly-review-summary",
            str(weekly_review_summary_path.relative_to(tmp_path)),
            "--format",
            "text",
        ]
    )
    assert rc == 0
    assert "Release readiness board" in capsys.readouterr().out


def test_board_supports_weekly_review_payload(tmp_path: Path, capsys) -> None:
    reliability_summary_path = tmp_path / "reliability-summary.json"
    weekly_review_summary_path = tmp_path / "weekly-review-summary.json"
    reliability_summary_path.write_text(
        json.dumps({"summary": {"reliability_score": 92.0, "gate_status": "pass"}}) + "\n",
        encoding="utf-8",
    )
    weekly_review_summary_path.write_text(
        json.dumps({"kpis": {"completion_rate_percent": 95}}) + "\n", encoding="utf-8"
    )
    _write_page(tmp_path)

    rc = rrb.main(
        [
            "--root",
            str(tmp_path),
            "--reliability-summary",
            str(reliability_summary_path.relative_to(tmp_path)),
            "--weekly-review-summary",
            str(weekly_review_summary_path.relative_to(tmp_path)),
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["summary"]["strict_all_green"] is True
    assert out["summary"]["release_score"] == 92.9
