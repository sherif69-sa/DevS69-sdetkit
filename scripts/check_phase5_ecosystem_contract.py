#!/usr/bin/env python3
"""Validate Phase 5 ecosystem/platform scaling contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REQUIRED_INDEX_LINKS = [
    "- [Integrations and extension boundary](integrations-and-extension-boundary.md)",
]
REQUIRED_OPERATOR_LINES = [
    "make phase5-ecosystem-contract",
    "make phase4-governance-contract",
]
REQUIRED_FILES = [
    "src/sdetkit/plugin_system.py",
    "docs/integrations-and-extension-boundary.md",
    "pyproject.toml",
]
REQUIRED_PYPROJECT_SNIPPETS = [
    "[project.entry-points.\"sdetkit.notify_adapters\"]",
    "telegram = [",
    "whatsapp = [",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--format", choices=["text", "json"], default="text")
    ap.add_argument("--docs-index", default="docs/index.md")
    ap.add_argument("--operator-essentials", default="docs/operator-essentials.md")
    ap.add_argument("--pyproject", default="pyproject.toml")
    ns = ap.parse_args()

    checks: list[dict[str, object]] = []
    failures: list[str] = []

    docs_index = Path(ns.docs_index)
    index_text = docs_index.read_text(encoding="utf-8") if docs_index.is_file() else ""
    checks.append({"id": "docs_index_exists", "ok": docs_index.is_file(), "path": str(docs_index)})
    if not docs_index.is_file():
        failures.append("missing docs/index.md")

    for link in REQUIRED_INDEX_LINKS:
        present = link in index_text
        checks.append({"id": f"index_has::{link}", "ok": present})
        if not present:
            failures.append(f"docs/index.md missing ecosystem link: {link}")

    for file_path in REQUIRED_FILES:
        p = Path(file_path)
        present = p.is_file()
        checks.append({"id": f"required_file::{file_path}", "ok": present})
        if not present:
            failures.append(f"missing required file: {file_path}")

    operator_doc = Path(ns.operator_essentials)
    operator_text = operator_doc.read_text(encoding="utf-8") if operator_doc.is_file() else ""
    checks.append({"id": "operator_essentials_exists", "ok": operator_doc.is_file(), "path": str(operator_doc)})
    if not operator_doc.is_file():
        failures.append("missing docs/operator-essentials.md")

    for line in REQUIRED_OPERATOR_LINES:
        present = line in operator_text
        checks.append({"id": f"operator_has::{line}", "ok": present})
        if not present:
            failures.append(f"operator essentials missing line: {line}")

    pyproject = Path(ns.pyproject)
    pyproject_text = pyproject.read_text(encoding="utf-8") if pyproject.is_file() else ""
    for snippet in REQUIRED_PYPROJECT_SNIPPETS:
        present = snippet in pyproject_text
        checks.append({"id": f"pyproject_has::{snippet}", "ok": present})
        if not present:
            failures.append(f"pyproject missing ecosystem snippet: {snippet}")

    payload = {
        "ok": not failures,
        "schema_version": "sdetkit.phase5_ecosystem_contract.v1",
        "checks": checks,
        "failures": failures,
    }

    if ns.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("phase5-ecosystem-contract: OK" if payload["ok"] else "phase5-ecosystem-contract: FAIL")
        for check in checks:
            print(f"[{'OK' if check['ok'] else 'FAIL'}] {check['id']}")
        if failures:
            for failure in failures:
                print(f"- {failure}")

    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
