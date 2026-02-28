from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

_PAGE_PATH = "docs/integrations-github-actions-quickstart.md"

_SECTION_HEADER = "# GitHub Actions quickstart (Day 15)"
_REQUIRED_SECTIONS = [
    "## Who this recipe is for",
    "## 5-minute setup",
    "## Minimal workflow",
    "## Strict workflow variant",
    "## Nightly reliability variant",
    "## Fast verification commands",
    "## Multi-channel distribution loop",
    "## Failure recovery playbook",
    "## Rollout checklist",
]

_REQUIRED_COMMANDS = [
    "python -m sdetkit doctor --format text",
    "python -m sdetkit repo audit --format json",
    "python -m pytest -q tests/test_github_actions_quickstart.py tests/test_cli_help_lists_subcommands.py",
    "python scripts/check_day15_github_actions_quickstart_contract.py",
    "python -m sdetkit github-actions-quickstart --execute --evidence-dir docs/artifacts/day15-github-pack/evidence --format json --strict",
]


def _workflow_content(variant: str) -> str:
    if variant == "strict":
        return """name: sdetkit-github-strict
on:
  pull_request:
  workflow_dispatch:

jobs:
  strict-gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: python -m pip install -r requirements-test.txt -e .
      - run: python -m pytest -q tests/test_cli_sdetkit.py tests/test_github_actions_quickstart.py tests/test_cli_help_lists_subcommands.py
      - run: python -m sdetkit github-actions-quickstart --format json --strict
      - run: python scripts/check_day15_github_actions_quickstart_contract.py
"""

    if variant == "nightly":
        return """name: sdetkit-github-nightly
on:
  schedule:
    - cron: '0 4 * * *'
  workflow_dispatch:

jobs:
  nightly-audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: python -m pip install -r requirements-test.txt -e .
      - run: python -m sdetkit doctor --format text
      - run: python -m sdetkit repo audit --format json
      - run: python -m sdetkit github-actions-quickstart --execute --evidence-dir docs/artifacts/day15-github-pack/evidence --format json --strict
"""

    return """name: sdetkit-github-quickstart
on:
  pull_request:
  workflow_dispatch:

jobs:
  quality-gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: python -m pip install -r requirements-test.txt -e .
      - run: python -m sdetkit github-actions-quickstart --format json --strict
      - run: python -m pytest -q tests/test_cli_sdetkit.py tests/test_github_actions_quickstart.py
"""


