from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from importlib import metadata
from pathlib import Path
from typing import Any


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


def _is_ignored_binary(p: Path) -> bool:
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
    want = ["git", "pre-commit", "pytest", "ruff", "python3"]
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="doctor")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--ascii", action="store_true")
    parser.add_argument("--ci", action="store_true")
    parser.add_argument("--pre-commit", dest="pre_commit", action="store_true")
    parser.add_argument("--deps", action="store_true")
    parser.add_argument("--clean-tree", dest="clean_tree", action="store_true")
    parser.add_argument("--dev", action="store_true")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--release", action="store_true")

    ns = parser.parse_args(list(argv) if argv is not None else None)
    root = Path.cwd()

    if ns.all or ns.release:
        ns.ascii = True
        ns.ci = True
        ns.pre_commit = True
        ns.deps = True
        ns.clean_tree = True
        ns.dev = True

    data: dict[str, Any] = {"python": _python_info(), "package": _package_info()}
    ok = True

    if ns.dev:
        present, missing = _check_tools()
        data["tools"] = present
        data["missing"] = missing
        if missing:
            ok = False
    else:
        data.setdefault("missing", [])

    if ns.ascii:
        bad, bad_err = _scan_non_ascii(root)
        data["non_ascii"] = bad
        if bad:
            ok = False
        for line in bad_err:
            sys.stderr.write(line + "\n")

    if ns.ci:
        miss, invalid = _check_ci(root)
        data["ci_missing"] = miss
        data["yaml_invalid"] = invalid
        if miss or invalid:
            ok = False

    if ns.pre_commit:
        pc_ok = _check_pre_commit(root)
        data["pre_commit_ok"] = pc_ok
        if not pc_ok:
            ok = False

    if ns.deps:
        deps_ok = _check_deps(root)
        data["deps_ok"] = deps_ok
        if not deps_ok:
            ok = False

    if ns.clean_tree:
        ct_ok = _check_clean_tree(root)
        data["clean_tree_ok"] = ct_ok
        if not ct_ok:
            ok = False

    data["ok"] = bool(ok)

    if ns.json:
        sys.stdout.write(json.dumps(data, sort_keys=True) + "\n")
    else:
        if not ok:
            sys.stderr.write("doctor: problems found\n")

    return 0 if ok else 1
