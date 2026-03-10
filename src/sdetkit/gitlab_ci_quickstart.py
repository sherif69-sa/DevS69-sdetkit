from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

_PAGE_PATH = "docs/integrations-gitlab-ci-quickstart.md"

_SECTION_HEADER = "# GitLab CI quickstart (Day 16)"
_REQUIRED_SECTIONS = [
    "## Who this recipe is for",
    "## 5-minute setup",
    "## Minimal pipeline",
    "## Strict pipeline variant",
    "## Nightly reliability variant",
    "## Fast verification commands",
    "## Multi-channel distribution loop",
    "## Failure recovery playbook",
    "## Rollout checklist",
]

_REQUIRED_COMMANDS = [
    "python -m sdetkit doctor --format text",
    "python -m sdetkit repo audit --format json",
    "python -m pytest -q tests/test_gitlab_ci_quickstart.py tests/test_cli_help_lists_subcommands.py",
    "python scripts/check_day16_gitlab_ci_quickstart_contract.py",
    "python -m sdetkit gitlab-ci-quickstart --variant strict --bootstrap-pipeline --pipeline-path .gitlab-ci.yml --format json --strict",
    "python -m sdetkit gitlab-ci-quickstart --execute --evidence-dir docs/artifacts/day16-gitlab-pack/evidence --format json --strict",
]


def _pipeline_content(variant: str) -> str:
    if variant == "strict":
        return """stages:
  - quality

variables:
  PIP_DISABLE_PIP_VERSION_CHECK: "1"

strict-gate:
  stage: quality
  image: python:3.11
  script:
    - python -m pip install -r requirements-test.txt -e .
    - python -m pytest -q tests/test_cli_sdetkit.py tests/test_gitlab_ci_quickstart.py tests/test_cli_help_lists_subcommands.py
    - python -m sdetkit gitlab-ci-quickstart --format json --strict
    - python scripts/check_day16_gitlab_ci_quickstart_contract.py
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_PIPELINE_SOURCE == "web"
"""

    if variant == "nightly":
        return """stages:
  - nightly

variables:
  PIP_DISABLE_PIP_VERSION_CHECK: "1"

nightly-audit:
  stage: nightly
  image: python:3.11
  script:
    - python -m pip install -r requirements-test.txt -e .
    - python -m sdetkit doctor --format text
    - python -m sdetkit repo audit --format json
    - python -m sdetkit gitlab-ci-quickstart --execute --evidence-dir docs/artifacts/day16-gitlab-pack/evidence --format json --strict
  rules:
    - if: $CI_PIPELINE_SOURCE == "schedule"
    - if: $CI_PIPELINE_SOURCE == "web"
"""

    return """stages:
  - quality

variables:
  PIP_DISABLE_PIP_VERSION_CHECK: "1"

quickstart-gate:
  stage: quality
  image: python:3.11
  script:
    - python -m pip install -r requirements-test.txt -e .
    - python -m sdetkit gitlab-ci-quickstart --format json --strict
    - python -m pytest -q tests/test_cli_sdetkit.py tests/test_gitlab_ci_quickstart.py
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_PIPELINE_SOURCE == "web"
"""


