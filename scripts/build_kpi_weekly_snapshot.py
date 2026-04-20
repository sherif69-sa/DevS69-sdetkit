#!/usr/bin/env python3
"""Build a weekly KPI snapshot JSON payload from portfolio scorecard evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

_SCHEMA_VERSION = "1.0.0"


def _metric(
    value: Any, unit: str, sample_size: int | None, quality: str, source: str
) -> dict[str, Any]:
    return {
        "value": value,
        "unit": unit,
        "sample_size": sample_size,
        "quality": quality,
        "source": source,
    }


def _build_payload(
    *,
    portfolio: dict[str, Any],
    week_ending: str,
    program_status: str,
    rollback_count: int,
    median_release_decision_time: float | None,
    mean_time_to_triage_first_failure: float | None,
    docs_to_adoption_conversion: float | None,
) -> dict[str, Any]:
    repos = list(portfolio.get("repos", []))
    totals = dict(portfolio.get("totals", {}))
    total_repos = int(totals.get("repo_count_total", len(repos)))

    release_confidence_pass = sum(
        1 for row in repos if bool(row.get("release_confidence_ok", False))
    )
    onboarding_rate = (
        round((release_confidence_pass / total_repos * 100), 2) if total_repos else 0.0
    )

    failed_release_gate_frequency = float(totals.get("release_gate_failure_rate_percent", 0.0))

    source = "portfolio scorecard + weekly operations ledger"

    return {
        "schema_version": _SCHEMA_VERSION,
        "week_ending": week_ending,
        "program_status": program_status,
        "kpis": {
            "first_time_success_onboarding_rate": _metric(
                onboarding_rate,
                "percent",
                total_repos,
                "seed",
                source,
            ),
            "median_release_decision_time": _metric(
                median_release_decision_time,
                "minutes" if median_release_decision_time is not None else "n/a",
                total_repos if median_release_decision_time is not None else None,
                "seed",
                "timing instrumentation pending"
                if median_release_decision_time is None
                else source,
            ),
            "failed_release_gate_frequency": _metric(
                failed_release_gate_frequency,
                "percent",
                total_repos,
                "seed",
                source,
            ),
            "rollback_rate": _metric(
                rollback_count,
                "count",
                rollback_count,
                "seed",
                source,
            ),
            "mean_time_to_triage_first_failure": _metric(
                mean_time_to_triage_first_failure,
                "minutes" if mean_time_to_triage_first_failure is not None else "n/a",
                total_repos if mean_time_to_triage_first_failure is not None else None,
                "seed",
                "incident timing fields pending"
                if mean_time_to_triage_first_failure is None
                else source,
            ),
            "docs_to_adoption_conversion": _metric(
                docs_to_adoption_conversion,
                "percent" if docs_to_adoption_conversion is not None else "n/a",
                total_repos if docs_to_adoption_conversion is not None else None,
                "seed",
                "docs telemetry pending" if docs_to_adoption_conversion is None else source,
            ),
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Build weekly KPI snapshot JSON payload")
    ap.add_argument("--portfolio-scorecard", required=True, help="Portfolio scorecard JSON path")
    ap.add_argument("--out", required=True, help="Output KPI JSON path")
    ap.add_argument("--week-ending", required=True, help="Week ending date (YYYY-MM-DD)")
    ap.add_argument("--program-status", default="green", choices=("green", "amber", "red"))
    ap.add_argument("--rollback-count", type=int, default=0)
    ap.add_argument("--median-release-decision-time", type=float, default=None)
    ap.add_argument("--mean-time-to-triage-first-failure", type=float, default=None)
    ap.add_argument("--docs-to-adoption-conversion", type=float, default=None)
    args = ap.parse_args()

    portfolio = json.loads(Path(args.portfolio_scorecard).read_text())
    payload = _build_payload(
        portfolio=portfolio,
        week_ending=args.week_ending,
        program_status=args.program_status,
        rollback_count=args.rollback_count,
        median_release_decision_time=args.median_release_decision_time,
        mean_time_to_triage_first_failure=args.mean_time_to_triage_first_failure,
        docs_to_adoption_conversion=args.docs_to_adoption_conversion,
    )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
