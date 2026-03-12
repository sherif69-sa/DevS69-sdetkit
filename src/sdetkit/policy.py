from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

from .doctor import _scan_non_ascii
from .import_hazards import find_stdlib_shadowing
from .repo import run_repo_audit
from .security_gate import scan_repo

SCHEMA_VERSION = "sdetkit.policy.v2"
EXIT_OK = 0
EXIT_REGRESSION = 1
EXIT_USAGE = 2


def _stable_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, indent=2) + "\n"


def _error(code: str, message: str, *, detail: dict[str, Any] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"schema_version": SCHEMA_VERSION, "error": {"code": code, "message": message}}
    if detail:
        out["error"]["detail"] = detail
    return out


def _snapshot(root: Path) -> dict[str, Any]:
    findings = scan_repo(root)
    sec_counts: dict[str, int] = {}
    for item in findings:
        sec_counts[item.rule_id] = sec_counts.get(item.rule_id, 0) + 1
    audit = run_repo_audit(root)
    non_ascii, _ = _scan_non_ascii(root)
    return {
        "schema_version": SCHEMA_VERSION,
        "version": 2,
        "security": {"rule_counts": dict(sorted(sec_counts.items()))},
        "repo": {"summary": audit.get("summary", {})},
        "hygiene": {
            "non_ascii_files": sorted(non_ascii),
            "stdlib_shadowing": find_stdlib_shadowing(root),
        },
    }


def _load_waivers(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not path.is_file():
        return [], [{"code": "waiver_file_missing", "message": f"waiver file not found: {path}"}]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [], [{"code": "waiver_parse_error", "message": str(exc)}]
    waivers = payload.get("waivers") if isinstance(payload, dict) else None
    if not isinstance(waivers, list):
        return [], [{"code": "waiver_shape_invalid", "message": "waivers must be a list"}]

    errs: list[dict[str, Any]] = []
    out: list[dict[str, Any]] = []
    for i, item in enumerate(waivers):
        if not isinstance(item, dict):
            errs.append({"code": "waiver_item_invalid", "message": f"waivers[{i}] must be an object"})
            continue
        required = ("type", "owner", "justification", "expires_on")
        missing = [k for k in required if not isinstance(item.get(k), str) or not str(item.get(k)).strip()]
        if missing:
            errs.append({"code": "waiver_missing_required", "message": f"waivers[{i}] missing fields: {', '.join(missing)}"})
            continue
        try:
            expiry = dt.date.fromisoformat(str(item["expires_on"]))
        except ValueError:
            errs.append({"code": "waiver_expiry_invalid", "message": f"waivers[{i}] has invalid expires_on"})
            continue
        if expiry < dt.date.today():
            errs.append({"code": "waiver_expired", "message": f"waivers[{i}] is expired"})
            continue
        if item.get("type") not in {"security_rule_increase", "new_non_ascii", "new_stdlib_shadowing"}:
            errs.append({"code": "waiver_type_unknown", "message": f"waivers[{i}] has unsupported type"})
            continue
        out.append(item)
    return out, errs


def _apply_waivers(
    regressions: list[dict[str, Any]], waivers: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    remaining = [dict(item) for item in regressions]
    used: list[dict[str, Any]] = []
    for reg in remaining:
        for w in waivers:
            if w["type"] != reg.get("type"):
                continue
            if w["type"] == "security_rule_increase" and w.get("rule_id") != reg.get("rule_id"):
                continue
            if w["type"] in {"new_non_ascii", "new_stdlib_shadowing"} and w.get("path") and w.get("path") != reg.get("path"):
                continue
            reg["waived"] = True
            reg["waiver"] = {
                "owner": w["owner"],
                "justification": w["justification"],
                "expires_on": w["expires_on"],
            }
            used.append(w)
            break
    active = [r for r in remaining if not r.get("waived")]
    return remaining, active


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
    cp.add_argument("--waivers", default=None, help="JSON waiver file with owner/justification/expiry.")
    cp.add_argument("--format", choices=["text", "json"], default="text")

    dp = sub.add_parser("diff")
    dp.add_argument("--baseline", required=True)
    dp.add_argument("--format", choices=["text", "json", "sarif"], default="text")
    dp.add_argument("--waivers", default=None, help="JSON waiver file with owner/justification/expiry.")

    ns = p.parse_args(argv)
    root = Path.cwd()

    if ns.cmd == "snapshot":
        payload = _snapshot(root)
        out = Path(ns.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(_stable_json(payload), encoding="utf-8")
        sys.stdout.write(out.as_posix() + "\n")
        return EXIT_OK

    baseline = Path(ns.baseline)
    if not baseline.is_file():
        msg = f"baseline not found: {baseline}"
        if getattr(ns, "format", "text") == "json":
            sys.stdout.write(_stable_json(_error("baseline_missing", msg)))
        else:
            sys.stdout.write(msg + "\n")
        return EXIT_USAGE
    base = json.loads(baseline.read_text(encoding="utf-8"))
    cur = _snapshot(root)
    regressions = _regressions(base, cur)
    waiver_errors: list[dict[str, Any]] = []
    waivers: list[dict[str, Any]] = []
    if isinstance(getattr(ns, "waivers", None), str) and ns.waivers:
        waivers, waiver_errors = _load_waivers(Path(ns.waivers))
    if waiver_errors:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "ok": False,
            "error": {"code": "waiver_validation_failed", "detail": waiver_errors},
        }
        sys.stdout.write(_stable_json(payload) if getattr(ns, "format", "text") == "json" else "waiver validation failed\n")
        return EXIT_USAGE

    regressions_all, regressions_active = _apply_waivers(regressions, waivers)

    if ns.cmd == "check":
        relevant = (
            [item for item in regressions_active if item.get("type") == "security_rule_increase"]
            if ns.fail_on == "security"
            else regressions_active
        )
        failed = bool(relevant)
        if ns.format == "json":
            payload = {
                "schema_version": SCHEMA_VERSION,
                "ok": not failed,
                "fail_on": ns.fail_on,
                "baseline": baseline.as_posix(),
                "regressions": regressions_all,
                "active_regressions": regressions_active,
            }
            sys.stdout.write(_stable_json(payload))
        else:
            for item in regressions_all:
                sys.stdout.write(json.dumps(item, sort_keys=True) + "\n")
        if ns.fail_on == "security":
            return EXIT_REGRESSION if any(item.get("type") == "security_rule_increase" for item in regressions_active) else EXIT_OK
        return EXIT_REGRESSION if regressions_active else EXIT_OK

    payload = {
        "schema_version": SCHEMA_VERSION,
        "baseline": baseline.as_posix(),
        "regressions": regressions_all,
        "active_regressions": regressions_active,
    }
    if ns.format == "json":
        sys.stdout.write(_stable_json(payload))
    elif ns.format == "sarif":
        sys.stdout.write(json.dumps(_as_sarif(regressions_active), sort_keys=True, indent=2) + "\n")
    else:
        for item in regressions_all:
            sys.stdout.write(f"RED-FLAG {item['type']}: {json.dumps(item, sort_keys=True)}\n")
    return EXIT_OK
