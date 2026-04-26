from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import tomllib


def _project_meta(pyproject: Path) -> tuple[str, str]:
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    project = data.get("project", {})
    name = str(project.get("name", "")).strip()
    version = str(project.get("version", "")).strip()
    if not name or not version:
        raise ValueError("pyproject.toml missing [project].name or [project].version")
    return name, version


def _run(cmd: list[str]) -> str:
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def _plan(name: str, version: str) -> dict[str, object]:
    return {
        "package": name,
        "version": version,
        "verification": {
            "external_install": [
                "python -m venv .venv-release-verify && . .venv-release-verify/bin/activate",
                "python -m pip install -U pip",
                f"python -m pip install {name}=={version}",
                "python -m sdetkit --help",
                f"python -m pip show {name}",
            ],
            "index_checks": [
                f"PyPI project page exists: https://pypi.org/project/{name}/{version}/",
                f"PyPI files tab shows both sdist + wheel for {version}",
                "GitHub Release exists for matching tag and contains dist artifacts",
            ],
            "success_signals": [
                "pip install resolves from PyPI without --index-url overrides",
                "CLI help command exits 0",
                "pip show reports expected version",
                "Release workflow includes successful Publish to PyPI step",
            ],
        },
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Build a deterministic post-publish verification plan for maintainers."
    )
    parser.add_argument("--pyproject", default="pyproject.toml")
    parser.add_argument("--plan", action="store_true", help="Print JSON verification plan.")
    parser.add_argument(
        "--assert-install-string",
        action="store_true",
        help="Fail if `pip install <name>==<version>` syntax generation is invalid.",
    )
    args = parser.parse_args(argv[1:])

    try:
        name, version = _project_meta(Path(args.pyproject))
    except (FileNotFoundError, tomllib.TOMLDecodeError, ValueError) as exc:
        print(f"post-release verification prep failed: {exc}", file=sys.stderr)
        return 1

    if args.assert_install_string:
        cmd = [sys.executable, "-m", "pip", "--version"]
        _ = _run(cmd)
        install_string = f"{name}=={version}"
        if " " in install_string.strip():
            print("post-release verification prep failed: invalid install string", file=sys.stderr)
            return 1
        print(f"post-release verification prep ok: install string `{install_string}`")

    if args.plan:
        print(json.dumps(_plan(name, version), indent=2))

    if not args.plan and not args.assert_install_string:
        print(f"post-release verification prep ok: package={name} version={version}")
    return 0


if __name__ in {"__main__", "main_"}:
    raise SystemExit(main(sys.argv))
