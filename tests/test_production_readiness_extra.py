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
