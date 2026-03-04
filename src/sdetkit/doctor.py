from __future__ import annotations

import argparse
import difflib
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from importlib import metadata
from pathlib import Path
from typing import Any

from . import _toml
from .import_hazards import find_stdlib_shadowing
from .security import SecurityError, safe_path

SEVERITY_ORDER = {"low": 1, "medium": 2, "high": 3}

CHECK_ORDER = [
    "pyproject",
    "stdlib_shadowing",
    "venv",
    "dev_tools",
    "clean_tree",
    "deps",
    "pre_commit",
    "ci_workflows",
    "security_files",
    "repo_readiness",
    "release_meta",
    "ascii",
]

SUPPORTED_POLICY_CHECKS = {
    "ascii",
    "stdlib_shadowing",
    "ci_workflows",
    "security_files",
    "clean_tree",
    "deps",
    "pre_commit",
    "repo_readiness",
    "release_meta",
}


def _make_check(
    *,
    ok: bool,
    severity: str = "medium",
    summary: str = "",
    evidence: list[dict[str, Any]] | None = None,
    fix: list[str] | None = None,
    skipped: bool | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "ok": ok,
        "severity": severity,
        "summary": summary,
        "evidence": evidence or [],
        "fix": fix or [],
    }
    if skipped is not None:
        item["skipped"] = skipped
    if meta:
        item["meta"] = meta
    return item


def _baseline_checks() -> dict[str, dict[str, Any]]:
    return {
        "ascii": _make_check(
            ok=True,
            summary="ASCII scan not requested",
            skipped=True,
            fix=["Run doctor with --ascii to scan src/ and tools/."],
        ),
        "stdlib_shadowing": _make_check(
            ok=True,
            summary="no stdlib shadowing detected",
            fix=["Rename top-level modules under src/ that shadow stdlib names."],
        ),
        "ci_workflows": _make_check(
            ok=True,
            summary="CI workflow check not requested",
            skipped=True,
            fix=["Run doctor with --ci to verify workflow policy."],
        ),
        "security_files": _make_check(
            ok=True,
            summary="security governance file check not requested",
            skipped=True,
            fix=["Run doctor with --ci to verify governance files."],
        ),
        "clean_tree": _make_check(
            ok=True,
            summary="clean tree check not requested",
            skipped=True,
            fix=["Run doctor with --clean-tree."],
        ),
        "deps": _make_check(
            ok=True,
            summary="dependency consistency check not requested",
            skipped=True,
            fix=["Run doctor with --deps."],
        ),
        "pre_commit": _make_check(
            ok=True,
            summary="pre-commit check not requested",
            skipped=True,
            fix=["Run doctor with --pre-commit."],
        ),
        "repo_readiness": _make_check(
            ok=True,
            summary="repo readiness check not requested",
            skipped=True,
            fix=[
                "Run doctor with --repo to validate gate scripts, templates, and pre-commit hooks."
            ],
        ),
        "release_meta": _make_check(
            ok=True,
            severity="high",
            summary="release metadata check not requested",
            skipped=True,
            fix=[
                "Run doctor with --release to validate version, changelog, and release workflow wiring."
            ],
        ),
    }


def _run(cmd: list[str], *, cwd: str | Path | None = None) -> tuple[int, str, str]:
    p = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd is not None else None,
        text=True,
        capture_output=True,
    )
    return p.returncode, p.stdout, p.stderr


def _python_info() -> dict[str, str]:
    return {
        "version": ".".join(str(x) for x in sys.version_info[:3]),
        "implementation": getattr(sys.implementation, "name", "python").capitalize(),
        "executable": sys.executable,
    }


def _package_info() -> dict[str, str]:
    name = "sdetkit"
    try:
        ver = metadata.version(name)
    except Exception:
        ver = "unknown"
    return {"name": name, "version": ver}


def _in_virtualenv() -> bool:
    if os.environ.get("VIRTUAL_ENV"):
        return True
    return sys.prefix != getattr(sys, "base_prefix", sys.prefix)


def _check_pyproject_toml(root: Path) -> tuple[bool, str]:
    path = root / "pyproject.toml"
    if not path.exists():
        return False, "pyproject.toml is missing"
    try:
        with path.open("rb") as f:
            _toml.loads(f.read().decode("utf-8"))
    except Exception as exc:
        return False, f"pyproject.toml parse failed: {exc}"
    return True, "pyproject.toml is valid TOML"


def _project_version_from_pyproject(root: Path) -> tuple[str | None, str | None]:
    path = root / "pyproject.toml"
    if not path.exists():
        return None, "pyproject.toml is missing"
    try:
        payload = _toml.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"pyproject.toml parse failed: {exc}"
    if not isinstance(payload, dict):
        return None, "pyproject.toml did not parse to a table"
    project = payload.get("project")
    if not isinstance(project, dict):
        return None, "[project] table is missing"
    version = project.get("version")
    if not isinstance(version, str) or not version.strip():
        return None, "[project].version is missing"
    return version.strip(), None


