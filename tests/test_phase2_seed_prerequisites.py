from __future__ import annotations

from pathlib import Path

from scripts import phase2_seed_prerequisites


def test_seed_prerequisites_writes_required_inputs(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("", encoding="utf-8")
    (tmp_path / "docs/index.md").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs/index.md").write_text("", encoding="utf-8")
    rc = phase2_seed_prerequisites.main(["--root", str(tmp_path)])
    assert rc == 0
    assert (tmp_path / "docs/artifacts/phase1-wrap-pack/phase1-wrap-summary.json").exists()
    assert (
        tmp_path / "docs/artifacts/kpi-deep-audit-closeout-pack/kpi-deep-audit-closeout-summary.json"
    ).exists()
    assert (
        tmp_path / "docs/artifacts/phase3-preplan-closeout-pack/phase3-preplan-closeout-summary.json"
    ).exists()
