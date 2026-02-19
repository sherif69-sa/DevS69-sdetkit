from __future__ import annotations

import json

from ..types import CheckAction, CheckResult, MaintenanceContext
from ..utils import run_cmd

CHECK_NAME = "security_check"


def run(ctx: MaintenanceContext) -> CheckResult:
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
    if isinstance(findings, list):
        for item in findings:
            if not isinstance(item, dict):
                continue
            sev = str(item.get("severity", "info")).lower()
            if sev in counts:
                counts[sev] += 1
            else:
                counts["info"] += 1

    ok = result.returncode == 0 and counts["error"] == 0 and counts["warn"] == 0
    summary = (
        "security check has no error/warn findings"
        if ok
        else "security check reported error/warn findings"
    )
    actions = [
        CheckAction(
            id="security-triage",
            title="Run security triage summary",
            applied=False,
            notes="python tools/triage.py --mode security --run-security --security-baseline tools/security.baseline.json",
        )
    ]
    return CheckResult(
        ok=ok,
        summary=summary,
        details={
            "returncode": result.returncode,
            "counts": counts,
            "stdout": result.stdout,
            "stderr": result.stderr,
        },
        actions=actions,
    )


CHECK_MODES = {"full"}
