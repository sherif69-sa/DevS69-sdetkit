#!/usr/bin/env python3
"""Validate Phase 4 governance docs and execution contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REQUIRED_INDEX_LINKS = [
    "- [Versioning and support posture](versioning-and-support.md)",
    "- [Stability levels](stability-levels.md)",
]
REQUIRED_GOV_DOCS = [
    "docs/versioning-and-support.md",
    "docs/stability-levels.md",
    "docs/integrations-and-extension-boundary.md",
]
REQUIRED_OPERATOR_LINES = [
    "make phase4-governance-contract",
    "python scripts/validate_enterprise_contracts.py",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs-index", default="docs/index.md")
    ap.add_argument("--operator-essentials", default="docs/operator-essentials.md")
    ap.add_argument("--format", choices=["text", "json"], default="text")
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
            failures.append(f"docs/index.md missing governance link: {link}")

    for path_text in REQUIRED_GOV_DOCS:
        p = Path(path_text)
        exists = p.is_file()
        checks.append({"id": f"gov_doc_exists::{path_text}", "ok": exists})
        if not exists:
            failures.append(f"missing governance doc: {path_text}")

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
            failures.append(f"operator essentials missing governance line: {line}")

    payload = {
        "ok": not failures,
        "schema_version": "sdetkit.phase4_governance_contract.v1",
        "checks": checks,
        "failures": failures,
    }

    if ns.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("phase4-governance-contract: OK" if payload["ok"] else "phase4-governance-contract: FAIL")
        for check in checks:
            print(f"[{'OK' if check['ok'] else 'FAIL'}] {check['id']}")
        if failures:
            for failure in failures:
                print(f"- {failure}")

    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
