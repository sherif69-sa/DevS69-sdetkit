#!/usr/bin/env python3
"""Validate operator-essentials docs contract for phase-2 surface clarity."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REQUIRED_INDEX_LINK = "- [Operator essentials](operator-essentials.md)"
REQUIRED_LINES = [
    "python -m sdetkit gate fast",
    "python -m sdetkit gate release",
    "python -m sdetkit doctor",
    "make phase1-baseline",
    "make phase2-surface-clarity",
    "make phase3-quality-contract",
    "make phase4-governance-contract",
    "make phase5-ecosystem-contract",
    "make phase6-metrics-contract",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs-index", default="docs/index.md")
    ap.add_argument("--operator-essentials", default="docs/operator-essentials.md")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    ns = ap.parse_args()

    docs_index = Path(ns.docs_index)
    operator_doc = Path(ns.operator_essentials)

    failures: list[str] = []
    checks: list[dict[str, object]] = []

    index_exists = docs_index.is_file()
    checks.append({"id": "docs_index_exists", "ok": index_exists, "path": str(docs_index)})
    if not index_exists:
        failures.append("docs/index.md missing")

    doc_exists = operator_doc.is_file()
    checks.append({"id": "operator_doc_exists", "ok": doc_exists, "path": str(operator_doc)})
    if not doc_exists:
        failures.append("docs/operator-essentials.md missing")

    index_text = docs_index.read_text(encoding="utf-8") if index_exists else ""
    doc_text = operator_doc.read_text(encoding="utf-8") if doc_exists else ""

    link_ok = REQUIRED_INDEX_LINK in index_text
    checks.append(
        {
            "id": "index_links_operator_essentials",
            "ok": link_ok,
            "expected": REQUIRED_INDEX_LINK,
        }
    )
    if not link_ok:
        failures.append("docs/index.md does not link docs/operator-essentials.md")

    for required in REQUIRED_LINES:
        present = required in doc_text
        checks.append({"id": f"operator_doc_has::{required}", "ok": present})
        if not present:
            failures.append(f"docs/operator-essentials.md missing '{required}'")

    payload = {
        "ok": not failures,
        "schema_version": "sdetkit.operator_essentials_contract.v1",
        "checks": checks,
        "failures": failures,
    }

    if ns.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("operator-essentials-contract: OK" if payload["ok"] else "operator-essentials-contract: FAIL")
        for check in checks:
            print(f"[{'OK' if check['ok'] else 'FAIL'}] {check['id']}")
        if failures:
            for failure in failures:
                print(f"- {failure}")

    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
