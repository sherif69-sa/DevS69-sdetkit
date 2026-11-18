"""Automated safe remediation: diagnose errors and apply verified mechanical fixes."""

from __future__ import annotations

import argparse
import ast
import difflib
import json
import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from sdetkit import adaptive_safe_fix, investigate
from sdetkit.gates.project_env import resolve_project_python

SCHEMA_VERSION = "sdetkit.auto_fix.v1"
JsonObject = dict[str, Any]
SUPPORTED_RULES = ("all", "format", "imports", "unused_imports", "whitespace", "lint")


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def _safe_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return []


def _is_text_file(path: Path) -> bool:
    try:
        data = path.read_bytes()
        return b"\x00" not in data[:1024]
    except OSError:
        # File may be missing, locked, or unreadable during check.
        return False


def _fix_trailing_whitespace(path: Path) -> bool:
    if not _is_text_file(path):
        return False
    try:
        content = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        # Skip binary or unreadable files.
        return False

    lines = content.splitlines()
    fixed_lines = [line.rstrip(" \t") for line in lines]
    new_content = "\n".join(fixed_lines)
    if fixed_lines:
        new_content += "\n"
    if new_content != content:
        try:
            path.write_text(new_content, encoding="utf-8")
            return True
        except OSError:
            # Cannot write file; skip.
            return False
    return False


def _verify_python_syntax(paths: Sequence[Path]) -> tuple[bool, str | None]:
    for p in paths:
        if p.is_file() and p.suffix == ".py":
            try:
                code = p.read_text(encoding="utf-8", errors="replace")
                ast.parse(code, filename=str(p))
            except SyntaxError as exc:
                return False, f"SyntaxError in {p.name}:{exc.lineno}: {exc.msg}"
    return True, None


def _take_snapshots(paths: Sequence[Path]) -> dict[Path, str]:
    snaps: dict[Path, str] = {}
    for p in paths:
        if p.is_file():
            try:
                snaps[p] = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                # Ignore unreadable files when capturing pre-fix snapshot.
                pass
    return snaps


def _restore_snapshots(snapshots: dict[Path, str]) -> None:
    for path, content in snapshots.items():
        try:
            path.write_text(content, encoding="utf-8")
        except OSError:
            # Best-effort restoration on verification failure.
            pass


def _compute_diff(snapshots: dict[Path, str], root: Path) -> str:
    diff_lines: list[str] = []
    for path in sorted(snapshots):
        if not path.is_file():
            continue
        try:
            new_text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            # Ignore unreadable file during diff generation.
            continue
        old_text = snapshots[path]
        if new_text != old_text:
            try:
                rel = path.relative_to(root).as_posix()
            except ValueError:
                rel = path.name
            diff = difflib.unified_diff(
                old_text.splitlines(keepends=True),
                new_text.splitlines(keepends=True),
                fromfile=f"a/{rel}",
                tofile=f"b/{rel}",
            )
            diff_lines.extend(diff)
    return "".join(diff_lines)


def _inspect_working_tree_issues(
    executable: str,
    root: Path,
    timeout: int,
    rules: set[str] | None = None,
) -> str:
    logs: list[str] = []
    active = rules or {"all"}
    check_commands: list[list[str]] = []

    if "all" in active or "lint" in active:
        check_commands.append([executable, "-m", "ruff", "check", "."])
    elif "imports" in active:
        check_commands.append([executable, "-m", "ruff", "check", "--select", "I", "."])
    elif "unused_imports" in active:
        check_commands.append([executable, "-m", "ruff", "check", "--select", "F401", "."])

    if "all" in active or "format" in active:
        check_commands.append([executable, "-m", "ruff", "format", "--check", "."])

    for cmd in check_commands:
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
            # Best-effort inspection: ignore if tool is absent or command times out.
            continue
    return "\n".join(logs).strip()


def diagnose_evidence(
    log_text: str | None = None,
    *,
    root: Path,
    timeout: int = 60,
    rules: Sequence[str] | None = None,
) -> JsonObject:
    env = resolve_project_python(root)
    text = (log_text or "").strip()
    active_rules = set(r.strip().lower() for r in (rules or []))
    if not text:
        text = _inspect_working_tree_issues(env.executable, root, timeout, active_rules)
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


