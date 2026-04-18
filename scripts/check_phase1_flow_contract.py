#!/usr/bin/env python3
"""Validate that documented Phase 1 flow commands map to Makefile targets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

DOC_PATH = Path("docs/phase-execution-one-by-one.md")
MAKEFILE_PATH = Path("Makefile")


def _extract_doc_targets(doc_text: str) -> list[str]:
    in_block = False
    targets: list[str] = []
    for line in doc_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```bash"):
            in_block = True
            continue
        if in_block and stripped.startswith("```"):
            break
        if in_block and stripped.startswith("make "):
            parts = stripped.split()
            if len(parts) >= 2:
                targets.append(parts[1])
    return targets


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check Phase 1 flow contract between docs and Makefile.")
    parser.add_argument("--doc", default=str(DOC_PATH))
    parser.add_argument("--makefile", default=str(MAKEFILE_PATH))
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)

    doc_path = Path(args.doc)
    make_path = Path(args.makefile)

    if not doc_path.is_file() or not make_path.is_file():
        payload = {
            "ok": False,
            "schema_version": "sdetkit.phase1_flow_contract.v1",
            "reason": "missing doc or makefile",
        }
        if args.format == "json":
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"phase1-flow-contract: FAIL ({payload['reason']})")
        return 1

    doc_targets = _extract_doc_targets(doc_path.read_text(encoding="utf-8"))
    make_text = make_path.read_text(encoding="utf-8")

    missing = [target for target in doc_targets if f"{target}:" not in make_text]
    ok = not missing
    payload = {
        "ok": ok,
        "schema_version": "sdetkit.phase1_flow_contract.v1",
        "doc": str(doc_path),
        "makefile": str(make_path),
        "doc_targets": doc_targets,
        "missing_makefile_targets": missing,
    }

    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("phase1-flow-contract: OK" if ok else "phase1-flow-contract: FAIL")
        for target in missing:
            print(f"- missing target: {target}")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
