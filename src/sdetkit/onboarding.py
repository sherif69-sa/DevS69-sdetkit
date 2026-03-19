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

_JOURNEY_PLAYBOOK = {
    "fast-start": {
        "label": "Fast start / first 15 minutes",
        "goal": "Get one trustworthy signal from the repo and understand which kit to explore next.",
        "steps": [
            "python -m sdetkit kits list",
            "python -m sdetkit doctor --format markdown",
            "python -m sdetkit onboarding --role sdet --platform linux --format markdown",
        ],
        "outcome": "You leave with a visible quality snapshot and a role-specific next move.",
    },
    "first-pr": {
        "label": "First PR / contributor runway",
        "goal": "Move from clone to a reviewable first contribution with minimal repo spelunking.",
        "steps": [
            "python -m sdetkit first-contribution --format markdown --strict",
            "python -m sdetkit onboarding --journey first-pr --format markdown",
            "python -m pytest tests/test_onboarding_cli.py tests/test_first_contribution_extra.py -q",
        ],
        "outcome": "You have an explicit checklist, a scoped starter path, and a focused validation loop.",
    },
    "ci-rollout": {
        "label": "CI rollout / team standardization",
        "goal": "Adopt deterministic gates in automation without guessing command order.",
        "steps": [
            "python -m sdetkit release gate fast --format json --stable-json --out build/gate-fast.json",
            "python -m sdetkit repo audit --format markdown",
            "python -m sdetkit onboarding --role platform --journey ci-rollout --format markdown",
        ],
        "outcome": "You get a reusable baseline artifact and a crisp path to CI integration.",
    },
    "artifact-review": {
        "label": "Artifact review / stakeholder proof",
        "goal": "Create evidence that is easy to hand to leads, reviewers, and release owners.",
        "steps": [
            "python -m sdetkit evidence pack --output build/evidence.zip",
            "python -m sdetkit forensics bundle --run examples/kits/forensics/run-b.json --output build/repro.zip",
            "python -m sdetkit onboarding --role manager --journey artifact-review --format markdown",
        ],
        "outcome": "You produce artifacts that make the repo feel operational, not just aspirational.",
    },
}


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sdetkit onboarding",
        description="Render role-based onboarding guidance, cross-platform setup snippets, and contributor journeys.",
    )
    p.add_argument(
        "--role",
        choices=["all", *_ROLE_PLAYBOOK.keys()],
        default="all",
        help="Role-specific onboarding path to print.",
    )
    p.add_argument(
        "--journey",
        choices=["all", *_JOURNEY_PLAYBOOK.keys()],
        default="all",
        help="Curated command journey to print alongside role guidance.",
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
        help="Cross-platform setup snippets to print.",
    )
    p.add_argument(
        "--output",
        default="",
        help="Optional file path to also write the rendered onboarding guide.",
    )
    return p


def _platform_payload(platform: str) -> dict[str, dict[str, Any]]:
    if platform == "all":
        return {name: details for name, details in _PLATFORM_SETUP.items()}
    return {platform: _PLATFORM_SETUP[platform]}


def _journey_payload(journey: str) -> dict[str, dict[str, Any]]:
    if journey == "all":
        return {name: details for name, details in _JOURNEY_PLAYBOOK.items()}
    return {journey: _JOURNEY_PLAYBOOK[journey]}


def _role_payload(role: str) -> dict[str, dict[str, Any]]:
    if role == "all":
        return {name: details for name, details in _ROLE_PLAYBOOK.items()}
    return {role: _ROLE_PLAYBOOK[role]}


def _build_payload(role: str, platform: str, journey: str) -> dict[str, Any]:
    setup = _platform_payload(platform)
    journeys = _journey_payload(journey)
    payload: dict[str, Any] = {
        "roles": _role_payload(role),
        "journeys": journeys,
        "platform_setup": setup,
        "day5_platform_setup": setup,
        "recommended_sequence": [
            "sdetkit kits list",
            "sdetkit onboarding --journey fast-start --format markdown",
            "sdetkit first-contribution --format markdown --strict",
        ],
    }
    if role != "all":
        payload[role] = _ROLE_PLAYBOOK[role]
    return payload


