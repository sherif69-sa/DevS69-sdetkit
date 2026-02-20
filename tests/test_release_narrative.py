from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli
from sdetkit import release_narrative as rn


def _write_day19_summary(path: Path, gate_status: str = "pass", score: float = 96.4) -> Path:
    summary = path / "day19.json"
    summary.write_text(
        json.dumps(
            {
                "summary": {"release_score": score, "gate_status": gate_status},
                "recommendations": ["Track one follow-up risk in backlog."],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return summary


def _write_day20_page(root: Path) -> None:
    path = root / "docs/integrations-release-narrative.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rn._DAY20_DEFAULT_PAGE, encoding="utf-8")


def test_day20_release_narrative_json(tmp_path: Path, capsys) -> None:
    summary = _write_day19_summary(tmp_path)
    _write_day20_page(tmp_path)

    rc = rn.main(
        [
            "--root",
            str(tmp_path),
            "--day19-summary",
            str(summary.relative_to(tmp_path)),
            "--format",
            "json",
        ]
    )
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["name"] == "day20-release-narrative"
    assert out["summary"]["readiness_label"] == "ready"
    assert out["score"] == 100.0


def test_day20_release_narrative_emit_pack_and_execute(tmp_path: Path) -> None:
    summary = _write_day19_summary(tmp_path)
    _write_day20_page(tmp_path)

    rc = rn.main(
        [
            "--root",
            str(tmp_path),
            "--day19-summary",
            str(summary.relative_to(tmp_path)),
            "--emit-pack-dir",
            "artifacts/day20-pack",
            "--execute",
            "--evidence-dir",
            "artifacts/day20-pack/evidence",
            "--format",
            "json",
        ]
    )
    assert rc == 0
    assert (tmp_path / "artifacts/day20-pack/day20-release-narrative-summary.json").exists()
    assert (tmp_path / "artifacts/day20-pack/day20-release-narrative.md").exists()
    assert (tmp_path / "artifacts/day20-pack/day20-audience-blurbs.md").exists()
    assert (tmp_path / "artifacts/day20-pack/day20-channel-posts.md").exists()
    assert (tmp_path / "artifacts/day20-pack/day20-validation-commands.md").exists()
    assert (tmp_path / "artifacts/day20-pack/evidence/day20-execution-summary.json").exists()


def test_day20_release_narrative_strict_gate_fails_when_not_ready(tmp_path: Path) -> None:
    summary = _write_day19_summary(tmp_path, gate_status="warn", score=83)
    _write_day20_page(tmp_path)

    rc = rn.main(
        [
            "--root",
            str(tmp_path),
            "--day19-summary",
            str(summary.relative_to(tmp_path)),
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 1


def test_day20_release_narrative_strict_gate_fails_when_docs_contract_missing(
    tmp_path: Path,
) -> None:
    summary = _write_day19_summary(tmp_path)
    path = tmp_path / "docs/integrations-release-narrative.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# Release narrative (Day 20)\n", encoding="utf-8")

    rc = rn.main(
        [
            "--root",
            str(tmp_path),
            "--day19-summary",
            str(summary.relative_to(tmp_path)),
            "--format",
            "json",
            "--strict",
        ]
    )
    assert rc == 1


def test_day20_cli_dispatch(tmp_path: Path, capsys) -> None:
    summary = _write_day19_summary(tmp_path)
    _write_day20_page(tmp_path)

    rc = cli.main(
        [
            "release-narrative",
            "--root",
            str(tmp_path),
            "--day19-summary",
            str(summary.relative_to(tmp_path)),
            "--format",
            "text",
        ]
    )
    assert rc == 0
    assert "Day 20 release narrative" in capsys.readouterr().out
