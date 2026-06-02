"""Apply local mechanical formatting before proof gates.

This developer workflow reduces repeated formatter-only pre-commit loops.
It does not authorize automation, patch safety, merge, or semantic equivalence.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

TEXT_SUFFIXES = {
    ".cfg",
    ".css",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".py",
    ".sh",
    ".toml",
    ".ts",
    ".txt",
    ".yaml",
    ".yml",
}
TEXT_NAMES = {
    ".gitignore",
    ".pre-commit-config.yaml",
    "Makefile",
}
SKIP_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "htmlcov",
    "site",
}


def is_text_candidate(path: Path) -> bool:
    """Return whether a tracked path should receive generic text normalization."""
    if any(part in SKIP_PARTS for part in path.parts):
        return False
    return path.name in TEXT_NAMES or path.suffix.lower() in TEXT_SUFFIXES


def normalize_text(text: str) -> str:
    """Trim trailing horizontal whitespace and ensure a final newline."""
    if text == "":
        return ""

    parts: list[str] = []
    for line in text.splitlines(keepends=True):
        if line.endswith("\r\n"):
            body = line[:-2]
            newline = "\r\n"
        elif line.endswith("\n"):
            body = line[:-1]
            newline = "\n"
        elif line.endswith("\r"):
            body = line[:-1]
            newline = "\r"
        else:
            body = line
            newline = ""
        parts.append(body.rstrip(" \t") + newline)

    normalized = "".join(parts)
    if normalized and not normalized.endswith(("\n", "\r")):
        normalized += "\n"
    return normalized


def normalize_file(path: Path) -> bool:
    """Normalize one text file. Return True when the file changed."""
    raw = path.read_bytes()
    if b"\0" in raw:
        return False

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return False

    normalized = normalize_text(text)
    if normalized == text:
        return False

    path.write_text(normalized, encoding="utf-8")
    return True


def iter_tracked_files(root: Path) -> list[Path]:
    """Return git-tracked files under root."""
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    files: list[Path] = []
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        rel = raw.decode("utf-8", errors="ignore")
        path = root / rel
        if path.is_file():
            files.append(path)
    return files


def normalize_tracked_text_files(root: Path) -> list[str]:
    """Normalize tracked text files and return changed relative paths."""
    changed: list[str] = []
    for path in iter_tracked_files(root):
        rel = path.relative_to(root)
        if is_text_candidate(rel) and normalize_file(path):
            changed.append(rel.as_posix())
    return changed


def run_command(root: Path, command: list[str]) -> None:
    subprocess.run(command, cwd=root, check=True)


def run_format_before_proof(root: Path, *, skip_ruff: bool = False) -> dict[str, Any]:
    changed = normalize_tracked_text_files(root)

    ruff_check_fix = "skipped"
    ruff_format = "skipped"
    if not skip_ruff:
        run_command(root, ["python", "-m", "ruff", "check", "--fix", "."])
        ruff_check_fix = "passed"
        run_command(root, ["python", "-m", "ruff", "format", "."])
        ruff_format = "passed"

    return {
        "changed_files": changed,
        "changed_file_count": len(changed),
        "ruff_check_fix": ruff_check_fix,
        "ruff_format": ruff_format,
        "automation_allowed": False,
        "patch_application_authorized": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.format_before_proof")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--skip-ruff", action="store_true")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_format_before_proof(args.root.resolve(), skip_ruff=args.skip_ruff)

    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"format_before_proof_changed_files={result['changed_file_count']}")
        print(f"ruff_check_fix={result['ruff_check_fix']}")
        print(f"ruff_format={result['ruff_format']}")
        print("automation_allowed=false")
        print("merge_authorized=false")
        print("semantic_equivalence_proven=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