def _check_release_meta(
    root: Path,
) -> tuple[bool, str, list[dict[str, Any]], list[str], dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    fix: list[str] = []
    meta: dict[str, Any] = {}

    version, verr = _project_version_from_pyproject(root)
    if verr:
        evidence.append({"type": "pyproject_version", "message": verr, "path": "pyproject.toml"})
        fix.append("Set [project].version in pyproject.toml.")
    else:
        meta["version"] = version

    changelog = root / "CHANGELOG.md"
    if not changelog.exists():
        evidence.append(
            {"type": "missing_file", "message": "CHANGELOG.md is missing", "path": "CHANGELOG.md"}
        )
        fix.append("Add CHANGELOG.md with a version heading for the current release.")
    elif version:
        text = changelog.read_text(encoding="utf-8", errors="replace")
        pat = re.compile(rf"^##\s+\[?v?{re.escape(version)}\]?\s*$", re.M)
        if not pat.search(text):
            evidence.append(
                {
                    "type": "changelog",
                    "message": f"missing changelog heading for {version}",
                    "path": "CHANGELOG.md",
                }
            )
            fix.append(
                f"Add a CHANGELOG.md heading for {version} (e.g., ## [{version}] or ## v{version})."
            )

    wf_candidates = [
        root / ".github" / "workflows" / "release.yml",
        root / ".github" / "workflows" / "release.yaml",
    ]
    wf = next((x for x in wf_candidates if x.exists()), None)
    if wf is None:
        evidence.append(
            {
                "type": "missing_file",
                "message": "release workflow is missing",
                "path": ".github/workflows/release.yml",
            }
        )
        fix.append("Add .github/workflows/release.yml that validates tag vs package version.")
    else:
        wf_text = wf.read_text(encoding="utf-8", errors="replace")
        if "scripts/check_release_tag_version.py" not in wf_text:
            evidence.append(
                {
                    "type": "workflow",
                    "message": "release workflow does not run scripts/check_release_tag_version.py",
                    "path": wf.relative_to(root).as_posix(),
                }
            )
            fix.append(
                "Update the release workflow to run scripts/check_release_tag_version.py on the resolved tag."
            )

    script = root / "scripts" / "check_release_tag_version.py"
    if not script.exists():
        evidence.append(
            {
                "type": "missing_file",
                "message": "release tag/version check script missing",
                "path": "scripts/check_release_tag_version.py",
            }
        )
        fix.append("Add scripts/check_release_tag_version.py used by the release workflow.")

    ok = not bool(evidence)
    if ok and version:
        summary = f"release metadata present for v{version}"
    elif ok:
        summary = "release metadata present"
    else:
        summary = "release metadata missing or inconsistent"
    return ok, summary, evidence, fix, meta


def _is_ignored_binary(p: Path) -> bool:
    if any(part.endswith(".egg-info") for part in p.parts):
        return True
    if p.suffix.lower() == ".pyc":
        return True
    return "__pycache__" in p.parts


def _scan_non_ascii(root: Path) -> tuple[list[str], list[str]]:
    bad_rel: list[str] = []
    bad_stderr: list[str] = []
    for top in ("src", "tools"):
        base = root / top
        if not base.exists():
            continue
        for fp in base.rglob("*"):
            if not fp.is_file() or _is_ignored_binary(fp):
                continue
            try:
                b = fp.read_bytes()
            except OSError:
                continue
            if any(x >= 0x80 for x in b):
                rel = fp.relative_to(root).as_posix()
                bad_rel.append(rel)
                bad_stderr.append(f"non-ascii: {rel}")
    bad_rel.sort()
    bad_stderr.sort()
    return bad_rel, bad_stderr


def _check_ci_workflows(root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    groups = {
        "ci": [
            ".github/workflows/ci.yml",
            ".github/workflows/ci.yaml",
            ".github/workflows/tests.yml",
        ],
        "quality": [".github/workflows/quality.yml", ".github/workflows/quality.yaml"],
        "security": [".github/workflows/security.yml", ".github/workflows/security.yaml"],
    }
    missing_groups: list[str] = []
    evidence: list[dict[str, Any]] = []
    for group, options in groups.items():
        if not any((root / option).exists() for option in options):
            missing_groups.append(group)
            evidence.append(
                {
                    "type": "missing_group",
                    "message": f"missing required workflow group: {group}",
                    "path": ", ".join(options),
                }
            )
    return evidence, missing_groups


def _check_security_files(root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    groups = {
        "SECURITY.md": ["SECURITY.md"],
        "CONTRIBUTING.md": ["CONTRIBUTING.md"],
        "CODE_OF_CONDUCT.md": ["CODE_OF_CONDUCT.md"],
        "LICENSE": ["LICENSE", "LICENSE.txt", "LICENSE.md"],
    }
    missing: list[str] = []
    evidence: list[dict[str, Any]] = []
    for group, options in groups.items():
        if not any((root / option).exists() for option in options):
            missing.append(group)
            evidence.append(
                {
                    "type": "missing_file",
                    "message": f"missing required security/governance file: {group}",
                    "path": ", ".join(options),
                }
            )
    return evidence, missing


def _check_pre_commit(root: Path) -> bool:
    if not (root / ".pre-commit-config.yaml").exists():
        return False
    rc1, _o1, _e1 = _run([sys.executable, "-m", "pre_commit", "--version"], cwd=root)
    if rc1 != 0:
        return False
    rc2, _o2, _e2 = _run([sys.executable, "-m", "pre_commit", "validate-config"], cwd=root)
    return rc2 == 0


def _check_deps(root: Path) -> bool:
    rc, _o, _e = _run([sys.executable, "-m", "pip", "check"], cwd=root)
    return rc == 0


def _check_clean_tree(root: Path) -> bool:
    rc, out, _e = _run(["git", "status", "--porcelain"], cwd=root)
    if rc != 0:
        return False
    return out.strip() == ""


def _check_repo_readiness(root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    required = [
        "scripts/bootstrap.sh",
        "ci.sh",
        "quality.sh",
        "security.sh",
        "scripts/check_repo_layout.py",
        ".pre-commit-config.yaml",
    ]
    missing: list[str] = []
    evidence: list[dict[str, Any]] = []
    for rel in required:
        if not (root / rel).exists():
            missing.append(rel)
            evidence.append(
                {"type": "missing_file", "message": f"missing required file: {rel}", "path": rel}
            )

    layout = root / "scripts" / "check_repo_layout.py"
    if layout.exists():
        rc, out, err = _run([sys.executable, "scripts/check_repo_layout.py"], cwd=root)
        if rc != 0:
            missing.append("scripts/check_repo_layout.py:failed")
            msg = (err.strip() or out.strip() or "repo layout check failed").splitlines()[0]
            evidence.append(
                {"type": "repo_layout", "message": msg, "path": "scripts/check_repo_layout.py"}
            )

    pc = root / ".pre-commit-config.yaml"
    if pc.exists():
        content = pc.read_text(encoding="utf-8", errors="replace")
        for hook_id in ("ruff", "ruff-format", "mypy"):
            if f"id: {hook_id}" not in content:
                missing.append(f"pre-commit hook: {hook_id}")
                evidence.append(
                    {
                        "type": "pre_commit_hook",
                        "message": f"missing pre-commit hook id: {hook_id}",
                        "path": ".pre-commit-config.yaml",
                    }
                )

    return evidence, missing


def _check_tools() -> tuple[list[str], list[str]]:
    want_bins = ["git", "python3"]
    want_mods = {"pytest": "pytest", "ruff": "ruff"}
    present: set[str] = set()
    for t in want_bins:
        if shutil.which(t):
            present.add(t)
    for tool, mod in want_mods.items():
        if shutil.which(tool) or importlib.util.find_spec(mod) is not None:
            present.add(tool)
    missing = sorted([t for t in (want_bins + list(want_mods)) if t not in present])
    return sorted(present), missing


def _parse_check_csv(value: str | None) -> list[str]:
    if value is None:
        return []
    out: list[str] = []
    for part in value.split(","):
        s = part.strip()
        if s:
            out.append(s)
    return out


def _baseline_snapshot_path(root: Path) -> Path:
    return root / ".sdetkit" / "doctor.snapshot.json"


def _baseline_cmd(argv: list[str]) -> int:
    bp = argparse.ArgumentParser(prog="doctor baseline")
    bp.add_argument("action", choices=["write", "check"])
    bp.add_argument("--path", default=None)
    bp.add_argument("--diff", action="store_true")
    bp.add_argument("--diff-context", type=int, default=3)
    ns, extra = bp.parse_known_args(argv)
    if extra and extra[0] == "--":
        extra = extra[1:]

    root = Path.cwd()
    snap = Path(ns.path) if isinstance(ns.path, str) and ns.path else _baseline_snapshot_path(root)
    if not snap.is_absolute():
        snap = root / snap
    snap.parent.mkdir(parents=True, exist_ok=True)

    base = [
        "--dev",
        "--ci",
        "--deps",
        "--repo",
        "--fail-on",
        "high",
        "--format",
        "json",
    ]
    # Keep baseline snapshots stable by default, but never conflict with caller filters.
    if "--only" not in extra and "--skip" not in extra:
        base.extend(["--skip", "clean_tree"])
    if ns.action == "write":
        return main(base + ["--snapshot", str(snap)] + list(extra))

    diff_args: list[str] = []
    if getattr(ns, "diff", False):
        diff_args.append("--diff")
        diff_args.extend(["--diff-context", str(getattr(ns, "diff_context", 3))])

    return main(base + ["--diff-snapshot", str(snap)] + diff_args + list(extra))


def _stable_json(data: dict[str, Any]) -> str:
    return (
        json.dumps(
            data,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        + "\n"
    )


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _calculate_score(checks: list[bool]) -> int:
    if not checks:
        return 100
    passed = sum(1 for item in checks if item)
    return round((passed / len(checks)) * 100)


def _treatments(root: Path) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []

    cmd = [sys.executable, "-m", "ruff", "check", "--fix", "."]
    rc, stdout_text, stderr_text = _run(cmd, cwd=root)
    steps.append(
        {
            "id": "ruff_fix",
            "cmd": cmd,
            "rc": rc,
            "ok": rc == 0,
            "stdout": stdout_text,
            "stderr": stderr_text,
        }
    )

    cmd = [sys.executable, "-m", "ruff", "format", "."]
    rc, stdout_text, stderr_text = _run(cmd, cwd=root)
    steps.append(
        {
            "id": "ruff_format_apply",
            "cmd": cmd,
            "rc": rc,
            "ok": rc == 0,
            "stdout": stdout_text,
            "stderr": stderr_text,
        }
    )

    return steps


def _plan_id(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )
    return hashlib.sha256(raw).hexdigest()[:12]


def _build_plan(ns, is_selected) -> dict[str, Any]:
    actions: list[dict[str, Any]] = []
    actions.append(
        {
            "id": "ruff_fix",
            "cmd": [sys.executable, "-m", "ruff", "check", "--fix", "."],
            "reason": "Apply safe autofixes.",
            "affects_checks": [],
        }
    )
    actions.append(
        {
            "id": "ruff_format_apply",
            "cmd": [sys.executable, "-m", "ruff", "format", "."],
            "reason": "Normalize formatting.",
            "affects_checks": [],
        }
    )
    if getattr(ns, "pre_commit", False) and is_selected("pre_commit"):
        actions.append(
            {
                "id": "pre_commit_run",
                "cmd": [sys.executable, "-m", "pre_commit", "run", "-a"],
                "reason": "Apply repo hooks consistently.",
                "affects_checks": ["pre_commit"],
            }
        )
    plan: dict[str, Any] = {"actions": actions}
    plan["plan_id"] = _plan_id(plan)
    return plan


def _apply_plan(plan: dict[str, Any], root: Path) -> tuple[list[dict[str, Any]], bool]:
    steps: list[dict[str, Any]] = []
    for a in plan.get("actions", []):
        cmd = a.get("cmd")
        if not isinstance(cmd, list) or not cmd:
            continue
        rc, stdout_text, stderr_text = _run(cmd, cwd=root)
        steps.append(
            {
                "id": a.get("id"),
                "cmd": cmd,
                "rc": rc,
                "ok": rc == 0,
                "stdout": stdout_text,
                "stderr": stderr_text,
            }
        )
    ok = all(bool(s.get("ok")) for s in steps)
    return steps, ok


def _recommendations(data: dict[str, Any]) -> list[str]:
    recs: list[str] = []
    if data.get("venv_ok") is False:
        recs.append(
            "Create/activate a virtual environment before running dev checks: python -m venv .venv && source .venv/bin/activate."
        )
    if data.get("missing"):
        recs.append(
            f"Install missing developer tools: {', '.join(str(x) for x in data['missing'])}."
        )
    if data.get("pyproject_ok") is False:
        recs.append("Fix pyproject.toml syntax and re-run doctor before opening a PR.")
    if data.get("non_ascii"):
        recs.append(
            "Replace non-ASCII artifacts in src/ or tools/ with UTF-8 text, or move binaries outside scanned paths."
        )
    if data.get("ci_missing"):
        recs.append(f"Add missing CI workflows: {', '.join(str(x) for x in data['ci_missing'])}.")
    if data.get("security_missing"):
        recs.append(
            f"Add missing governance/security files: {', '.join(str(x) for x in data['security_missing'])}."
        )
    if data.get("pre_commit_ok") is False:
        recs.append("Install and validate pre-commit to enforce local quality gates.")
    if data.get("deps_ok") is False:
        recs.append("Run dependency updates and resolve `pip check` conflicts.")
    if data.get("clean_tree_ok") is False:
        recs.append("Commit or stash pending changes before release/CI validation.")
    if not recs:
        recs.append(
            "No immediate blockers detected. Keep CI, docs, and tests green for premium delivery quality."
        )
    return recs


def _print_human_report(data: dict[str, Any]) -> None:
    lines = [f"doctor score: {data['score']}%"]
    checks = data.get("checks", {})
    for key in sorted(checks):
        item = checks[key]
        marker = "OK" if item.get("ok") else "FAIL"
        lines.append(f"[{marker}] {key}: {item.get('summary') or ''}")
    lines.append("recommendations:")
    for rec in data.get("recommendations", []):
        lines.append(f"- {rec}")
    sys.stdout.write("\n".join(lines) + "\n")


def _print_pr_report(data: dict[str, Any]) -> None:
    checks = data.get("checks", {})
    lines = [
        "### SDET Doctor Report",
        f"- overall: {'PASS' if data.get('ok') else 'FAIL'}",
        f"- score: {data.get('score')}%",
        "- checks:",
    ]
    for key in sorted(checks):
        item = checks[key]
        marker = "PASS" if item.get("ok") else "FAIL"
        lines.append(f"  - {marker} `{key}`: {item.get('summary') or ''}")
    lines.append("- next steps:")
    for rec in data.get("recommendations", []):
        lines.append(f"  - {rec}")
    sys.stdout.write("\n".join(lines) + "\n")


def _format_doctor_markdown(data: dict[str, Any]) -> str:
    checks = data.get("checks", {})
    ordered_ids = sorted(checks)
    lines = [
        "### SDET Doctor Report",
        f"- overall: {'PASS' if data.get('ok') else 'FAIL'}",
        f"- score: {data.get('score')}%",
        "",
        "| Check | Severity | Status | Summary |",
        "| --- | --- | --- | --- |",
    ]
    for check_id in ordered_ids:
        item = checks[check_id]
        lines.append(
            f"| `{check_id}` | {item.get('severity', 'medium')} | {'PASS' if item.get('ok') else 'FAIL'} | {item.get('summary') or ''} |"
        )

    action_rows: list[tuple[int, str, str]] = []
    for check_id in ordered_ids:
        item = checks[check_id]
        if item.get("ok"):
            continue
        severity = str(item.get("severity", "medium"))
        rank = SEVERITY_ORDER.get(severity, SEVERITY_ORDER["medium"])
        for fix in item.get("fix", []):
            action_rows.append((rank, check_id, str(fix)))

    lines.append("")
    lines.append("#### Action items")
    if action_rows:
        for _rank, check_id, fix in sorted(
            action_rows, key=lambda item: (-item[0], item[1], item[2])
        ):
            lines.append(f"- `{check_id}`: {fix}")
    else:
        lines.append("- None")

    lines.append("")
    lines.append("#### Evidence")
    has_evidence = False
    for check_id in ordered_ids:
        item = checks[check_id]
        if item.get("ok"):
            continue
        evidence = item.get("evidence", [])
        if not evidence:
            continue
        has_evidence = True
        lines.append(f"- `{check_id}`")
        for ev in evidence:
            message = str(ev.get("message", ""))
            path = ev.get("path")
            if path:
                lines.append(f"  - {message} ({path})")
            else:
                lines.append(f"  - {message}")
    if not has_evidence:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def _resolve_policy_path(root: Path, policy_path: str | None) -> Path:
    if policy_path:
        return safe_path(root, policy_path, allow_absolute=True)
    return root / "sdetkit.policy.toml"


def _load_policy(root: Path, policy_path: str | None) -> dict[str, Any]:
    try:
        path = _resolve_policy_path(root, policy_path)
    except SecurityError as exc:
        return {"_error": f"policy path rejected: {exc}", "_path": str(policy_path or "")}
    if not path.exists():
        return {}
    try:
        payload = _toml.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_error": f"policy parse failed: {exc}", "_path": str(path)}
    return payload if isinstance(payload, dict) else {}


def _apply_policy(
    checks: dict[str, dict[str, Any]],
    policy: dict[str, Any],
    *,
    strict: bool,
) -> tuple[list[str], str | None]:
    policy_checks = policy.get("checks") if isinstance(policy, dict) else None
    unknown: list[str] = []
    if isinstance(policy_checks, dict):
        for key in sorted(policy_checks):
            if key not in checks:
                unknown.append(key)
                continue
            cfg = policy_checks.get(key)
            if not isinstance(cfg, dict):
                continue
            severity = cfg.get("severity")
            if severity in SEVERITY_ORDER:
                checks[key]["severity"] = severity
            require_ok = cfg.get("require_ok")
            if isinstance(require_ok, bool):
                checks[key].setdefault("meta", {})["require_ok"] = require_ok
            weight = cfg.get("weight")
            if isinstance(weight, int) and 0 <= weight <= 100:
                checks[key].setdefault("meta", {})["weight"] = weight
            enabled = cfg.get("enabled")
            if enabled is False:
                checks[key] = _make_check(
                    ok=True,
                    severity=checks[key].get("severity", "medium"),
                    summary=f"{key} check disabled by policy",
                    evidence=[],
                    fix=[],
                    skipped=True,
                    meta=checks[key].get("meta", {}),
                )
    strict_error = None
    if strict and unknown:
        strict_error = f"unknown policy checks: {', '.join(unknown)}"
    return unknown, strict_error


def _resolve_threshold(ns: argparse.Namespace, policy: dict[str, Any]) -> str:
    if isinstance(ns.fail_on, str):
        return ns.fail_on
    thresholds = policy.get("thresholds") if isinstance(policy, dict) else None
    if isinstance(thresholds, dict):
        candidate = thresholds.get("fail_on")
        if isinstance(candidate, str) and candidate in SEVERITY_ORDER:
            return candidate
    return "high"


def _evaluate_gate(checks: dict[str, dict[str, Any]], threshold: str) -> tuple[bool, list[str]]:
    failed: list[str] = []
    gate = SEVERITY_ORDER[threshold]
    for check_id in sorted(checks):
        item = checks[check_id]
        require_ok = item.get("meta", {}).get("require_ok", True)
        if not require_ok:
            continue
        sev = item.get("severity", "medium")
        sev_rank = SEVERITY_ORDER.get(sev, SEVERITY_ORDER["medium"])
        if (not item.get("ok", False)) and sev_rank >= gate:
            failed.append(check_id)
    return (not failed), failed


def main(argv: list[str] | None = None) -> int:
    raw = list(argv) if argv is not None else None
    args0 = raw if raw is not None else list(sys.argv[1:])
    value_opts = {
        "--format",
        "--fail-on",
        "--policy",
        "--out",
        "--only",
        "--skip",
        "--apply-plan",
        "--snapshot",
        "--diff-snapshot",
    }
    i = 0
    while i < len(args0):
        a = args0[i]
        if a in value_opts:
            i += 2
            continue
        if a == "baseline":
            return _baseline_cmd(args0[i + 1 :])
        i += 1

    parser = argparse.ArgumentParser(prog="doctor")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--format", choices=["text", "json", "md", "markdown"], default="text")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--ascii", action="store_true")
    parser.add_argument("--ci", action="store_true")
    parser.add_argument("--pre-commit", dest="pre_commit", action="store_true")
    parser.add_argument("--deps", action="store_true")
    parser.add_argument("--clean-tree", dest="clean_tree", action="store_true")
    parser.add_argument("--repo", "--repo-readiness", dest="repo_readiness", action="store_true")
    parser.add_argument("--dev", action="store_true")
    parser.add_argument("--pyproject", action="store_true")
    parser.add_argument("--pr", action="store_true", help="print a PR-ready markdown summary")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--release", action="store_true")
    parser.add_argument("--release-full", dest="release_full", action="store_true")
    parser.add_argument("--policy")
    parser.add_argument("--fail-on", choices=["low", "medium", "high"])
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--out", default=None)
    parser.add_argument("--treat", action="store_true")
    parser.add_argument("--treat-only", dest="treat_only", action="store_true")
    parser.add_argument("--plan", action="store_true")
    parser.add_argument("--apply-plan", dest="apply_plan", default=None)
    parser.add_argument("--snapshot", default=None)
    parser.add_argument("--diff-snapshot", dest="diff_snapshot", default=None)
    parser.add_argument("--diff", action="store_true")
    parser.add_argument("--diff-context", type=int, default=3)
    parser.add_argument("--list-checks", action="store_true")
    parser.add_argument("--only", default=None)
    parser.add_argument("--skip", default=None)

    ns = parser.parse_args(list(argv) if argv is not None else None)
    if ns.format == "markdown":
        ns.format = "md"
    if ns.format == "json":
        ns.json = True
    root = Path.cwd()
    if ns.list_checks:
        sys.stdout.write("\n".join(CHECK_ORDER) + "\n")
        return 0

    only_raw = _parse_check_csv(ns.only)
    skip_raw = _parse_check_csv(ns.skip)
    if only_raw and skip_raw:
        parser.error("use only one of --only or --skip")
    unknown = sorted({x for x in (only_raw + skip_raw) if x not in CHECK_ORDER})
    if unknown:
        parser.error("unknown check id(s): " + ", ".join(unknown))
    only_set = set(only_raw)
    skip_set = set(skip_raw)

    if only_set:
        ns.ascii = False
        ns.ci = False
        ns.pre_commit = False
        ns.deps = False
        ns.clean_tree = False
        ns.repo_readiness = False
        ns.dev = False
        ns.pyproject = False
        ns.all = False
        ns.release = False
        ns.release_full = False

        if "pyproject" in only_set:
            ns.pyproject = True
        if "ascii" in only_set:
            ns.ascii = True
        if "ci_workflows" in only_set or "security_files" in only_set:
            ns.ci = True
        if "deps" in only_set:
            ns.deps = True
        if "clean_tree" in only_set:
            ns.clean_tree = True
        if "repo_readiness" in only_set:
            ns.repo_readiness = True
        if "pre_commit" in only_set:
            ns.pre_commit = True
        if "venv" in only_set or "dev_tools" in only_set:
            ns.dev = True
        if "release_meta" in only_set:
            ns.release = True

    def _is_selected(check_id: str) -> bool:
        if only_set:
            return check_id in only_set
        if skip_set:
            return check_id not in skip_set
        return True

    release_any = bool(ns.release or getattr(ns, "release_full", False))

    plan = _build_plan(ns, _is_selected)

    if getattr(ns, "plan", False):
        payload = {"ok": True, "plan": plan}
        rendered = json.dumps(payload) + "\n"
        if ns.out:
            Path(ns.out).write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
        return 0

    plan_steps: list[dict[str, Any]] = []
    plan_ok = True
    if isinstance(getattr(ns, "apply_plan", None), str) and ns.apply_plan:
        if ns.apply_plan != plan.get("plan_id"):
            payload = {
                "ok": False,
                "error": "plan_id_mismatch",
                "expected": plan.get("plan_id"),
                "provided": ns.apply_plan,
                "plan": plan,
            }
            rendered = json.dumps(payload) + "\n"
            if ns.out:
                Path(ns.out).write_text(rendered, encoding="utf-8")
            else:
                sys.stdout.write(rendered)
            return 2
        plan_steps, plan_ok = _apply_plan(plan, root)

    if ns.all:
        ns.ascii = True
        ns.ci = True
        ns.deps = True
        ns.clean_tree = True

    if release_any and _is_selected("release_meta"):
        ns.pyproject = True
        ns.clean_tree = True

    if getattr(ns, "release_full", False):
        ns.ascii = True
        ns.ci = True
        ns.pre_commit = True
        ns.deps = True
        ns.dev = True
        ns.repo_readiness = True

    if ns.dev and (ns.ci or ns.deps or ns.clean_tree):
        ns.pyproject = True

    treat_steps: list[dict[str, Any]] = []
    data_treat_ok = True

    if ns.treat or getattr(ns, "treat_only", False):
        treat_steps = _treatments(root)
        data_treat_ok = all(bool(s.get("ok")) for s in treat_steps)
        if getattr(ns, "treat_only", False):
            payload = {
                "ok": data_treat_ok,
                "treatments": treat_steps,
                "treatments_ok": data_treat_ok,
                "post_treat_ok": data_treat_ok,
            }
            rendered = json.dumps(payload) + "\n"
            if ns.out:
                Path(ns.out).write_text(rendered, encoding="utf-8")
            else:
                sys.stdout.write(rendered)
            return 0 if data_treat_ok else 2

    data: dict[str, Any] = {
        "python": _python_info(),
        "package": _package_info(),
        "checks": _baseline_checks(),
    }
    if ns.treat:
        data["treatments"] = treat_steps
        data["treatments_ok"] = data_treat_ok

    if isinstance(getattr(ns, "apply_plan", None), str) and ns.apply_plan:
        data["plan"] = plan
        data["plan_steps"] = plan_steps
        data["plan_ok"] = plan_ok

    score_items: list[bool] = []

    if _is_selected("stdlib_shadowing"):
        shadow = find_stdlib_shadowing(Path("."))
        if shadow:
            data["checks"]["stdlib_shadowing"] = _make_check(
                ok=False,
                severity="high",
                summary="stdlib shadowing detected",
                evidence=[
                    {
                        "type": "shadowing",
                        "message": f"stdlib module shadowed: {name}",
                        "path": f"src/{name}.py",
                    }
                    for name in shadow
                ],
                fix=["Rename modules under src/ that match Python stdlib module names."],
                meta={"shadow": shadow},
            )
            data["checks"]["stdlib_shadowing"]["shadow"] = shadow
            sys.stderr.write("[WARN] stdlib-shadow: " + ", ".join(shadow) + "\n")
        else:
            data["checks"]["stdlib_shadowing"] = _make_check(
                ok=True,
                severity="high",
                summary="no stdlib shadowing detected",
                evidence=[],
                fix=["Keep src/ module names distinct from Python standard library modules."],
                meta={"shadow": []},
            )
            data["checks"]["stdlib_shadowing"]["shadow"] = []
    else:
        data["checks"]["stdlib_shadowing"] = _make_check(
            ok=True,
            severity="high",
            summary="stdlib shadowing check not selected",
            evidence=[],
            fix=[],
            skipped=True,
            meta={"shadow": []},
        )
        data["checks"]["stdlib_shadowing"]["shadow"] = []

    if ns.dev:
        venv_ok = _in_virtualenv()
        data["venv_ok"] = venv_ok
        data["checks"]["venv"] = _make_check(
            ok=venv_ok,
            summary="virtual environment is active"
            if venv_ok
            else "virtual environment is not active (recommended for stable tooling/deps)",
            severity="high" if release_any else "low",
            evidence=[] if venv_ok else [{"type": "environment", "message": "VIRTUAL_ENV not set"}],
            fix=[] if venv_ok else ["python -m venv .venv && source .venv/bin/activate"],
        )
        score_items.append(venv_ok)

        present, missing = _check_tools()
        data["tools"] = present
        data["missing"] = missing
        tools_ok = not bool(missing)
        data["checks"]["dev_tools"] = _make_check(
            ok=tools_ok,
            severity="medium",
            summary="all required developer tools are available"
            if tools_ok
            else "some developer tools are missing",
            evidence=[] if tools_ok else [{"type": "missing_tools", "message": ", ".join(missing)}],
            fix=[] if tools_ok else ["Install required developer tools listed in evidence."],
        )
        score_items.append(tools_ok)
    else:
        data.setdefault("missing", [])

    if ns.pyproject and _is_selected("pyproject"):
        pyproject_ok, pyproject_summary = _check_pyproject_toml(root)
        data["pyproject_ok"] = pyproject_ok
        data["checks"]["pyproject"] = _make_check(
            ok=pyproject_ok,
            severity="high",
            summary=pyproject_summary,
            evidence=[]
            if pyproject_ok
            else [{"type": "parse", "message": pyproject_summary, "path": "pyproject.toml"}],
            fix=[] if pyproject_ok else ["Fix pyproject.toml syntax."],
        )
        score_items.append(pyproject_ok)
    if release_any:
        rel_ok, rel_summary, rel_ev, rel_fix, rel_meta = _check_release_meta(root)
        data["release_meta_ok"] = rel_ok
        data["checks"]["release_meta"] = _make_check(
            ok=rel_ok,
            severity="high",
            summary=rel_summary,
            evidence=rel_ev,
            fix=rel_fix,
            skipped=False,
            meta=rel_meta,
        )
        score_items.append(rel_ok)

    if ns.ascii and _is_selected("ascii"):
        bad, bad_err = _scan_non_ascii(root)
        data["non_ascii"] = bad
        check_ok = not bool(bad)
        data["checks"]["ascii"] = _make_check(
            ok=check_ok,
            severity="medium",
            summary="only ASCII content found under src/ and tools/"
            if check_ok
            else "non-ASCII bytes detected under src/ or tools/",
            evidence=[
                {"type": "non_ascii", "message": "non-ASCII bytes detected", "path": rel}
                for rel in bad
            ],
            fix=[]
            if check_ok
            else ["Replace non-ASCII bytes or relocate binary artifacts outside src/ and tools/."],
            skipped=False,
        )
        score_items.append(check_ok)
        for line in bad_err:
            sys.stderr.write(line + "\n")

    if ns.ci and _is_selected("ci_workflows"):
        ci_evidence, ci_missing_groups = _check_ci_workflows(root)
        sec_evidence, sec_missing = _check_security_files(root)
        data["ci_missing"] = ci_missing_groups
        data["security_missing"] = sec_missing

        ci_ok = not bool(ci_missing_groups)
        data["checks"]["ci_workflows"] = _make_check(
            ok=ci_ok,
            severity="high",
            summary="required CI workflows found"
            if ci_ok
            else f"missing workflow groups: {', '.join(ci_missing_groups)}",
            evidence=ci_evidence,
            fix=[]
            if ci_ok
            else ["Add minimal CI workflow", "Add quality workflow", "Add security workflow"],
            skipped=False,
        )
        score_items.append(ci_ok)

        sec_ok = not bool(sec_missing)
        data["checks"]["security_files"] = _make_check(
            ok=sec_ok,
            severity="medium",
            summary="required governance/security files found"
            if sec_ok
            else f"missing files: {', '.join(sec_missing)}",
            evidence=sec_evidence,
            fix=[]
            if sec_ok
            else [
                "Add SECURITY.md",
                "Add CONTRIBUTING.md",
                "Add CODE_OF_CONDUCT.md",
                "Add a LICENSE file",
            ],
            skipped=False,
        )
        score_items.append(sec_ok)

    if ns.pre_commit and _is_selected("pre_commit"):
        pc_ok = _check_pre_commit(root)
        data["pre_commit_ok"] = pc_ok
        data["checks"]["pre_commit"] = _make_check(
            ok=pc_ok,
            severity="medium",
            summary="pre-commit is installed and configuration is valid"
            if pc_ok
            else "pre-commit is missing or configuration is invalid",
            evidence=[]
            if pc_ok
            else [
                {
                    "type": "tooling",
                    "message": "pre-commit unavailable or invalid config",
                    "path": ".pre-commit-config.yaml",
                }
            ],
            fix=[] if pc_ok else ["Install pre-commit and run pre-commit validate-config."],
            skipped=False,
        )
        score_items.append(pc_ok)

    if ns.deps and _is_selected("deps"):
        deps_ok = _check_deps(root)
        data["deps_ok"] = deps_ok
        data["checks"]["deps"] = _make_check(
            ok=deps_ok,
            severity="high",
            summary="pip dependency graph is consistent"
            if deps_ok
            else "pip dependency issues detected",
            evidence=[]
            if deps_ok
            else [{"type": "dependency", "message": "pip check reported dependency conflicts"}],
            fix=[] if deps_ok else ["Run pip check locally and resolve dependency conflicts."],
            skipped=False,
        )
        score_items.append(deps_ok)

    if ns.clean_tree and _is_selected("clean_tree"):
        ct_ok = _check_clean_tree(root)
        data["clean_tree_ok"] = ct_ok
        data["checks"]["clean_tree"] = _make_check(
            ok=ct_ok,
            severity="high" if release_any else "low",
            summary="working tree is clean" if ct_ok else "working tree has uncommitted changes",
            evidence=[]
            if ct_ok
            else [{"type": "git", "message": "git status --porcelain returned changes"}],
            fix=[] if ct_ok else ["Commit or stash local changes."],
            skipped=False,
        )
        score_items.append(ct_ok)

    if ns.repo_readiness and _is_selected("repo_readiness"):
        rr_evidence, rr_missing = _check_repo_readiness(root)
        data["repo_readiness_missing"] = rr_missing
        rr_ok = not bool(rr_missing)
        data["checks"]["repo_readiness"] = _make_check(
            ok=rr_ok,
            severity="high",
            summary="repo readiness checks passed" if rr_ok else "repo readiness issues detected",
            evidence=rr_evidence,
            fix=[]
            if rr_ok
            else [
                "Add missing gate scripts and required templates.",
                "Ensure scripts/check_repo_layout.py passes.",
                "Add required pre-commit hooks: ruff, ruff-format, mypy.",
            ],
            skipped=False,
        )
        score_items.append(rr_ok)

    policy = _load_policy(root, ns.policy)
    if policy.get("_error"):
        sys.stderr.write(str(policy["_error"]) + "\n")
    unknown_policy_checks, strict_error = _apply_policy(data["checks"], policy, strict=ns.strict)
    if strict_error:
        data["checks"]["policy_strict"] = _make_check(
            ok=False,
            severity="high",
            summary=strict_error,
            evidence=[{"type": "policy", "message": strict_error}],
            fix=["Remove unknown check ids from policy file or disable --strict."],
        )
    if unknown_policy_checks:
        sys.stderr.write(
            f"[WARN] unknown policy checks ignored: {', '.join(unknown_policy_checks)}\n"
        )

    threshold = _resolve_threshold(ns, policy)
    gate_ok, failed_checks = _evaluate_gate(data["checks"], threshold)
    data["selected_checks"] = [cid for cid in CHECK_ORDER if _is_selected(cid)]
    next_actions: list[dict[str, Any]] = []
    for cid in CHECK_ORDER:
        chk = data["checks"].get(cid)
        if not isinstance(chk, dict):
            continue
        if chk.get("skipped"):
            continue
        if chk.get("ok") is False:
            next_actions.append(
                {
                    "id": cid,
                    "severity": chk.get("severity"),
                    "summary": chk.get("summary"),
                    "fix": chk.get("fix", []),
                }
            )
    next_actions.sort(
        key=lambda x: (-SEVERITY_ORDER.get(str(x.get("severity")), 0), str(x.get("id")))
    )
    data["next_actions"] = next_actions

    try:
        policy_resolved = _resolve_policy_path(root, ns.policy)
        policy_path_text = str(policy_resolved)
    except SecurityError:
        policy_path_text = str(ns.policy) if ns.policy else str(root / "sdetkit.policy.toml")

    data["policy"] = {
        "path": policy_path_text,
        "strict": bool(ns.strict),
        "fail_on": threshold,
    }
    data["score"] = _calculate_score(score_items)
    data["recommendations"] = _recommendations(data)
    data["ok"] = bool(gate_ok)
    if failed_checks:
        data["failed_checks"] = failed_checks
    if isinstance(getattr(ns, "apply_plan", None), str) and ns.apply_plan:
        data["post_plan_ok"] = bool(data.get("ok")) and bool(data.get("plan_ok"))

    if ns.format == "json" or ns.json:
        output = json.dumps(data, sort_keys=True) + "\n"
        is_json = True
    elif ns.format == "md" or ns.pr:
        output = _format_doctor_markdown(data)
        is_json = False
    else:
        lines = [f"doctor score: {data['score']}%"]
        checks = data.get("checks", {})
        for key in sorted(checks):
            item = checks[key]
            marker = "OK" if item.get("ok") else "FAIL"
            lines.append(f"[{marker}] {key}: {item.get('summary') or ''}")
        lines.append("recommendations:")
        for rec in data.get("recommendations", []):
            lines.append(f"- {rec}")
        output = "\n".join(lines) + "\n"
        is_json = False

    snap_base = data
    stable_text = _stable_json(snap_base)

    if isinstance(getattr(ns, "snapshot", None), str) and ns.snapshot:
        Path(ns.snapshot).write_text(stable_text, encoding="utf-8")

    if isinstance(getattr(ns, "diff_snapshot", None), str) and ns.diff_snapshot:
        snap_path = Path(ns.diff_snapshot)
        snap_text = _read_text(snap_path) if snap_path.exists() else ""
        diff_ok = snap_text == stable_text
        diff_summary: list[str] = []
        if not diff_ok:
            diff_summary.append("snapshot drift detected")
            if not snap_path.exists():
                diff_summary.append("snapshot file missing")
            gate_ok = False
            data["ok"] = False

        data["snapshot_diff_ok"] = diff_ok
        data["snapshot_diff_summary"] = diff_summary

        if getattr(ns, "diff", False) and not diff_ok:
            n = int(getattr(ns, "diff_context", 3) or 0)
            n = n if n >= 0 else 0
            a = snap_text
            b = stable_text
            try:
                ao = json.loads(a)
                a = json.dumps(ao, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
            except json.JSONDecodeError:
                pass
            try:
                bo = json.loads(b)
                b = json.dumps(bo, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
            except json.JSONDecodeError:
                pass
            diff_lines = difflib.unified_diff(
                a.splitlines(keepends=True),
                b.splitlines(keepends=True),
                fromfile="snapshot",
                tofile="current",
                n=n,
            )
            diff_text = "".join(diff_lines)
            if diff_text and not diff_text.endswith("\n"):
                diff_text += "\n"
            data["snapshot_diff"] = diff_text

        if is_json:
            output = _stable_json(data)

    if ns.out:
        Path(ns.out).write_text(output, encoding="utf-8")

    sys.stdout.write(output)

    if not gate_ok and not is_json:
        sys.stderr.write("doctor: problems found\n")

    return 0 if gate_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
