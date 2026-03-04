from __future__ import annotations

import json
from pathlib import Path

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

    payload: dict[str, object] = {}
    try:
        payload = json.loads(result.stdout) if result.stdout.strip() else {}
    except json.JSONDecodeError:
        payload = {}

    findings = payload.get("findings", []) if isinstance(payload, dict) else []
    if (
        baseline.exists()
        and isinstance(payload, dict)
        and isinstance(payload.get("new_findings"), list)
    ):
        findings = payload.get("new_findings", [])

    counts = {"error": 0, "warn": 0, "info": 0}
    fingerprints: set[str] = set()
    if isinstance(findings, list):
        for item in findings:
            if not isinstance(item, dict):
                continue
            sev = str(item.get("severity", "info")).lower()
            if sev in counts:
                counts[sev] += 1
            else:
                counts["info"] += 1
            if sev in {"error", "warn"} and item.get("fingerprint"):
                fingerprints.add(str(item["fingerprint"]))

    ok = result.returncode == 0 and counts["error"] == 0 and counts["warn"] == 0
    details: dict[str, object] = {
        "returncode": result.returncode,
        "counts": counts,
        "fingerprints": sorted(fingerprints),
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

    repeated = bool(active_fingerprints & previous_fingerprints)
    ok = follow_up_ok or not repeated
    if not initial_ok and follow_up_ok:
        summary = "security check recovered after auto-fix/retry"
    elif not follow_up_ok and not repeated:
        summary = "security check found non-repeated warnings (recorded for next run)"
    elif not follow_up_ok:
        summary = "security check reported error/warn findings (reproduced)"

    return CheckResult(
        ok=ok,
        summary=summary,
        details={
            "initial": initial_details,
            "fix": fix_details,
            "follow_up": follow_up_details,
            "previous_fingerprints": sorted(previous_fingerprints),
            "repeated": repeated,
            "state_path": str(state_path.relative_to(ctx.repo_root)),
            "auto_fix_enabled": auto_fix_enabled,
        },
        actions=actions,
    )


CHECK_MODES = {"full"}
