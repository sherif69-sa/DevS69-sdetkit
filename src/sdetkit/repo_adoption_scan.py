from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.repo_adoption_scan.v1"
SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    ".mypy_cache",
    ".ruff_cache",
    "__pycache__",
}


def _rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _iter_files(root: Path, *, max_files: int) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if len(files) >= max_files:
            break
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.is_file():
            files.append(path)
    return sorted(files, key=lambda item: item.as_posix())


def _exists(root: Path, *names: str) -> bool:
    return any((root / name).exists() for name in names)


def _detect_stack(root: Path, files: list[Path]) -> dict[str, Any]:
    suffixes = {path.suffix.lower() for path in files}
    names = {path.name for path in files}
    return {
        "python": _exists(root, "pyproject.toml", "setup.py", "requirements.txt")
        or ".py" in suffixes,
        "javascript": _exists(root, "package.json", "pnpm-lock.yaml", "yarn.lock")
        or ".js" in suffixes
        or ".ts" in suffixes,
        "docs": _exists(root, "mkdocs.yml", "docs")
        or any(part == "docs" for path in files for part in path.parts),
        "docker": _exists(root, "Dockerfile", "docker-compose.yml", "compose.yaml"),
        "github_actions": (root / ".github" / "workflows").exists(),
        "gitlab_ci": (root / ".gitlab-ci.yml").exists(),
        "has_tests": any(
            path.parts and ("test" in path.name.lower() or "tests" in path.parts) for path in files
        ),
        "has_readme": "README.md" in names or "README.rst" in names,
        "has_license": "LICENSE" in names or "LICENSE.md" in names,
    }


def _adoption_gaps(root: Path, stack: dict[str, Any]) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    if stack["python"] and not (root / "pyproject.toml").exists():
        gaps.append(
            {
                "code": "PYTHON_PROJECT_METADATA_MISSING",
                "severity": "medium",
                "fix": "Add pyproject.toml or document the Python build/test contract.",
            }
        )
    if stack["python"] and not _exists(
        root, "requirements-test.txt", "requirements-dev.txt", "pyproject.toml"
    ):
        gaps.append(
            {
                "code": "TEST_DEPENDENCY_CONTRACT_MISSING",
                "severity": "medium",
                "fix": "Declare test dependencies so CI and local proof are reproducible.",
            }
        )
    if not stack["has_tests"]:
        gaps.append(
            {
                "code": "TEST_SURFACE_MISSING",
                "severity": "high",
                "fix": "Add a minimal smoke/regression test surface before release gating.",
            }
        )
    if not (stack["github_actions"] or stack["gitlab_ci"]):
        gaps.append(
            {
                "code": "CI_CONTRACT_MISSING",
                "severity": "high",
                "fix": "Add CI that runs the canonical SDETKit gate and adaptive evidence commands.",
            }
        )
    if stack["docs"] and not (root / "mkdocs.yml").exists():
        gaps.append(
            {
                "code": "DOCS_BUILD_CONTRACT_MISSING",
                "severity": "low",
                "fix": "Add mkdocs.yml or document the docs build command.",
            }
        )
    if not stack["has_readme"]:
        gaps.append(
            {
                "code": "README_MISSING",
                "severity": "medium",
                "fix": "Add README quickstart, test command, and release proof instructions.",
            }
        )
    if not stack["has_license"]:
        gaps.append(
            {
                "code": "LICENSE_MISSING",
                "severity": "low",
                "fix": "Add or document the license/compliance policy.",
            }
        )
    return gaps


def _recommended_commands(stack: dict[str, Any], gaps: list[dict[str, Any]]) -> list[str]:
    commands = [
        "python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json",
        "python -m sdetkit gate release --format json --out build/release-preflight.json",
        "python -m sdetkit doctor --format json --out build/doctor.json",
        "python -m sdetkit review . --format operator-json --out-dir build/sdetkit-review",
    ]
    if stack["python"]:
        commands.append("PYTHONPATH=src python -m pytest -q")
        commands.append("PYTHONPATH=src python -m ruff check .")
    if stack["docs"]:
        commands.append("NO_MKDOCS_2_WARNING=1 python -m mkdocs build -q")
    if gaps:
        commands.append(
            "python -m sdetkit adaptive dashboard --format html --out build/sdetkit/adaptive-dashboard.html"
        )
    return commands


def _risk_score(gaps: list[dict[str, Any]]) -> int:
    weights = {"high": 30, "medium": 15, "low": 5}
    return min(100, sum(weights.get(str(gap.get("severity")), 5) for gap in gaps))


def build_repo_adoption_scan(root: Path, *, max_files: int = 4000) -> dict[str, Any]:
    root = root.resolve()
    files = _iter_files(root, max_files=max_files)
    stack = _detect_stack(root, files)
    gaps = _adoption_gaps(root, stack)
    risk_score = _risk_score(gaps)
    if risk_score >= 60:
        recommendation = "ADOPT_WITH_FOUNDATION_FIXES"
    elif risk_score:
        recommendation = "ADOPT_WITH_CONTROLS"
    else:
        recommendation = "READY_FOR_CANONICAL_ADOPTION"
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": risk_score < 60,
        "root": root.as_posix(),
        "file_count_sampled": len(files),
        "stack": stack,
        "risk_score": risk_score,
        "recommendation": recommendation,
        "adoption_gaps": gaps,
        "recommended_commands": _recommended_commands(stack, gaps),
        "first_72h_plan": [
            "Run gate fast/release and doctor to establish baseline evidence.",
            "Fix high-severity adoption gaps before requiring release-room signoff.",
            "Publish build/sdetkit-review and adaptive dashboard artifacts in CI.",
        ],
        "next_owner_action": gaps[0]["fix"]
        if gaps
        else "Adopt the canonical gate/review path in CI now.",
    }


def render_text(payload: dict[str, Any]) -> str:
    lines = [
        f"schema_version={payload['schema_version']}",
        f"ok={str(payload['ok']).lower()}",
        f"recommendation={payload['recommendation']}",
        f"risk_score={payload['risk_score']}",
        f"file_count_sampled={payload['file_count_sampled']}",
    ]
    for key, value in payload["stack"].items():
        lines.append(f"stack_{key}={str(value).lower()}")
    for gap in payload["adoption_gaps"]:
        lines.append(f"gap={gap['severity']}|{gap['code']}|{gap['fix']}")
    lines.append("recommended_commands:")
    lines.extend(f"- {command}" for command in payload["recommended_commands"])
    lines.append(f"next_owner_action={payload['next_owner_action']}")
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.repo_adoption_scan")
    parser.add_argument("path", nargs="?", default=".")
    parser.add_argument("--max-files", type=int, default=4000)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--out", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        payload = build_repo_adoption_scan(Path(args.path), max_files=int(args.max_files))
        rendered = (
            json.dumps(payload, indent=2, sort_keys=True) + "\n"
            if args.format == "json"
            else render_text(payload)
        )
        if args.out:
            out = Path(args.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
    except (OSError, ValueError) as exc:
        print(f"error={exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
