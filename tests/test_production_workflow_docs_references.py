from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

LEGACY_COMMANDS = (
    "make platform-readiness-quality-contract",
    "make platform-readiness-quality-report",
    "make platform-readiness-do-it",
    "make phase1-closeout",
    "make phase1-retire-plan",
    "make phase1-finish-signal",
    "make baseline-next-pass",
    "make phase1-do-it",
    "make operational-readiness-governance-contract",
    "make adoption-readiness-ecosystem-contract",
    "make scale-readiness-metrics-contract",
)

SEARCH_ROOTS = (
    ROOT / "docs",
    ROOT / ".github",
    ROOT / "README.md",
)


def iter_text_files() -> list[Path]:
    files: list[Path] = []
    for root in SEARCH_ROOTS:
        if root.is_file():
            files.append(root)
        elif root.is_dir():
            files.extend(
                p
                for p in root.rglob("*")
                if p.is_file() and p.suffix.lower() in {".md", ".txt", ".yml", ".yaml"}
            )
    return sorted(files)


def test_user_facing_docs_prefer_production_workflow_aliases() -> None:
    violations: list[str] = []

    for path in iter_text_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for command in LEGACY_COMMANDS:
            if command in text:
                rel = path.relative_to(ROOT).as_posix()
                violations.append(f"{rel}: replace {command!r} with its production alias")

    assert not violations, "\n".join(violations)
