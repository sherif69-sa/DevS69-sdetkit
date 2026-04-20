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


def test_seed_prerequisites_writes_phase1_baseline_summary_for_phase3_contract(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("", encoding="utf-8")
    rc = phase2_seed_prerequisites.main(["--root", str(tmp_path)])
    assert rc == 0
    summary = tmp_path / "build/phase1-baseline/phase1-baseline-summary.json"
    assert summary.exists()

    payload = __import__("json").loads(summary.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "sdetkit.phase1_baseline.v1"
    assert isinstance(payload["checks"], list) and payload["checks"]
