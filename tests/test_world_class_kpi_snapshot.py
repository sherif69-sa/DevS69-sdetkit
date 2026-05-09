from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType


def _load_snapshot_module() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "scripts" / "generate_world_class_kpi_snapshot.py"
    spec = importlib.util.spec_from_file_location("generate_world_class_kpi_snapshot", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


snapshot = _load_snapshot_module()


def _baseline() -> dict[str, object]:
    return {
        "program": "repo quality",
        "dashboard": "world-class kpi dashboard",
        "version": "1",
        "snapshot_window": "weekly",
        "review_cadence": "weekly",
        "owners": {"ci": {"primary": "release", "backup": "quality"}},
        "kpis": [
            {
                "id": "ci_green",
                "lane": "ci",
                "metric": "Green CI",
                "target": ">=99%",
            }
        ],
    }


def test_missing_kpi_values_render_operator_placeholders_without_unresolved_markers(
    tmp_path: Path,
) -> None:
    forbidden_marker = "TO" + "DO"

    markdown = snapshot._render_snapshot(_baseline(), "2026-05-09", {})
    summary = snapshot._build_summary_payload(
        _baseline(),
        "2026-05-09",
        {},
        tmp_path / "snapshot.md",
    )

    assert forbidden_marker not in markdown
    assert forbidden_marker not in json.dumps(summary, sort_keys=True)
    assert snapshot.MISSING_METRIC_VALUE in markdown
    assert snapshot.MISSING_METRIC_STATUS in markdown
    assert snapshot.MISSING_EVIDENCE_LINK in markdown
    assert summary["missing_kpi_ids"] == ["ci_green"]
    assert summary["kpis"][0]["covered"] is False
    assert summary["kpis"][0]["status"] == snapshot.MISSING_METRIC_STATUS


def test_metric_payload_defaults_are_explicit_operational_placeholders(
    tmp_path: Path,
) -> None:
    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text(json.dumps({"ci_green": {}}), encoding="utf-8")

    metrics = snapshot._load_metrics(str(metrics_path), None)

    assert metrics["ci_green"] == {
        "current_value": snapshot.MISSING_METRIC_VALUE,
        "delta": snapshot.MISSING_DELTA_VALUE,
        "status": snapshot.MISSING_METRIC_STATUS,
        "evidence_link": snapshot.MISSING_EVIDENCE_LINK,
    }


def test_rendered_notes_describe_pending_evidence_without_task_markers() -> None:
    forbidden_marker = "TO" + "DO"

    markdown = snapshot._render_snapshot(_baseline(), "2026-05-09", {})

    assert forbidden_marker not in markdown
    assert "Raw export links for CI/SCM/security data should be attached" in markdown


def test_summary_coverage_counts_only_baseline_kpis(tmp_path: Path) -> None:
    metrics = {
        "unknown_metric": {
            "current_value": "100%",
            "delta": "n/a",
            "status": "ok",
            "evidence_link": "artifact.json",
        }
    }

    summary = snapshot._build_summary_payload(
        _baseline(),
        "2026-05-09",
        metrics,
        tmp_path / "snapshot.md",
    )

    assert summary["provided_kpi_count"] == 1
    assert summary["covered_kpi_count"] == 0
    assert summary["coverage_ratio"] == 0.0
    assert summary["missing_metric_count"] == 1
    assert summary["missing_kpi_ids"] == ["ci_green"]
    assert summary["unknown_metric_ids"] == ["unknown_metric"]


def test_markdown_coverage_counts_only_baseline_kpis() -> None:
    metrics = {
        "unknown_metric": {
            "current_value": "100%",
            "delta": "n/a",
            "status": "ok",
            "evidence_link": "artifact.json",
        }
    }

    markdown = snapshot._render_snapshot(_baseline(), "2026-05-09", metrics)

    assert "KPI coverage: `0/1` baseline KPI values covered" in markdown
    assert "Missing KPI values: `1`" in markdown
    assert "Extra KPI values not in baseline: `1`" in markdown


def test_strict_metrics_rejects_unknown_metric_ids() -> None:
    metrics = {
        "ci_green": {
            "current_value": "100%",
            "delta": "n/a",
            "status": "ok",
            "evidence_link": "artifact.json",
        },
        "unknown_metric": {
            "current_value": "100%",
            "delta": "n/a",
            "status": "ok",
            "evidence_link": "artifact.json",
        },
    }

    try:
        snapshot._validate_metrics_completeness(_baseline(), metrics)
    except SystemExit as exc:
        assert "unknown KPI values" in str(exc)
        assert "unknown_metric" in str(exc)
    else:
        raise AssertionError("strict metrics accepted an unknown KPI id")


def test_strict_metrics_accepts_exact_baseline_metric_ids() -> None:
    metrics = {
        "ci_green": {
            "current_value": "100%",
            "delta": "n/a",
            "status": "ok",
            "evidence_link": "artifact.json",
        }
    }

    snapshot._validate_metrics_completeness(_baseline(), metrics)
