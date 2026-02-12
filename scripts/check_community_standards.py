#!/usr/bin/env python3
"""Validate repository community standards baseline files."""

from pathlib import Path

REQUIRED_FILES = [
    "README.md",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "SECURITY.md",
    ".github/PULL_REQUEST_TEMPLATE.md",
]

REQUIRED_DIRS = [
    ".github/ISSUE_TEMPLATE",
]


def main() -> int:
    root = Path.cwd()
    missing: list[str] = []

    for rel in REQUIRED_FILES:
        if not (root / rel).is_file():
            missing.append(rel)

    for rel in REQUIRED_DIRS:
        if not (root / rel).is_dir():
            missing.append(rel)

    issue_dir = root / ".github" / "ISSUE_TEMPLATE"
    has_issue_templates = issue_dir.is_dir() and any(
        p.suffix in {".yml", ".yaml", ".md"} and p.is_file() for p in issue_dir.iterdir()
    )
    if not has_issue_templates:
        missing.append(".github/ISSUE_TEMPLATE/*.{yml,yaml,md}")

    if missing:
        print("Community standards check failed. Missing required items:")
        for item in missing:
            print(f"- {item}")
        return 1

    print("Community standards check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
