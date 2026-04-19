from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from ._toml import loads as toml_loads
from .test_bootstrap import REQUIRED_TEST_MODULES

MODULE_TO_PACKAGE = {
    "httpx": "httpx",
    "hypothesis": "hypothesis",
    "yaml": "PyYAML",
}

_SPEC_SEP = re.compile(r"[<>=!~\[\]]")


def normalize_package_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).strip().lower()


def extract_requirement_name(line: str) -> str:
    raw = line.strip()
    if not raw or raw.startswith("#"):
        return ""
    token = _SPEC_SEP.split(raw, maxsplit=1)[0].strip()
    return normalize_package_name(token)


def load_requirements_packages(path: Path) -> set[str]:
    packages: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        name = extract_requirement_name(line)
        if name:
            packages.add(name)
    return packages


def load_pyproject_test_packages(path: Path) -> set[str]:
    content = path.read_text(encoding="utf-8")
    data = toml_loads(content)
    core_deps = data.get("project", {}).get("dependencies", [])
    test_deps = data.get("project", {}).get("optional-dependencies", {}).get("test", [])
    all_test_visible = [*core_deps, *test_deps]
    names = {extract_requirement_name(str(item)) for item in all_test_visible}
    return {name for name in names if name}


def build_report(repo_root: Path) -> dict[str, object]:
    expected_packages = sorted(
        {normalize_package_name(MODULE_TO_PACKAGE[module]) for module in REQUIRED_TEST_MODULES}
    )
    requirements_packages = load_requirements_packages(repo_root / "requirements-test.txt")
    pyproject_test_packages = load_pyproject_test_packages(repo_root / "pyproject.toml")

    missing_from_requirements = sorted(set(expected_packages) - requirements_packages)
    missing_from_pyproject_test = sorted(set(expected_packages) - pyproject_test_packages)

    ok = not missing_from_requirements and not missing_from_pyproject_test
    return {
        "ok": ok,
        "expected_packages": expected_packages,
        "missing_from_requirements_test": missing_from_requirements,
        "missing_from_pyproject_test_visible_deps": missing_from_pyproject_test,
        "paths": {
            "requirements_test": str(repo_root / "requirements-test.txt"),
            "pyproject": str(repo_root / "pyproject.toml"),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate contract alignment between test bootstrap required modules and "
            "declared test dependency manifests."
        )
    )
    parser.add_argument("--format", choices=("text", "json"), default="text", help="Output format.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when contract mismatches.")
    parser.add_argument(
        "--out",
        default="",
        help="Optional output file path. When set, writes rendered output to this file.",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root containing requirements-test.txt and pyproject.toml (default: current directory).",
    )
    return parser.parse_args()


def render_text(report: dict[str, object]) -> str:
    lines = [f"[bootstrap-contract] ok: {report['ok']}"]
    lines.append(f"[bootstrap-contract] expected packages: {', '.join(report['expected_packages'])}")
    if report["missing_from_requirements_test"]:
        lines.append(
            "[bootstrap-contract] missing from requirements-test.txt: "
            + ", ".join(report["missing_from_requirements_test"])
        )
    if report["missing_from_pyproject_test_visible_deps"]:
        lines.append(
            "[bootstrap-contract] missing from pyproject dependencies/test extra: "
            + ", ".join(report["missing_from_pyproject_test_visible_deps"])
        )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    repo_root = Path(getattr(args, "repo_root", ".")).resolve()
    report = build_report(repo_root)
    rendered = json.dumps(report, indent=2, sort_keys=True) if args.format == "json" else render_text(report)
    print(rendered)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered + "\n", encoding="utf-8")
    return 0 if (report["ok"] or not args.strict) else 2


if __name__ == "__main__":
    raise SystemExit(main())
