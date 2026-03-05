from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .doctor import _scan_non_ascii
from .import_hazards import find_stdlib_shadowing
from .repo import run_repo_audit
from .security_gate import scan_repo


def _snapshot(root: Path) -> dict[str, Any]:
    findings = scan_repo(root)
    sec_counts: dict[str, int] = {}
    for item in findings:
        sec_counts[item.rule_id] = sec_counts.get(item.rule_id, 0) + 1
    audit = run_repo_audit(root)
    non_ascii, _ = _scan_non_ascii(root)
    return {
        "version": 1,
        "security": {"rule_counts": dict(sorted(sec_counts.items()))},
        "repo": {"summary": audit.get("summary", {})},
        "hygiene": {
            "non_ascii_files": sorted(non_ascii),
            "stdlib_shadowing": find_stdlib_shadowing(root),
        },
    }


def _regressions(base: dict[str, Any], cur: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    base_rules = base.get("security", {}).get("rule_counts", {})
    cur_rules = cur.get("security", {}).get("rule_counts", {})
    for rule in sorted(set(base_rules) | set(cur_rules)):
        old = int(base_rules.get(rule, 0))
        new = int(cur_rules.get(rule, 0))
        if new > old:
            out.append({"type": "security_rule_increase", "rule_id": rule, "old": old, "new": new})
    old_ascii = set(base.get("hygiene", {}).get("non_ascii_files", []))
    new_ascii = set(cur.get("hygiene", {}).get("non_ascii_files", []))
    for item in sorted(new_ascii - old_ascii):
        out.append({"type": "new_non_ascii", "path": item})
    old_shadow = set(base.get("hygiene", {}).get("stdlib_shadowing", []))
    new_shadow = set(cur.get("hygiene", {}).get("stdlib_shadowing", []))
    for item in sorted(new_shadow - old_shadow):
        out.append({"type": "new_stdlib_shadowing", "path": item})
    return out


def _as_sarif(regressions: list[dict[str, Any]]) -> dict[str, Any]:
    results = []
    for item in regressions:
        rule_id = item.get("rule_id", item["type"])
        msg = json.dumps(item, sort_keys=True)
        results.append({"ruleId": rule_id, "level": "error", "message": {"text": msg}})
    return {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [{"tool": {"driver": {"name": "sdetkit policy"}}, "results": results}],
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="sdetkit policy")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("snapshot")
    sp.add_argument("--output", default=".sdetkit/policies/baseline.json")

    cp = sub.add_parser("check")
    cp.add_argument("--baseline", default=".sdetkit/policies/baseline.json")
    cp.add_argument("--fail-on", choices=["any", "security"], default="any")

    dp = sub.add_parser("diff")
    dp.add_argument("--baseline", required=True)
    dp.add_argument("--format", choices=["text", "json", "sarif"], default="text")

    ns = p.parse_args(argv)
    root = Path.cwd()

    if ns.cmd == "snapshot":
        payload = _snapshot(root)
        out = Path(ns.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        sys.stdout.write(out.as_posix() + "\n")
        return 0

    baseline = Path(ns.baseline)
    if not baseline.is_file():
        sys.stdout.write(f"baseline not found: {baseline}\n")
        return 2
    base = json.loads(baseline.read_text(encoding="utf-8"))
    cur = _snapshot(root)
    regressions = _regressions(base, cur)

    if ns.cmd == "check":
        for item in regressions:
            sys.stdout.write(json.dumps(item, sort_keys=True) + "\n")
        if ns.fail_on == "security":
            security_only = [
                item for item in regressions if item.get("type") == "security_rule_increase"
            ]
            return 1 if security_only else 0
        return 1 if regressions else 0

    payload = {"baseline": baseline.as_posix(), "regressions": regressions}
    if ns.format == "json":
        sys.stdout.write(json.dumps(payload, sort_keys=True, indent=2) + "\n")
    elif ns.format == "sarif":
        sys.stdout.write(json.dumps(_as_sarif(regressions), sort_keys=True, indent=2) + "\n")
    else:
        for item in regressions:
            sys.stdout.write(f"RED-FLAG {item['type']}: {json.dumps(item, sort_keys=True)}\n")
    return 0