def plan_remediation(
    diagnosis: JsonObject,
    *,
    root: Path,
    rules: Sequence[str] | None = None,
) -> JsonObject:
    norm_rules = [r.strip().lower() for r in (rules or []) if r.strip()]
    selected_rules = set(norm_rules) if norm_rules else {"all"}

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
            "rules": list(selected_rules),
            "fix_whitespace": False,
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
    fix_whitespace = "all" in selected_rules or "whitespace" in selected_rules

    if safe or selected_rules != {"all"}:
        if "all" in selected_rules:
            if fix_type == "format_only":
                commands.append([py, "-m", "ruff", "format", *target_args])
                proof_commands.append([py, "-m", "ruff", "format", "--check", *target_args])
            elif fix_type == "ruff_fixable_lint":
                commands.append([py, "-m", "ruff", "check", "--fix", *target_args])
                commands.append([py, "-m", "ruff", "format", *target_args])
                proof_commands.append([py, "-m", "ruff", "check", *target_args])
                proof_commands.append([py, "-m", "ruff", "format", "--check", *target_args])
            else:
                commands.append([py, "-m", "ruff", "check", "--fix", *target_args])
                commands.append([py, "-m", "ruff", "format", *target_args])
                proof_commands.append([py, "-m", "ruff", "check", *target_args])
                proof_commands.append([py, "-m", "ruff", "format", "--check", *target_args])
        else:
            if "format" in selected_rules:
                commands.append([py, "-m", "ruff", "format", *target_args])
                proof_commands.append([py, "-m", "ruff", "format", "--check", *target_args])
            if "imports" in selected_rules:
                commands.append([py, "-m", "ruff", "check", "--select", "I", "--fix", *target_args])
                proof_commands.append([py, "-m", "ruff", "check", "--select", "I", *target_args])
            if "unused_imports" in selected_rules:
                commands.append(
                    [py, "-m", "ruff", "check", "--select", "F401", "--fix", *target_args]
                )
                proof_commands.append([py, "-m", "ruff", "check", "--select", "F401", *target_args])
            if "lint" in selected_rules:
                commands.append([py, "-m", "ruff", "check", "--fix", *target_args])
                proof_commands.append([py, "-m", "ruff", "check", *target_args])

        safe = bool(commands or fix_whitespace)
        if safe:
            reason = (
                f"Safe mechanical fixes planned for rules: {', '.join(sorted(selected_rules))}."
            )
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
        "rules": list(selected_rules),
        "fix_whitespace": fix_whitespace,
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
        # Best-effort helper: inability to query git status should not fail auto-fix execution.
        return []
    return []


def _resolve_candidate_files(plan: JsonObject, root: Path) -> list[Path]:
    affected = _safe_list(plan.get("affected_files"))
    candidates: list[Path] = []
    if affected:
        for f in affected:
            p = (root / f).resolve()
            if p.is_file():
                candidates.append(p)
    if not candidates:
        for rel in _git_status_files(root):
            p = (root / rel).resolve()
            if p.is_file():
                candidates.append(p)
    if not candidates and plan.get("fix_whitespace"):
        for p in root.rglob("*.py"):
            if p.is_file() and ".git" not in p.parts:
                candidates.append(p.resolve())
    return candidates


