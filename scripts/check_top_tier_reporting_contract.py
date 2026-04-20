#!/usr/bin/env python3
"""Validate consistency between portfolio scorecard and KPI weekly snapshot artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _fail(message: str) -> None:
    raise ValueError(message)


def _expect(condition: bool, message: str) -> None:
    if not condition:
        _fail(message)


def _as_float(value: Any) -> float:
    return float(value)


def _validate(portfolio: dict[str, Any], kpi_payload: dict[str, Any]) -> dict[str, Any]:
    repos = list(portfolio.get("repos", []))
    totals = dict(portfolio.get("totals", {}))
    repo_count = int(totals.get("repo_count_total", len(repos)))

    _expect(repo_count == len(repos), "repo_count_total must equal number of repos")

    kpis = dict(kpi_payload.get("kpis", {}))
    required_kpis = {
        "first_time_success_onboarding_rate",
        "failed_release_gate_frequency",
        "rollback_rate",
    }
    missing = required_kpis - set(kpis)
    _expect(not missing, f"missing required KPI keys: {sorted(missing)}")

    release_confidence_pass = sum(
        1 for row in repos if bool(row.get("release_confidence_ok", False))
    )
    expected_onboarding_rate = (
        round((release_confidence_pass / repo_count * 100), 2) if repo_count else 0.0
    )

    actual_onboarding = _as_float(kpis["first_time_success_onboarding_rate"]["value"])
    _expect(
        abs(actual_onboarding - expected_onboarding_rate) < 0.01,
        f"onboarding rate mismatch: expected {expected_onboarding_rate}, got {actual_onboarding}",
    )

    expected_failed_release = _as_float(totals.get("release_gate_failure_rate_percent", 0.0))
    actual_failed_release = _as_float(kpis["failed_release_gate_frequency"]["value"])
    _expect(
        abs(actual_failed_release - expected_failed_release) < 0.01,
        f"failed release frequency mismatch: expected {expected_failed_release}, got {actual_failed_release}",
    )

    sample_size = kpis["failed_release_gate_frequency"].get("sample_size")
    _expect(
        sample_size == repo_count,
        f"failed_release_gate_frequency.sample_size must equal {repo_count}",
    )

    evidence_window_end_values = {
        row.get("evidence_window_end") for row in repos if row.get("evidence_window_end")
    }
    if evidence_window_end_values and kpi_payload.get("week_ending"):
        _expect(
            kpi_payload["week_ending"] in evidence_window_end_values,
            "kpi week_ending must match evidence_window_end in portfolio repos",
        )

    return {
        "ok": True,
        "repo_count": repo_count,
        "week_ending": kpi_payload.get("week_ending"),
        "checks": [
            "repo_count_total_matches_repos",
            "onboarding_rate_consistent",
            "failed_release_rate_consistent",
            "sample_size_consistent",
            "week_alignment_consistent",
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Check top-tier reporting contract consistency")
    ap.add_argument("--portfolio-scorecard", required=True)
    ap.add_argument("--kpi-weekly", required=True)
    ap.add_argument("--out", default="", help="Optional JSON report output path")
    args = ap.parse_args()

    portfolio = json.loads(Path(args.portfolio_scorecard).read_text())
    kpi_weekly = json.loads(Path(args.kpi_weekly).read_text())

    report = _validate(portfolio, kpi_weekly)

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2) + "\n")

    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
