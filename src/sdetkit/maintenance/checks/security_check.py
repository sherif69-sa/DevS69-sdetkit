from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from ..types import CheckAction, CheckResult, MaintenanceContext
from ..utils import run_cmd

CHECK_NAME = "security_check"
_STATE_PATH = Path(".sdetkit/out/maintenance-security-check.json")


def _load_previous_fingerprints(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    if not isinstance(payload, dict) or not isinstance(payload.get("fingerprints"), list):
        return set()
    return {str(item) for item in payload["fingerprints"]}


def _save_fingerprints(path: Path, fingerprints: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"fingerprints": sorted(fingerprints)}
    path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _rule_hint(rule_id: str) -> str:
    hints = {
        "SEC_EMPTY_EXCEPT": "Replace broad/empty except blocks with specific exception handling and explicit error paths.",
        "SEC_DEBUG_PRINT": "Route runtime output through structured logging and remove debug print statements from src/ code.",
    }
    return hints.get(
        rule_id,
        "Review the rule metadata and apply the documented remediation before accepting drift.",
    )


def _build_findings_digest(findings: list[dict[str, Any]]) -> dict[str, object]:
    severity_counts: dict[str, int] = {"error": 0, "warn": 0, "info": 0}
    rule_counts: Counter[str] = Counter()
    path_counts: Counter[str] = Counter()
    sample: list[dict[str, object]] = []

    fingerprints: set[str] = set()
    for item in findings:
        sev = str(item.get("severity", "info")).lower()
        if sev in severity_counts:
            severity_counts[sev] += 1
        else:
            severity_counts["info"] += 1

        rule_id = str(item.get("rule_id", "UNKNOWN"))
        path = str(item.get("path", "<unknown>"))
        rule_counts[rule_id] += 1
        path_counts[path] += 1

        if sev in {"error", "warn"} and item.get("fingerprint"):
            fingerprints.add(str(item["fingerprint"]))

        if len(sample) < 5:
            sample.append(
                {
                    "severity": sev,
                    "rule_id": rule_id,
                    "path": path,
                    "line": item.get("line"),
                    "message": item.get("message", ""),
                }
            )

    top_rules = [{"rule_id": rule, "count": count} for rule, count in rule_counts.most_common(5)]
    remediation_hints = [
        {"rule_id": item["rule_id"], "hint": _rule_hint(str(item["rule_id"]))}
        for item in top_rules
        if isinstance(item, dict) and item.get("rule_id")
    ]

    return {
        "counts": severity_counts,
        "fingerprints": sorted(fingerprints),
        "findings_total": len(findings),
        "top_rules": top_rules,
        "top_paths": [{"path": path, "count": count} for path, count in path_counts.most_common(5)],
        "sample_findings": sample,
        "remediation_hints": remediation_hints,
    }


def _run_security_check(ctx: MaintenanceContext) -> tuple[bool, dict[str, object]]:
    cmd = [
        ctx.python_exe,
        "-m",
        "sdetkit",
        "security",
        "check",
        "--format",
        "json",
        "--fail-on",
        "none",
    ]
    baseline = ctx.repo_root / "tools" / "security.baseline.json"
    if baseline.exists():
        cmd.extend(["--baseline", str(baseline)])
    result = run_cmd(cmd, cwd=ctx.repo_root)

    payload: dict[str, Any] = {}
    try:
        payload = json.loads(result.stdout) if result.stdout.strip() else {}
    except json.JSONDecodeError:
        payload = {}

    findings = payload.get("findings", []) if isinstance(payload, dict) else []
    source = "findings"
    if (
        baseline.exists()
        and isinstance(payload, dict)
        and isinstance(payload.get("new_findings"), list)
    ):
        findings = payload.get("new_findings", [])
        source = "new_findings"

    normalized_findings: list[dict[str, Any]] = [
        item for item in findings if isinstance(item, dict)
    ]
    digest = _build_findings_digest(normalized_findings)
    counts_obj = digest.get("counts")
    counts: dict[str, int] = {"error": 0, "warn": 0, "info": 0}
    if isinstance(counts_obj, dict):
        counts = {
            "error": int(counts_obj.get("error", 0)),
            "warn": int(counts_obj.get("warn", 0)),
            "info": int(counts_obj.get("info", 0)),
        }
    error_count = counts["error"]
    warn_count = counts["warn"]

    ok = result.returncode == 0 and error_count == 0 and warn_count == 0
    details: dict[str, object] = {
        "returncode": result.returncode,
        "source": source,
        "counts": counts,
        "fingerprints": digest.get("fingerprints", []),
        "findings_total": digest.get("findings_total", 0),
        "top_rules": digest.get("top_rules", []),
        "top_paths": digest.get("top_paths", []),
        "sample_findings": digest.get("sample_findings", []),
        "remediation_hints": digest.get("remediation_hints", []),
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
    return ok, details


def run(ctx: MaintenanceContext) -> CheckResult:
    state_path = ctx.repo_root / _STATE_PATH
    previous_fingerprints = _load_previous_fingerprints(state_path)

    initial_ok, initial_details = _run_security_check(ctx)
    summary = "security check has no error/warn findings"
    actions = [
        CheckAction(
            id="security-triage",
            title="Run security triage summary",
            applied=False,
            notes="python tools/triage.py --mode security --run-security --security-baseline tools/security.baseline.json",
        )
    ]

    fix_details: dict[str, object] | None = None
    auto_fix_enabled = ctx.env.get("SDETKIT_MAINTENANCE_SECURITY_AUTOFIX", "1") != "0"
    if not initial_ok and (ctx.fix or auto_fix_enabled):
        fix_run = run_cmd(
            [ctx.python_exe, "-m", "sdetkit", "security", "fix", "--apply"],
            cwd=ctx.repo_root,
        )
        fix_details = {
            "returncode": fix_run.returncode,
            "stdout": fix_run.stdout,
            "stderr": fix_run.stderr,
        }
        actions.append(
            CheckAction(
                id="security-fix",
                title="Apply `sdetkit security fix --apply`",
                applied=fix_run.returncode == 0,
                notes=(fix_run.stdout + fix_run.stderr).strip(),
            )
        )

    follow_up_ok, follow_up_details = (
        _run_security_check(ctx) if not initial_ok else (initial_ok, initial_details)
    )

    raw_fingerprints = follow_up_details.get("fingerprints")
    active_fingerprints: set[str] = set()
    if isinstance(raw_fingerprints, list):
        active_fingerprints = {str(item) for item in raw_fingerprints if isinstance(item, str)}
    _save_fingerprints(state_path, active_fingerprints)

    repeated_fingerprints = sorted(active_fingerprints & previous_fingerprints)
    repeated = bool(repeated_fingerprints)
    ok = follow_up_ok or not repeated

    top_rules = follow_up_details.get("top_rules")
    top_rule = ""
    if isinstance(top_rules, list) and top_rules and isinstance(top_rules[0], dict):
        top_rule = str(top_rules[0].get("rule_id", "")).strip()

    if not initial_ok and follow_up_ok:
        summary = "security check recovered after auto-fix/retry"
    elif not follow_up_ok and not repeated:
        summary = "security check found non-repeated warnings (recorded for next run)"
        if top_rule:
            summary += f"; top rule: {top_rule}"
    elif not follow_up_ok:
        summary = "security check reported error/warn findings (reproduced)"
        if repeated_fingerprints:
            summary += f"; repeated fingerprints: {', '.join(repeated_fingerprints[:3])}"

    return CheckResult(
        ok=ok,
        summary=summary,
        details={
            "initial": initial_details,
            "fix": fix_details,
            "follow_up": follow_up_details,
            "previous_fingerprints": sorted(previous_fingerprints),
            "repeated": repeated,
            "repeated_fingerprints": repeated_fingerprints,
            "state_path": str(state_path.relative_to(ctx.repo_root)),
            "auto_fix_enabled": auto_fix_enabled,
        },
        actions=actions,
    )


CHECK_MODES = {"full"}
