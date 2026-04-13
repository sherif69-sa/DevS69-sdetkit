from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    root = Path(__file__).resolve().parents[1]
    return subprocess.run(
        [sys.executable, "scripts/adoption_scorecard.py", *args],
        cwd=root,
        text=True,
        capture_output=True,
        env={"PYTHONPATH": str(root / "src")},
    )


def test_adoption_scorecard_reports_excellent_when_all_inputs_ok(tmp_path: Path) -> None:
    golden = tmp_path / "golden.json"
    drift = tmp_path / "drift.json"
    legacy = tmp_path / "legacy.json"
    out = tmp_path / "score.json"
    golden.write_text(
        json.dumps(
            {
                "overall_ok": True,
                "freshness_age_seconds": 100,
                "checks": {"gate_release": {"ok": True}},
            }
        ),
        encoding="utf-8",
    )
    drift.write_text(json.dumps({"overall_ok": True}), encoding="utf-8")
    legacy.write_text(json.dumps({"overall_ok": True, "count": 0}), encoding="utf-8")
    proc = _run(
        "--golden",
        str(golden),
        "--drift",
        str(drift),
        "--legacy",
        str(legacy),
        "--out",
        str(out),
        "--format",
        "json",
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["schema_version"] == "2"
    assert payload["score"] >= 80
    assert payload["band"] in {"strong", "excellent"}
    assert sorted(payload["dimensions"]) == ["onboarding", "ops", "quality", "release"]


def test_adoption_scorecard_reports_early_when_inputs_missing(tmp_path: Path) -> None:
    out = tmp_path / "score.json"
    proc = _run("--out", str(out), "--format", "json")
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["score"] < 40
    assert payload["band"] == "early"


def test_adoption_scorecard_release_trend_and_backwards_compatible_dimensions(
    tmp_path: Path,
) -> None:
    golden = tmp_path / "golden.json"
    drift = tmp_path / "drift.json"
    legacy = tmp_path / "legacy.json"
    release_history = tmp_path / "release-history.json"
    out = tmp_path / "score.json"
    golden.write_text(
        json.dumps({"overall_ok": True, "checks": {"gate_release": {"ok": True}}}), encoding="utf-8"
    )
    drift.write_text(json.dumps({"overall_ok": False}), encoding="utf-8")
    legacy.write_text(json.dumps({"overall_ok": False, "count": 6}), encoding="utf-8")
    release_history.write_text(json.dumps({"series": [30, 40, 60, 85]}), encoding="utf-8")

    proc = _run(
        "--golden",
        str(golden),
        "--drift",
        str(drift),
        "--legacy",
        str(legacy),
        "--release-history",
        str(release_history),
        "--release-window",
        "4",
        "--out",
        str(out),
        "--format",
        "json",
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["graded_dimensions"]["release"] >= 90
    assert payload["dimensions"]["release"] <= 25
    assert payload["signals"]["release"]["trend_delta"] == 55.0


def test_adoption_scorecard_legacy_baseline_and_custom_weights(tmp_path: Path) -> None:
    golden = tmp_path / "golden.json"
    drift = tmp_path / "drift.json"
    legacy = tmp_path / "legacy.json"
    legacy_baseline = tmp_path / "legacy-baseline.json"
    test_signal = tmp_path / "test-signal.json"
    out = tmp_path / "score.json"

    golden.write_text(
        json.dumps({"overall_ok": False, "checks": {"gate_release": {"ok": False}}}),
        encoding="utf-8",
    )
    drift.write_text(json.dumps({"overall_ok": True}), encoding="utf-8")
    legacy.write_text(json.dumps({"overall_ok": False, "count": 5}), encoding="utf-8")
    legacy_baseline.write_text(json.dumps({"count": 20}), encoding="utf-8")
    test_signal.write_text(json.dumps({"pass_rate": 0.8}), encoding="utf-8")

    proc = _run(
        "--golden",
        str(golden),
        "--drift",
        str(drift),
        "--legacy",
        str(legacy),
        "--legacy-baseline",
        str(legacy_baseline),
        "--test-signal",
        str(test_signal),
        "--weight-onboarding",
        "0.1",
        "--weight-release",
        "0.1",
        "--weight-ops",
        "0.5",
        "--weight-quality",
        "0.3",
        "--out",
        str(out),
        "--format",
        "json",
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["signals"]["ops"]["legacy_reduction_pct"] == 75.0
    assert payload["weights"]["ops"] == 0.5
    assert payload["score"] >= 55