_DAY16_DEFAULT_PAGE = f"""# GitLab CI quickstart (Day 16)

A production-ready integration recipe to run `sdetkit` quality checks in GitLab CI with quickstart, strict, and nightly variants.

## Who this recipe is for

- Maintainers who need CI guardrails in less than 5 minutes.
- Teams migrating from ad-hoc local checks into merge request quality gates.
- Contributors who want deterministic quality signals in merge request pipelines.

## 5-minute setup

1. Add `.gitlab-ci.yml` using the minimal pipeline below.
2. Open a merge request to trigger the quality gate.
3. Confirm the quickstart-gate job passes before merge.

## Minimal pipeline

```yaml
{_pipeline_content("minimal").rstrip()}
```

## Strict pipeline variant

```yaml
{_pipeline_content("strict").rstrip()}
```

## Nightly reliability variant

```yaml
{_pipeline_content("nightly").rstrip()}
```

## Fast verification commands

Run these locally before opening merge requests:

```bash
python -m sdetkit doctor --format text
python -m sdetkit repo audit --format json
python -m pytest -q tests/test_gitlab_ci_quickstart.py tests/test_cli_help_lists_subcommands.py
python scripts/check_day16_gitlab_ci_quickstart_contract.py
python -m sdetkit gitlab-ci-quickstart --variant strict --bootstrap-pipeline --pipeline-path .gitlab-ci.yml --format json --strict
python -m sdetkit gitlab-ci-quickstart --execute --evidence-dir docs/artifacts/day16-gitlab-pack/evidence --format json --strict
```

## Multi-channel distribution loop

1. Share merged `.gitlab-ci.yml` updates in engineering chat with before/after timing.
2. Publish docs updates in `docs/index.md` weekly rollout section.
3. Attach one artifact (`day16-execution-summary.json`) in retro for adoption tracking.

## Failure recovery playbook

- If checks fail because docs content drifted, run `--write-defaults` then rerun strict mode.
- If tests fail, keep strict gate required and move nightly lane to diagnostics-only until stable.
- If flaky behavior appears, attach evidence logs from `--execute --evidence-dir` to incident notes.

## Rollout checklist

- [ ] Pipeline runs for merge requests and manual dispatches.
- [ ] CI installs from `requirements-test.txt` and editable package source.
- [ ] Day 16 contract check is part of docs validation.
- [ ] Execution evidence bundle is generated weekly.
- [ ] Team channel has a pinned link to this quickstart page.
"""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sdetkit gitlab-ci-quickstart",
        description="Render and validate a GitLab CI quickstart report.",
    )
    parser.add_argument(
        "--format",
        choices=["text", "markdown", "json"],
        default="text",
        help="Output format.",
    )
    parser.add_argument("--root", default=".", help="Repository root where docs live.")
    parser.add_argument(
        "--output",
        default="",
        help="Optional file path to also write the rendered GitLab CI quickstart report.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero when required quickstart content is missing.",
    )
    parser.add_argument(
        "--write-defaults",
        action="store_true",
        help="Write or repair the GitLab CI quickstart page before validation.",
    )
    parser.add_argument(
        "--emit-pack-dir",
        default="",
        help="Optional directory to also write the GitLab CI quickstart pack.",
    )
    parser.add_argument(
        "--variant",
        choices=["minimal", "strict", "nightly"],
        default="minimal",
        help="Pipeline variant to render in the report.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Run the required GitLab CI command sequence and capture pass/fail details.",
    )
    parser.add_argument(
        "--bootstrap-pipeline",
        action="store_true",
        help="Write the selected pipeline variant to --pipeline-path.",
    )
    parser.add_argument(
        "--pipeline-path",
        default=".gitlab-ci.yml",
        help="Pipeline file path to write when using --bootstrap-pipeline.",
    )
    parser.add_argument(
        "--evidence-dir",
        default="",
        help="Optional directory to also write execution summary JSON and command logs.",
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
        "quickstart-gate:",
        "strict-gate:",
        "nightly-audit:",
    ]
    return [item for item in checks if item not in page_text]


def _write_defaults(base: Path) -> list[str]:
    page = base / _PAGE_PATH
    current = _read(page)
    if current and not _missing_checks(current):
        return []

    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(_DAY16_DEFAULT_PAGE, encoding="utf-8")
    return [_PAGE_PATH]


