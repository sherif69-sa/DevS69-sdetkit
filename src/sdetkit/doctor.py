from __future__ import annotations

import argparse
import importlib
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from importlib import metadata
from pathlib import Path
from typing import Any, cast

from .import_hazards import find_stdlib_shadowing


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
        mod = importlib.import_module("tomllib")
        loads_name = "loads"
        loads = cast(Callable[[bytes], Any], getattr(mod, loads_name))
        with path.open("rb") as f:
            loads(f.read())
    except Exception as exc:  # pragma: no cover - defensive error path
        return False, f"pyproject.toml parse failed: {exc}"
    return True, "pyproject.toml is valid TOML"


def _is_ignored_binary(p: Path) -> bool:
    if any(part.endswith(".egg-info") for part in p.parts):
        return True
    if p.suffix.lower() == ".pyc":
        return True
    parts = p.parts
    for part in parts:
        if part == "__pycache__":
            return True
    return False


def _scan_non_ascii(root: Path) -> tuple[list[str], list[str]]:
    bad_rel: list[str] = []
    bad_stderr: list[str] = []

    for top in ("src", "tools"):
        base = root / top
        if not base.exists():
            continue
        for fp in base.rglob("*"):
            if not fp.is_file():
                continue
            if _is_ignored_binary(fp):
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


def _check_ci(root: Path) -> tuple[list[str], list[str]]:
    required = [
        ".github/workflows/ci.yml",
        ".github/workflows/quality.yml",
        ".github/workflows/security.yml",
    ]
    missing = [p for p in required if not (root / p).exists()]
    missing.sort()

    invalid: list[str] = []
    rc, out, _err = _run(
        [sys.executable, "-m", "pre_commit", "run", "check-yaml", "--all-files"],
        cwd=root,
    )
    if rc != 0:
        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.endswith(".yml") or line.endswith(".yaml"):
                invalid.append(line.replace("\\", "/"))
        invalid.sort()

    return missing, invalid


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


def _check_tools() -> tuple[list[str], list[str]]:
    want = ["git", "pytest", "ruff", "python3"]
    present: list[str] = []
    missing: list[str] = []
    for t in want:
        if shutil.which(t):
            present.append(t)
        else:
            missing.append(t)
    present.sort()
    missing.sort()
    return present, missing


def _calculate_score(checks: list[bool]) -> int:
    if not checks:
        return 100
    passed = sum(1 for item in checks if item)
    return round((passed / len(checks)) * 100)


