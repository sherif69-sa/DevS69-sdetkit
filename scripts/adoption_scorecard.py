from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return raw if isinstance(raw, dict) else None


def _bool_score(value: bool) -> int:
    return 25 if value else 0


def _clamp(value: float, *, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _round_int(value: float) -> int:
    return int(round(value))


def _load_history_series(path: Path | None) -> list[float]:
    if path is None:
        return []
    payload = _load_json(path)
    if payload is None:
        return []
    series_raw = payload.get("series")
    if not isinstance(series_raw, list):
        return []
    series: list[float] = []
    for item in series_raw:
        if isinstance(item, bool):
            series.append(100.0 if item else 0.0)
        elif isinstance(item, (int, float)):
            series.append(_clamp(float(item)))
        elif isinstance(item, dict):
            score = item.get("score")
            if isinstance(score, (int, float)):
                series.append(_clamp(float(score)))
            elif item.get("overall_ok") is True:
                series.append(100.0)
            elif item.get("overall_ok") is False:
                series.append(0.0)
    return series


def _trend_grade(series: list[float], window: int) -> tuple[int, float]:
    if not series:
        return 50, 0.0
    clipped = series[-max(window, 2) :]
    first = clipped[0]
    last = clipped[-1]
    delta = last - first
    if delta >= 20:
        return 100, delta
    if delta >= 0:
        return 75, delta
    if delta > -20:
        return 40, delta
    return 10, delta


def _normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    total = sum(weights.values())
    if total <= 0:
        return {"onboarding": 0.25, "release": 0.25, "ops": 0.25, "quality": 0.25}
    return {k: v / total for k, v in weights.items()}


def _build_scorecard(
    golden: dict[str, Any] | None,
    drift: dict[str, Any] | None,
    legacy: dict[str, Any] | None,
    *,
    test_signal: dict[str, Any] | None,
    release_history: list[float],
    release_window: int,
    legacy_baseline: dict[str, Any] | None,
    stale_after_seconds: int,
    weights: dict[str, float],
) -> dict[str, Any]:
    onboarding_ok = bool(golden and golden.get("overall_ok") is True)
    release_ok = bool(
        golden
        and isinstance(golden.get("checks"), dict)
        and isinstance(golden["checks"].get("gate_release"), dict)
        and golden["checks"]["gate_release"].get("ok") is True
    )
    quality_ok = bool(drift and drift.get("overall_ok") is True)
    ops_ok = bool(legacy and legacy.get("overall_ok") is True)

    freshness_score = 50.0
    if golden is not None:
        age_seconds = golden.get("freshness_age_seconds")
        if isinstance(age_seconds, (int, float)):
            freshness_score = _clamp(
                100.0 - (float(age_seconds) / max(stale_after_seconds, 1) * 100.0)
            )
        elif onboarding_ok:
            freshness_score = 100.0
    onboarding_grade = _round_int((freshness_score + (100.0 if onboarding_ok else 0.0)) / 2.0)

    release_trend_score, release_trend_delta = _trend_grade(release_history, release_window)
    release_grade = _round_int(((100.0 if release_ok else 0.0) * 0.6) + (release_trend_score * 0.4))

    current_legacy_count = int(legacy.get("count", 0)) if isinstance(legacy, dict) else 0
    baseline_legacy_count = (
        int(legacy_baseline.get("count", 0))
        if isinstance(legacy_baseline, dict)
        else current_legacy_count
    )
    if baseline_legacy_count <= 0:
        reduction_pct = 0.0
    else:
        reduction_pct = (
            (baseline_legacy_count - current_legacy_count) / baseline_legacy_count
        ) * 100.0
    legacy_density_health = 100.0 if ops_ok else _clamp(100.0 - current_legacy_count * 10.0)
    legacy_trend_health = _clamp(50.0 + reduction_pct)
    ops_grade = _round_int((legacy_density_health + legacy_trend_health) / 2.0)

    test_signal_score = 50.0
    if isinstance(test_signal, dict):
        if isinstance(test_signal.get("pass_rate"), (int, float)):
            rate = float(test_signal["pass_rate"])
            if rate <= 1:
                rate *= 100.0
            test_signal_score = _clamp(rate)
        elif test_signal.get("overall_ok") is True:
            test_signal_score = 100.0
        elif test_signal.get("overall_ok") is False:
            test_signal_score = 0.0
    quality_grade = _round_int(((100.0 if quality_ok else 0.0) + test_signal_score) / 2.0)

    grades = {
        "onboarding": onboarding_grade,
        "release": release_grade,
        "ops": ops_grade,
        "quality": quality_grade,
    }
    norm_weights = _normalize_weights(weights)
    weighted_total = sum(grades[key] * norm_weights[key] for key in grades)
    total = _round_int(weighted_total)
    if total >= 90:
        band = "excellent"
    elif total >= 70:
        band = "strong"
    elif total >= 40:
        band = "developing"
    else:
        band = "early"
    dimensions = {key: _round_int(value / 4.0) for key, value in grades.items()}
    return {
        "schema_version": "2",
        "score": total,
        "band": band,
        "dimensions": dimensions,
        "graded_dimensions": grades,
        "weights": {k: round(v, 4) for k, v in norm_weights.items()},
        "signals": {
            "onboarding": {
                "artifact_freshness_score": _round_int(freshness_score),
                "canonical_pass_rate": 100 if onboarding_ok else 0,
            },
            "release": {
                "current_gate_release": 100 if release_ok else 0,
                "trend_window": max(release_window, 2),
                "trend_delta": math.floor(release_trend_delta * 1000) / 1000.0,
            },
            "ops": {
                "current_legacy_count": current_legacy_count,
                "baseline_legacy_count": baseline_legacy_count,
                "legacy_reduction_pct": math.floor(reduction_pct * 1000) / 1000.0,
            },
            "quality": {
                "drift_guard": 100 if quality_ok else 0,
                "test_signal": _round_int(test_signal_score),
            },
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python scripts/adoption_scorecard.py")
    parser.add_argument("--golden", default=".sdetkit/out/golden-path-health.json")
    parser.add_argument("--drift", default=".sdetkit/out/canonical-path-drift.json")
    parser.add_argument("--legacy", default=".sdetkit/out/legacy-command-analyzer.json")
    parser.add_argument("--legacy-baseline")
    parser.add_argument("--release-history")
    parser.add_argument("--release-window", type=int, default=4)
    parser.add_argument("--test-signal")
    parser.add_argument("--stale-after-seconds", type=int, default=604800)
    parser.add_argument("--weight-onboarding", type=float, default=0.30)
    parser.add_argument("--weight-release", type=float, default=0.25)
    parser.add_argument("--weight-ops", type=float, default=0.20)
    parser.add_argument("--weight-quality", type=float, default=0.25)
    parser.add_argument("--out", default=".sdetkit/out/adoption-scorecard.json")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    ns = parser.parse_args(argv)

    scorecard = _build_scorecard(
        _load_json(Path(ns.golden)),
        _load_json(Path(ns.drift)),
        _load_json(Path(ns.legacy)),
        test_signal=_load_json(Path(ns.test_signal)) if ns.test_signal else None,
        release_history=_load_history_series(Path(ns.release_history))
        if ns.release_history
        else [],
        release_window=max(ns.release_window, 2),
        legacy_baseline=_load_json(Path(ns.legacy_baseline)) if ns.legacy_baseline else None,
        stale_after_seconds=max(ns.stale_after_seconds, 1),
        weights={
            "onboarding": ns.weight_onboarding,
            "release": ns.weight_release,
            "ops": ns.weight_ops,
            "quality": ns.weight_quality,
        },
    )
    out = Path(ns.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(scorecard, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if ns.format == "json":
        print(json.dumps(scorecard, sort_keys=True))
    else:
        print(f"adoption-scorecard: score={scorecard['score']} band={scorecard['band']}")
        for k, v in scorecard["dimensions"].items():
            print(f"- {k}: {v}/25")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
