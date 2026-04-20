from __future__ import annotations

from scripts import check_phase6_metrics_contract as contract


def test_metrics_drift_alerts_are_sorted_and_thresholded() -> None:
    payload = {"metrics_contract": {"linkage_guards": ["g1"]}}
    snapshot = {"missing_kpis": ["kpi_b", "kpi_a"], "freshness_status": "stale"}
    scorecard = {"commercialization_status": "partial"}

    drift = contract._build_metrics_drift_alerts(payload, snapshot, scorecard, drift_threshold=2)

    assert drift["alerts"] == sorted(drift["alerts"])
    assert drift["drift_score"] == 3
    assert drift["drift_status"] == "drift"


def test_metrics_drift_alerts_missing_linkage_guards_raises_drift_signal() -> None:
    payload = {"metrics_contract": {"linkage_guards": []}}
    snapshot = {"missing_kpis": [], "freshness_status": "fresh"}
    scorecard = {"commercialization_status": "ready"}

    drift = contract._build_metrics_drift_alerts(payload, snapshot, scorecard, drift_threshold=1)

    assert "linkage_guards_missing" in drift["alerts"]
    assert drift["drift_status"] == "drift"