def _recommendations(data: dict[str, Any]) -> list[str]:
    recs: list[str] = []

    if data.get("venv_ok") is False:
        recs.append(
            "Create/activate a virtual environment before running dev checks: "
            "python -m venv .venv && source .venv/bin/activate."
        )
    if data.get("missing"):
        tools = ", ".join(str(x) for x in data["missing"])
        recs.append(f"Install missing developer tools: {tools}.")
    if data.get("pyproject_ok") is False:
        recs.append("Fix pyproject.toml syntax and re-run doctor before opening a PR.")
    if data.get("non_ascii"):
        recs.append(
            "Replace non-ASCII artifacts in src/ or tools/ with UTF-8 text, or move binaries outside scanned paths."
        )
    if data.get("ci_missing"):
        missing = ", ".join(str(x) for x in data["ci_missing"])
        recs.append(f"Add missing CI workflows: {missing}.")
    if data.get("yaml_invalid"):
        bad = ", ".join(str(x) for x in data["yaml_invalid"])
        recs.append(f"Fix workflow YAML syntax errors: {bad}.")
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
    lines: list[str] = [f"doctor score: {data['score']}%"]

    checks = data.get("checks", {})
    for key in sorted(checks):
        item = checks[key]
        marker = "OK" if item["ok"] else "FAIL"
        lines.append(f"[{marker}] {key}: {item['summary']}")

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
        marker = "PASS" if item["ok"] else "FAIL"
        lines.append(f"  - {marker} `{key}`: {item['summary']}")
    lines.append("- next steps:")
    for rec in data.get("recommendations", []):
        lines.append(f"  - {rec}")
    sys.stdout.write("\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="doctor")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--ascii", action="store_true")
    parser.add_argument("--ci", action="store_true")
    parser.add_argument("--pre-commit", dest="pre_commit", action="store_true")
    parser.add_argument("--deps", action="store_true")
    parser.add_argument("--clean-tree", dest="clean_tree", action="store_true")
    parser.add_argument("--dev", action="store_true")
    parser.add_argument("--pyproject", action="store_true")
    parser.add_argument("--pr", action="store_true", help="print a PR-ready markdown summary")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--release", action="store_true")

    ns = parser.parse_args(list(argv) if argv is not None else None)
    if getattr(ns, "format", "text") == "json":
        ns.json = True
    root = Path.cwd()

    if ns.all or ns.release:
        ns.ascii = True
        ns.ci = True
        ns.pre_commit = True
        ns.deps = True
        ns.clean_tree = True
        ns.dev = True
        ns.pyproject = True

    if ns.dev and (ns.ci or ns.deps or ns.clean_tree):
        ns.pyproject = True

    data: dict[str, Any] = {"python": _python_info(), "package": _package_info(), "checks": {}}
    ok = True
    score_items: list[bool] = []

    if ns.dev:
        venv_ok = _in_virtualenv()
        data["venv_ok"] = venv_ok
        data["checks"]["venv"] = {
            "ok": venv_ok,
            "summary": "virtual environment is active"
            if venv_ok
            else "virtual environment is not active (recommended for stable tooling/deps)",
        }
        score_items.append(venv_ok)
        # Keep this check informational so CI/local tooling still works when
        # running in a managed interpreter without an activated venv.

        present, missing = _check_tools()
        data["tools"] = present
        data["missing"] = missing
        tools_ok = not bool(missing)
        data["checks"]["dev_tools"] = {
            "ok": tools_ok,
            "summary": "all required developer tools are available"
            if tools_ok
            else "some developer tools are missing",
        }
        score_items.append(tools_ok)
        if not tools_ok:
            ok = False
    else:
        data.setdefault("missing", [])

    if ns.pyproject:
        pyproject_ok, pyproject_summary = _check_pyproject_toml(root)
        data["pyproject_ok"] = pyproject_ok
        data["checks"]["pyproject"] = {"ok": pyproject_ok, "summary": pyproject_summary}
        score_items.append(pyproject_ok)
        if not pyproject_ok:
            ok = False

    if ns.ascii:
        bad, bad_err = _scan_non_ascii(root)
        data["non_ascii"] = bad
        check_ok = not bool(bad)
        data["checks"]["ascii"] = {
            "ok": check_ok,
            "summary": "only ASCII content found under src/ and tools/"
            if check_ok
            else "non-ASCII bytes detected under src/ or tools/",
        }
        score_items.append(check_ok)
        if not check_ok:
            ok = False
        for line in bad_err:
            sys.stderr.write(line + "\n")

    if ns.ci:
        miss, invalid = _check_ci(root)
        data["ci_missing"] = miss
        data["yaml_invalid"] = invalid
        check_ok = not (miss or invalid)
        data["checks"]["ci"] = {
            "ok": check_ok,
            "summary": "required workflow files exist and YAML validates"
            if check_ok
            else "CI workflow files are missing or invalid",
        }
        score_items.append(check_ok)
        if not check_ok:
            ok = False

    if ns.pre_commit:
        pc_ok = _check_pre_commit(root)
        data["pre_commit_ok"] = pc_ok
        data["checks"]["pre_commit"] = {
            "ok": pc_ok,
            "summary": "pre-commit is installed and configuration is valid"
            if pc_ok
            else "pre-commit is missing or configuration is invalid",
        }
        score_items.append(pc_ok)
        if not pc_ok:
            ok = False

    if ns.deps:
        deps_ok = _check_deps(root)
        data["deps_ok"] = deps_ok
        data["checks"]["dependencies"] = {
            "ok": deps_ok,
            "summary": "pip dependency graph is consistent"
            if deps_ok
            else "pip dependency issues detected",
        }
        score_items.append(deps_ok)
        if not deps_ok:
            ok = False

    if ns.clean_tree:
        ct_ok = _check_clean_tree(root)
        data["clean_tree_ok"] = ct_ok
        data["checks"]["clean_tree"] = {
            "ok": ct_ok,
            "summary": "working tree is clean" if ct_ok else "working tree has uncommitted changes",
        }
        score_items.append(ct_ok)
        if not ct_ok:
            ok = False

    data["score"] = _calculate_score(score_items)
    data["recommendations"] = _recommendations(data)
    shadow = find_stdlib_shadowing(Path("."))
    if shadow:
        print("[WARN] stdlib-shadow: " + ", ".join(shadow))
        _recs = locals().get("recommendations")
        if isinstance(_recs, list):
            _recs.append(
                "Remove top-level modules under src/ that shadow the Python standard library."
            )
    data["ok"] = bool(ok)

    if ns.json:
        sys.stdout.write(json.dumps(data, sort_keys=True) + "\n")
    elif ns.pr:
        _print_pr_report(data)
    else:
        _print_human_report(data)

    if not ok and not ns.json:
        sys.stderr.write("doctor: problems found\n")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