def _as_json(role: str, platform: str, journey: str) -> str:
    return json.dumps(_build_payload(role, platform, journey), indent=2, sort_keys=True)


def _render_journeys_markdown(journey: str) -> list[str]:
    lines = ["", "## Contributor journeys", ""]
    for key, details in _JOURNEY_PLAYBOOK.items():
        if journey != "all" and journey != key:
            continue
        lines.append(f"### {details['label']}")
        lines.append("")
        lines.append(f"- Goal: {details['goal']}")
        lines.append(f"- Outcome: {details['outcome']}")
        lines.append("")
        lines.append("```bash")
        lines.extend(details["steps"])
        lines.append("```")
        lines.append("")
    return lines


def _as_markdown(role: str, platform: str, journey: str) -> str:
    rows: list[str] = ["| Role | First command | Next action |", "|---|---|---|"]
    for key, details in _ROLE_PLAYBOOK.items():
        if role != "all" and role != key:
            continue
        rows.append(
            f"| {details['label']} | `{details['first_command']}` | {details['next_action']} |"
        )
    rows.extend(_render_journeys_markdown(journey))
    rows.append("## Platform setup snippets")
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
    rows.append("Recommended sequence:")
    rows.append("")
    rows.append("```bash")
    rows.append("python -m sdetkit kits list")
    rows.append("python -m sdetkit onboarding --journey fast-start --format markdown")
    rows.append("python -m sdetkit first-contribution --format markdown --strict")
    rows.append("```")
    rows.append("")
    rows.append("Quick start: [Docs fast start](../index.md#fast-start)")
    return "\n".join(rows)


def _as_text(role: str, platform: str, journey: str) -> str:
    lines = ["Onboarding paths", ""]
    for key, details in _ROLE_PLAYBOOK.items():
        if role != "all" and role != key:
            continue
        lines.append(f"[{details['label']}]")
        lines.append(f"  first: {details['first_command']}")
        lines.append(f"  next : {details['next_action']}")
        lines.append(f"  docs : {', '.join(details['docs'])}")
        lines.append("")
    lines.extend(["Contributor journeys", ""])
    for key, details in _JOURNEY_PLAYBOOK.items():
        if journey != "all" and journey != key:
            continue
        lines.append(f"[{details['label']}]")
        lines.append(f"  goal   : {details['goal']}")
        lines.append(f"  outcome: {details['outcome']}")
        lines.append("  steps  :")
        for step in details["steps"]:
            lines.append(f"    - {step}")
        lines.append("")
    lines.extend(["Platform setup snippets", ""])
    for key, details in _PLATFORM_SETUP.items():
        if platform != "all" and platform != key:
            continue
        lines.append(f"[{details['label']}]")
        for cmd in details["commands"]:
            lines.append(f"  {cmd}")
        lines.append("")
    lines.append("Recommended sequence:")
    lines.append("  1. sdetkit kits list")
    lines.append("  2. sdetkit onboarding --journey fast-start --format markdown")
    lines.append("  3. sdetkit first-contribution --format markdown --strict")
    lines.append("")
    lines.append("Start here: docs/index.md -> Fast start")
    return "\n".join(lines)


def _render(role: str, platform: str, journey: str, fmt: str) -> str:
    if fmt == "json":
        return _as_json(role, platform, journey)
    if fmt == "markdown":
        return _as_markdown(role, platform, journey)
    return _as_text(role, platform, journey)


def main(argv: Sequence[str] | None = None) -> int:
    ns = _build_parser().parse_args(argv)

    rendered = _render(ns.role, ns.platform, ns.journey, ns.format)
    print(rendered)

    if ns.output:
        out_path = Path(ns.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        trailing = "" if rendered.endswith("\n") else "\n"
        out_path.write_text(rendered + trailing, encoding="utf-8")
    return 0
