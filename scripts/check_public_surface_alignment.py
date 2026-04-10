from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

README = Path("README.md")
DOCS_INDEX = Path("docs/index.md")
DOCS_STABILITY = Path("docs/stability-levels.md")
MKDOCS = Path("mkdocs.yml")
PAGES_WORKFLOW = Path(".github/workflows/pages.yml")
PUBLIC_COMMAND_CONTRACT = Path("src/sdetkit/public_command_surface.json")

CANONICAL_PROMISE = "deterministic ship/no-ship decisions with machine-readable evidence"
CANONICAL_FAST_COMMAND = (
    "python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json"
)
CANONICAL_RELEASE_COMMAND = (
    "python -m sdetkit gate release --format json --out build/release-preflight.json"
)
PRIMARY_NAV_SECTIONS = (
    "Start here",
    "Canonical first-proof path (primary)",
    "Team adoption and CI rollout (primary)",
)
SECONDARY_NAV_SECTION = "Current reference and discoverability (secondary)"
ARCHIVE_NAV_SECTION = "Historical archive (non-primary)"


def _missing_lines(path: Path, expected: tuple[str, ...]) -> list[str]:
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    return [line for line in expected if line not in text]


def main() -> int:
    errors: list[str] = []

    required_files = (
        README,
        DOCS_INDEX,
        DOCS_STABILITY,
        MKDOCS,
        PAGES_WORKFLOW,
        PUBLIC_COMMAND_CONTRACT,
    )
    for file_path in required_files:
        if not file_path.is_file():
            errors.append(f"missing required file: {file_path}")

    if errors:
        print("public-surface-alignment check failed:", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        return 1

    contract = json.loads(PUBLIC_COMMAND_CONTRACT.read_text(encoding="utf-8"))
    canonical_path = tuple(contract.get("canonical_first_path", []))
    required_tiers = tuple(contract.get("required_policy_tiers", []))
    readme_missing = _missing_lines(
        README,
        (
            "release-confidence CLI",
            CANONICAL_PROMISE,
            *canonical_path,
        ),
    )
    docs_home_missing = _missing_lines(
        DOCS_INDEX,
        (
            "release-confidence CLI",
            CANONICAL_PROMISE,
            "product homepage/router",
            *canonical_path,
        ),
    )
    errors.extend(f"{README}: missing '{entry}'" for entry in readme_missing)
    errors.extend(f"{DOCS_INDEX}: missing '{entry}'" for entry in docs_home_missing)
    if contract.get("advanced_supported_next_step") != "python -m sdetkit kits list":
        errors.append(
            "public command contract: advanced_supported_next_step must be 'python -m sdetkit kits list'"
        )
    stability_text = DOCS_STABILITY.read_text(encoding="utf-8")
    for tier in required_tiers:
        if tier not in stability_text:
            errors.append(
                f"{DOCS_STABILITY}: missing policy tier '{tier}' from machine-readable contract"
            )

    mkdocs_text = MKDOCS.read_text(encoding="utf-8")
    if "nav:" not in mkdocs_text:
        errors.append("mkdocs.yml: nav is missing")
    elif "\n  - Start here: index.md" not in mkdocs_text:
        errors.append("mkdocs.yml: first nav item must be 'Start here: index.md'")
    nav_block = mkdocs_text.split("\nnav:\n", 1)[1].split("\nexclude_docs:", 1)[0]
    top_level_labels: list[str] = []
    for line in nav_block.splitlines():
        match = re.match(r"^  - ([^:]+):", line)
        if match:
            top_level_labels.append(match.group(1))
    for section in PRIMARY_NAV_SECTIONS:
        if section not in top_level_labels:
            errors.append(f"mkdocs.yml: missing primary nav section '{section}'")
    if SECONDARY_NAV_SECTION not in top_level_labels:
        errors.append(f"mkdocs.yml: missing secondary nav section '{SECONDARY_NAV_SECTION}'")
    if ARCHIVE_NAV_SECTION not in top_level_labels:
        errors.append(f"mkdocs.yml: missing archive nav section '{ARCHIVE_NAV_SECTION}'")
    if ARCHIVE_NAV_SECTION in top_level_labels and top_level_labels[-1] != ARCHIVE_NAV_SECTION:
        errors.append(
            "mkdocs.yml: historical archive section must be the final top-level nav section"
        )

    workflow = yaml.safe_load(PAGES_WORKFLOW.read_text(encoding="utf-8"))
    build_steps = workflow.get("jobs", {}).get("build", {}).get("steps", [])
    run_commands = "\n".join(step.get("run", "") for step in build_steps if isinstance(step, dict))

    if "python scripts/check_public_surface_alignment.py" not in run_commands:
        errors.append("pages workflow: missing public-surface alignment contract check")
    if "python -m mkdocs build --strict" not in run_commands:
        errors.append("pages workflow: missing strict mkdocs build command")

    if errors:
        print("public-surface-alignment check failed:", file=sys.stderr)
        for error in errors:
            print(f" - {error}", file=sys.stderr)
        return 1

    print("public-surface-alignment check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
