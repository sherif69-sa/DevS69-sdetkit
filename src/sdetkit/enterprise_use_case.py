from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/use-cases-enterprise-regulated.md"

_SECTION_HEADER = "# Enterprise + regulated workflow"
_REQUIRED_SECTIONS = [
    "## Who this is for",
    "## 15-minute enterprise baseline",
    "## Governance operating cadence",
    "## Compliance evidence controls",
    "## CI compliance lane recipe",
    "## KPI and control dashboard",
    "## Automated evidence bundle",
    "## Rollout model across business units",
]

_REQUIRED_COMMANDS = [
    "python -m sdetkit repo audit . --profile enterprise --format json",
    "python -m sdetkit security report --format text",
    "python -m sdetkit policy snapshot --output .sdetkit/day13-policy-snapshot.json",
    "python -m pytest -q tests/test_enterprise_use_case.py tests/test_cli_help_lists_subcommands.py",
    "python scripts/check_day13_enterprise_use_case_contract.py",
]

_CI_COMPLIANCE_LANE = """name: enterprise-compliance-lane
on:
  pull_request:
  workflow_dispatch:

jobs:
  enterprise-compliance:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: python -m pip install -r requirements-test.txt -e .
      - run: python -m sdetkit enterprise-use-case --format json --strict
      - run: python -m sdetkit enterprise-use-case --execute --evidence-dir docs/artifacts/day13-enterprise-pack/evidence --format json --strict
      - run: python scripts/check_day13_enterprise_use_case_contract.py
"""

_DAY13_DEFAULT_PAGE = f"""# Enterprise + regulated workflow

A governance-first landing page for organizations that need deterministic quality, policy evidence, and compliance-safe release controls.

## Who this is for

- Regulated engineering organizations with compliance, audit, or legal controls.
- Platform and quality teams supporting multiple repositories and business units.
- Security and GRC stakeholders needing repeatable evidence and change traceability.

## 15-minute enterprise baseline

Use this sequence to establish an enterprise guardrail baseline:

```bash
python -m sdetkit repo audit . --profile enterprise --format json
python -m sdetkit security report --format text
python -m sdetkit policy snapshot --output .sdetkit/day13-policy-snapshot.json
python -m pytest -q tests/test_enterprise_use_case.py tests/test_cli_help_lists_subcommands.py
python scripts/check_day13_enterprise_use_case_contract.py
```

## Governance operating cadence

1. Run `repo audit --profile enterprise` at the start of each sprint and before release freeze.
2. Run `security --strict` and `policy` for every release candidate.
3. Publish signed artifacts from these checks into your long-term evidence store.

## Compliance evidence controls

- **Separation of duties:** require review ownership split between platform and service teams.
- **Artifact retention:** archive JSON/markdown outputs for traceability and audit requests.
- **Policy drift detection:** fail PR checks when controls deviate from approved baselines.

## CI compliance lane recipe

Use this workflow to enforce Day 13 enterprise contract checks on every PR:

```yaml
{_CI_COMPLIANCE_LANE.rstrip()}
```

## KPI and control dashboard

Track these outcomes weekly:

- Policy violations by severity and mean time to resolution.
- Audit readiness score across repositories.
- Compliance check pass rate in PRs.
- Percentage of releases with complete evidence bundles.

## Automated evidence bundle

Generate and persist command outputs in one pass:

```bash
python -m sdetkit enterprise-use-case --execute --evidence-dir docs/artifacts/day13-enterprise-pack/evidence --format json --strict
```

This writes a structured `day13-execution-summary.json` and one per-command log file for audit-ready handoff.

## Rollout model across business units

1. Pilot with one regulated service and one shared platform repository.
2. Expand to all critical repositories with a policy baseline and CI lane.
3. Standardize quarterly audits using generated Day 13 artifacts.
"""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sdetkit enterprise-use-case",
        description="Render and validate the Day 13 enterprise/regulated use-case landing page.",
    )
    parser.add_argument("--format", choices=["text", "markdown", "json"], default="text")
    parser.add_argument("--root", default=".", help="Repository root where docs live.")
    parser.add_argument("--output", default="", help="Optional output file path.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero when required use-case content is missing.",
    )
    parser.add_argument(
        "--write-defaults",
        action="store_true",
        help="Write or repair the Day 13 enterprise use-case page before validation.",
    )
    parser.add_argument(
        "--emit-pack-dir",
        default="",
        help="Optional path to emit a Day 13 enterprise operating pack (checklist, CI recipe, controls register).",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Run the required Day 13 command sequence and capture pass/fail details.",
    )
    parser.add_argument(
        "--evidence-dir",
        default="",
        help="Optional output directory for execution summary JSON and command logs.",
    )
    parser.add_argument(
        "--timeout-sec",
        type=int,
        default=300,
        help="Per-command timeout in seconds for --execute mode.",
    )
    return parser


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _missing_checks(page_text: str) -> list[str]:
    checks = [
        _SECTION_HEADER,
        *_REQUIRED_SECTIONS,
        *_REQUIRED_COMMANDS,
        "name: enterprise-compliance-lane",
    ]
    return [item for item in checks if item not in page_text]


