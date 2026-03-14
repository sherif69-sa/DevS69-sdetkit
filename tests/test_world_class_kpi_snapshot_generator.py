from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


SCRIPT = Path("scripts/generate_world_class_kpi_snapshot.py")


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *args], text=True, capture_output=True)


def test_generator_writes_snapshot_from_baseline(tmp_path: Path) -> None:
    baseline = {
        "program": "world-class-quality",
        "dashboard": "world-class-kpi",
        "version": "v1",
        "snapshot_window": "rolling-30-impact",
        "review_cadence": "weekly",
        "owners": {"reliability": {"primary": "A", "backup": "B"}},
        "kpis": [
            {
                "id": "mainline_pass_rate",
                "lane": "reliability",
                "metric": "Mainline unit+integration pass rate",
                "target": ">=99%",
            }
        ],
    }
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
    output_path = tmp_path / "snapshot.md"

    proc = _run(
        "--baseline-json",
        str(baseline_path),
        "--snapshot-date",
        "2026-03-20",
        "--output",
        str(output_path),
    )

    assert proc.returncode == 0
    assert output_path.exists()
    text = output_path.read_text(encoding="utf-8")
    assert "World-Class KPI Dashboard Weekly Snapshot — 2026-03-20" in text
    assert "| mainline_pass_rate | reliability |" in text
    assert "| Reliability | A | B |" in text
    assert "KPI coverage: `0/1`" in text


