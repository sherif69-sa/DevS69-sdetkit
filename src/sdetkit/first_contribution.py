from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

_CHECKLIST_SECTION_HEADER = "## 0) Day 10 first-contribution checklist"

_CHECKLIST_ITEMS = [
    "Fork the repository and clone your fork locally.",
    "Create and activate a virtual environment.",
    "Install editable dependencies for dev/test/docs.",
    "Create a branch named `feat/<topic>` or `fix/<topic>`.",
    "Run focused tests for changed modules before committing.",
    "Run full quality gates (`pre-commit`, `quality.sh`, docs build) before opening a PR.",
    "Open a PR using the repository template and include test evidence.",
]

_COMMAND_BLOCKS = [
    "python3 -m venv .venv",
    "source .venv/bin/activate",
    "python -m pip install -e .[dev,test,docs]",
    "pre-commit run -a",
    "bash quality.sh cov",
    "mkdocs build",
]

_DAY10_DEFAULT_BLOCK = """## 0) Day 10 first-contribution checklist

Use this guided path from local clone to first merged PR:

- [ ] Fork the repository and clone your fork locally.
- [ ] Create and activate a virtual environment.
- [ ] Install editable dependencies for dev/test/docs.
- [ ] Create a branch named `feat/<topic>` or `fix/<topic>`.
- [ ] Run focused tests for changed modules before committing.
- [ ] Run full quality gates (`pre-commit`, `quality.sh`, docs build) before opening a PR.
- [ ] Open a PR using the repository template and include test evidence.

Recommended shell sequence:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .[dev,test,docs]
pre-commit run -a
bash quality.sh cov
mkdocs build
```

"""


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sdetkit first-contribution",
        description="Render and validate the Day 10 first-contribution checklist.",
    )
    p.add_argument("--format", choices=["text", "markdown", "json"], default="text")
    p.add_argument("--root", default=".", help="Repository root where CONTRIBUTING.md lives.")
    p.add_argument("--output", default="", help="Optional output file path.")
    p.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero if required checklist content is missing.",
    )
    p.add_argument(
        "--write-defaults",
        action="store_true",
        help="Write Day 10 checklist block into CONTRIBUTING.md if missing, then validate again.",
    )
    return p


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _missing_checks(guide_text: str) -> list[str]:
    checks = [_CHECKLIST_SECTION_HEADER, *_CHECKLIST_ITEMS, *_COMMAND_BLOCKS]
    return [item for item in checks if item not in guide_text]


def _write_defaults(base: Path) -> list[str]:
    guide = base / "CONTRIBUTING.md"
    current = _read(guide)
    if _CHECKLIST_SECTION_HEADER in current:
        return []

    if current:
        updated = current.rstrip() + "\n\n" + _DAY10_DEFAULT_BLOCK
    else:
        updated = "# Contributing\n\n" + _DAY10_DEFAULT_BLOCK

    guide.write_text(updated, encoding="utf-8")
    return ["CONTRIBUTING.md"]


def build_first_contribution_status(root: str = ".") -> dict[str, Any]:
    base = Path(root)
    guide = base / "CONTRIBUTING.md"
    guide_text = _read(guide)
    missing = _missing_checks(guide_text)

    total_checks = len([_CHECKLIST_SECTION_HEADER, *_CHECKLIST_ITEMS, *_COMMAND_BLOCKS])
    passed_checks = total_checks - len(missing)
    score = round((passed_checks / total_checks) * 100, 1) if total_checks else 0.0

    return {
        "name": "day10-first-contribution-checklist",
        "score": score,
        "total_checks": total_checks,
        "passed_checks": passed_checks,
        "checklist": list(_CHECKLIST_ITEMS),
        "required_commands": list(_COMMAND_BLOCKS),
        "guide": str(guide),
        "missing": missing,
        "actions": {
            "open_guide": "docs/contributing.md",
            "validate": "sdetkit first-contribution --format json --strict",
            "write_defaults": "sdetkit first-contribution --write-defaults --strict",
            "artifact": "sdetkit first-contribution --format markdown --output docs/artifacts/day10-first-contribution-checklist-sample.md",
        },
    }


def _render_text(payload: dict[str, Any]) -> str:
    lines = [
        "Day 10 first-contribution checklist",
        f"score: {payload['score']} ({payload['passed_checks']}/{payload['total_checks']})",
        "",
        "checklist:",
    ]
    for idx, item in enumerate(payload["checklist"], start=1):
        lines.append(f"{idx}. {item}")
    lines.extend(["", "required commands:"])
    for cmd in payload["required_commands"]:
        lines.append(f"- {cmd}")
    lines.extend(["", f"guide: {payload['guide']}"])
    if payload["missing"]:
        lines.append("missing guide content:")
        for item in payload["missing"]:
            lines.append(f"- {item}")
    else:
        lines.append("missing guide content: none")
    lines.extend(["", "actions:"])
    lines.append(f"- open guide: {payload['actions']['open_guide']}")
    lines.append(f"- validate: {payload['actions']['validate']}")
    lines.append(f"- write defaults: {payload['actions']['write_defaults']}")
    lines.append(f"- export artifact: {payload['actions']['artifact']}")
    return "\n".join(lines) + "\n"


def _render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Day 10 first-contribution checklist",
        "",
        f"- Score: **{payload['score']}** ({payload['passed_checks']}/{payload['total_checks']})",
        f"- Guide file: `{payload['guide']}`",
        "",
        "## Checklist",
        "",
    ]
    for item in payload["checklist"]:
        lines.append(f"- [ ] {item}")
    lines.extend(["", "## Required command sequence", "", "```bash"])
    lines.extend(payload["required_commands"])
    lines.extend(["```", "", "## Missing guide content", ""])
    if payload["missing"]:
        for item in payload["missing"]:
            lines.append(f"- `{item}`")
    else:
        lines.append("- none")
    lines.extend(["", "## Actions", ""])
    lines.append(f"- `{payload['actions']['open_guide']}`")
    lines.append(f"- `{payload['actions']['validate']}`")
    lines.append(f"- `{payload['actions']['write_defaults']}`")
    lines.append(f"- `{payload['actions']['artifact']}`")
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(list(argv) if argv is not None else None)

    touched: list[str] = []
    if args.write_defaults:
        touched = _write_defaults(Path(args.root))

    payload = build_first_contribution_status(args.root)
    payload["touched_files"] = touched

    if args.format == "json":
        rendered = json.dumps(payload, indent=2) + "\n"
    elif args.format == "markdown":
        rendered = _render_markdown(payload)
    else:
        rendered = _render_text(payload)

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered, encoding="utf-8")

    print(rendered, end="")

    if args.strict and payload["passed_checks"] != payload["total_checks"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
