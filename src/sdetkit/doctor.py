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

from . import _toml, upgrade_audit
from .bools import coerce_bool
from .evidence_workspace import record_workspace_run
from .import_hazards import find_stdlib_shadowing
from .judgment import build_judgment, load_latest_previous_payload
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
    "upgrade_audit",
    "ascii",
]

SCHEMA_VERSION = "sdetkit.doctor.v2"
EXIT_OK = 0
EXIT_FAILED = 2
EVIDENCE_SCHEMA_VERSION = "sdetkit.doctor.evidence.v2"
EVIDENCE_MANIFEST_SCHEMA_VERSION = "sdetkit.doctor.evidence.manifest.v1"
EVIDENCE_PROFILES = ("ci", "release", "full")
EVIDENCE_INCLUDES = ("failed", "actionable", "all")

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
    "upgrade_audit",
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


def _int_value(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


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
        "upgrade_audit": _make_check(
            ok=True,
            severity="medium",
            summary="upgrade audit check not requested",
            skipped=True,
            fix=[
                "Run doctor with --upgrade-audit to surface dependency upgrade hints and impact areas."
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


def _build_explain_payload(data: dict[str, Any]) -> dict[str, Any]:
    judgment = data.get("judgment", {}) if isinstance(data.get("judgment"), dict) else {}
    confidence_obj = judgment.get("confidence", {}) if isinstance(judgment, dict) else {}
    confidence_score = confidence_obj.get("score") if isinstance(confidence_obj, dict) else 0
    base_confidence = (
        float(confidence_score) / 100.0 if isinstance(confidence_score, (int, float)) else 0.0
    )
    explain_steps: list[dict[str, Any]] = []
    severity_weight = {"high": 0.95, "medium": 0.75, "low": 0.6}
    for index, action in enumerate(data.get("next_actions", []), start=1):
        if not isinstance(action, dict):
            continue
        severity = str(action.get("severity", "medium"))
        weighted = round(min(0.99, max(0.05, base_confidence * severity_weight.get(severity, 0.7))), 2)
        fix_list = action.get("fix", [])
        first_fix = fix_list[0] if isinstance(fix_list, list) and fix_list else "Review check output"
        explain_steps.append(
            {
                "priority": index,
                "check_id": str(action.get("id", "unknown")),
                "severity": severity,
                "confidence": weighted,
                "reason": str(action.get("summary", "")),
                "recommended_fix": str(first_fix),
            }
        )
    return {
        "mode": "doctor-explain",
        "overall_ok": bool(data.get("ok")),
        "summary": "Prioritized remediation plan generated from current doctor findings.",
        "steps": explain_steps,
    }


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
    ok = all(coerce_bool(s.get("ok"), default=False) for s in steps)
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
    upgrade_meta = data.get("checks", {}).get("upgrade_audit", {}).get("meta", {})
    priority_queue = upgrade_meta.get("priority_queue", [])
    if isinstance(priority_queue, list):
        for item in priority_queue[:2]:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            action = str(item.get("manifest_action", "")).strip()
            suggested = item.get("suggested_version")
            next_action = str(item.get("next_action", "")).strip()
            if name and action and action != "none":
                version_text = (
                    f" to {suggested}" if isinstance(suggested, str) and suggested else ""
                )
                recs.append(
                    f"Upgrade-audit priority: {name} via {action}{version_text}. {next_action}"
                )
    impact_summary = upgrade_meta.get("impact_summary", [])
    if isinstance(impact_summary, list):
        for item in impact_summary:
            if not isinstance(item, dict) or int(item.get("actionable_packages", 0)) <= 0:
                continue
            impact_area = str(item.get("impact_area", "")).strip()
            commands = item.get("validation_commands", [])
            command_text = ""
            if isinstance(commands, list) and commands:
                command_text = str(commands[0]).strip()
            if impact_area == "quality-tooling":
                rec = "Quality lane follow-up: batch actionable quality-tooling upgrades with full gate reruns."
                if command_text:
                    rec += f" Start with {command_text}."
                recs.append(rec)
            elif impact_area == "runtime-core":
                rec = "Runtime lane follow-up: validate runtime-core dependency upgrades against the fast gate first."
                if command_text:
                    rec += f" Start with {command_text}."
                recs.append(rec)
            elif impact_area == "integration-adapters":
                rec = "Integration lane follow-up: keep adapter upgrades isolated and verify notification/integration tests."
                if command_text:
                    rec += f" Start with {command_text}."
                recs.append(rec)
            if len(recs) >= 6:
                break
    risk_summary = upgrade_meta.get("risk_summary", [])
    if isinstance(risk_summary, list):
        for item in risk_summary:
            if not isinstance(item, dict):
                continue
            band = str(item.get("risk_band", "")).strip()
            actionable_count = _int_value(item.get("actionable_packages", 0))
            packages = item.get("packages", [])
            package_text = ", ".join(
                str(name).strip() for name in packages[:3] if str(name).strip()
            )
            if band in {"critical", "high"} and actionable_count > 0:
                rec = f"Risk compression: clear the {band}-band upgrade queue before broad repo churn."
                if package_text:
                    rec += f" Start with {package_text}."
                recs.append(rec)
                break
    release_freshness_summary = upgrade_meta.get("release_freshness_summary", [])
    if isinstance(release_freshness_summary, list):
        for item in release_freshness_summary:
            if not isinstance(item, dict):
                continue
            freshness = str(item.get("release_freshness", "")).strip()
            count = int(item.get("count", 0))
            actionable_count = _int_value(item.get("actionable_packages", 0))
            packages = item.get("packages", [])
            package_text = ", ".join(
                str(name).strip() for name in packages[:3] if str(name).strip()
            )
            if freshness == "fresh-release" and count > 0:
                rec = f"Fresh release watchlist: {count} package(s) landed in the last 14 days."
                if package_text:
                    rec += f" Review {package_text} for fast-follow validation."
                recs.append(rec)
            elif freshness == "stale" and actionable_count > 0:
                rec = f"Stale dependency lane: {actionable_count} actionable package(s) target releases older than a year."
                if package_text:
                    rec += f" Start with {package_text}."
                recs.append(rec)
            if len(recs) >= 6:
                break
    validation_summary = upgrade_meta.get("validation_summary", [])
    if isinstance(validation_summary, list):
        for item in validation_summary:
            if not isinstance(item, dict):
                continue
            command = str(item.get("command", "")).strip()
            actionable_count = _int_value(item.get("actionable_packages", 0))
            if command and actionable_count > 0:
                recs.append(
                    f"Validation batching: use `{command}` as a shared guardrail across {actionable_count} actionable package(s)."
                )
                break
    if not recs:
        recs.append(
            "No immediate blockers detected. Keep CI, docs, and tests green for premium delivery quality."
        )
    return recs


def _build_quality_summary(
    checks: dict[str, dict[str, Any]],
    *,
    selected_checks: list[str],
    hints: list[str] | None = None,
) -> dict[str, Any]:
    ordered_selected = [check_id for check_id in CHECK_ORDER if check_id in selected_checks]
    passed = 0
    failed = 0
    skipped = 0
    highest_failure_severity = "none"
    highest_failure_rank = 0
    failed_check_ids: list[str] = []
    fix_count = 0
    evidence_count = 0
    severity_breakdown = {"low": 0, "medium": 0, "high": 0}
    checks_with_fix = 0
    checks_with_evidence = 0

    for check_id in ordered_selected:
        item = checks.get(check_id, {})
        if item.get("skipped"):
            skipped += 1
            continue
        if item.get("ok"):
            passed += 1
            continue
        failed += 1
        failed_check_ids.append(check_id)
        severity = str(item.get("severity", "medium"))
        severity_rank = SEVERITY_ORDER.get(severity, 0)
        if severity_rank > highest_failure_rank:
            highest_failure_rank = severity_rank
            highest_failure_severity = severity
        if severity in severity_breakdown:
            severity_breakdown[severity] += 1
        item_fix_count = len(item.get("fix", []))
        item_evidence_count = len(item.get("evidence", []))
        fix_count += item_fix_count
        evidence_count += item_evidence_count
        if item_fix_count:
            checks_with_fix += 1
        if item_evidence_count:
            checks_with_evidence += 1

    total = len(ordered_selected)
    actionable = passed + failed
    pass_rate = 100 if actionable == 0 else round((passed / actionable) * 100)

    return {
        "selected_checks": total,
        "actionable_checks": actionable,
        "passed_checks": passed,
        "failed_checks": failed,
        "skipped_checks": skipped,
        "pass_rate": pass_rate,
        "highest_failure_severity": highest_failure_severity,
        "failed_check_ids": failed_check_ids,
        "fix_count": fix_count,
        "evidence_count": evidence_count,
        "failed_severity_breakdown": severity_breakdown,
        "checks_with_fix": checks_with_fix,
        "checks_with_evidence": checks_with_evidence,
        "hint_count": len(hints or []),
    }


def _build_hints(data: dict[str, Any], *, limit: int = 8) -> list[str]:
    hints: list[str] = []

    next_actions = data.get("next_actions", [])
    if isinstance(next_actions, list):
        for item in next_actions[:3]:
            if not isinstance(item, dict):
                continue
            check_id = str(item.get("id", "")).strip()
            summary = str(item.get("summary", "")).strip()
            fix_list = item.get("fix", [])
            first_fix = ""
            if isinstance(fix_list, list) and fix_list:
                first_fix = str(fix_list[0]).strip()
            parts = [
                part
                for part in [f"{check_id}: {summary}" if check_id and summary else "", first_fix]
                if part
            ]
            if parts:
                hints.append(" - ".join(parts))

    upgrade_meta = data.get("checks", {}).get("upgrade_audit", {}).get("meta", {})
    priority_queue = upgrade_meta.get("priority_queue", [])
    if isinstance(priority_queue, list):
        for item in priority_queue[:3]:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            action = str(item.get("manifest_action", "")).strip()
            target = str(item.get("suggested_version", "")).strip()
            validations = item.get("validation_commands", [])
            validation = ""
            if isinstance(validations, list) and validations:
                validation = str(validations[0]).strip()
            lane = str(item.get("lane", "")).strip()
            actionable = action and action != "none"
            if actionable:
                detail = f"{name}: {action}"
                if target:
                    detail += f" -> {target}"
                if lane:
                    detail += f" [{lane}]"
                if validation:
                    detail += f" - validate with {validation}"
                hints.append(detail)
                continue
            detail = f"watchlist {name}"
            if lane:
                detail += f" [{lane}]"
            if validation:
                detail += f" - keep validating with {validation}"
            hints.append(detail)

    lane_summary = upgrade_meta.get("lane_summary", [])
    if isinstance(lane_summary, list):
        for item in lane_summary[:2]:
            if not isinstance(item, dict):
                continue
            lane = str(item.get("lane", "")).strip()
            count = int(item.get("count", 0))
            actionable_count = _int_value(item.get("actionable_packages", 0))
            packages = item.get("packages", [])
            package_text = ""
            if isinstance(packages, list) and packages:
                package_text = ", ".join(
                    str(name).strip() for name in packages[:3] if str(name).strip()
                )
            if lane and count > 0:
                detail = f"lane {lane}: {count} package(s)"
                if actionable_count > 0:
                    detail += f", actionable {actionable_count}"
                if package_text:
                    detail += f" - focus on {package_text}"
                hints.append(detail)

    impact_summary = upgrade_meta.get("impact_summary", [])
    if isinstance(impact_summary, list):
        for item in impact_summary[:2]:
            if not isinstance(item, dict):
                continue
            impact_area = str(item.get("impact_area", "")).strip()
            actionable_count = _int_value(item.get("actionable_packages", 0))
            commands = item.get("validation_commands", [])
            command_text = ""
            if isinstance(commands, list) and commands:
                command_text = str(commands[0]).strip()
            if impact_area and actionable_count > 0:
                detail = f"impact {impact_area}: {actionable_count} actionable package(s)"
                if command_text:
                    detail += f" - validate with {command_text}"
                hints.append(detail)

    release_freshness_summary = upgrade_meta.get("release_freshness_summary", [])
    if isinstance(release_freshness_summary, list):
        for item in release_freshness_summary[:2]:
            if not isinstance(item, dict):
                continue
            freshness = str(item.get("release_freshness", "")).strip()
            count = int(item.get("count", 0))
            actionable_count = _int_value(item.get("actionable_packages", 0))
            packages = item.get("packages", [])
            package_text = ""
            if isinstance(packages, list) and packages:
                package_text = ", ".join(
                    str(name).strip() for name in packages[:3] if str(name).strip()
                )
            if freshness and count > 0:
                detail = f"release freshness {freshness}: {count} package(s)"
                if actionable_count > 0:
                    detail += f", actionable {actionable_count}"
                if package_text:
                    detail += f" - includes {package_text}"
                hints.append(detail)

    action_summary = upgrade_meta.get("action_summary", [])
    if isinstance(action_summary, list):
        for item in action_summary[:2]:
            if not isinstance(item, dict):
                continue
            action = str(item.get("manifest_action", "")).strip()
            count = int(item.get("count", 0))
            packages = item.get("packages", [])
            package_text = ""
            if isinstance(packages, list) and packages:
                package_text = ", ".join(
                    str(name).strip() for name in packages[:3] if str(name).strip()
                )
            if action and count > 0:
                detail = f"action {action}: {count} package(s)"
                if package_text:
                    detail += f" - includes {package_text}"
                hints.append(detail)

    hotspots = upgrade_meta.get("hotspots", [])
    if isinstance(hotspots, list):
        for item in hotspots[:2]:
            if not isinstance(item, dict):
                continue
            path = str(item.get("path", "")).strip()
            actionable_count = _int_value(item.get("actionable_packages", 0))
            packages = item.get("packages", [])
            package_text = ""
            if isinstance(packages, list) and packages:
                package_text = ", ".join(
                    str(name).strip() for name in packages[:3] if str(name).strip()
                )
            commands = item.get("validation_commands", [])
            command_text = ""
            if isinstance(commands, list) and commands:
                command_text = str(commands[0]).strip()
            if path:
                detail = f"hotspot {path}: {actionable_count} actionable package(s)"
                if package_text:
                    detail += f" - packages {package_text}"
                if command_text:
                    detail += f" - validate with {command_text}"
                hints.append(detail)

    risk_summary = upgrade_meta.get("risk_summary", [])
    if isinstance(risk_summary, list):
        for item in risk_summary[:2]:
            if not isinstance(item, dict):
                continue
            band = str(item.get("risk_band", "")).strip()
            count = int(item.get("count", 0))
            actionable_count = _int_value(item.get("actionable_packages", 0))
            packages = item.get("packages", [])
            package_text = ""
            if isinstance(packages, list) and packages:
                package_text = ", ".join(
                    str(name).strip() for name in packages[:3] if str(name).strip()
                )
            if band and count > 0:
                detail = f"risk {band}: {count} package(s)"
                if actionable_count > 0:
                    detail += f", actionable {actionable_count}"
                if package_text:
                    detail += f" - includes {package_text}"
                hints.append(detail)

    for key, label in (("group_summary", "group"), ("source_summary", "source")):
        summary_rows = upgrade_meta.get(key, [])
        if not isinstance(summary_rows, list):
            continue
        for item in summary_rows[:2]:
            if not isinstance(item, dict):
                continue
            name = str(item.get(label, "")).strip()
            count = int(item.get("count", 0))
            actionable_count = _int_value(item.get("actionable_packages", 0))
            if name and count > 0 and actionable_count > 0:
                hints.append(f"{label} {name}: {count} package(s), actionable {actionable_count}")

    validation_summary = upgrade_meta.get("validation_summary", [])
    if isinstance(validation_summary, list):
        for item in validation_summary[:2]:
            if not isinstance(item, dict):
                continue
            command = str(item.get("command", "")).strip()
            actionable_count = _int_value(item.get("actionable_packages", 0))
            count = int(item.get("count", 0))
            if command and count > 0:
                detail = f"validation {command}: {count} package(s)"
                if actionable_count > 0:
                    detail += f", actionable {actionable_count}"
                hints.append(detail)

    deduped: list[str] = []
    seen: set[str] = set()
    for hint in hints:
        normalized = hint.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped[: max(limit, 0)]


def _check_upgrade_audit(
    root: Path,
    *,
    offline: bool,
    signals: list[str] | None = None,
    policies: list[str] | None = None,
    packages: list[str] | None = None,
    groups: list[str] | None = None,
    sources: list[str] | None = None,
    metadata_sources: list[str] | None = None,
    lanes: list[str] | None = None,
    queries: list[str] | None = None,
    impact_areas: list[str] | None = None,
    manifest_actions: list[str] | None = None,
    validation_commands: list[str] | None = None,
    repo_usage_tiers: list[str] | None = None,
    release_freshness: list[str] | None = None,
    used_in_repo_only: bool = False,
    outdated_only: bool = False,
    min_release_age_days: int | None = None,
    max_release_age_days: int | None = None,
    top: int | None = None,
) -> tuple[bool, str, list[dict[str, Any]], list[str], dict[str, Any]]:
    pyproject_path = root / "pyproject.toml"
    if not pyproject_path.exists():
        return (
            False,
            "pyproject.toml is missing for upgrade audit",
            [
                {
                    "type": "missing_file",
                    "message": "pyproject.toml is missing",
                    "path": "pyproject.toml",
                }
            ],
            ["Add pyproject.toml before running upgrade audit checks."],
            {},
        )

    requirement_paths = upgrade_audit._discover_requirement_files(root, include_lockfiles=False)
    dependencies = upgrade_audit._load_dependencies(pyproject_path, requirement_paths)
    if not dependencies:
        return (
            True,
            "no dependencies declared for upgrade audit",
            [],
            ["Add dependency manifests when you are ready to track package upgrades."],
            {
                "packages_audited": 0,
                "actionable_packages": 0,
                "priority_queue": [],
                "offline": offline,
            },
        )

    by_package: dict[str, list[upgrade_audit.Dependency]] = {}
    for dep in dependencies:
        by_package.setdefault(dep.name, []).append(dep)

    package_names = sorted(by_package)
    project_python_requires = upgrade_audit._load_project_python_requires(pyproject_path)
    repo_usage = upgrade_audit._collect_repo_usage(root, package_names)
    metadata_by_package = upgrade_audit._collect_package_metadata(
        package_names,
        timeout_s=5.0,
        cache_path=upgrade_audit.DEFAULT_CACHE_PATH,
        cache_ttl_hours=24.0,
        offline=offline,
        max_workers=4,
        project_python_requires=project_python_requires,
        include_prereleases=False,
    )

    reports: list[upgrade_audit.PackageReport] = []
    for package in package_names:
        metadata = metadata_by_package[package]
        reports.append(
            upgrade_audit._build_package_report(
                package,
                by_package[package],
                latest_version=metadata.latest_version,
                release_date=metadata.release_date,
                project_python_requires=project_python_requires,
                compatible_version=metadata.compatible_version,
                compatible_release_date=metadata.compatible_release_date,
                compatibility_status=metadata.compatibility_status,
                metadata_source=metadata.source,
                repo_usage_files=repo_usage.get(package, []),
            )
        )
    reports = upgrade_audit._sort_reports(reports)
    filtered_reports = upgrade_audit._filter_reports(
        reports,
        signals=signals,
        policies=policies,
        packages=packages,
        groups=groups,
        sources=sources,
        metadata_sources=metadata_sources,
        lanes=lanes,
        impact_areas=impact_areas,
        manifest_actions=manifest_actions,
        repo_usage_tiers=repo_usage_tiers,
        release_freshness=release_freshness,
        queries=queries,
        min_release_age_days=min_release_age_days,
        max_release_age_days=max_release_age_days,
        validation_commands=validation_commands,
        used_in_repo_only=used_in_repo_only,
        outdated_only=outdated_only,
        top=top,
    )
    actionable = [
        report for report in filtered_reports if upgrade_audit._is_actionable_upgrade(report)
    ]
    priority_source = actionable if actionable else filtered_reports
    priority_queue = upgrade_audit._priority_queue(priority_source, limit=3)

    has_high_risk = any(report.upgrade_signal in {"critical", "high"} for report in actionable)
    has_drift = any(report.alignment == "drift" for report in filtered_reports)
    ok = not has_high_risk and not has_drift

    summary_bits = [f"{len(actionable)} actionable package(s)"]
    if len(filtered_reports) != len(reports):
        summary_bits.append(f"focused view {len(filtered_reports)}/{len(reports)} package(s)")
    if priority_queue:
        top_item = priority_queue[0]
        top_name = str(top_item.get("name", "")).strip()
        top_signal = str(top_item.get("signal", "")).strip()
        top_action = str(top_item.get("manifest_action", "")).strip()
        if top_name:
            summary_label = "watchlist led by" if top_action == "none" else "top priority"
            summary_bits.append(
                f"{summary_label} {top_name} [{top_signal or 'watch'} / {top_action or 'review'}]"
            )
    summary = "upgrade audit found " + "; ".join(summary_bits)

    evidence: list[dict[str, Any]] = []
    for item in priority_queue:
        name = str(item.get("name", "")).strip()
        signal = str(item.get("signal", "")).strip()
        action = str(item.get("manifest_action", "")).strip()
        impact_area = str(item.get("impact_area", "")).strip()
        next_action = str(item.get("next_action", "")).strip()
        version = str(item.get("suggested_version", "")).strip()
        actionable_item = bool(action and action != "none")
        message = f"{name}: {signal or 'watch'} / {action or 'review'}"
        if version:
            message += f" -> {version}"
        if impact_area:
            message += f" [{impact_area}]"
        if next_action:
            message += f" - {next_action}"
        elif not actionable_item:
            message += " - no immediate manifest change required"
        evidence.append({"type": "upgrade_priority", "message": message, "path": "pyproject.toml"})

    fix = [
        "Run `python -m sdetkit intelligence upgrade-audit --format md --top 5` for the full ranked report."
    ]
    fix.extend(
        str(command)
        for item in priority_queue
        for command in _string_list(item.get("validation_commands", []))
    )
    deduped_fix: list[str] = []
    for fix_item in fix:
        if fix_item not in deduped_fix:
            deduped_fix.append(fix_item)

    meta = {
        "packages_audited": len(reports),
        "packages_in_scope": len(filtered_reports),
        "actionable_packages": len(actionable),
        "priority_queue": priority_queue,
        "lane_summary": upgrade_audit._lane_summary(filtered_reports),
        "risk_summary": upgrade_audit._risk_summary(filtered_reports),
        "impact_summary": upgrade_audit._impact_summary(filtered_reports),
        "repo_usage_summary": upgrade_audit._repo_usage_summary(filtered_reports),
        "hotspots": upgrade_audit._repo_hotspots(filtered_reports),
        "release_freshness_summary": upgrade_audit._release_freshness_summary(filtered_reports),
        "action_summary": upgrade_audit._action_summary(filtered_reports),
        "validation_summary": upgrade_audit._validation_summary(filtered_reports),
        "group_summary": upgrade_audit._group_summary(filtered_reports),
        "source_summary": upgrade_audit._source_summary(filtered_reports),
        "offline": offline,
        "requirements": [path.name for path in requirement_paths],
        "filters": {
            "signals": signals or [],
            "policies": policies or [],
            "packages": packages or [],
            "groups": groups or [],
            "sources": sources or [],
            "metadata_sources": metadata_sources or [],
            "lanes": lanes or [],
            "queries": queries or [],
            "impact_areas": impact_areas or [],
            "manifest_actions": manifest_actions or [],
            "validation_commands": validation_commands or [],
            "repo_usage_tiers": repo_usage_tiers or [],
            "release_freshness": release_freshness or [],
            "min_release_age": min_release_age_days,
            "max_release_age": max_release_age_days,
            "used_in_repo_only": used_in_repo_only,
            "outdated_only": outdated_only,
            "top": top,
        },
    }
    return ok, summary, evidence, deduped_fix[:5], meta


def _print_human_report(data: dict[str, Any]) -> None:
    lines = [f"doctor score: {data['score']}%"]
    quality = data.get("quality", {})
    if isinstance(quality, dict) and quality:
        lines.append(
            "quality: "
            f"{quality.get('passed_checks', 0)} passed / "
            f"{quality.get('failed_checks', 0)} failed / "
            f"{quality.get('skipped_checks', 0)} skipped"
        )
    checks = data.get("checks", {})
    for key in sorted(checks):
        item = checks[key]
        marker = "OK" if item.get("ok") else "FAIL"
        lines.append(f"[{marker}] {key}: {item.get('summary') or ''}")
    lines.append("recommendations:")
    for rec in data.get("recommendations", []):
        lines.append(f"- {rec}")
    hints = data.get("hints", [])
    if hints:
        lines.append("hints:")
        for hint in hints:
            lines.append(f"- {hint}")
    sys.stdout.write("\n".join(lines) + "\n")


def _print_pr_report(data: dict[str, Any]) -> None:
    checks = data.get("checks", {})
    quality = data.get("quality", {})
    lines = [
        "### SDET Doctor Report",
        f"- overall: {'PASS' if data.get('ok') else 'FAIL'}",
        f"- score: {data.get('score')}%",
        (
            "- quality: "
            f"{quality.get('passed_checks', 0)} passed / "
            f"{quality.get('failed_checks', 0)} failed / "
            f"{quality.get('skipped_checks', 0)} skipped"
        ),
        "- checks:",
    ]
    for key in sorted(checks):
        item = checks[key]
        marker = "PASS" if item.get("ok") else "FAIL"
        lines.append(f"  - {marker} `{key}`: {item.get('summary') or ''}")
    lines.append("- next steps:")
    for rec in data.get("recommendations", []):
        lines.append(f"  - {rec}")
    hints = data.get("hints", [])
    if hints:
        lines.append("- hints:")
        for hint in hints:
            lines.append(f"  - {hint}")
    sys.stdout.write("\n".join(lines) + "\n")


def _format_doctor_markdown(data: dict[str, Any]) -> str:
    checks = data.get("checks", {})
    ordered_ids = sorted(checks)
    quality = data.get("quality", {})
    lines = [
        "### SDET Doctor Report",
        f"- overall: {'PASS' if data.get('ok') else 'FAIL'}",
        f"- score: {data.get('score')}%",
        (
            "- quality: "
            f"{quality.get('passed_checks', 0)} passed / "
            f"{quality.get('failed_checks', 0)} failed / "
            f"{quality.get('skipped_checks', 0)} skipped"
        ),
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
    lines.append("#### Quality summary")
    if isinstance(quality, dict) and quality:
        lines.append(
            f"- pass rate: {quality.get('pass_rate', 0)}% across {quality.get('actionable_checks', 0)} actionable check(s)"
        )
        lines.append(
            f"- highest failure severity: {quality.get('highest_failure_severity', 'none')}"
        )
        failed_check_ids = quality.get("failed_check_ids", [])
        if isinstance(failed_check_ids, list) and failed_check_ids:
            lines.append(
                "- failing checks: " + ", ".join(f"`{check_id}`" for check_id in failed_check_ids)
            )
        else:
            lines.append("- failing checks: none")
        lines.append(
            f"- hint coverage: {quality.get('hint_count', 0)} hint(s), {quality.get('fix_count', 0)} fix item(s), {quality.get('evidence_count', 0)} evidence item(s)"
        )
        severity_breakdown = quality.get("failed_severity_breakdown", {})
        if isinstance(severity_breakdown, dict):
            lines.append(
                "- failure mix: "
                f"high {severity_breakdown.get('high', 0)}, "
                f"medium {severity_breakdown.get('medium', 0)}, "
                f"low {severity_breakdown.get('low', 0)}"
            )
        lines.append(
            f"- fix-ready checks: {quality.get('checks_with_fix', 0)}, evidence-rich checks: {quality.get('checks_with_evidence', 0)}"
        )
    else:
        lines.append("- None")
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
    lines.append("")
    lines.append("#### Hints")
    hints = data.get("hints", [])
    if hints:
        for hint in hints:
            lines.append(f"- {hint}")
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def _evidence_next_commands(data: dict[str, Any]) -> list[str]:
    commands: list[str] = []
    seen: set[str] = set()

    def _add(candidate: str) -> None:
        item = candidate.strip()
        if not item:
            return
        lowered = item.lower()
        if not (
            item.startswith("python ")
            or item.startswith("python3 ")
            or item.startswith("sdetkit ")
            or item.startswith("git ")
            or lowered.startswith("run ")
        ):
            return
        if item in seen:
            return
        seen.add(item)
        commands.append(item)

    for rec in data.get("recommendations", []):
        if not isinstance(rec, str):
            continue
        _add(rec)
        for token in rec.split("`"):
            _add(token)

    for action in data.get("next_actions", []):
        if not isinstance(action, dict):
            continue
        for fix in action.get("fix", []):
            if isinstance(fix, str):
                _add(fix)

    return commands[:8]


def _evidence_diagnostics_rows(checks: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for check_id in CHECK_ORDER:
        item = checks.get(check_id)
        if not isinstance(item, dict) or item.get("skipped"):
            continue
        fix = item.get("fix", [])
        evidence = item.get("evidence", [])
        rows.append(
            {
                "id": check_id,
                "status": "pass" if item.get("ok") else "fail",
                "severity": str(item.get("severity", "medium")),
                "summary": str(item.get("summary", "")),
                "fix_count": len(fix) if isinstance(fix, list) else 0,
                "evidence_count": len(evidence) if isinstance(evidence, list) else 0,
            }
        )
    return rows


def _structured_recommendations(data: dict[str, Any]) -> list[dict[str, Any]]:
    recs: list[dict[str, Any]] = []
    for priority, item in enumerate(data.get("next_actions", []), start=1):
        if not isinstance(item, dict):
            continue
        fixes = item.get("fix", [])
        fix_list = [str(fix) for fix in fixes if isinstance(fix, str)]
        commands: list[str] = []
        for candidate in fix_list:
            if candidate.startswith("python ") or candidate.startswith("python3 "):
                commands.append(candidate)
        recs.append(
            {
                "check_id": str(item.get("id", "")),
                "priority": priority,
                "purpose": str(item.get("summary", "")),
                "severity": str(item.get("severity", "medium")),
                "summary": str(item.get("summary", "")),
                "suggested_command": commands[0] if commands else "",
                "commands": commands[:3],
                "actions": fix_list[:5],
                "related_checks": [str(item.get("id", ""))] if item.get("id") else [],
                "related_evidence_refs": [],
            }
        )
    evidence_refs = data.get("evidence_refs_by_check", {})
    if isinstance(evidence_refs, dict):
        for rec in recs:
            check_id = str(rec.get("check_id", ""))
            refs = evidence_refs.get(check_id, [])
            if not isinstance(refs, list):
                continue
            rec["related_evidence_refs"] = sorted(str(ref) for ref in refs if str(ref).strip())[:5]
    return recs


def _select_evidence_rows(
    *,
    profile: str,
    include: str,
    failed_checks: list[dict[str, Any]],
    passing_controls: list[dict[str, Any]],
    diagnostics_rows: list[dict[str, Any]],
    structured_recommendations: list[dict[str, Any]],
    evidence_refs: list[dict[str, str]],
) -> dict[str, Any]:
    failed_ids = {str(row.get("id", "")) for row in failed_checks}
    actionable_ids = {
        str(row.get("check_id", ""))
        for row in structured_recommendations
        if str(row.get("check_id", "")).strip()
    }
    if not actionable_ids:
        actionable_ids = set(failed_ids)
    selected_ids = set(failed_ids)
    include_pass_controls = True
    include_recommendations = True
    if include == "failed":
        include_pass_controls = False
        include_recommendations = False
    elif include == "actionable":
        selected_ids = actionable_ids
    elif include == "all":
        selected_ids = {
            str(row.get("id", "")) for row in diagnostics_rows if str(row.get("id", "")).strip()
        }
    if profile == "ci":
        allowed = {
            "pyproject",
            "ci_workflows",
            "security_files",
            "pre_commit",
            "deps",
            "clean_tree",
        }
        selected_ids = {check_id for check_id in selected_ids if check_id in allowed}
    elif profile == "release":
        allowed = {
            "pyproject",
            "clean_tree",
            "release_meta",
            "repo_readiness",
            "upgrade_audit",
            "ci_workflows",
        }
        selected_ids = {check_id for check_id in selected_ids if check_id in allowed}
    filtered_failed = [row for row in failed_checks if row.get("id") in selected_ids]
    filtered_controls = [row for row in passing_controls if row.get("id") in selected_ids]
    filtered_diag = [row for row in diagnostics_rows if row.get("id") in selected_ids]
    filtered_recs = [
        row for row in structured_recommendations if str(row.get("check_id", "")) in selected_ids
    ]
    filtered_refs = [row for row in evidence_refs if row.get("check_id") in selected_ids]
    if not include_pass_controls:
        filtered_controls = []
    if not include_recommendations:
        filtered_recs = []
    return {
        "failed_checks": filtered_failed,
        "passing_controls": filtered_controls,
        "diagnostics_rows": filtered_diag,
        "structured_recommendations": filtered_recs,
        "evidence_refs": filtered_refs,
        "selected_check_ids": sorted(selected_ids),
    }


def _surface_consistency(data: dict[str, Any], checks: dict[str, Any]) -> dict[str, Any]:
    sync_checks = [
        ("ci_workflows", "ci_workflows"),
        ("security_files", "security_files"),
        ("pre_commit", "pre_commit"),
        ("deps", "deps"),
        ("clean_tree", "clean_tree"),
        ("repo_readiness", "repo_readiness"),
        ("upgrade_audit", "upgrade_audit"),
    ]
    key_alias = {
        "ci_workflows": "ci_missing",
        "security_files": "security_missing",
        "pre_commit": "pre_commit_ok",
        "deps": "deps_ok",
        "clean_tree": "clean_tree_ok",
        "repo_readiness": "repo_readiness_missing",
        "upgrade_audit": "upgrade_audit_ok",
    }
    mismatches: list[dict[str, str]] = []
    for check_id, alias_key in sync_checks:
        item = checks.get(check_id)
        if not isinstance(item, dict) or item.get("skipped"):
            continue
        if alias_key not in data:
            continue
        alias_value = data.get(alias_key)
        check_ok = bool(item.get("ok"))
        if alias_key.endswith("_ok"):
            if bool(alias_value) != check_ok:
                mismatches.append(
                    {
                        "check_id": check_id,
                        "field": alias_key,
                        "message": f"check status ({check_ok}) differs from {alias_key} ({bool(alias_value)})",
                    }
                )
            continue
        if isinstance(alias_value, list):
            alias_ok = len(alias_value) == 0
            if alias_ok != check_ok:
                mismatches.append(
                    {
                        "check_id": check_id,
                        "field": alias_key,
                        "message": f"check status ({check_ok}) differs from {alias_key} emptiness ({alias_ok})",
                    }
                )
            continue
        normalized_key = key_alias.get(check_id, "")
        if normalized_key and normalized_key in data and data[normalized_key] != alias_value:
            mismatches.append(
                {
                    "check_id": check_id,
                    "field": alias_key,
                    "message": f"cross-surface alias mismatch for {check_id}",
                }
            )
    return {
        "ok": len(mismatches) == 0,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
    }


def _write_evidence(
    root: Path, evidence_dir: Path, data: dict[str, Any], *, profile: str, include: str
) -> tuple[bool, str]:
    quality = data.get("quality", {})
    checks = data.get("checks", {})
    selected = data.get("selected_checks", [])
    if (
        not isinstance(quality, dict)
        or not isinstance(checks, dict)
        or not isinstance(selected, list)
        or int(quality.get("actionable_checks", 0)) <= 0
    ):
        return (
            False,
            "doctor evidence requires at least one actionable check; rerun doctor with checks enabled",
        )

    failed_checks: list[dict[str, Any]] = []
    passing_controls: list[dict[str, Any]] = []
    evidence_refs: list[dict[str, str]] = []
    evidence_refs_by_check: dict[str, list[str]] = {}

    for check_id in CHECK_ORDER:
        item = checks.get(check_id)
        if not isinstance(item, dict) or item.get("skipped"):
            continue
        row = {
            "id": check_id,
            "severity": str(item.get("severity", "medium")),
            "summary": str(item.get("summary", "")),
        }
        if item.get("ok"):
            if row["severity"] in {"high", "medium"}:
                passing_controls.append(row)
        else:
            failed_checks.append(row)
        for ev in item.get("evidence", []):
            if not isinstance(ev, dict):
                continue
            path = str(ev.get("path", "")).strip()
            if path:
                evidence_refs_by_check.setdefault(check_id, []).append(path)
                evidence_refs.append(
                    {
                        "check_id": check_id,
                        "path": path,
                        "message": str(ev.get("message", "")).strip(),
                    }
                )

    next_commands = _evidence_next_commands(data)
    if not failed_checks and not passing_controls and not evidence_refs and not next_commands:
        return (
            False,
            "doctor evidence is empty: no failures or actionable next commands were found",
        )

    diagnostics_rows = _evidence_diagnostics_rows(checks)
    data["evidence_refs_by_check"] = evidence_refs_by_check
    structured_recommendations = _structured_recommendations(data)
    surface_consistency = _surface_consistency(data, checks)
    filtered = _select_evidence_rows(
        profile=profile,
        include=include,
        failed_checks=failed_checks,
        passing_controls=passing_controls,
        diagnostics_rows=diagnostics_rows,
        structured_recommendations=structured_recommendations,
        evidence_refs=evidence_refs,
    )

    evidence_payload = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "doctor_schema_version": data.get("schema_version"),
        "profile": profile,
        "include": include,
        "ok": bool(data.get("ok")),
        "score": int(data.get("score", 0)),
        "policy": data.get("policy", {}),
        "quality": quality,
        "summary": {
            "selected_checks": len(selected),
            "actionable_checks": int(quality.get("actionable_checks", 0)),
            "failed_checks": int(quality.get("failed_checks", 0)),
            "passed_checks": int(quality.get("passed_checks", 0)),
            "skipped_checks": int(quality.get("skipped_checks", 0)),
            "highest_failure_severity": str(quality.get("highest_failure_severity", "none")),
        },
        "failed_checks": filtered["failed_checks"],
        "passing_controls": filtered["passing_controls"],
        "next_commands": next_commands,
        "structured_recommendations": filtered["structured_recommendations"],
        "diagnostics_rows": filtered["diagnostics_rows"],
        "surface_consistency": surface_consistency,
        "evidence_refs": sorted(
            filtered["evidence_refs"],
            key=lambda item: (item["check_id"], item["path"], item["message"]),
        ),
        "selected_check_ids": filtered["selected_check_ids"],
        "artifacts": {
            "doctor_output": str(data.get("output_path", "")),
            "evidence_json": "doctor-evidence.json",
            "evidence_markdown": "doctor-evidence.md",
            "evidence_manifest": "doctor-evidence-manifest.json",
        },
    }

    evidence_lines = [
        "# SDETKit doctor evidence",
        "",
        f"- overall: {'PASS' if evidence_payload['ok'] else 'FAIL'}",
        f"- score: {evidence_payload['score']}%",
        (
            "- quality: "
            f"{evidence_payload['summary']['passed_checks']} passed / "
            f"{evidence_payload['summary']['failed_checks']} failed / "
            f"{evidence_payload['summary']['skipped_checks']} skipped"
        ),
        "",
        "## Failed checks",
    ]
    if evidence_payload["failed_checks"]:
        for row in evidence_payload["failed_checks"]:
            evidence_lines.append(f"- `{row['id']}` ({row['severity']}): {row['summary']}")
    else:
        evidence_lines.append("- none")

    evidence_lines.append("")
    evidence_lines.append("## Stable passing controls")
    if evidence_payload["passing_controls"]:
        for row in evidence_payload["passing_controls"]:
            evidence_lines.append(f"- `{row['id']}` ({row['severity']}): {row['summary']}")
    else:
        evidence_lines.append("- none")

    evidence_lines.append("")
    evidence_lines.append("## Recommended next commands")
    if next_commands:
        for cmd in next_commands:
            evidence_lines.append(f"- `{cmd}`")
    else:
        evidence_lines.append("- none")

    evidence_lines.append("")
    evidence_lines.append("## Diagnostics rows")
    evidence_lines.append("| Check | Status | Severity | Evidence | Actions |")
    evidence_lines.append("| --- | --- | --- | ---: | ---: |")
    for row in evidence_payload["diagnostics_rows"]:
        evidence_lines.append(
            f"| `{row['id']}` | {row['status']} | {row['severity']} | {row['evidence_count']} | {row['fix_count']} |"
        )

    evidence_lines.append("")
    evidence_lines.append("## Evidence references")
    if evidence_payload["evidence_refs"]:
        for ref in evidence_payload["evidence_refs"][:20]:
            detail = f"- `{ref['check_id']}`: `{ref['path']}`"
            if ref["message"]:
                detail += f" — {ref['message']}"
            evidence_lines.append(detail)
    else:
        evidence_lines.append("- none")

    evidence_lines.append("")
    evidence_lines.append("## Surface consistency")
    if surface_consistency["ok"]:
        evidence_lines.append("- doctor evidence surfaces are consistent")
    else:
        evidence_lines.append(
            f"- detected {surface_consistency['mismatch_count']} cross-surface mismatch(es)"
        )
        for mismatch in surface_consistency["mismatches"][:10]:
            evidence_lines.append(
                f"- `{mismatch['check_id']}` / `{mismatch['field']}`: {mismatch['message']}"
            )
    evidence_lines.append("")
    evidence_lines.append("## Evidence profile")
    evidence_lines.append(f"- profile: `{profile}`")
    evidence_lines.append(f"- include: `{include}`")
    evidence_lines.append(
        f"- selected checks: {', '.join(f'`{check_id}`' for check_id in evidence_payload['selected_check_ids']) or 'none'}"
    )
    evidence_lines.append("")

    evidence_dir.mkdir(parents=True, exist_ok=True)
    manifest_payload = {
        "schema_version": EVIDENCE_MANIFEST_SCHEMA_VERSION,
        "doctor_schema_version": data.get("schema_version"),
        "profile": profile,
        "include": include,
        "ok": bool(evidence_payload["ok"]),
        "score": int(evidence_payload["score"]),
        "summary": {
            "selected_checks": len(evidence_payload["selected_check_ids"]),
            "failed_checks": len(evidence_payload["failed_checks"]),
            "passing_controls": len(evidence_payload["passing_controls"]),
            "recommendations": len(evidence_payload["structured_recommendations"]),
            "evidence_refs": len(evidence_payload["evidence_refs"]),
        },
        "artifacts": {
            "doctor_output": str(data.get("output_path", "")),
            "evidence_json": "doctor-evidence.json",
            "evidence_markdown": "doctor-evidence.md",
            "evidence_manifest": "doctor-evidence-manifest.json",
        },
        "ordering": {
            "check_order_source": "sdetkit.doctor.CHECK_ORDER",
            "evidence_refs_sorted_by": ["check_id", "path", "message"],
            "structured_recommendations_sorted_by": ["priority", "check_id"],
        },
        "surface_consistency": {
            "ok": bool(surface_consistency.get("ok", False)),
            "mismatch_count": int(surface_consistency.get("mismatch_count", 0)),
            "mismatches": list(surface_consistency.get("mismatches", []))[:5],
        },
    }
    (evidence_dir / "doctor-evidence.json").write_text(
        json.dumps(evidence_payload, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    (evidence_dir / "doctor-evidence.md").write_text("\n".join(evidence_lines), encoding="utf-8")
    (evidence_dir / "doctor-evidence-manifest.json").write_text(
        json.dumps(manifest_payload, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return True, ""


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
        "--bundle",
        "--evidence-dir",
        "--apply-plan",
        "--snapshot",
        "--diff-snapshot",
        "--upgrade-audit-signal",
        "--upgrade-audit-policy",
        "--upgrade-audit-package",
        "--upgrade-audit-group",
        "--upgrade-audit-source",
        "--upgrade-audit-metadata-source",
        "--upgrade-audit-lane",
        "--upgrade-audit-query",
        "--upgrade-audit-impact-area",
        "--upgrade-audit-manifest-action",
        "--upgrade-audit-validation-command",
        "--upgrade-audit-repo-usage-tier",
        "--upgrade-audit-release-freshness",
        "--upgrade-audit-top",
        "--upgrade-audit-min-release-age-days",
        "--upgrade-audit-max-release-age-days",
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
    parser.add_argument(
        "--explain",
        action="store_true",
        help="Emit prioritized remediation guidance with confidence scoring.",
    )
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--ascii", action="store_true")
    parser.add_argument("--ci", action="store_true")
    parser.add_argument("--pre-commit", dest="pre_commit", action="store_true")
    parser.add_argument("--deps", action="store_true")
    parser.add_argument("--clean-tree", dest="clean_tree", action="store_true")
    parser.add_argument("--repo", "--repo-readiness", dest="repo_readiness", action="store_true")
    parser.add_argument(
        "--upgrade-audit",
        dest="upgrade_audit",
        action="store_true",
        help="Run dependency upgrade audit hints and impact analysis.",
    )
    parser.add_argument(
        "--upgrade-audit-offline",
        dest="upgrade_audit_offline",
        action="store_true",
        help="Use cached metadata only for upgrade-audit hints.",
    )
    parser.add_argument(
        "--upgrade-audit-signal",
        dest="upgrade_audit_signals",
        action="append",
        choices=["critical", "high", "medium", "watch", "investigate", "unknown"],
        default=None,
        help="Focus doctor upgrade-audit hints on specific upgrade signal severities.",
    )
    parser.add_argument(
        "--upgrade-audit-policy",
        dest="upgrade_audit_policies",
        action="append",
        choices=["allowed", "blocked", "no-spec"],
        default=None,
        help="Focus doctor upgrade-audit hints on version-policy status.",
    )
    parser.add_argument(
        "--upgrade-audit-package",
        dest="upgrade_audit_packages",
        action="append",
        default=None,
        help="Focus doctor upgrade-audit hints on one or more package names or glob patterns.",
    )
    parser.add_argument(
        "--upgrade-audit-group",
        dest="upgrade_audit_groups",
        action="append",
        default=None,
        help="Focus doctor upgrade-audit hints on dependency groups such as default, dev, test, or docs.",
    )
    parser.add_argument(
        "--upgrade-audit-source",
        dest="upgrade_audit_sources",
        action="append",
        default=None,
        help="Focus doctor upgrade-audit hints on manifest sources such as pyproject.toml or requirements.txt.",
    )
    parser.add_argument(
        "--upgrade-audit-metadata-source",
        dest="upgrade_audit_metadata_sources",
        action="append",
        choices=["pypi", "cache", "cache-stale", "offline-no-cache", "error"],
        default=None,
        help="Focus doctor upgrade-audit hints on where package metadata came from.",
    )
    parser.add_argument(
        "--upgrade-audit-lane",
        dest="upgrade_audit_lanes",
        action="append",
        choices=[
            "stabilize-manifests",
            "refresh-baselines",
            "upgrade-now",
            "next-maintenance-batch",
            "investigate-metadata",
            "policy-covered-watchlist",
            "backlog-watchlist",
        ],
        default=None,
        help="Focus doctor upgrade-audit hints on specific execution lanes.",
    )
    parser.add_argument(
        "--upgrade-audit-query",
        dest="upgrade_audit_queries",
        action="append",
        default=None,
        help="Focus doctor upgrade-audit hints using free-text search across packages, lanes, notes, and commands.",
    )
    parser.add_argument(
        "--upgrade-audit-impact-area",
        dest="upgrade_audit_impact_areas",
        action="append",
        choices=[
            "runtime-core",
            "quality-tooling",
            "integration-adapters",
            "docs-tooling",
            "packaging-release",
            "security-compliance",
            "repo-tooling",
        ],
        default=None,
        help="Focus doctor upgrade-audit hints on specific repo impact areas.",
    )
    parser.add_argument(
        "--upgrade-audit-manifest-action",
        dest="upgrade_audit_manifest_actions",
        action="append",
        choices=[
            "none",
            "refresh-pin",
            "raise-floor",
            "stage-upgrade",
            "plan-major-upgrade",
            "establish-baseline",
            "investigate-metadata",
        ],
        default=None,
        help="Focus doctor upgrade-audit hints on specific manifest actions.",
    )
    parser.add_argument(
        "--upgrade-audit-validation-command",
        dest="upgrade_audit_validation_commands",
        action="append",
        default=None,
        help=(
            "Focus doctor upgrade-audit hints on packages whose suggested validation commands "
            "match a command or glob pattern."
        ),
    )
    parser.add_argument(
        "--upgrade-audit-top",
        dest="upgrade_audit_top",
        type=int,
        default=None,
        help="Limit doctor upgrade-audit hint generation to the highest-risk N matching packages.",
    )
    parser.add_argument(
        "--upgrade-audit-repo-usage-tier",
        dest="upgrade_audit_repo_usage_tiers",
        action="append",
        choices=["hot-path", "active", "edge", "declared-only"],
        default=None,
        help="Focus doctor upgrade-audit hints on packages by repo-usage tier.",
    )
    parser.add_argument(
        "--upgrade-audit-release-freshness",
        dest="upgrade_audit_release_freshness",
        action="append",
        choices=list(upgrade_audit.RELEASE_FRESHNESS_BUCKETS),
        default=None,
        help="Focus doctor upgrade-audit hints on selected target-release freshness buckets.",
    )
    parser.add_argument(
        "--upgrade-audit-min-release-age-days",
        dest="upgrade_audit_min_release_age_days",
        type=int,
        default=None,
        help="Focus doctor upgrade-audit hints on packages whose target release is at least N days old.",
    )
    parser.add_argument(
        "--upgrade-audit-max-release-age-days",
        dest="upgrade_audit_max_release_age_days",
        type=int,
        default=None,
        help="Focus doctor upgrade-audit hints on packages whose target release is at most N days old.",
    )
    parser.add_argument(
        "--upgrade-audit-used-in-repo-only",
        dest="upgrade_audit_used_in_repo_only",
        action="store_true",
        help="Limit doctor upgrade-audit hints to dependencies that appear in repo code or tests.",
    )
    parser.add_argument(
        "--upgrade-audit-outdated-only",
        dest="upgrade_audit_outdated_only",
        action="store_true",
        help="Limit doctor upgrade-audit hints to actionable upgrades only.",
    )
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
    parser.add_argument(
        "--bundle",
        "--evidence-dir",
        dest="evidence_dir",
        default=None,
        help="Write doctor evidence files (doctor-evidence.json + doctor-evidence.md) to a target directory.",
    )
    parser.add_argument(
        "--evidence-profile",
        choices=list(EVIDENCE_PROFILES),
        default="full",
        help="Choose evidence density profile for doctor evidence output (default: full).",
    )
    parser.add_argument(
        "--evidence-include",
        choices=list(EVIDENCE_INCLUDES),
        default="all",
        help="Filter evidence output to failed, actionable, or all checks (default: all).",
    )
    parser.add_argument(
        "--workspace-root",
        default=".sdetkit/workspace",
        help="Shared evidence workspace root for inspect/doctor run records.",
    )
    parser.add_argument(
        "--no-workspace",
        action="store_true",
        help="Disable shared workspace run recording.",
    )

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
        ns.upgrade_audit = False
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
        if "upgrade_audit" in only_set:
            ns.upgrade_audit = True

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
                "schema_version": SCHEMA_VERSION,
                "ok": False,
                "error": {
                    "code": "plan_id_mismatch",
                    "message": "apply plan id does not match generated plan",
                },
                "expected": plan.get("plan_id"),
                "provided": ns.apply_plan,
                "plan": plan,
            }
            rendered = json.dumps(payload) + "\n"
            if ns.out:
                Path(ns.out).write_text(rendered, encoding="utf-8")
            else:
                sys.stdout.write(rendered)
            return EXIT_FAILED
        plan_steps, plan_ok = _apply_plan(plan, root)

    if ns.all:
        ns.ascii = True
        ns.ci = True
        ns.deps = True
        ns.clean_tree = True
        ns.upgrade_audit = True

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
        ns.upgrade_audit = True

    if ns.dev and (ns.ci or ns.deps or ns.clean_tree):
        ns.pyproject = True

    treat_steps: list[dict[str, Any]] = []
    data_treat_ok = True

    if ns.treat or getattr(ns, "treat_only", False):
        treat_steps = _treatments(root)
        data_treat_ok = all(coerce_bool(s.get("ok"), default=False) for s in treat_steps)
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
        "schema_version": SCHEMA_VERSION,
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

    if ns.upgrade_audit and _is_selected("upgrade_audit"):
        ua_ok, ua_summary, ua_evidence, ua_fix, ua_meta = _check_upgrade_audit(
            root,
            offline=bool(ns.upgrade_audit_offline),
            signals=ns.upgrade_audit_signals,
            policies=ns.upgrade_audit_policies,
            packages=ns.upgrade_audit_packages,
            groups=ns.upgrade_audit_groups,
            sources=ns.upgrade_audit_sources,
            metadata_sources=ns.upgrade_audit_metadata_sources,
            lanes=ns.upgrade_audit_lanes,
            queries=ns.upgrade_audit_queries,
            impact_areas=ns.upgrade_audit_impact_areas,
            manifest_actions=ns.upgrade_audit_manifest_actions,
            validation_commands=ns.upgrade_audit_validation_commands,
            repo_usage_tiers=ns.upgrade_audit_repo_usage_tiers,
            release_freshness=ns.upgrade_audit_release_freshness,
            min_release_age_days=ns.upgrade_audit_min_release_age_days,
            max_release_age_days=ns.upgrade_audit_max_release_age_days,
            used_in_repo_only=bool(ns.upgrade_audit_used_in_repo_only),
            outdated_only=bool(ns.upgrade_audit_outdated_only),
            top=ns.upgrade_audit_top,
        )
        data["upgrade_audit_ok"] = ua_ok
        data["checks"]["upgrade_audit"] = _make_check(
            ok=ua_ok,
            severity="medium" if ua_ok else "high",
            summary=ua_summary,
            evidence=ua_evidence,
            fix=ua_fix,
            skipped=False,
            meta=ua_meta,
        )
        score_items.append(ua_ok)

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
    data["hints"] = _build_hints(data)
    data["quality"] = _build_quality_summary(
        data["checks"],
        selected_checks=data["selected_checks"],
        hints=data["hints"],
    )

    scope_name = root.name or "repo"
    previous_payload = None
    previous_summary = None
    stability = 0.7
    if not ns.no_workspace:
        previous_payload, _ = load_latest_previous_payload(
            workspace_root=Path(ns.workspace_root),
            workflow="doctor",
            scope=scope_name,
        )
    if isinstance(previous_payload, dict):
        prev_score = int(previous_payload.get("score", 0))
        cur_score = int(data.get("score", 0))
        if cur_score < prev_score:
            stability = 0.35
            previous_summary = "regressing"
        elif cur_score > prev_score:
            stability = 0.85
            previous_summary = "improving"
        else:
            pass

    finding_items = [
        {
            "id": f"doctor:{row.get('id', 'unknown')}",
            "kind": str(row.get("id", "check")),
            "severity": str(row.get("severity", "medium")),
            "priority": 70 if str(row.get("severity", "medium")) == "high" else 45,
            "why_it_matters": str(row.get("summary", "")),
            "next_action": str((row.get("fix") or ["Review doctor findings"])[0]),
            "message": str(row.get("summary", "")),
        }
        for row in data.get("next_actions", [])[:10]
        if isinstance(row, dict)
    ]
    contradictory = []
    surface = _surface_consistency(data, data.get("checks", {}))
    if isinstance(surface, dict) and not bool(surface.get("ok", True)):
        contradictory.append(
            {
                "id": "doctor:surface-consistency",
                "kind": "cross_surface_disagreement",
                "message": "Doctor cross-surface aliases disagree with check outcomes.",
            }
        )
    supporting = [
        {"kind": "failed_check", "id": item.get("id"), "severity": item.get("severity")}
        for item in data.get("next_actions", [])
        if isinstance(item, dict)
    ]
    doctor_ok = bool(gate_ok)
    blocking = any(str(item.get("severity", "")) == "high" for item in data.get("next_actions", []))
    data["judgment"] = build_judgment(
        workflow="doctor",
        findings=finding_items,
        supporting_evidence=supporting,
        conflicting_evidence=contradictory,
        completeness=1.0 if data.get("selected_checks") else 0.4,
        stability=stability,
        previous_summary=previous_summary,
        workflow_ok=doctor_ok,
        blocking=blocking,
    )

    data["ok"] = doctor_ok
    if failed_checks:
        data["failed_checks"] = failed_checks
    if isinstance(getattr(ns, "apply_plan", None), str) and ns.apply_plan:
        data["post_plan_ok"] = coerce_bool(data.get("ok"), default=False) and coerce_bool(
            data.get("plan_ok"), default=False
        )
    if getattr(ns, "explain", False):
        data["explain"] = _build_explain_payload(data)

    if ns.format == "json" or ns.json:
        output = json.dumps(data, sort_keys=True) + "\n"
        is_json = True
    elif ns.format == "md" or ns.pr:
        output = _format_doctor_markdown(data)
        is_json = False
    else:
        lines = [f"doctor score: {data['score']}%"]
        judgment = data.get("judgment", {})
        if isinstance(judgment, dict):
            lines.append(
                "judgment_summary: "
                f"status={judgment.get('status')} severity={judgment.get('severity')} confidence={judgment.get('confidence', {}).get('score')}"
            )
        checks = data.get("checks", {})
        for key in sorted(checks):
            item = checks[key]
            marker = "OK" if item.get("ok") else "FAIL"
            lines.append(f"[{marker}] {key}: {item.get('summary') or ''}")
        top = judgment.get("top_judgment", {}) if isinstance(judgment, dict) else {}
        if isinstance(top, dict) and top.get("next_move"):
            lines.append(f"judgment_next_move: {top.get('next_move')}")
        contradictions = judgment.get("contradictions", []) if isinstance(judgment, dict) else []
        if isinstance(contradictions, list) and contradictions:
            lines.append(f"judgment_contradictions: {len(contradictions)}")
        lines.append("recommendations:")
        for rec in data.get("recommendations", []):
            lines.append(f"- {rec}")
        hints = data.get("hints", [])
        if hints:
            lines.append("hints:")
            for hint in hints:
                lines.append(f"- {hint}")
        if getattr(ns, "explain", False):
            explain = data.get("explain", {})
            if isinstance(explain, dict):
                lines.append("explain:")
                for step in explain.get("steps", []):
                    if not isinstance(step, dict):
                        continue
                    lines.append(
                        f"- p{step.get('priority')} {step.get('check_id')} confidence={step.get('confidence')}: {step.get('recommended_fix')}"
                    )
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
                a = snap_text
            try:
                bo = json.loads(b)
                b = json.dumps(bo, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
            except json.JSONDecodeError:
                b = stable_text
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

    out_path: Path | None = None
    out_path_display: str | None = None
    if ns.out:
        try:
            out_path = safe_path(root, str(ns.out), allow_absolute=True)
        except SecurityError as exc:
            sys.stderr.write(f"doctor: --out rejected: {exc}\n")
            return EXIT_FAILED
        out_path.write_text(output, encoding="utf-8")
        out_path_display = str(ns.out)
        data["output_path"] = out_path_display
    else:
        data["output_path"] = ""

    evidence_dir: Path | None = None
    if isinstance(ns.evidence_dir, str) and ns.evidence_dir.strip():
        try:
            evidence_dir = safe_path(root, ns.evidence_dir.strip(), allow_absolute=True)
        except SecurityError as exc:
            sys.stderr.write(f"doctor: --evidence-dir rejected: {exc}\n")
            return EXIT_FAILED

    if isinstance(ns.evidence_dir, str) and ns.evidence_dir.strip():
        evidence_ok, evidence_error = _write_evidence(
            root,
            evidence_dir if evidence_dir is not None else Path(ns.evidence_dir.strip()),
            data,
            profile=str(getattr(ns, "evidence_profile", "full")),
            include=str(getattr(ns, "evidence_include", "all")),
        )
        if not evidence_ok:
            if is_json:
                fail_payload = {
                    "schema_version": SCHEMA_VERSION,
                    "ok": False,
                    "error": {
                        "code": "doctor_evidence_empty",
                        "message": evidence_error,
                    },
                }
                sys.stdout.write(_stable_json(fail_payload))
            sys.stderr.write(f"doctor: evidence write failed: {evidence_error}\n")
            return EXIT_FAILED

    if not ns.no_workspace:
        try:
            validated_workspace_root = safe_path(root, str(ns.workspace_root), allow_absolute=True)
        except SecurityError as exc:
            sys.stderr.write(f"doctor: --workspace-root rejected: {exc}\n")
            return EXIT_FAILED
        requested_workspace_root = Path(str(ns.workspace_root))
        workspace_root = (
            validated_workspace_root
            if requested_workspace_root.is_absolute()
            else requested_workspace_root
        )
        workspace_artifacts: dict[str, str] = {}
        if out_path_display is not None:
            workspace_artifacts["doctor_output"] = out_path_display
        if evidence_dir is not None:
            workspace_artifacts["doctor_evidence_json"] = (
                evidence_dir / "doctor-evidence.json"
            ).as_posix()
            workspace_artifacts["doctor_evidence_markdown"] = (
                evidence_dir / "doctor-evidence.md"
            ).as_posix()
            workspace_artifacts["doctor_evidence_manifest"] = (
                evidence_dir / "doctor-evidence-manifest.json"
            ).as_posix()
        workspace_entry = record_workspace_run(
            workspace_root=workspace_root,
            workflow="doctor",
            scope=root.name or "repo",
            payload=data,
            artifacts=workspace_artifacts,
            recommendations=list(data.get("recommendations", [])),
        )
        data["workspace"] = workspace_entry
        if is_json:
            output = _stable_json(data)
            if out_path is not None:
                out_path.write_text(output, encoding="utf-8")

    sys.stdout.write(output)

    if not gate_ok and not is_json:
        sys.stderr.write("doctor: problems found\n")

    return EXIT_OK if gate_ok else EXIT_FAILED


if __name__ == "__main__":
    raise SystemExit(main())
