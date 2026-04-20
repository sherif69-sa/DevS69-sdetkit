from __future__ import annotations

from scripts import check_phase6_metrics_contract as contract


def test_kpi_snapshot_deterministic_sort_and_missing_kpis() -> None:
    payload = {
        "metric_snapshots": [
            {"metric_id": "kpi_b", "status": "green"},
            {"metric_id": "kpi_a", "status": "green"},
        ],
        "metrics_contract": {
            "required_kpis": ["kpi_c", "kpi_a"],
            "freshness_sla_days": 7,
            "linkage_guards": ["g1"],
        },
    }

    snapshot = contract._build_kpi_snapshot(payload)

    assert snapshot["required_kpis"] == ["kpi_a", "kpi_c"]
    assert snapshot["observed_kpis"] == ["kpi_a", "kpi_b"]
    assert snapshot["missing_kpis"] == ["kpi_c"]


def test_kpi_snapshot_freshness_status_stale_unknown_and_fresh() -> None:
    stale = contract._build_kpi_snapshot(
        {
            "metric_snapshots": [{"metric_id": "kpi_a", "status": "red"}],
            "metrics_contract": {
                "required_kpis": ["kpi_a"],
                "freshness_sla_days": 7,
                "linkage_guards": ["g1"],
            },
        }
    )
    unknown = contract._build_kpi_snapshot(
        {
            "metric_snapshots": [],
            "metrics_contract": {
                "required_kpis": ["kpi_a"],
                "freshness_sla_days": 7,
                "linkage_guards": ["g1"],
            },
        }
    )
    fresh = contract._build_kpi_snapshot(
        {
            "metric_snapshots": [{"metric_id": "kpi_a", "status": "green"}],
            "metrics_contract": {
                "required_kpis": ["kpi_a"],
                "freshness_sla_days": 7,
                "linkage_guards": ["g1"],
            },
        }
    )

    assert stale["freshness_status"] == "stale"
    assert unknown["freshness_status"] == "unknown"
    assert fresh["freshness_status"] == "fresh"
