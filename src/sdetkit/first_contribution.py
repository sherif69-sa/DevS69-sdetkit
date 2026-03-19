from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

_STARTER_PROFILES = {
    "docs-polish": {
        "label": "Docs polish",
        "impact": "Clarify commands, fix internal links, and improve first-run confidence.",
        "starter_files": ["README.md", "docs/choose-your-path.md", "CONTRIBUTING.md"],
        "validation": ["python -m pre_commit run -a", "mkdocs build"],
        "first_steps": [
            "Read README.md and docs/choose-your-path.md to find wording drift or broken handoffs.",
            "Make one focused docs update that shortens the path from landing page to first successful command.",
            "Run docs-safe validation before opening your PR.",
        ],
    },
    "test-hardening": {
        "label": "Test hardening",
        "impact": "Add focused regression coverage without changing the public surface area.",
        "starter_files": ["tests/", "src/sdetkit/"],
        "validation": ["python -m pytest -q", "bash quality.sh cov"],
        "first_steps": [
            "Pick one documented CLI behavior and find the closest existing test module.",
            "Add one regression or edge-case assertion without broad refactors.",
            "Run the focused test file first, then the repo quality gate if scope grows.",
        ],
    },
    "automation-upgrade": {
        "label": "Automation upgrade",
        "impact": "Improve CI repeatability, artifact quality, or release safety checks.",
        "starter_files": ["scripts/", "templates/automations/", ".github/"],
        "validation": ["python -m pre_commit run -a", "bash quality.sh cov", "python -m build"],
        "first_steps": [
            "Inspect one automation path with a clear before/after improvement opportunity.",
            "Keep the change scoped to one workflow or template family.",
            "Validate both local quality checks and packaging/build safety when relevant.",
        ],
    },
}

