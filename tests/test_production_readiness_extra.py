from __future__ import annotations

import json
from pathlib import Path

from sdetkit import production_readiness as pr


def test_render_markdown_with_remediation(tmp_path: Path) -> None:
    payload = pr.build_production_readiness_summary(tmp_path)
    md = pr._render_markdown(payload)
    assert "Remediation priorities" in md


def test_main_emit_pack_and_strict_failure(tmp_path: Path, capsys) -> None:
    out = tmp_path / "pack"
    rc = pr.main(
        ["--root", str(tmp_path), "--format", "json", "--emit-pack-dir", str(out), "--strict"]
    )
    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["strict_pass"] is False
    assert (out / "production-readiness-summary.json").exists()
    assert (out / "production-readiness-report.md").exists()


def test_render_text_includes_check_status_lines(tmp_path: Path) -> None:
    payload = pr.build_production_readiness_summary(tmp_path)

    text = pr._render_text(payload)

    assert text.startswith("production-readiness\n")
    assert "checks:" in text
    assert "- [FAIL] governance_core_docs" in text


def test_main_markdown_and_text_output_modes(tmp_path: Path, capsys) -> None:
    markdown_rc = pr.main(["--root", str(tmp_path), "--format", "markdown"])
    markdown_out = capsys.readouterr().out

    assert markdown_rc == 0
    assert markdown_out.startswith("# Production readiness report")

    text_rc = pr.main(["--root", str(tmp_path), "--format", "text"])
    text_out = capsys.readouterr().out

    assert text_rc == 0
    assert text_out.startswith("production-readiness")


def test_phase_boost_check_accepts_supported_blueprint_variants(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir(parents=True)
    (tmp_path / "docs/production-s-class-90-day-boost.md").write_text(
        "# phase boost\n", encoding="utf-8"
    )

    payload = pr.build_production_readiness_summary(tmp_path)

    phase_boost = next(
        c for c in payload["checks"] if c["check_id"] == "phase_boost_blueprint_present"
    )
    assert phase_boost["passed"] is True
    assert phase_boost["evidence"] == "docs/production-s-class-90-day-boost.md"
