from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

_ROLE_PLAYBOOK = {
    "sdet": {
        "label": "SDET / QA engineer",
        "first_command": "sdetkit doctor --format markdown",
        "next_action": "Run `sdetkit repo audit --format markdown` and triage the highest-signal findings.",
        "docs": ["docs/doctor.md", "docs/repo-audit.md"],
    },
    "platform": {
        "label": "Platform / DevOps engineer",
        "first_command": "sdetkit repo audit --format markdown",
        "next_action": "Wire checks into CI with `docs/github-action.md` and enforce deterministic gates.",
        "docs": ["docs/repo-audit.md", "docs/github-action.md"],
    },
    "security": {
        "label": "Security / compliance lead",
        "first_command": "sdetkit security --format markdown",
        "next_action": "Apply policy controls from `docs/security.md` and `docs/policy-and-baselines.md`.",
        "docs": ["docs/security.md", "docs/policy-and-baselines.md"],
    },
    "manager": {
        "label": "Engineering manager / tech lead",
        "first_command": "sdetkit doctor --format markdown",
        "next_action": "Standardize team workflows using `docs/automation-os.md` and `docs/repo-tour.md`.",
        "docs": ["docs/automation-os.md", "docs/repo-tour.md"],
    },
}

_PLATFORM_SETUP = {
    "linux": {
        "label": "Linux (bash)",
        "commands": [
            "python3 -m venv .venv",
            "source .venv/bin/activate",
            "python -m pip install -r requirements-test.txt -e .",
            "python -m sdetkit doctor --format text",
        ],
    },
    "macos": {
        "label": "macOS (zsh/bash)",
        "commands": [
            "python3 -m venv .venv",
            "source .venv/bin/activate",
            "python -m pip install -r requirements-test.txt -e .",
            "python -m sdetkit doctor --format text",
        ],
    },
    "windows": {
        "label": "Windows (PowerShell)",
        "commands": [
            "py -3 -m venv .venv",
            ".\\.venv\\Scripts\\Activate.ps1",
            "python -m pip install -r requirements-test.txt -e .",
            "python -m sdetkit doctor --format text",
        ],
    },
}


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sdetkit onboarding")
    p.add_argument(
        "--role",
        choices=["all", *_ROLE_PLAYBOOK.keys()],
        default="all",
        help="Role-specific onboarding path to print.",
    )
    p.add_argument(
        "--format",
        choices=["text", "markdown", "json"],
        default="text",
        help="Output format.",
    )
    p.add_argument(
        "--platform",
        choices=["all", *_PLATFORM_SETUP.keys()],
        default="all",
        help="Platform-specific setup snippets for Day 5 onboarding.",
    )
    p.add_argument(
        "--output",
        default="",
        help="Optional file path to also write the rendered onboarding output.",
    )
    return p


def _platform_payload(platform: str) -> dict[str, dict[str, Any]]:
    if platform == "all":
        return {name: details for name, details in _PLATFORM_SETUP.items()}
    return {platform: _PLATFORM_SETUP[platform]}


def _as_json(role: str, platform: str) -> str:
    payload: dict[str, Any]
    if role == "all":
        payload = {name: details for name, details in _ROLE_PLAYBOOK.items()}
    else:
        payload = {role: _ROLE_PLAYBOOK[role]}
    payload["day5_platform_setup"] = _platform_payload(platform)
    return json.dumps(payload, indent=2, sort_keys=True)


def _as_markdown(role: str, platform: str) -> str:
    rows: list[str] = ["| Role | First command | Next action |", "|---|---|---|"]
    for key, details in _ROLE_PLAYBOOK.items():
        if role != "all" and role != key:
            continue
        rows.append(
            f"| {details['label']} | `{details['first_command']}` | {details['next_action']} |"
        )
    rows.append("")
    rows.append("## Day 5 platform onboarding snippets")
    rows.append("")
    for key, details in _PLATFORM_SETUP.items():
        if platform != "all" and platform != key:
            continue
        rows.append(f"### {details['label']}")
        rows.append("")
        rows.append("```bash")
        rows.extend(details["commands"])
        rows.append("```")
        rows.append("")
    rows.append("Quick start: [README quick start](../README.md#quick-start)")
    return "\n".join(rows)


def _as_text(role: str, platform: str) -> str:
    lines = ["Day 1 onboarding paths", ""]
    for key, details in _ROLE_PLAYBOOK.items():
        if role != "all" and role != key:
            continue
        lines.append(f"[{details['label']}]")
        lines.append(f"  first: {details['first_command']}")
        lines.append(f"  next : {details['next_action']}")
        lines.append(f"  docs : {', '.join(details['docs'])}")
        lines.append("")
    lines.extend(["Day 5 platform onboarding snippets", ""])
    for key, details in _PLATFORM_SETUP.items():
        if platform != "all" and platform != key:
            continue
        lines.append(f"[{details['label']}]")
        for cmd in details["commands"]:
            lines.append(f"  {cmd}")
        lines.append("")
    lines.append("Start here: README quick start -> #quick-start")
    return "\n".join(lines)


def _render(role: str, platform: str, fmt: str) -> str:
    if fmt == "json":
        return _as_json(role, platform)
    if fmt == "markdown":
        return _as_markdown(role, platform)
    return _as_text(role, platform)


def main(argv: Sequence[str] | None = None) -> int:
    ns = _build_parser().parse_args(argv)

    rendered = _render(ns.role, ns.platform, ns.format)
    print(rendered)

    if ns.output:
        out_path = Path(ns.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        trailing = "" if rendered.endswith("\n") else "\n"
        out_path.write_text(rendered + trailing, encoding="utf-8")
    return 0