_TRUST_ASSETS = {
    "starter_inventory": {
        "label": "Starter work inventory",
        "path": "docs/starter-work-inventory.md",
        "why": "Gives first-time contributors concrete, repo-specific starter lanes.",
    },
    "quickstart": {
        "label": "First contribution quickstart",
        "path": "docs/first-contribution-quickstart.md",
        "why": "Provides a short path from clone to reviewable PR.",
    },
    "pr_template": {
        "label": "PR template",
        "path": ".github/PULL_REQUEST_TEMPLATE.md",
        "why": "Sets reviewer expectations and keeps contribution evidence consistent.",
    },
    "feature_request_template": {
        "label": "Feature request template",
        "path": ".github/ISSUE_TEMPLATE/feature_request.yml",
        "why": "Lets new contributors propose scoped work without guessing the maintainer format.",
    },
}

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
        description="Render and validate a first-contribution checklist report.",
    )
    p.add_argument(
        "--format",
        choices=["text", "markdown", "json"],
        default="text",
        help="Output format.",
    )
    p.add_argument("--root", default=".", help="Repository root where CONTRIBUTING.md lives.")
    p.add_argument(
        "--output",
        default="",
        help="Optional file path to also write the rendered first-contribution report.",
    )
    p.add_argument(
        "--profile",
        choices=["all", *_STARTER_PROFILES.keys()],
        default="all",
        help="Highlight one starter contribution profile instead of all profiles.",
    )
    p.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero if required checklist content is missing.",
    )
    p.add_argument(
        "--write-defaults",
        action="store_true",
        help="Write a default first-contribution checklist block into CONTRIBUTING.md if missing, then validate again.",
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


def _profile_payload(profile: str) -> dict[str, dict[str, Any]]:
    if profile == "all":
        return dict(_STARTER_PROFILES)
    return {profile: _STARTER_PROFILES[profile]}


def _trust_asset_status(base: Path) -> dict[str, dict[str, str | bool]]:
    status: dict[str, dict[str, str | bool]] = {}
    for key, details in _TRUST_ASSETS.items():
        path = base / details["path"]
        status[key] = {
            "label": details["label"],
            "path": details["path"],
            "why": details["why"],
            "exists": path.exists(),
        }
    return status


def build_first_contribution_status(root: str = ".", profile: str = "all") -> dict[str, Any]:
    base = Path(root)
    guide = base / "CONTRIBUTING.md"
    guide_text = _read(guide)
    missing = _missing_checks(guide_text)
    trust_assets = _trust_asset_status(base)
    missing_assets = [
        asset["path"]
        for asset in trust_assets.values()
        if not bool(asset["exists"])
    ]

    total_checks = len([_CHECKLIST_SECTION_HEADER, *_CHECKLIST_ITEMS, *_COMMAND_BLOCKS]) + len(
        trust_assets
    )
    passed_checks = total_checks - len(missing) - len(missing_assets)
    score = round((passed_checks / total_checks) * 100, 1) if total_checks else 0.0
    selected_profiles = _profile_payload(profile)
    recommended_profile = next(iter(selected_profiles)) if profile != "all" else "docs-polish"

    return {
        "name": "day10-first-contribution-checklist",
        "score": score,
        "total_checks": total_checks,
        "passed_checks": passed_checks,
        "checklist": list(_CHECKLIST_ITEMS),
        "required_commands": list(_COMMAND_BLOCKS),
        "guide": str(guide),
        "missing": missing,
        "missing_assets": missing_assets,
        "starter_profiles": selected_profiles,
        "available_starter_profiles": list(_STARTER_PROFILES),
        "selected_profile": profile,
        "recommended_profile": recommended_profile,
        "trust_assets": trust_assets,
        "good_first_issue_labels": [
            "good first issue",
            "help wanted",
            "documentation",
            "tests",
            "needs-triage",
        ],
        "actions": {
            "open_guide": "CONTRIBUTING.md",
            "validate": "sdetkit first-contribution --format json --strict",
            "profile_docs_polish": "sdetkit first-contribution --profile docs-polish --format markdown",
            "profile_test_hardening": "sdetkit first-contribution --profile test-hardening --format markdown",
            "profile_automation_upgrade": "sdetkit first-contribution --profile automation-upgrade --format markdown",
            "write_defaults": "sdetkit first-contribution --write-defaults --strict",
            "artifact": "sdetkit first-contribution --format markdown --output docs/artifacts/day10-first-contribution-checklist-sample.md",
        },
    }


def _render_text(payload: dict[str, Any]) -> str:
    lines = [
        "First contribution checklist report",
        f"Score: {payload['score']} ({payload['passed_checks']}/{payload['total_checks']})",
        "",
        "Checklist:",
    ]
    for idx, item in enumerate(payload["checklist"], start=1):
        lines.append(f"{idx}. {item}")
    lines.extend(["", "Required commands:"])
    for cmd in payload["required_commands"]:
        lines.append(f"- {cmd}")
    lines.extend(["", f"Guide file: {payload['guide']}"])
    if payload["missing"]:
        lines.append("Guide coverage gaps:")
        for item in payload["missing"]:
            lines.append(f"- {item}")
    else:
        lines.append("Guide coverage gaps: none")
    lines.extend(["", "Contributor trust assets:"])
    for asset in payload["trust_assets"].values():
        status = "ok" if asset["exists"] else "missing"
        lines.append(f"- [{status}] {asset['label']}: {asset['path']}")
        lines.append(f"  why      : {asset['why']}")
    if payload["missing_assets"]:
        lines.append("Missing trust assets:")
        for item in payload["missing_assets"]:
            lines.append(f"- {item}")
    else:
        lines.append("Missing trust assets: none")
    lines.extend(["", "Starter profiles:"])
    for key, details in payload["starter_profiles"].items():
        lines.append(f"- {details['label']} ({key}): {details['impact']}")
        lines.append(f"  files     : {', '.join(details['starter_files'])}")
        lines.append(f"  validate  : {'; '.join(details['validation'])}")
        lines.append(f"  first step: {details['first_steps'][0]}")
    lines.extend(["", "Good-first-issue labels:"])
    for label in payload["good_first_issue_labels"]:
        lines.append(f"- {label}")
    lines.extend(["", "Actions:"])
    lines.append(f"- Open guide: {payload['actions']['open_guide']}")
    lines.append(f"- Validate: {payload['actions']['validate']}")
    lines.append(f"- Spotlight docs profile: {payload['actions']['profile_docs_polish']}")
    lines.append(f"- Spotlight test profile: {payload['actions']['profile_test_hardening']}")
    lines.append(f"- Spotlight automation profile: {payload['actions']['profile_automation_upgrade']}")
    lines.append(f"- Write defaults: {payload['actions']['write_defaults']}")
    lines.append(f"- Export artifact: {payload['actions']['artifact']}")
    return "\n".join(lines) + "\n"


def _render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# First contribution checklist report",
        "",
        f"- Score: **{payload['score']}** ({payload['passed_checks']}/{payload['total_checks']})",
        f"- Guide file: `{payload['guide']}`",
        f"- Selected starter profile: `{payload['selected_profile']}`",
        f"- Recommended starter profile: `{payload['recommended_profile']}`",
        "",
        "## Checklist",
        "",
    ]
    for item in payload["checklist"]:
        lines.append(f"- [ ] {item}")
    lines.extend(["", "## Required command sequence", "", "```bash"])
    lines.extend(payload["required_commands"])
    lines.extend(["```", "", "## Starter profiles", ""])
    for key, details in payload["starter_profiles"].items():
        lines.append(f"### {details['label']} (`{key}`)")
        lines.append("")
        lines.append(f"- Impact: {details['impact']}")
        lines.append(f"- Good starter files: `{'`, `'.join(details['starter_files'])}`")
        lines.append(f"- Validate with: `{'`, `'.join(details['validation'])}`")
        lines.append("- First steps:")
        for step in details["first_steps"]:
            lines.append(f"  - {step}")
        lines.append("")
    lines.extend(["## Contributor trust assets", ""])
    for asset in payload["trust_assets"].values():
        lines.append(
            f"- [{'x' if asset['exists'] else ' '}] `{asset['path']}` — {asset['label']}: {asset['why']}"
        )
    lines.extend(["", "## Guide coverage gaps", ""])
    if payload["missing"]:
        for item in payload["missing"]:
            lines.append(f"- `{item}`")
    else:
        lines.append("- none")
    lines.extend(["", "## Missing trust assets", ""])
    if payload["missing_assets"]:
        for item in payload["missing_assets"]:
            lines.append(f"- `{item}`")
    else:
        lines.append("- none")
    lines.extend(["", "## Good-first-issue labels", ""])
    for label in payload["good_first_issue_labels"]:
        lines.append(f"- `{label}`")
    lines.extend(["", "## Actions", ""])
    lines.append(f"- Open guide: `{payload['actions']['open_guide']}`")
    lines.append(f"- Validate: `{payload['actions']['validate']}`")
    lines.append(f"- Spotlight docs profile: `{payload['actions']['profile_docs_polish']}`")
    lines.append(f"- Spotlight test profile: `{payload['actions']['profile_test_hardening']}`")
    lines.append(f"- Spotlight automation profile: `{payload['actions']['profile_automation_upgrade']}`")
    lines.append(f"- Write defaults: `{payload['actions']['write_defaults']}`")
    lines.append(f"- Export artifact: `{payload['actions']['artifact']}`")
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(list(argv) if argv is not None else None)

    touched: list[str] = []
    if args.write_defaults:
        touched = _write_defaults(Path(args.root))

    payload = build_first_contribution_status(args.root, profile=args.profile)
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
