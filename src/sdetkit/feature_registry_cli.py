from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from typing import Any

from .feature_registry import (
    load_feature_registry,
    render_feature_registry_docs_block,
    render_feature_registry_table,
    summarize_feature_registry,
)


def _parse_count_expectations(items: list[str], *, label: str) -> tuple[dict[str, int], str | None]:
    out: dict[str, int] = {}
    for raw in items:
        token = str(raw).strip()
        if not token:
            continue
        if "=" not in token:
            return {}, f"feature-registry: invalid {label} expectation `{token}` (use KEY=INT)"
        key, value = token.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            return {}, f"feature-registry: invalid {label} expectation `{token}` (missing key)"
        try:
            parsed = int(value)
        except ValueError:
            return (
                {},
                f"feature-registry: invalid {label} expectation `{token}` (count must be int)",
            )
        if parsed < 0:
            return (
                {},
                f"feature-registry: invalid {label} expectation `{token}` (count must be >= 0)",
            )
        out[key] = parsed
    return out, None


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sdetkit feature-registry",
        description="Inspect feature registry entries and filter by tier/status.",
    )
    p.add_argument("--tier", choices=["A", "B", "C"], default=None)
    p.add_argument(
        "--only-core",
        action="store_true",
        help="Convenience alias for --tier A.",
    )
    p.add_argument("--status", choices=["stable", "advanced", "experimental"], default=None)
    p.add_argument(
        "--expect-command",
        action="append",
        default=[],
        help="Require one or more command names to exist in the filtered result set.",
    )
    p.add_argument(
        "--fail-on-empty",
        action="store_true",
        help="Exit non-zero when filters return zero rows.",
    )
    p.add_argument(
        "--expect-tier-count",
        action="append",
        default=[],
        help="Assert tier counts using KEY=INT (repeatable), e.g. --expect-tier-count A=8.",
    )
    p.add_argument(
        "--expect-status-count",
        action="append",
        default=[],
        help="Assert status counts using KEY=INT (repeatable), e.g. --expect-status-count stable=8.",
    )
    p.add_argument(
        "--expect-total",
        type=int,
        default=None,
        help="Assert total row count after filtering.",
    )
    p.add_argument(
        "--format", choices=["table", "json", "markdown", "summary-json"], default="table"
    )
    return p


def main(argv: list[str] | None = None) -> int:
    ns = _build_parser().parse_args(argv)
    rows = load_feature_registry()

    if ns.only_core:
        if ns.tier not in (None, "A"):
            raise SystemExit("--only-core cannot be combined with --tier B/C")
        ns.tier = "A"

    if ns.tier is not None:
        rows = [item for item in rows if item.tier == ns.tier]
    if ns.status is not None:
        rows = [item for item in rows if item.status == ns.status]
    commands = {item.command for item in rows}

    missing_commands = sorted(
        {str(name).strip() for name in ns.expect_command if str(name).strip()} - commands
    )
    if missing_commands:
        print(
            "feature-registry: missing expected command(s): " + ", ".join(missing_commands),
            file=sys.stderr,
        )
        return 2

    if ns.fail_on_empty and not rows:
        print("feature-registry: filtered result set is empty", file=sys.stderr)
        return 1
    summary: dict[str, Any] = summarize_feature_registry(rows)

    tier_expectations, tier_error = _parse_count_expectations(
        list(ns.expect_tier_count), label="tier-count"
    )
    if tier_error is not None:
        print(tier_error, file=sys.stderr)
        return 2
    for tier, expected in tier_expectations.items():
        by_tier = summary.get("by_tier")
        tier_counts = by_tier if isinstance(by_tier, dict) else {}
        actual = int(tier_counts.get(tier, 0))
        if actual != expected:
            print(
                f"feature-registry: tier count mismatch for `{tier}` (expected {expected}, got {actual})",
                file=sys.stderr,
            )
            return 2

    status_expectations, status_error = _parse_count_expectations(
        list(ns.expect_status_count), label="status-count"
    )
    if status_error is not None:
        print(status_error, file=sys.stderr)
        return 2
    for status, expected in status_expectations.items():
        by_status = summary.get("by_status")
        status_counts = by_status if isinstance(by_status, dict) else {}
        actual = int(status_counts.get(status, 0))
        if actual != expected:
            print(
                f"feature-registry: status count mismatch for `{status}` (expected {expected}, got {actual})",
                file=sys.stderr,
            )
            return 2

    if ns.expect_total is not None:
        if ns.expect_total < 0:
            print("feature-registry: --expect-total must be >= 0", file=sys.stderr)
            return 2
        actual_total = int(summary.get("total", 0))
        if actual_total != ns.expect_total:
            print(
                f"feature-registry: total count mismatch (expected {ns.expect_total}, got {actual_total})",
                file=sys.stderr,
            )
            return 2

    if ns.format == "json":
        print(json.dumps([asdict(item) for item in rows], indent=2, sort_keys=True))
        return 0

    if ns.format == "summary-json":
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0

    if ns.format == "markdown":
        print(render_feature_registry_docs_block(rows))
        return 0

    print(render_feature_registry_table(rows))
    return 0