def execute_safe_fix(
    plan: JsonObject,
    *,
    root: Path,
    timeout: int = 120,
    dry_run: bool = False,
    include_diff: bool = False,
) -> JsonObject:
    if plan.get("clean"):
        return {
            "ok": True,
            "applied": False,
            "clean": True,
            "safe_to_auto_fix": True,
            "requires_human_review": False,
            "classification": "CLEAN_TREE",
            "message": "Working tree is clean; no fixable issues found.",
            "changed_files": [],
            "commands": [],
            "commands_run": [],
            "proof_passed": True,
            "diff": "",
        }

    if not plan.get("safe_to_auto_fix"):
        return {
            "ok": False,
            "applied": False,
            "clean": False,
            "safe_to_auto_fix": False,
            "classification": plan.get("classification", "REVIEW_REQUIRED"),
            "reason": plan.get("reason", "manual review required"),
            "requires_human_review": True,
            "proof_commands": [" ".join(c) for c in plan.get("proof_commands", [])],
            "changed_files": [],
            "commands": [],
            "commands_run": [],
            "proof_passed": False,
            "diff": "",
        }

    candidates = _resolve_candidate_files(plan, root)
    snapshots = _take_snapshots(candidates)

    if plan.get("fix_whitespace"):
        for path in candidates:
            _fix_trailing_whitespace(path)

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
            _restore_snapshots(snapshots)
            return {
                "ok": False,
                "applied": False,
                "clean": False,
                "safe_to_auto_fix": bool(plan.get("safe_to_auto_fix", True)),
                "requires_human_review": True,
                "classification": plan.get("classification"),
                "error": f"failed executing fix command {cmd}: {err}",
                "commands": plan.get("commands", []),
                "commands_run": commands_run,
                "changed_files": [],
                "proof_passed": False,
                "diff": "",
            }

    changed_from_status = _git_status_files(root)
    changed_paths_set = {(root / f).resolve() for f in changed_from_status if (root / f).is_file()}
    for snap_path, old_text in snapshots.items():
        if snap_path.is_file():
            try:
                if snap_path.read_text(encoding="utf-8", errors="replace") != old_text:
                    changed_paths_set.add(snap_path)
            except OSError:
                # Ignore unreadable file during change detection.
                pass
    changed_paths = sorted(changed_paths_set)
    changed = [
        str(p.relative_to(root)).replace("\\", "/") if p.is_relative_to(root) else p.name
        for p in changed_paths
    ]

    syntax_ok, syntax_err = _verify_python_syntax(changed_paths)
    if not syntax_ok:
        _restore_snapshots(snapshots)
        return {
            "ok": False,
            "applied": False,
            "clean": False,
            "safe_to_auto_fix": bool(plan.get("safe_to_auto_fix", True)),
            "requires_human_review": True,
            "classification": plan.get("classification"),
            "error": f"Syntax preservation failure: {syntax_err}. Changes safely rolled back.",
            "commands": plan.get("commands", []),
            "commands_run": commands_run,
            "changed_files": [],
            "proof_passed": False,
            "syntax_error": True,
            "diff": "",
        }

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

    diff_text = _compute_diff(snapshots, root) if (include_diff or dry_run) else ""

    if dry_run:
        _restore_snapshots(snapshots)
        return {
            "ok": proof_passed,
            "applied": False,
            "clean": False,
            "dry_run": True,
            "safe_to_auto_fix": bool(plan.get("safe_to_auto_fix", True)),
            "requires_human_review": bool(plan.get("requires_human_review", False)),
            "classification": plan.get("classification"),
            "fix_type": plan.get("fix_type"),
            "changed_files": changed,
            "commands": plan.get("commands", []),
            "commands_run": commands_run,
            "proof_passed": proof_passed,
            "proof_failures": proof_failures,
            "reason": plan.get("reason"),
            "diff": diff_text,
        }

    if not proof_passed:
        _restore_snapshots(snapshots)
        return {
            "ok": False,
            "applied": False,
            "clean": False,
            "safe_to_auto_fix": bool(plan.get("safe_to_auto_fix", True)),
            "requires_human_review": True,
            "classification": plan.get("classification"),
            "fix_type": plan.get("fix_type"),
            "changed_files": [],
            "commands": plan.get("commands", []),
            "commands_run": commands_run,
            "proof_passed": False,
            "proof_failures": proof_failures,
            "reason": "Proof verification failed; changes safely reverted.",
            "diff": diff_text,
        }

    return {
        "ok": True,
        "applied": True,
        "clean": False,
        "safe_to_auto_fix": bool(plan.get("safe_to_auto_fix", True)),
        "requires_human_review": False,
        "classification": plan.get("classification"),
        "fix_type": plan.get("fix_type"),
        "changed_files": changed,
        "commands": plan.get("commands", []),
        "commands_run": commands_run,
        "proof_passed": True,
        "proof_failures": [],
        "reason": plan.get("reason"),
        "diff": diff_text,
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

    if dry_run or result.get("dry_run"):
        fix_type = result.get("fix_type", "mechanical")
        text = (
            f"### \u2139\ufe0f SDETKit auto-fix: PREVIEW ({cls})\n\n"
            f"**Fix type**: `{fix_type}` | **Safe to auto-fix**: `true`\n"
            f"**Rationale**: {result.get('reason', '')}\n"
        )
        cmds = result.get("commands") or result.get("commands_run") or []
        if cmds:
            text += "\n**Planned fix commands**:\n"
            for cmd in cmds:
                text += f"- `{' '.join(cmd) if isinstance(cmd, list) else cmd}`\n"
        diff = result.get("diff")
        if diff:
            text += f"\n**Proposed diff**:\n```diff\n{diff}```\n"
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

    diff = result.get("diff")
    if diff:
        text += f"\n**Remediation diff**:\n```diff\n{diff}```\n"

    return text.strip()


# =============================================================================
# Autonomous Self-Healing Diagnostic Daemon Engine
# =============================================================================

HEAL_SCHEMA_VERSION = "sdetkit.heal.v1"


def heal_workspace(
    root: Path,
    *,
    apply: bool = False,
    verify: bool = True,
    target_test: str | None = None,
    log_text: str | None = None,
    rules: Sequence[str] | None = None,
    timeout: int = 180,
) -> JsonObject:
    resolved_root = root.resolve()
    actions_taken: list[JsonObject] = []
    issues_detected: list[JsonObject] = []
    changed_files: list[str] = []
    diff_text: str = ""

    # 1. Mechanical diagnosis and remediation
    rule_list = list(rules) if rules else ["all"]
    diag = diagnose_evidence(log_text, root=resolved_root, rules=rule_list)

    is_clean = bool(diag.get("clean", False))
    safe_to_fix = bool(diag.get("safe_to_auto_fix", False))
    cls = str(diag.get("classification") or "CLEAN_TREE")

    if not is_clean:
        issues_detected.append(
            {
                "category": "MECHANICAL" if safe_to_fix else "LOGIC",
                "classification": cls,
                "description": diag.get("reason", "Code drift or error detected"),
                "affected_files": diag.get("affected_files", []),
            }
        )

    if safe_to_fix:
        plan = plan_remediation(diag, root=resolved_root, rules=rule_list)
        fix_result = execute_safe_fix(
            plan,
            root=resolved_root,
            timeout=timeout,
            dry_run=not apply,
            include_diff=True,
        )
        if fix_result.get("applied") or fix_result.get("changed_files"):
            changed_files.extend(fix_result.get("changed_files", []))
            diff_text = str(fix_result.get("diff", ""))
            actions_taken.append(
                {
                    "type": "AUTO_FIX_APPLIED" if apply else "AUTO_FIX_PREVIEW",
                    "rules": rule_list,
                    "changed_files": fix_result.get("changed_files", []),
                    "commands": fix_result.get("commands_run", []),
                }
            )

    # 2. Flake hunting and automatic quarantine if target_test provided
    if target_test:
        from sdetkit.flake_hunter import add_to_quarantine, hunt_flakes

        flake_res = hunt_flakes(resolved_root, target=target_test, runs=5, timeout=timeout)
        if flake_res.get("verdict") == "flaky":
            issues_detected.append(
                {
                    "category": "FLAKY_TEST",
                    "classification": "NON_DETERMINISTIC_TEST",
                    "description": (
                        f"Test {target_test} exhibited non-determinism with "
                        f"{flake_res.get('flake_rate_pct')}% flake rate."
                    ),
                    "target_test": target_test,
                    "flake_details": flake_res,
                }
            )
            if apply:
                q_res = add_to_quarantine(
                    resolved_root,
                    target_test,
                    reason=f"Auto-healed: {flake_res.get('flake_rate_pct')}% flake rate",
                    owner="sdetkit-heal",
                    classification=str(flake_res.get("classification", "TIMING_RACE")),
                )
                actions_taken.append(
                    {
                        "type": "TEST_QUARANTINED",
                        "test_id": target_test,
                        "expires_at": q_res.get("expires_at"),
                        "owner": "sdetkit-heal",
                    }
                )
            else:
                actions_taken.append(
                    {
                        "type": "TEST_QUARANTINE_PREVIEW",
                        "test_id": target_test,
                        "flake_rate_pct": flake_res.get("flake_rate_pct"),
                    }
                )

    # 3. Impact-guided proof verification & blast radius check
    verification_passed = True
    impact_report: JsonObject | None = None
    blast_radius_report: JsonObject | None = None

    if verify and (changed_files or apply):
        from sdetkit.dependency_map import (
            analyze_impact,
            evaluate_blast_radius,
            run_impacted_tests,
        )

        impact_report = analyze_impact(
            resolved_root, files=changed_files if changed_files else None
        )
        if impact_report.get("all_impacted_tests") and apply:
            run_res = run_impacted_tests(impact_report, root=resolved_root, timeout=timeout)
            verification_passed = bool(run_res.get("ok", True))
            actions_taken.append(
                {
                    "type": "IMPACTED_TESTS_VERIFIED",
                    "tests_executed": impact_report.get("selected_tests_count", 0),
                    "passed": verification_passed,
                }
            )

        blast_radius_report = evaluate_blast_radius(
            resolved_root, files=changed_files if changed_files else None
        )

    # 4. Synthesize final status and verdict
    has_unfixable_logic = any(i.get("category") == "LOGIC" for i in issues_detected)
    if has_unfixable_logic:
        status = "NEEDS_HUMAN_REVIEW"
        verdict = "REVIEW_REQUIRED"
        heal_score = 0.0
        recommendation = (
            "Logic error or assertion failure detected. Manual engineer review required."
        )
    elif not issues_detected:
        status = "CLEAN"
        verdict = "HEALTHY"
        heal_score = 100.0
        recommendation = "Workspace is completely healthy. Zero failures or drift detected."
    elif not apply:
        status = "PREVIEW_READY"
        verdict = "DRY_RUN"
        heal_score = 100.0
        recommendation = (
            "Auto-remediation plan synthesized. Run with --apply to execute verified fixes."
        )
    elif verification_passed:
        status = "HEALED"
        verdict = "SHIP"
        heal_score = 100.0
        recommendation = (
            "All detected issues were automatically healed and verified against impacted tests."
        )
    else:
        status = "HEAL_VERIFICATION_FAILED"
        verdict = "NO_SHIP"
        heal_score = 50.0
        recommendation = "Fixes applied but post-heal verification tests failed."

    return {
        "schema_version": HEAL_SCHEMA_VERSION,
        "status": status,
        "verdict": verdict,
        "heal_score": heal_score,
        "applied": apply,
        "issues_detected": issues_detected,
        "actions_taken": actions_taken,
        "changed_files": sorted(set(changed_files)),
        "diff": diff_text,
        "impact": impact_report,
        "blast_radius": blast_radius_report,
        "recommendation": recommendation,
    }


def render_heal_markdown(report: JsonObject) -> str:
    status = report.get("status", "UNKNOWN")
    verdict = report.get("verdict", "UNKNOWN")
    score = report.get("heal_score", 0.0)
    applied = report.get("applied", False)
    issues = report.get("issues_detected") or []
    actions = report.get("actions_taken") or []
    changed = report.get("changed_files") or []
    rec = report.get("recommendation", "")
    diff = report.get("diff", "")
    blast = report.get("blast_radius") or {}

    lines = [
        f"### [HEAL: {verdict} ({score}%)] SDETKit Autonomous Self-Healing",
        "",
        f"- **Status**: `{status}`",
        f"- **Mode**: `{'APPLIED & EXECUTED' if applied else 'PREVIEW (DRY-RUN)'}`",
        f"- **Issues Detected**: `{len(issues)}`",
        f"- **Actions Taken**: `{len(actions)}`",
    ]

    if changed:
        lines.append(f"- **Modified Files**: `{', '.join(changed)}`")
    if blast:
        idx = blast.get("blast_radius_index", 0.0)
        tier = blast.get("risk_tier", "LOW")
        lines.append(f"- **Blast Radius**: `{idx}% [{tier}]`")

    lines.append("")
    lines.append(f"> **Policy Decision**: {rec}")
    lines.append("")

    if actions:
        lines.append("#### Remediation Actions")
        for a in actions:
            lines.append(f"- `{a.get('type')}`: {a}")
        lines.append("")

    if diff:
        lines.append("<details><summary><b>Remediation Diff</b></summary>\n")
        lines.append(f"```diff\n{diff}\n```")
        lines.append("\n</details>\n")

    return "\n".join(lines).strip() + "\n"


def heal_main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit heal",
        description="Autonomous self-healing engine: diagnose, remediate, quarantine, and prove.",
    )
    parser.add_argument(
        "--repo-root", default=".", help="Root directory of the repository (default: current dir)"
    )
    parser.add_argument(
        "--apply", action="store_true", help="Apply the verified heal plan to the workspace"
    )
    parser.add_argument(
        "--dry-run",
        "--check",
        action="store_true",
        help="Preview the heal plan without modifying files (default)",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip post-heal impacted test verification",
    )
    parser.add_argument(
        "--target-test",
        default=None,
        help="Target test ID to verify for flakiness and auto-quarantine",
    )
    parser.add_argument(
        "--log", default=None, help="Path to error log or traceback file to diagnose and heal"
    )
    parser.add_argument("--text", default=None, help="Inline log or error text")
    parser.add_argument(
        "--rules",
        default="all",
        help="Comma-separated rules to apply: all, format, imports, unused_imports, whitespace, lint",
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

    rule_list = [r.strip() for r in str(args.rules).split(",") if r.strip()]

    log_text: str | None = None
    if args.text:
        log_text = args.text
    elif args.log:
        target = Path(args.log)
        if not target.is_absolute():
            target = root / target
        if not target.is_file():
            sys.stderr.write(f"heal error: log file does not exist: {target}\n")
            return 2
        log_text = target.read_text(encoding="utf-8")

    should_apply = args.apply and not args.dry_run

    report = heal_workspace(
        root,
        apply=should_apply,
        verify=not args.no_verify,
        target_test=args.target_test,
        log_text=log_text,
        rules=rule_list,
    )

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    if args.format == "json":
        print(json.dumps(report, indent=2))
    elif args.format in ("md", "markdown"):
        print(render_heal_markdown(report))
    else:
        print(render_heal_markdown(report))

    if report.get("verdict") in ("NO_SHIP", "REVIEW_REQUIRED"):
        return 1
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args_list = list(argv) if argv is not None else list(sys.argv[1:])
    is_heal = (
        ("heal" in sys.argv)
        or (os.environ.get("SDETKIT_SUBCOMMAND") == "heal")
        or (bool(args_list) and args_list[0] == "heal")
    )
    if is_heal:
        if args_list and args_list[0] == "heal":
            args_list = args_list[1:]
        return heal_main(args_list)
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
        "--dry-run",
        "--check",
        action="store_true",
        help="Preview the fix without modifying files (default)",
    )
    parser.add_argument(
        "--rules",
        default="all",
        help="Comma-separated rules to apply: all, format, imports, unused_imports, whitespace, lint",
    )
    parser.add_argument(
        "--diff", "--preview", action="store_true", help="Output unified diff of proposed changes"
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

    rule_list = [r.strip() for r in str(args.rules).split(",") if r.strip()]

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

    diagnosis = diagnose_evidence(log_text, root=root, rules=rule_list)
    plan = plan_remediation(diagnosis, root=root, rules=rule_list)

    should_apply = args.apply and not args.dry_run

    result = execute_safe_fix(
        plan,
        root=root,
        dry_run=not should_apply,
        include_diff=args.diff,
    )

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