_DAY15_DEFAULT_PAGE = f"""# GitHub Actions quickstart (Day 15)

A production-ready integration recipe to run `sdetkit` quality checks in GitHub Actions with quickstart, strict, and nightly variants.

## Who this recipe is for

- Maintainers who need CI guardrails in less than 5 minutes.
- Teams moving from local-only checks to PR gate automation.
- Contributors who want deterministic quality signals in pull requests.

## 5-minute setup

1. Add `.github/workflows/sdetkit-quickstart.yml` with the minimal workflow below.
2. Push a branch and open a pull request.
3. Confirm the quality-gate job passes before merge.

## Minimal workflow

```yaml
{_workflow_content("minimal").rstrip()}
```

## Strict workflow variant

```yaml
{_workflow_content("strict").rstrip()}
```

## Nightly reliability variant

```yaml
{_workflow_content("nightly").rstrip()}
```

## Fast verification commands

Run these locally before opening PRs:

```bash
python -m sdetkit doctor --format text
python -m sdetkit repo audit --format json
python -m pytest -q tests/test_github_actions_quickstart.py tests/test_cli_help_lists_subcommands.py
python scripts/check_day15_github_actions_quickstart_contract.py
python -m sdetkit github-actions-quickstart --execute --evidence-dir docs/artifacts/day15-github-pack/evidence --format json --strict
```

## Multi-channel distribution loop

1. Post merged workflow update in engineering chat with before/after CI timing.
2. Publish docs update in `docs/index.md` weekly rollout section.
3. Share one artifact (`day15-execution-summary.json`) in team retro for adoption tracking.

## Failure recovery playbook

- If checks fail from missing docs content, run `--write-defaults` and rerun strict validation.
- If tests fail, keep quickstart lane blocking and move nightly lane to diagnostics-only until stable.
- If flaky behavior appears, attach evidence logs from `--execute --evidence-dir` to the incident thread.

## Rollout checklist

- [ ] Workflow is enabled on `pull_request` and `workflow_dispatch`.
- [ ] CI installs from `requirements-test.txt` and editable package source.
- [ ] Day 15 contract check is part of docs validation.
- [ ] Execution evidence bundle is generated weekly.
- [ ] Team channel has a pinned link to this quickstart page.
"""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sdetkit github-actions-quickstart",
        description="Render and validate the Day 15 GitHub Actions quickstart integration recipe.",
    )
    parser.add_argument("--format", choices=["text", "markdown", "json"], default="text")
    parser.add_argument("--root", default=".", help="Repository root where docs live.")
    parser.add_argument("--output", default="", help="Optional output file path.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero when required quickstart content is missing.",
    )
    parser.add_argument(
        "--write-defaults",
        action="store_true",
        help="Write or repair the Day 15 quickstart page before validation.",
    )
    parser.add_argument(
        "--emit-pack-dir", default="", help="Optional path to emit a Day 15 quickstart pack."
    )
    parser.add_argument(
        "--variant",
        choices=["minimal", "strict", "nightly"],
        default="minimal",
        help="Workflow variant for markdown/text snippets.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Run Day 15 command sequence and capture pass/fail details.",
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
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _missing_checks(page_text: str) -> list[str]:
    checks = [
        _SECTION_HEADER,
        *_REQUIRED_SECTIONS,
        *_REQUIRED_COMMANDS,
        "name: sdetkit-github-quickstart",
        "name: sdetkit-github-strict",
        "name: sdetkit-github-nightly",
    ]
    return [item for item in checks if item not in page_text]


def _write_defaults(base: Path) -> list[str]:
    page = base / _PAGE_PATH
    current = _read(page)
    if current and not _missing_checks(current):
        return []

    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(_DAY15_DEFAULT_PAGE, encoding="utf-8")
    return [_PAGE_PATH]


def _emit_pack(base: Path, out_dir: str) -> list[str]:
    root = base / out_dir
    root.mkdir(parents=True, exist_ok=True)

    checklist = root / "day15-github-checklist.md"
    checklist.write_text(
        "\n".join(
            [
                "# Day 15 GitHub Actions rollout checklist",
                "",
                "- [ ] Validate quickstart page in strict mode.",
                "- [ ] Commit workflow files under .github/workflows/.",
                "- [ ] Verify PR run passes doctor, repo audit, and tests.",
                "- [ ] Generate evidence bundle from --execute mode.",
                "- [ ] Share workflow + evidence links in onboarding docs.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    minimal_workflow = root / "day15-sdetkit-quickstart.yml"
    minimal_workflow.write_text(_workflow_content("minimal"), encoding="utf-8")

    strict_workflow = root / "day15-sdetkit-strict.yml"
    strict_workflow.write_text(_workflow_content("strict"), encoding="utf-8")

    nightly_workflow = root / "day15-sdetkit-nightly.yml"
    nightly_workflow.write_text(_workflow_content("nightly"), encoding="utf-8")

    distribution_plan = root / "day15-distribution-plan.md"
    distribution_plan.write_text(
        "\n".join(
            [
                "# Day 15 distribution plan",
                "",
                "| Channel | Artifact | Owner | Cadence |",
                "| --- | --- | --- | --- |",
                "| Engineering Slack | quickstart workflow + execution summary | QE lead | weekly |",
                "| Docs portal | Day 15 integration page | Docs owner | weekly |",
                "| Sprint retro | evidence logs and failure themes | Team lead | bi-weekly |",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    validation = root / "day15-validation-commands.md"
    validation.write_text(
        "\n".join(["# Day 15 validation commands", "", "```bash", *_REQUIRED_COMMANDS, "```", ""])
        + "\n",
        encoding="utf-8",
    )

    return [
        str(path.relative_to(base))
        for path in (
            checklist,
            minimal_workflow,
            strict_workflow,
            nightly_workflow,
            distribution_plan,
            validation,
        )
    ]


def _execute_commands(commands: list[str], timeout_sec: int) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for idx, command in enumerate(commands, start=1):
        try:
            argv = shlex.split(command)
            if argv and argv[0] == "python":
                argv[0] = sys.executable
            proc = subprocess.run(
                argv,
                shell=False,
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

    summary = root / "day15-execution-summary.json"
    payload = {
        "name": "day15-github-actions-execution",
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


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    base = Path(args.root).resolve()

    touched = _write_defaults(base) if args.write_defaults else []
    page = base / _PAGE_PATH
    text = _read(page)

    missing = _missing_checks(text)
    total = len(
        [
            _SECTION_HEADER,
            *_REQUIRED_SECTIONS,
            *_REQUIRED_COMMANDS,
            "name: sdetkit-github-quickstart",
            "name: sdetkit-github-strict",
            "name: sdetkit-github-nightly",
        ]
    )
    passed = total - len(missing)
    score = round((passed / total) * 100, 1)

    payload: dict[str, Any] = {
        "name": "day15-github-actions-quickstart",
        "page": _PAGE_PATH,
        "variant": args.variant,
        "selected_workflow": _workflow_content(args.variant),
        "passed_checks": passed,
        "total_checks": total,
        "score": score,
        "missing": missing,
        "touched_files": touched,
    }

    if args.emit_pack_dir:
        payload["pack_files"] = _emit_pack(base, args.emit_pack_dir)

    execution_failed = False
    if args.execute:
        commands = [
            "python -m sdetkit doctor --format text",
            "python -m sdetkit repo audit --format json",
            "python -m pytest -q tests/test_github_actions_quickstart.py tests/test_cli_help_lists_subcommands.py",
            "python -m sdetkit github-actions-quickstart --format json --strict",
        ]
        results = _execute_commands(commands, timeout_sec=args.timeout_sec)
        execution = {
            "total_commands": len(results),
            "passed_commands": len([r for r in results if r.get("ok")]),
            "failed_commands": len([r for r in results if not r.get("ok")]),
            "results": results,
        }
        payload["execution"] = execution
        execution_failed = int(cast(Any, execution["failed_commands"])) > 0

        evidence_dir = args.evidence_dir or "docs/artifacts/day15-github-pack/evidence"
        payload["evidence_files"] = _write_execution_evidence(base, evidence_dir, results)

    if args.format == "json":
        rendered = json.dumps(payload, indent=2) + "\n"
    elif args.format == "markdown":
        lines = [
            "# Day 15 GitHub Actions quickstart",
            "",
            f"- Page: `{_PAGE_PATH}`",
            f"- Variant: `{args.variant}`",
            f"- Score: **{score}** ({passed}/{total})",
        ]
        if missing:
            lines.append("- Missing:")
            lines.extend(f"  - `{item}`" for item in missing)
        else:
            lines.append("- Missing: none \u2705")

        lines.extend(
            [
                "",
                "## Commands",
                "",
                "```bash",
                "sdetkit github-actions-quickstart --format text --strict",
                "sdetkit github-actions-quickstart --format json --variant strict --strict",
                "sdetkit github-actions-quickstart --emit-pack-dir docs/artifacts/day15-github-pack --format json --strict",
                "sdetkit github-actions-quickstart --execute --evidence-dir docs/artifacts/day15-github-pack/evidence --format json --strict",
                "```",
            ]
        )
        rendered = "\n".join(lines) + "\n"
    else:
        rendered = (
            "Day 15 GitHub Actions quickstart\n"
            f"page: {_PAGE_PATH}\n"
            f"variant: {args.variant}\n"
            f"score: {score} ({passed}/{total})\n"
            f"missing checks: {len(missing)}\n"
        )

    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")

    if args.strict and (missing or execution_failed):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
