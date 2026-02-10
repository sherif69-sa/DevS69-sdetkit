from __future__ import annotations

import argparse
import json
import platform
import sys
from importlib import metadata
from pathlib import Path


def _dist_version(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def _py_version() -> str:
    v = sys.version_info
    return f"{v.major}.{v.minor}.{v.micro}"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="sdetkit doctor")
    p.add_argument("--json", action="store_true")
    p.add_argument("--dev", action="store_true")
    p.add_argument("--docs", action="store_true")
    p.add_argument(
        "--ascii", action="store_true", help="fail if non-ascii bytes are found in src/ or tools/"
    )
    ns = p.parse_args(argv)

    info: dict = {
        "python": {"version": _py_version(), "executable": sys.executable},
        "venv": sys.prefix != getattr(sys, "base_prefix", sys.prefix),
        "platform": platform.platform(),
        "package": {"name": "sdetkit", "version": _dist_version("sdetkit")},
        "runtime": {"httpx": _dist_version("httpx")},
        "tools": {},
        "missing": [],
    }

    checks: list[tuple[str, str]] = []
    if ns.dev:
        checks.extend(
            [
                ("pytest", "pytest"),
                ("ruff", "ruff"),
                ("mypy", "mypy"),
                ("mutmut", "mutmut"),
                ("hypothesis", "hypothesis"),
            ]
        )
    if ns.docs:
        checks.extend(
            [
                ("mkdocs", "mkdocs"),
                ("mkdocs-material", "mkdocs-material"),
            ]
        )

    tools: dict[str, str | None] = {}
    missing: list[str] = []
    for key, dist in checks:
        v = _dist_version(dist)
        tools[key] = v
        if v is None:
            missing.append(key)

    info["tools"] = tools
    info["missing"] = missing

    non_ascii: list[str] = []
    if ns.ascii:
        for root in (Path("src"), Path("tools")):
            if not root.exists():
                continue
            for fp in root.rglob("*"):
                if not fp.is_file():
                    continue
                if "__pycache__" in fp.parts:
                    continue
                if fp.suffix in (".pyc", ".pyo"):
                    continue
                try:
                    b = fp.read_bytes()
                except OSError:
                    continue
                if any(x >= 128 for x in b):
                    non_ascii.append(str(fp))

    non_ascii = sorted(non_ascii)
    info["non_ascii"] = non_ascii
    if ns.ascii and non_ascii:
        for x in non_ascii:
            sys.stderr.write("non-ascii: " + x + "\n")

    if ns.json:
        sys.stdout.write(json.dumps(info, sort_keys=True) + "\n")
    else:
        print(f"python: {info['python']['version']} ({info['python']['executable']})")
        print(f"venv: {info['venv']}")
        print(f"platform: {info['platform']}")
        print(f"sdetkit: {info['package']['version']}")
        print(f"httpx: {info['runtime']['httpx']}")
        if checks:
            for k in sorted(tools):
                print(f"{k}: {tools[k]}")
        if missing:
            print("missing:", ", ".join(missing))
    return 1 if (missing or (ns.ascii and non_ascii)) else 0