def _emit_pack(base: Path, out_dir: str) -> list[str]:
    root = base / out_dir
    root.mkdir(parents=True, exist_ok=True)

    checklist = root / "day16-gitlab-checklist.md"
    checklist.write_text(
        "\n".join(
            [
                "# Day 16 GitLab CI rollout checklist",
                "",
                "- [ ] Validate quickstart page in strict mode.",
                "- [ ] Commit `.gitlab-ci.yml` updates with staged variants.",
                "- [ ] Verify merge request pipeline passes doctor, repo audit, and tests.",
                "- [ ] Generate evidence bundle from --execute mode.",
                "- [ ] Share pipeline + evidence links in onboarding docs.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    minimal_pipeline = root / "day16-sdetkit-quickstart.yml"
    minimal_pipeline.write_text(_pipeline_content("minimal"), encoding="utf-8")

    strict_pipeline = root / "day16-sdetkit-strict.yml"
    strict_pipeline.write_text(_pipeline_content("strict"), encoding="utf-8")

    nightly_pipeline = root / "day16-sdetkit-nightly.yml"
    nightly_pipeline.write_text(_pipeline_content("nightly"), encoding="utf-8")

    distribution_plan = root / "day16-distribution-plan.md"
    distribution_plan.write_text(
        "\n".join(
            [
                "# Day 16 distribution plan",
                "",
                "| Channel | Artifact | Owner | Cadence |",
                "| --- | --- | --- | --- |",
                "| Engineering Slack | `.gitlab-ci.yml` quickstart + evidence summary | QE lead | weekly |",
                "| Docs portal | Day 16 integration page | Docs owner | weekly |",
                "| Sprint retro | evidence logs and failure themes | Team lead | bi-weekly |",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    validation = root / "day16-validation-commands.md"
    validation.write_text(
        "\n".join(["# Day 16 validation commands", "", "```bash", *_REQUIRED_COMMANDS, "```", ""])
        + "\n",
        encoding="utf-8",
    )

    return [
        str(path.relative_to(base))
        for path in (
            checklist,
            minimal_pipeline,
            strict_pipeline,
            nightly_pipeline,
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

    summary = root / "day16-execution-summary.json"
    payload = {
        "name": "day16-gitlab-ci-execution",
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
    text = _read(base / _PAGE_PATH)

    checks = [
        _SECTION_HEADER,
        *_REQUIRED_SECTIONS,
        *_REQUIRED_COMMANDS,
        "quickstart-gate:",
        "strict-gate:",
        "nightly-audit:",
    ]
    missing = _missing_checks(text)
    total = len(checks)
    passed = total - len(missing)
    score = round((passed / total) * 100, 1)

    payload: dict[str, Any] = {
        "name": "day16-gitlab-ci-quickstart",
        "page": _PAGE_PATH,
        "variant": args.variant,
        "selected_pipeline": _pipeline_content(args.variant),
        "required_sections": list(_REQUIRED_SECTIONS),
        "required_commands": list(_REQUIRED_COMMANDS),
        "passed_checks": passed,
        "total_checks": total,
        "score": score,
        "missing": missing,
        "touched_files": touched,
        "actions": {
            "open_page": _PAGE_PATH,
            "validate": "sdetkit gitlab-ci-quickstart --format json --strict",
            "validate_strict_variant": "sdetkit gitlab-ci-quickstart --format json --variant strict --strict",
            "write_defaults": "sdetkit gitlab-ci-quickstart --write-defaults --format json --strict",
            "artifact": "sdetkit gitlab-ci-quickstart --format markdown --variant strict --output docs/artifacts/day16-gitlab-ci-quickstart-sample.md",
            "emit_pack": "sdetkit gitlab-ci-quickstart --emit-pack-dir docs/artifacts/day16-gitlab-pack --format json --strict",
            "bootstrap_pipeline": "sdetkit gitlab-ci-quickstart --variant strict --bootstrap-pipeline --pipeline-path .gitlab-ci.yml --format json --strict",
            "execute": "sdetkit gitlab-ci-quickstart --execute --evidence-dir docs/artifacts/day16-gitlab-pack/evidence --format json --strict",
        },
    }

    if args.emit_pack_dir:
        payload["pack_files"] = _emit_pack(base, args.emit_pack_dir)

    if args.bootstrap_pipeline:
        pipeline_target = (base / args.pipeline_path).resolve()
        pipeline_target.parent.mkdir(parents=True, exist_ok=True)
        pipeline_target.write_text(_pipeline_content(args.variant), encoding="utf-8")
        rel = (
            str(pipeline_target.relative_to(base))
            if pipeline_target.is_relative_to(base)
            else str(pipeline_target)
        )
        touched.append(rel)
        payload["bootstrapped_pipeline"] = rel

    execution_failed = False
    if args.execute:
        commands = [
            "python -m sdetkit doctor --format text",
            "python -m sdetkit repo audit --format json",
            "python -m pytest -q tests/test_gitlab_ci_quickstart.py tests/test_cli_help_lists_subcommands.py",
            "python -m sdetkit gitlab-ci-quickstart --format json --strict",
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

        evidence_dir = args.evidence_dir or "docs/artifacts/day16-gitlab-pack/evidence"
        payload["evidence_files"] = _write_execution_evidence(base, evidence_dir, results)

    if args.format == "json":
        rendered = json.dumps(payload, indent=2) + "\n"
    elif args.format == "markdown":
        lines = [
            "# GitLab CI quickstart report",
            "",
            f"- Score: **{payload['score']}** ({payload['passed_checks']}/{payload['total_checks']})",
            f"- Page: `{payload['page']}`",
            f"- Variant: `{payload['variant']}`",
            "",
            "## Required sections",
            "",
        ]
        for item in payload["required_sections"]:
            lines.append(f"- `{item}`")
        lines.extend(["", "## Required commands", "", "```bash"])
        lines.extend(payload["required_commands"])
        lines.extend(["```", "", "## Selected pipeline", "", "```yaml"])
        lines.extend(str(payload["selected_pipeline"]).rstrip().splitlines())
        lines.extend(["```"])
        if payload.get("bootstrapped_pipeline"):
            lines.extend(["", "## Bootstrapped pipeline", ""])
            lines.append(f"- `{payload['bootstrapped_pipeline']}`")
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
        lines.extend(["", "## Quickstart coverage gaps", ""])
        if payload["missing"]:
            for item in payload["missing"]:
                lines.append(f"- `{item}`")
        else:
            lines.append("- none")
        lines.extend(["", "## Actions", ""])
        lines.append(f"- Open page: `{payload['actions']['open_page']}`")
        lines.append(f"- Validate: `{payload['actions']['validate']}`")
        lines.append(
            f"- Validate strict variant: `{payload['actions']['validate_strict_variant']}`"
        )
        lines.append(f"- Write defaults: `{payload['actions']['write_defaults']}`")
        lines.append(f"- Export artifact: `{payload['actions']['artifact']}`")
        lines.append(f"- Emit pack: `{payload['actions']['emit_pack']}`")
        lines.append(f"- Bootstrap pipeline: `{payload['actions']['bootstrap_pipeline']}`")
        lines.append(f"- Execute: `{payload['actions']['execute']}`")
        rendered = "\n".join(lines) + "\n"
    else:
        lines = [
            "GitLab CI quickstart report",
            f"Score: {payload['score']} ({payload['passed_checks']}/{payload['total_checks']})",
            "",
            f"Page: {payload['page']}",
            f"Variant: {payload['variant']}",
            "",
            "Required sections:",
        ]
        for idx, item in enumerate(payload["required_sections"], start=1):
            lines.append(f"{idx}. {item}")
        lines.extend(["", "Required commands:"])
        for cmd in payload["required_commands"]:
            lines.append(f"- {cmd}")
        lines.extend(["", "Selected pipeline:", ""])
        lines.extend(str(payload["selected_pipeline"]).rstrip().splitlines())
        if payload.get("bootstrapped_pipeline"):
            lines.extend(["", f"Bootstrapped pipeline: {payload['bootstrapped_pipeline']}"])
        if payload.get("execution"):
            exec_data = payload["execution"]
            lines.extend(["", "Execution summary:"])
            lines.append(f"- Passed: {exec_data['passed_commands']}/{exec_data['total_commands']}")
            lines.append(f"- Failed: {exec_data['failed_commands']}")
        if payload.get("evidence_files"):
            lines.extend(["", "Evidence files:"])
            for item in payload["evidence_files"]:
                lines.append(f"- {item}")
        if payload.get("pack_files"):
            lines.extend(["", "Emitted pack files:"])
            for item in payload["pack_files"]:
                lines.append(f"- {item}")
        if payload["missing"]:
            lines.extend(["", "Quickstart coverage gaps:"])
            for item in payload["missing"]:
                lines.append(f"- {item}")
        else:
            lines.extend(["", "Quickstart coverage gaps: none"])
        lines.extend(["", "Actions:"])
        lines.append(f"- Open page: {payload['actions']['open_page']}")
        lines.append(f"- Validate: {payload['actions']['validate']}")
        lines.append(f"- Validate strict variant: {payload['actions']['validate_strict_variant']}")
        lines.append(f"- Write defaults: {payload['actions']['write_defaults']}")
        lines.append(f"- Export artifact: {payload['actions']['artifact']}")
        lines.append(f"- Emit pack: {payload['actions']['emit_pack']}")
        lines.append(f"- Bootstrap pipeline: {payload['actions']['bootstrap_pipeline']}")
        lines.append(f"- Execute: {payload['actions']['execute']}")
        rendered = "\n".join(lines) + "\n"

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")

    if args.strict and (missing or execution_failed):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