def _write_defaults(base: Path) -> list[str]:
    page = base / _PAGE_PATH
    current = _read(page)

    if current and not _missing_checks(current):
        return []

    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(_DAY13_DEFAULT_PAGE, encoding="utf-8")
    return [_PAGE_PATH]


def _emit_pack(base: Path, out_dir: str) -> list[str]:
    root = base / out_dir
    root.mkdir(parents=True, exist_ok=True)

    checklist = root / "enterprise-day13-checklist.md"
    checklist.write_text(
        "\n".join(
            [
                "# Day 13 enterprise operating checklist",
                "",
                "- [ ] Validate enterprise landing page contract in strict mode.",
                "- [ ] Regenerate enterprise artifact markdown for handoff.",
                "- [ ] Run enterprise compliance-lane tests for command integrity.",
                "- [ ] Generate execution evidence bundle for compliance handoff.",
                "- [ ] Publish compliance evidence bundle and controls register.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    ci_recipe = root / "enterprise-day13-ci.yml"
    ci_recipe.write_text(_CI_COMPLIANCE_LANE, encoding="utf-8")

    controls_register = root / "enterprise-day13-controls-register.md"
    controls_register.write_text(
        "\n".join(
            [
                "# Day 13 enterprise controls register",
                "",
                "| Control area | Trigger | Mitigation |",
                "| --- | --- | --- |",
                "| Documentation drift | Required enterprise sections are removed | Run `enterprise-use-case --strict` in CI |",
                "| Evidence gaps | Compliance artifacts are not published | Require `--execute --evidence-dir` in release pipeline |",
                "| Policy baseline mismatch | Profile or control set changes unexpectedly | Run `sdetkit policy snapshot --output .sdetkit/day13-policy-snapshot.json` and diff against baseline |",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    return [str(path.relative_to(base)) for path in [checklist, ci_recipe, controls_register]]


def _execute_commands(
    commands: list[str],
    timeout_sec: int,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for idx, command in enumerate(commands, start=1):
        try:
            proc = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                check=False,
            )
            results.append(
                {
                    "index": idx,
                    "command": command,
                    "returncode": proc.returncode,
                    "ok": proc.returncode == 0,
                    "stdout": proc.stdout,
                    "stderr": proc.stderr,
                }
            )
        except subprocess.TimeoutExpired as exc:
            results.append(
                {
                    "index": idx,
                    "command": command,
                    "returncode": 124,
                    "ok": False,
                    "stdout": (exc.stdout or "") if isinstance(exc.stdout, str) else "",
                    "stderr": (exc.stderr or "") if isinstance(exc.stderr, str) else "",
                    "error": f"timed out after {timeout_sec}s",
                }
            )
    return results


def _write_execution_evidence(base: Path, out_dir: str, results: list[dict[str, Any]]) -> list[str]:
    root = base / out_dir
    root.mkdir(parents=True, exist_ok=True)

    summary = root / "day13-execution-summary.json"
    payload = {
        "name": "day13-enterprise-execution",
        "total_commands": len(results),
        "passed_commands": len([r for r in results if r.get("ok")]),
        "failed_commands": len([r for r in results if not r.get("ok")]),
        "results": results,
    }
    summary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    emitted = [summary]
    for row in results:
        log_file = root / f"command-{row['index']:02d}.log"
        log_file.write_text(
            "\n".join(
                [
                    f"command: {row['command']}",
                    f"returncode: {row['returncode']}",
                    f"ok: {row['ok']}",
                    "--- stdout ---",
                    str(row.get("stdout", "")),
                    "--- stderr ---",
                    str(row.get("stderr", "")),
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        emitted.append(log_file)

    return [str(path.relative_to(base)) for path in emitted]


def build_enterprise_use_case_status(root: str = ".") -> dict[str, Any]:
    base = Path(root)
    page = base / _PAGE_PATH
    page_text = _read(page)
    missing = _missing_checks(page_text)

    total_checks = len(
        [
            _SECTION_HEADER,
            *_REQUIRED_SECTIONS,
            *_REQUIRED_COMMANDS,
            "name: enterprise-compliance-lane",
        ]
    )
    passed_checks = total_checks - len(missing)
    score = round((passed_checks / total_checks) * 100, 1) if total_checks else 0.0

    return {
        "name": "day13-enterprise-use-case",
        "score": score,
        "total_checks": total_checks,
        "passed_checks": passed_checks,
        "page": str(page),
        "required_sections": list(_REQUIRED_SECTIONS),
        "required_commands": list(_REQUIRED_COMMANDS),
        "missing": missing,
        "actions": {
            "open_page": _PAGE_PATH,
            "validate": "sdetkit enterprise-use-case --format json --strict",
            "write_defaults": "sdetkit enterprise-use-case --write-defaults --format json --strict",
            "artifact": "sdetkit enterprise-use-case --format markdown --output docs/artifacts/day13-enterprise-use-case-sample.md",
            "emit_pack": "sdetkit enterprise-use-case --emit-pack-dir docs/artifacts/day13-enterprise-pack --format json --strict",
            "execute": "sdetkit enterprise-use-case --execute --evidence-dir docs/artifacts/day13-enterprise-pack/evidence --format json --strict",
        },
    }


def _render_text(payload: dict[str, Any]) -> str:
    lines = [
        "Day 13 enterprise use-case page",
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
    if payload.get("execution"):
        lines.extend(["", "execution summary:"])
        exec_data = payload["execution"]
        lines.append(f"- passed: {exec_data['passed_commands']}/{exec_data['total_commands']}")
        lines.append(f"- failed: {exec_data['failed_commands']}")
    if payload.get("evidence_files"):
        lines.extend(["", "evidence files:"])
        for item in payload["evidence_files"]:
            lines.append(f"- {item}")
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


def _render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Day 13 enterprise use-case page",
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
    if payload.get("execution"):
        exec_data = payload["execution"]
        lines.extend(["", "## Execution summary", ""])
        lines.append(
            f"- Passed commands: **{exec_data['passed_commands']}**/{exec_data['total_commands']}"
        )
        lines.append(f"- Failed commands: **{exec_data['failed_commands']}**")
    if payload.get("evidence_files"):
        lines.extend(["", "## Evidence files", ""])
        for item in payload["evidence_files"]:
            lines.append(f"- `{item}`")
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
    lines.append(f"- `{payload['actions']['execute']}`")
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(list(argv) if argv is not None else None)

    touched: list[str] = []
    if args.write_defaults:
        touched = _write_defaults(Path(args.root))

    payload = build_enterprise_use_case_status(args.root)
    payload["touched_files"] = touched

    if args.emit_pack_dir:
        payload["pack_files"] = _emit_pack(Path(args.root), args.emit_pack_dir)

    if args.execute:
        results = _execute_commands(list(payload["required_commands"]), args.timeout_sec)
        execution = {
            "total_commands": len(results),
            "passed_commands": len([r for r in results if r["ok"]]),
            "failed_commands": len([r for r in results if not r["ok"]]),
        }
        payload["execution"] = execution
        payload["execution_results"] = results
        if args.evidence_dir:
            payload["evidence_files"] = _write_execution_evidence(
                Path(args.root), args.evidence_dir, results
            )

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

    checks_ok = payload["passed_checks"] == payload["total_checks"]
    execute_ok = True
    if args.execute:
        execute_ok = payload.get("execution", {}).get("failed_commands", 0) == 0

    if args.strict and not (checks_ok and execute_ok):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
