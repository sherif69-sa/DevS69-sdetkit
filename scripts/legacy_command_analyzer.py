from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from sdetkit.cli import LEGACY_COMMAND_MODULES


def _preferred_surface(command: str) -> str:
    if command.startswith("weekly-review"):
        return "python -m sdetkit weekly-review"
    if command.startswith(("phase1-", "phase2-", "phase3-")):
        return "python -m sdetkit playbooks --help"
    if command.endswith("-closeout"):
        return "python -m sdetkit playbooks --help"
    return "python -m sdetkit kits list"


def _candidate_files(root: Path) -> list[Path]:
    globs = ("*.md", "*.yml", "*.yaml", "*.sh", "*.txt", "*.py")
    seen: set[Path] = set()
    files: list[Path] = []
    for pattern in globs:
        for path in root.rglob(pattern):
            if any(part in {".git", ".venv", "site"} for part in path.parts):
                continue
            if path in seen or not path.is_file():
                continue
            seen.add(path)
            files.append(path)
    return files


def _analyze(root: Path) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    legacy_commands = sorted(LEGACY_COMMAND_MODULES.keys(), key=len, reverse=True)
    for path in _candidate_files(root):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for cmd in legacy_commands:
            patterns = (
                re.compile(rf"\bpython\s+-m\s+sdetkit\s+{re.escape(cmd)}\b"),
                re.compile(rf"\bsdetkit\s+{re.escape(cmd)}\b"),
            )
            if any(p.search(text) for p in patterns):
                findings.append(
                    {
                        "path": str(path.relative_to(root)),
                        "command": cmd,
                        "preferred_surface": _preferred_surface(cmd),
                    }
                )
    findings.sort(key=lambda item: (item["path"], item["command"]))
    return {
        "schema_version": "1",
        "overall_ok": len(findings) == 0,
        "count": len(findings),
        "findings": findings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python scripts/legacy_command_analyzer.py")
    parser.add_argument("--root", default=".")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    ns = parser.parse_args(argv)
    root = Path(ns.root).resolve()
    report = _analyze(root)
    if ns.format == "json":
        print(json.dumps(report, sort_keys=True))
    else:
        print(f"legacy-command-analyzer: {'OK' if report['overall_ok'] else 'FOUND'}")
        for item in report["findings"]:
            print(f"- {item['path']}: {item['command']} -> {item['preferred_surface']}")
    return 0 if report["overall_ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