def test_generator_applies_metrics_json_values_and_delta(tmp_path: Path) -> None:
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(
        json.dumps(
            {
                "owners": {"reliability": {"primary": "A", "backup": "B"}},
                "kpis": [
                    {
                        "id": "mainline_pass_rate",
                        "lane": "reliability",
                        "metric": "Mainline unit+integration pass rate",
                        "target": ">=99%",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text(
        json.dumps(
            {
                "mainline_pass_rate": {
                    "current_value": "99.4%",
                    "previous_value": "98.9%",
                    "status": "on_track",
                    "evidence_link": "ci://runs/mainline-pass-rate",
                }
            }
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "snapshot.md"

    proc = _run(
        "--baseline-json",
        str(baseline_path),
        "--metrics-json",
        str(metrics_path),
        "--snapshot-date",
        "2026-03-20",
        "--output",
        str(output_path),
    )

    assert proc.returncode == 0
    text = output_path.read_text(encoding="utf-8")
    assert "| KPI ID | Lane | KPI | Target | Current value | Delta vs previous | Status | Evidence link |" in text
    assert "| mainline_pass_rate | reliability | Mainline unit+integration pass rate | `>=99%` | 99.4% | +0.50% | on_track | ci://runs/mainline-pass-rate |" in text


def test_generator_uses_previous_metrics_file_for_delta(tmp_path: Path) -> None:
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(
        json.dumps(
            {
                "owners": {},
                "kpis": [
                    {
                        "id": "pr_cycle_time",
                        "lane": "velocity",
                        "metric": "PR impact time",
                        "target": "<24h",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    current_metrics_path = tmp_path / "current.json"
    current_metrics_path.write_text(
        json.dumps(
            {
                "pr_cycle_time": {
                    "current_value": "21h",
                    "status": "watch",
                    "evidence_link": "scm://analytics/pr-impact-time",
                }
            }
        ),
        encoding="utf-8",
    )
    previous_metrics_path = tmp_path / "previous.json"
    previous_metrics_path.write_text(
        json.dumps(
            {
                "pr_cycle_time": {
                    "current_value": "23h",
                    "status": "watch",
                    "evidence_link": "scm://analytics/pr-impact-time-prev",
                }
            }
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "snapshot.md"

    proc = _run(
        "--baseline-json",
        str(baseline_path),
        "--metrics-json",
        str(current_metrics_path),
        "--previous-metrics-json",
        str(previous_metrics_path),
        "--output",
        str(output_path),
    )

    assert proc.returncode == 0
    text = output_path.read_text(encoding="utf-8")
    assert "| pr_cycle_time | velocity | PR impact time | `<24h` | 21h | -2.00h | watch | scm://analytics/pr-impact-time |" in text


def test_generator_rejects_invalid_snapshot_date(tmp_path: Path) -> None:
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps({"owners": {}, "kpis": []}), encoding="utf-8")

    proc = _run("--baseline-json", str(baseline_path), "--snapshot-date", "2026/03/20")

    assert proc.returncode != 0
    assert "invalid --snapshot-date" in proc.stderr


def test_generator_rejects_non_object_metrics_payload(tmp_path: Path) -> None:
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps({"owners": {}, "kpis": []}), encoding="utf-8")
    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text(json.dumps(["not-an-object"]), encoding="utf-8")

    proc = _run("--baseline-json", str(baseline_path), "--metrics-json", str(metrics_path))

    assert proc.returncode != 0
    assert "top-level value must be an object" in proc.stderr


def test_generator_uses_na_delta_when_units_do_not_match(tmp_path: Path) -> None:
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(
        json.dumps(
            {
                "owners": {},
                "kpis": [
                    {
                        "id": "pr_cycle_time",
                        "lane": "velocity",
                        "metric": "PR impact time",
                        "target": "<24h",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text(
        json.dumps(
            {
                "pr_cycle_time": {
                    "current_value": "21h",
                    "previous_value": "88%",
                    "status": "watch",
                    "evidence_link": "scm://analytics/pr-impact-time",
                }
            }
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "snapshot.md"

    proc = _run(
        "--baseline-json",
        str(baseline_path),
        "--metrics-json",
        str(metrics_path),
        "--output",
        str(output_path),
    )

    assert proc.returncode == 0
    text = output_path.read_text(encoding="utf-8")
    assert "| pr_cycle_time | velocity | PR impact time | `<24h` | 21h | n/a | watch | scm://analytics/pr-impact-time |" in text


def test_generator_strict_metrics_fails_when_kpis_missing(tmp_path: Path) -> None:
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(
        json.dumps(
            {
                "owners": {},
                "kpis": [
                    {"id": "kpi_a", "lane": "reliability", "metric": "A", "target": ">=1"},
                    {"id": "kpi_b", "lane": "reliability", "metric": "B", "target": ">=1"},
                ],
            }
        ),
        encoding="utf-8",
    )
    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text(
        json.dumps({"kpi_a": {"current_value": "1", "status": "ok", "evidence_link": "x"}}),
        encoding="utf-8",
    )

    proc = _run(
        "--baseline-json",
        str(baseline_path),
        "--metrics-json",
        str(metrics_path),
        "--strict-metrics",
    )

    assert proc.returncode != 0
    assert "strict metrics check failed" in proc.stderr


def test_generator_strict_metrics_passes_with_full_coverage(tmp_path: Path) -> None:
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(
        json.dumps(
            {
                "owners": {},
                "kpis": [
                    {"id": "kpi_a", "lane": "reliability", "metric": "A", "target": ">=1"},
                ],
            }
        ),
        encoding="utf-8",
    )
    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text(
        json.dumps({"kpi_a": {"current_value": "1", "status": "ok", "evidence_link": "x"}}),
        encoding="utf-8",
    )
    output_path = tmp_path / "snapshot.md"

    proc = _run(
        "--baseline-json",
        str(baseline_path),
        "--metrics-json",
        str(metrics_path),
        "--strict-metrics",
        "--output",
        str(output_path),
    )

    assert proc.returncode == 0
    text = output_path.read_text(encoding="utf-8")
    assert "KPI coverage: `1/1`" in text


def test_generator_writes_machine_readable_summary_json(tmp_path: Path) -> None:
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(
        json.dumps(
            {
                "program": "world-class-quality",
                "dashboard": "world-class-kpi",
                "owners": {},
                "kpis": [
                    {"id": "kpi_a", "lane": "reliability", "metric": "A", "target": ">=1"},
                    {"id": "kpi_b", "lane": "velocity", "metric": "B", "target": "<2"},
                ],
            }
        ),
        encoding="utf-8",
    )
    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text(
        json.dumps({"kpi_a": {"current_value": "1", "status": "ok", "evidence_link": "x"}}),
        encoding="utf-8",
    )
    output_path = tmp_path / "snapshot.md"
    summary_path = tmp_path / "summary.json"

    proc = _run(
        "--baseline-json",
        str(baseline_path),
        "--metrics-json",
        str(metrics_path),
        "--output",
        str(output_path),
        "--summary-json",
        str(summary_path),
        "--snapshot-date",
        "2026-03-21",
    )

    assert proc.returncode == 0
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert payload["program"] == "world-class-quality"
    assert payload["snapshot_date"] == "2026-03-21"
    assert payload["baseline_kpi_count"] == 2
    assert payload["provided_kpi_count"] == 1
    assert payload["missing_kpi_ids"] == ["kpi_b"]
    assert payload["kpis"][0]["covered"] is True
    assert payload["kpis"][1]["covered"] is False
    assert payload["kpis"][0]["target_eval"] == "meets_target"
    assert payload["kpis"][1]["target_eval"] == "unknown"
    assert payload["target_eval_counts"] == {"meets_target": 1, "below_target": 0, "above_target": 0, "unknown": 1}


def test_summary_target_eval_flags_below_and_above_target(tmp_path: Path) -> None:
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(
        json.dumps(
            {
                "owners": {},
                "kpis": [
                    {"id": "pass_rate", "lane": "reliability", "metric": "Pass", "target": ">=99%"},
                    {"id": "cycle_time", "lane": "velocity", "metric": "Cycle", "target": "<24h"},
                ],
            }
        ),
        encoding="utf-8",
    )
    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text(
        json.dumps(
            {
                "pass_rate": {"current_value": "98.1%", "status": "watch", "evidence_link": "ci://x"},
                "cycle_time": {"current_value": "30h", "status": "risk", "evidence_link": "scm://y"},
            }
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "snapshot.md"
    summary_path = tmp_path / "summary.json"

    proc = _run(
        "--baseline-json",
        str(baseline_path),
        "--metrics-json",
        str(metrics_path),
        "--output",
        str(output_path),
        "--summary-json",
        str(summary_path),
    )

    assert proc.returncode == 0
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert payload["kpis"][0]["target_eval"] == "below_target"
    assert payload["kpis"][1]["target_eval"] == "above_target"
    assert payload["target_eval_counts"] == {"meets_target": 0, "below_target": 1, "above_target": 1, "unknown": 0}
    assert payload["breach_kpi_ids"] == ["pass_rate", "cycle_time"]


def test_fail_on_target_breach_returns_non_zero(tmp_path: Path) -> None:
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(
        json.dumps(
            {
                "owners": {},
                "kpis": [
                    {"id": "pass_rate", "lane": "reliability", "metric": "Pass", "target": ">=99%"},
                ],
            }
        ),
        encoding="utf-8",
    )
    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text(
        json.dumps({"pass_rate": {"current_value": "95%", "status": "risk", "evidence_link": "ci://x"}}),
        encoding="utf-8",
    )
    output_path = tmp_path / "snapshot.md"

    proc = _run(
        "--baseline-json",
        str(baseline_path),
        "--metrics-json",
        str(metrics_path),
        "--output",
        str(output_path),
        "--fail-on-target-breach",
    )

    assert proc.returncode != 0
    assert "target breach check failed" in proc.stderr
