#!/usr/bin/env python3
"""Validate Phase 6 metrics/commercialization contract surfaces."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REQUIRED_INDEX_LINKS = [
    "- [Release confidence ROI](release-confidence-roi.md)",
    "- [Repo health dashboard](repo-health-dashboard.md)",
]
REQUIRED_FILES = [
    "docs/release-confidence-roi.md",
    "docs/repo-health-dashboard.md",
    "scripts/build_kpi_weekly_snapshot.py",
    "scripts/check_kpi_weekly_contract.py",
]
REQUIRED_OPERATOR_LINES = [
    "make phase6-metrics-contract",
    "make phase5-ecosystem-contract",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--format", choices=["text", "json"], default="text")
    ap.add_argument("--docs-index", default="docs/index.md")
    ap.add_argument("--operator-essentials", default="docs/operator-essentials.md")
    ns = ap.parse_args()

    checks: list[dict[str, object]] = []
    failures: list[str] = []

    docs_index = Path(ns.docs_index)
    index_exists = docs_index.is_file()
    checks.append({"id": "docs_index_exists", "ok": index_exists, "path": str(docs_index)})
    index_text = docs_index.read_text(encoding="utf-8") if index_exists else ""
    if not index_exists:
        failures.append("missing docs/index.md")

    for link in REQUIRED_INDEX_LINKS:
        present = link in index_text
        checks.append({"id": f"index_has::{link}", "ok": present})
        if not present:
            failures.append(f"docs/index.md missing metrics link: {link}")

    for file_path in REQUIRED_FILES:
        p = Path(file_path)
        present = p.is_file()
        checks.append({"id": f"required_file::{file_path}", "ok": present})
        if not present:
            failures.append(f"missing metrics file: {file_path}")

    operator_doc = Path(ns.operator_essentials)
    operator_exists = operator_doc.is_file()
    checks.append({"id": "operator_essentials_exists", "ok": operator_exists, "path": str(operator_doc)})
    operator_text = operator_doc.read_text(encoding="utf-8") if operator_exists else ""
    if not operator_exists:
        failures.append("missing docs/operator-essentials.md")

    for line in REQUIRED_OPERATOR_LINES:
        present = line in operator_text
        checks.append({"id": f"operator_has::{line}", "ok": present})
        if not present:
            failures.append(f"operator essentials missing metrics line: {line}")

    payload = {
        "ok": not failures,
        "schema_version": "sdetkit.phase6_metrics_contract.v1",
        "checks": checks,
        "failures": failures,
    }

    if ns.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("phase6-metrics-contract: OK" if payload["ok"] else "phase6-metrics-contract: FAIL")
        for check in checks:
            print(f"[{'OK' if check['ok'] else 'FAIL'}] {check['id']}")
        if failures:
            for failure in failures:
                print(f"- {failure}")

    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
