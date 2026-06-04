from __future__ import annotations

from pathlib import Path

from scripts import release_readiness_seed_prerequisites


def test_seed_prerequisites_writes_required_inputs(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("", encoding="utf-8")
    (tmp_path / "docs/index.md").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs/index.md").write_text("", encoding="utf-8")
    rc = release_readiness_seed_prerequisites.main(["--root", str(tmp_path)])
    assert rc == 0
    assert (tmp_path / "docs/artifacts/baseline-wrap-pack/baseline-wrap-summary.json").exists()
    assert (
        tmp_path
        / "docs/artifacts/kpi-deep-audit-completion report-pack/kpi-deep-audit-completion report-summary.json"
    ).exists()
    assert (
        tmp_path
        / "docs/artifacts/platform-readiness-preplan-completion-report-pack/platform-readiness-preplan-completion-report-summary.json"
    ).exists()


def test_seed_prerequisites_writes_baseline_baseline_summary_for_phase3_contract(
    tmp_path: Path,
) -> None:
    (tmp_path / "README.md").write_text("", encoding="utf-8")
    rc = release_readiness_seed_prerequisites.main(["--root", str(tmp_path)])
    assert rc == 0
    summary = tmp_path / "build/baseline/baseline-summary.json"
    assert summary.exists()

    payload = __import__("json").loads(summary.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "sdetkit.baseline_baseline.v1"
    assert isinstance(payload["checks"], list) and payload["checks"]
