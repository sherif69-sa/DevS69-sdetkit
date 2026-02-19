from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

_PAGE_PATH = "docs/use-cases-startup-small-team.md"

_SECTION_HEADER = "# Startup + small-team workflow"
_REQUIRED_SECTIONS = [
    "## Who this is for",
    "## 10-minute startup path",
    "## Weekly operating rhythm",
    "## Guardrails that prevent regressions",
    "## CI fast-lane recipe",
    "## KPI snapshot for lean teams",
    "## Exit criteria to graduate to enterprise workflow",
]

_REQUIRED_COMMANDS = [
    "python -m sdetkit doctor --format text",
    "python -m sdetkit repo audit --json",
    "python -m sdetkit security --strict",
    "python -m pytest -q tests/test_startup_use_case.py tests/test_cli_help_lists_subcommands.py",
    "python -m sdetkit report --out reports/startup-weekly.json",
]

_CI_FAST_LANE = """name: startup-quality-fast-lane
on:
  pull_request:
  workflow_dispatch:

jobs:
  startup-fast-lane:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: python -m pip install -r requirements-test.txt -e .
      - run: python -m sdetkit startup-use-case --format json --strict
      - run: python scripts/check_day12_startup_use_case_contract.py
"""

_DAY12_DEFAULT_PAGE = f"""# Startup + small-team workflow

A practical landing page for lean engineering teams that need reliable quality gates without heavy process overhead.

## Who this is for

- Teams with 2-20 engineers shipping quickly.
- Founders or EMs who need confidence before each release.
- QA/SDET owners establishing a repeatable baseline in one sprint.

## 10-minute startup path

Use this sequence to move from clone to reliable checks quickly:

```bash
python -m sdetkit doctor --format text
python -m sdetkit repo audit --json
python -m sdetkit security --strict
python -m pytest -q tests/test_startup_use_case.py tests/test_cli_help_lists_subcommands.py
python -m sdetkit report --out reports/startup-weekly.json
```

## Weekly operating rhythm

1. Run `doctor` and `repo audit` at sprint start to catch drift early.
2. Run `security --strict` before release candidate tagging.
3. Publish `report` artifacts to preserve a quality trail.

## Guardrails that prevent regressions

- **Deterministic checks:** lock expected commands in CI and pre-merge workflows.
- **Single source of evidence:** save generated report artifacts under `reports/`.
- **Fast rollback:** revert to last known-good baseline when score drops.

## CI fast-lane recipe

Use this minimal workflow to enforce the Day 12 page contract in PRs:

```yaml
{_CI_FAST_LANE.rstrip()}
```

## KPI snapshot for lean teams

Track these signals every week:

- Mean time from PR open to merge.
- Failed quality gates per sprint.
- Security findings closed within SLA.
- New contributor first-PR success rate.

## Exit criteria to graduate to enterprise workflow

Move to the enterprise/regulated path once you need:

- Separation of duties and approval workflows.
- Extended audit retention and compliance mapping.
- Multi-repository governance at org level.
"""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sdetkit startup-use-case",
        description="Render and validate the Day 12 startup/small-team use-case landing page.",
    )
    parser.add_argument("--format", choices=["text", "markdown", "json"], default="text")
    parser.add_argument("--root", default=".", help="Repository root where docs live.")
    parser.add_argument("--output", default="", help="Optional output file path.")
    parser.add_argument("--strict", action="store_true", help="Return non-zero when required use-case content is missing.")
    parser.add_argument(
        "--write-defaults",
        action="store_true",
        help="Write or repair the Day 12 startup use-case page before validation.",
    )
    parser.add_argument(
        "--emit-pack-dir",
        default="",
        help="Optional path to emit a Day 12 startup operating pack (checklist, CI recipe, risk register).",
    )
    return parser


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _missing_checks(page_text: str) -> list[str]:
    checks = [_SECTION_HEADER, *_REQUIRED_SECTIONS, *_REQUIRED_COMMANDS, "name: startup-quality-fast-lane"]
    return [item for item in checks if item not in page_text]


def _write_defaults(base: Path) -> list[str]:
    page = base / _PAGE_PATH
    current = _read(page)

    if current and not _missing_checks(current):
        return []

    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(_DAY12_DEFAULT_PAGE, encoding="utf-8")
    return [_PAGE_PATH]


