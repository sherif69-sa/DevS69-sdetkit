from __future__ import annotations

from pathlib import Path

from scripts import check_phase6_metrics_contract as contract


def test_commercial_scorecard_missing_required_evidence_surfaces_is_partial(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    payload = {
        "commercialization_contract": {
            "required_evidence_surfaces": ["build/a.json", "build/b.json"],
            "reporting_audience": ["operators"],
            "auditability_status": "partial",
        }
    }

    scorecard = contract._build_commercial_scorecard(payload)

    assert scorecard["commercialization_status"] == "partial"
    assert scorecard["reporting_readiness"] == "partial"
    assert scorecard["blockers"] == sorted(scorecard["blockers"])
    assert scorecard["recommended_actions"]


def test_commercial_scorecard_missing_reporting_audience_is_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "build").mkdir(parents=True, exist_ok=True)
    (tmp_path / "build/a.json").write_text("{}\n", encoding="utf-8")

    payload = {
        "commercialization_contract": {
            "required_evidence_surfaces": ["build/a.json"],
            "reporting_audience": [],
            "auditability_status": "partial",
        }
    }

    scorecard = contract._build_commercial_scorecard(payload)

    assert scorecard["commercialization_status"] == "ready"
    assert scorecard["reporting_readiness"] == "missing"
