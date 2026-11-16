"""Automated safe remediation: diagnose errors and apply verified mechanical fixes."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from sdetkit import adaptive_safe_fix, investigate
from sdetkit.gates.project_env import resolve_project_python

SCHEMA_VERSION = "sdetkit.auto_fix.v1"
JsonObject = dict[str, Any]


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def _safe_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return []


def _inspect_working_tree_issues(executable: str, root: Path, timeout: int) -> str:
    logs: list[str] = []
    for cmd in (
        [executable, "-m", "ruff", "check", "."],
        [executable, "-m", "ruff", "format", "--check", "."],
    ):
        try:
            proc = subprocess.run(
                cmd,
                cwd=root,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            if proc.returncode != 0:
                output = (proc.stdout + "\n" + proc.stderr).strip()
                if output:
                    logs.append(output)
        except (OSError, subprocess.TimeoutExpired):
            continue
    return "\n".join(logs).strip()


def diagnose_evidence(
    log_text: str | None = None,
    *,
    root: Path,
    timeout: int = 60,
) -> JsonObject:
    env = resolve_project_python(root)
    text = (log_text or "").strip()
    if not text:
        text = _inspect_working_tree_issues(env.executable, root, timeout)
        if not text:
            return {
                "clean": True,
                "safe_to_auto_fix": True,
                "classification": "CLEAN_TREE",
                "summary": "Working tree is clean; no fixable formatting or lint issues found.",
                "confidence": "high",
                "requires_human_review": False,
                "proof_commands": [],
                "next_actions": [],
                "affected_files": [],
                "diagnosis": {},
            }

    normalized_text = text.replace("\\", "/")
    if "would be reformatted" in normalized_text:
        normalized_text = normalized_text.replace("would be reformatted", "reformatted")

    return investigate._payload_for_failure(normalized_text)


def plan_remediation(diagnosis: JsonObject, *, root: Path) -> JsonObject:
    if diagnosis.get("clean"):
        return {
            "schema_version": SCHEMA_VERSION,
            "clean": True,
            "safe_to_auto_fix": True,
            "fix_type": "none",
            "classification": "CLEAN_TREE",
            "confidence": "high",
            "requires_human_review": False,
            "reason": "Working tree is clean; no fixable issues found.",
            "commands": [],
            "proof_commands": [],
            "affected_files": [],
        }

    raw_diag = diagnosis.get("diagnosis")
    diag_payload = raw_diag if isinstance(raw_diag, dict) else {}
    plan = adaptive_safe_fix.build_plan(diag_payload)
    safe = bool(plan.get("safe_to_auto_fix", False))
    classification = _safe_str(diagnosis.get("classification") or "UNKNOWN")
    fix_type = _safe_str(plan.get("fix_type") or "review_required")
    reason = _safe_str(plan.get("reason") or "Manual review required.")
    affected = _safe_list(plan.get("affected_files") or diagnosis.get("affected_files"))
    confidence = _safe_str(diagnosis.get("confidence") or plan.get("confidence") or "medium")

    env = resolve_project_python(root)
    py = env.executable
    target_args = affected if affected else ["."]

    commands: list[list[str]] = []
    proof_commands: list[list[str]] = []

    if safe:
        if fix_type == "format_only":
            commands = [
                [py, "-m", "ruff", "format", *target_args],
            ]
            proof_commands = [
                [py, "-m", "ruff", "format", "--check", *target_args],
            ]
        elif fix_type == "ruff_fixable_lint":
            commands = [
                [py, "-m", "ruff", "check", "--fix", *target_args],
                [py, "-m", "ruff", "format", *target_args],
            ]
            proof_commands = [
                [py, "-m", "ruff", "check", *target_args],
                [py, "-m", "ruff", "format", "--check", *target_args],
            ]
    else:
        raw_proofs = _safe_list(diagnosis.get("proof_commands"))
        proof_commands = [[c] for c in raw_proofs] if raw_proofs else []

    return {
        "schema_version": SCHEMA_VERSION,
        "clean": False,
        "safe_to_auto_fix": safe,
        "fix_type": fix_type,
        "classification": classification,
        "confidence": confidence,
        "requires_human_review": not safe,
        "reason": reason,
        "commands": commands,
        "proof_commands": proof_commands,
        "affected_files": affected,
    }


def _git_status_files(root: Path) -> list[str]:
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if proc.returncode == 0:
            lines = proc.stdout.splitlines()
            return [line[3:].strip() for line in lines if len(line) > 3]
    except (OSError, subprocess.TimeoutExpired):
        pass
    return []


def execute_safe_fix(
    plan: JsonObject,
    *,
    root: Path,
    timeout: int = 120,
) -> JsonObject:
    if plan.get("clean"):
        return {
            "ok": True,
            "applied": False,
            "clean": True,
            "classification": "CLEAN_TREE",
            "message": "Working tree is clean; no fixable issues found.",
            "changed_files": [],
            "commands_run": [],
            "proof_passed": True,
        }

    if not plan.get("safe_to_auto_fix"):
        return {
            "ok": False,
            "applied": False,
            "clean": False,
            "classification": plan.get("classification", "REVIEW_REQUIRED"),
            "reason": plan.get("reason", "manual review required"),
            "requires_human_review": True,
            "proof_commands": [" ".join(c) for c in plan.get("proof_commands", [])],
            "changed_files": [],
            "commands_run": [],
            "proof_passed": False,
        }

    commands_run: list[str] = []
    for cmd in plan.get("commands", []):
        commands_run.append(" ".join(cmd))
        try:
            subprocess.run(
                cmd,
                cwd=root,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as err:
            return {
                "ok": False,
                "applied": True,
                "clean": False,
                "classification": plan.get("classification"),
                "error": f"failed executing fix command {cmd}: {err}",
                "commands_run": commands_run,
                "changed_files": [],
                "proof_passed": False,
            }

    changed = _git_status_files(root)

    proof_passed = True
    proof_failures: list[str] = []
    for pcmd in plan.get("proof_commands", []):
        try:
            pproc = subprocess.run(
                pcmd,
                cwd=root,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            if pproc.returncode != 0:
                proof_passed = False
                proof_failures.append(" ".join(pcmd))
        except (OSError, subprocess.TimeoutExpired):
            proof_passed = False
            proof_failures.append(" ".join(pcmd))

    return {
        "ok": proof_passed,
        "applied": True,
        "clean": False,
        "classification": plan.get("classification"),
        "fix_type": plan.get("fix_type"),
        "changed_files": changed,
        "commands_run": commands_run,
        "proof_passed": proof_passed,
        "proof_failures": proof_failures,
        "reason": plan.get("reason"),
    }


def render_markdown(result: JsonObject, *, dry_run: bool = False) -> str:
    if result.get("clean"):
        return (
            "### \u2705 SDETKit auto-fix: CLEAN\n\n"
            "Working tree is clean; no fixable formatting or lint issues detected."
        )

    safe = bool(result.get("safe_to_auto_fix", result.get("ok", False)))
    cls = result.get("classification", "UNKNOWN")

    if not safe and not result.get("applied"):
        reason = result.get("reason", "manual review required")
        text = (
            f"### \u26a0\ufe0f SDETKit auto-fix: BLOCKED ({cls})\n\n"
            f"**Boundary**: Auto-fix is restricted to verified mechanical fixes.\n"
            f"**Reason**: {reason}\n"
        )
        proofs = result.get("proof_commands") or []
        if proofs:
            text += "\n**Verification proof commands**:\n"
            for p in proofs:
                text += f"- `{p}`\n"
        return text.strip()

    if dry_run:
        fix_type = result.get("fix_type", "mechanical")
        text = (
            f"### \u2139\ufe0f SDETKit auto-fix: PREVIEW ({cls})\n\n"
            f"**Fix type**: `{fix_type}` | **Safe to auto-fix**: `true`\n"
            f"**Rationale**: {result.get('reason', '')}\n"
        )
        cmds = result.get("commands") or []
        if cmds:
            text += "\n**Planned fix commands**:\n"
            for cmd in cmds:
                text += f"- `{' '.join(cmd) if isinstance(cmd, list) else cmd}`\n"
        proofs = result.get("proof_commands") or []
        if proofs:
            text += "\n**Proof verification commands**:\n"
            for p in proofs:
                text += f"- `{' '.join(p) if isinstance(p, list) else p}`\n"
        return text.strip()

    proof_passed = result.get("proof_passed", False)
    icon = "\u2705" if proof_passed else "\u274c"
    changed = result.get("changed_files") or []

    text = (
        f"### {icon} SDETKit auto-fix: "
        f"{'APPLIED & VERIFIED' if proof_passed else 'APPLIED WITH PROOF FAILURE'}\n\n"
        f"**Classification**: `{cls}` | **Proof passed**: `{proof_passed}`\n"
    )
    if changed:
        text += f"\n**Modified files ({len(changed)})**:\n"
        for f in changed:
            text += f"- `{f}`\n"
    else:
        text += "\nNo files modified on disk.\n"

    cmds = result.get("commands_run") or []
    if cmds:
        text += "\n**Executed commands**:\n"
        for c in cmds:
            text += f"- `{c}`\n"

    return text.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit auto-fix",
        description="Diagnose failures and automatically apply verified safe mechanical fixes.",
    )
    parser.add_argument(
        "--repo-root", default=".", help="Root directory of the repository (default: current dir)"
    )
    parser.add_argument(
        "--log", default=None, help="Path to error log or traceback file to diagnose and fix"
    )
    parser.add_argument("--text", default=None, help="Inline log or error text")
    parser.add_argument(
        "--apply", action="store_true", help="Apply the verified fix to the working tree"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview the fix without modifying files (default)"
    )
    parser.add_argument(
        "--format",
        choices=["text", "json", "md"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument("--out", default=None, help="Write output payload to this file")

    args = parser.parse_args(argv)
    root = Path(args.repo_root).resolve()

    log_text: str | None = None
    if args.text:
        log_text = args.text
    elif args.log:
        target = Path(args.log)
        if not target.is_absolute():
            target = root / target
        if not target.is_file():
            sys.stderr.write(f"auto-fix error: log file does not exist: {target}\n")
            return 2
        log_text = target.read_text(encoding="utf-8")

    diagnosis = diagnose_evidence(log_text, root=root)
    plan = plan_remediation(diagnosis, root=root)

    should_apply = args.apply and not args.dry_run

    if should_apply:
        result = execute_safe_fix(plan, root=root)
    else:
        result = {
            **plan,
            "applied": False,
            "dry_run": True,
        }

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    if args.format == "json":
        print(json.dumps(result, indent=2))
    elif args.format == "md":
        print(render_markdown(result, dry_run=not should_apply))
    else:
        print(render_markdown(result, dry_run=not should_apply))

    if not result.get("safe_to_auto_fix", result.get("ok", False)):
        return 1
    return 0