def _emit_pack(base: Path, out_dir: str) -> list[str]:
    root = base / out_dir
    root.mkdir(parents=True, exist_ok=True)

    checklist = root / "startup-day12-checklist.md"
    checklist.write_text(
        "\n".join(
            [
                "# Day 12 startup operating checklist",
                "",
                "- [ ] Validate landing page contract in strict mode.",
                "- [ ] Regenerate startup artifact markdown for handoff.",
                "- [ ] Run startup fast-lane tests for command integrity.",
                "- [ ] Publish weekly startup report evidence.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    ci_recipe = root / "startup-day12-ci.yml"
    ci_recipe.write_text(_CI_FAST_LANE, encoding="utf-8")

    risk_register = root / "startup-day12-risk-register.md"
    risk_register.write_text(
        "\n".join(
            [
                "# Day 12 startup risk register",
                "",
                "| Risk | Trigger | Mitigation |",
                "| --- | --- | --- |",
                "| Docs drift | Required sections are removed | Run `startup-use-case --strict` in CI |",
                "| Broken command examples | CLI flags change | Keep Day 12 tests in startup fast-lane |",
                "| Missing artifacts | Report generation skipped | Require artifact publish in weekly cadence |",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    return [str(path.relative_to(base)) for path in [checklist, ci_recipe, risk_register]]


def build_startup_use_case_status(root: str = ".") -> dict[str, object]:
    base = Path(root)
    page = base / _PAGE_PATH
    page_text = _read(page)
    missing = _missing_checks(page_text)

    total_checks = len([_SECTION_HEADER, *_REQUIRED_SECTIONS, *_REQUIRED_COMMANDS, "name: startup-quality-fast-lane"])
    passed_checks = total_checks - len(missing)
    score = round((passed_checks / total_checks) * 100, 1) if total_checks else 0.0

    return {
        "name": "day12-startup-use-case",
        "score": score,
        "total_checks": total_checks,
        "passed_checks": passed_checks,
        "page": str(page),
        "required_sections": list(_REQUIRED_SECTIONS),
        "required_commands": list(_REQUIRED_COMMANDS),
        "missing": missing,
        "actions": {
            "open_page": _PAGE_PATH,
            "validate": "sdetkit startup-use-case --format json --strict",
            "write_defaults": "sdetkit startup-use-case --write-defaults --format json --strict",
            "artifact": "sdetkit startup-use-case --format markdown --output docs/artifacts/day12-startup-use-case-sample.md",
            "emit_pack": "sdetkit startup-use-case --emit-pack-dir docs/artifacts/day12-startup-pack --format json --strict",
        },
    }


def _render_text(payload: dict[str, object]) -> str:
    lines = [
        "Day 12 startup use-case page",
        f"score: {payload['score']} ({payload['passed_checks']}/{payload['total_checks']})",
        "",
        f"page: {payload['page']}",
        "",
        "required sections:",
    ]
    for idx, item in enumerate(payload["required_sections"], start=1):
        lines.append(f"{idx}. {item}")
    lines.extend(["", "required commands:"])
    for cmd in payload["required_commands"]:
        lines.append(f"- {cmd}")
    if payload.get("pack_files"):
        lines.extend(["", "emitted pack files:"])
        for item in payload["pack_files"]:
            lines.append(f"- {item}")
    if payload["missing"]:
        lines.append("")
        lines.append("missing use-case content:")
        for item in payload["missing"]:
            lines.append(f"- {item}")
    else:
        lines.extend(["", "missing use-case content: none"])
    return "\n".join(lines) + "\n"


def _render_markdown(payload: dict[str, object]) -> str:
    lines = [
        "# Day 12 startup use-case page",
        "",
        f"- Score: **{payload['score']}** ({payload['passed_checks']}/{payload['total_checks']})",
        f"- Page: `{payload['page']}`",
        "",
        "## Required sections",
        "",
    ]
    for item in payload["required_sections"]:
        lines.append(f"- `{item}`")
    lines.extend(["", "## Required commands", "", "```bash"])
    lines.extend(payload["required_commands"])
    lines.extend(["```"])
    if payload.get("pack_files"):
        lines.extend(["", "## Emitted pack files", ""])
        for item in payload["pack_files"]:
            lines.append(f"- `{item}`")
    lines.extend(["", "## Missing use-case content", ""])
    if payload["missing"]:
        for item in payload["missing"]:
            lines.append(f"- `{item}`")
    else:
        lines.append("- none")
    lines.extend(["", "## Actions", ""])
    lines.append(f"- `{payload['actions']['open_page']}`")
    lines.append(f"- `{payload['actions']['validate']}`")
    lines.append(f"- `{payload['actions']['write_defaults']}`")
    lines.append(f"- `{payload['actions']['artifact']}`")
    lines.append(f"- `{payload['actions']['emit_pack']}`")
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(list(argv) if argv is not None else None)

    touched: list[str] = []
    if args.write_defaults:
        touched = _write_defaults(Path(args.root))

    payload = build_startup_use_case_status(args.root)
    payload["touched_files"] = touched

    if args.emit_pack_dir:
        payload["pack_files"] = _emit_pack(Path(args.root), args.emit_pack_dir)

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
