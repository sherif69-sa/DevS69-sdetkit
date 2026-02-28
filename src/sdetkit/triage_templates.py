from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

_TEMPLATE_PATHS = {
    "bug": Path(".github/ISSUE_TEMPLATE/bug_report.yml"),
    "feature": Path(".github/ISSUE_TEMPLATE/feature_request.yml"),
    "pr": Path(".github/PULL_REQUEST_TEMPLATE.md"),
    "config": Path(".github/ISSUE_TEMPLATE/config.yml"),
}

_BUG_REQUIRED_IDS = {
    "severity",
    "impact",
    "expected-behavior",
    "actual-behavior",
    "reproduce",
    "env",
}
_FEATURE_REQUIRED_IDS = {
    "problem-statement",
    "proposed-solution",
    "acceptance-criteria",
    "priority",
    "ownership",
}
_PR_REQUIRED_HEADINGS = {
    "## summary",
    "## why",
    "## how",
    "## risk assessment",
    "## test evidence",
    "## rollback plan",
}
_CONFIG_REQUIRED_TOKENS = {
    "blank_issues_enabled:",
    "contact_links:",
    "security report",
    "questions / discussion",
}

_DEFAULT_BUG_TEMPLATE = """name: Bug report
description: Report a bug or regression
title: "[Bug]: "
labels: ["bug", "needs-triage"]
body:
  - type: markdown
    attributes:
      value: |
        Thanks for taking the time to report a bug. Please include enough detail for maintainers to reproduce and triage in one pass.

  - type: dropdown
    id: severity
    attributes:
      label: Severity
      description: How severe is this bug?
      options:
        - sev-1 (blocks release / production outage)
        - sev-2 (major regression)
        - sev-3 (minor bug)
    validations:
      required: true

  - type: textarea
    id: impact
    attributes:
      label: User impact
      description: Who is affected and what workflow is blocked?
      placeholder: Describe the impact radius and urgency.
    validations:
      required: true

  - type: textarea
    id: expected-behavior
    attributes:
      label: Expected behavior
      description: What should have happened?
      placeholder: Describe expected behavior.
    validations:
      required: true

  - type: textarea
    id: actual-behavior
    attributes:
      label: Actual behavior
      description: What happened instead?
      placeholder: Include the observed result or failure.
    validations:
      required: true

  - type: textarea
    id: reproduce
    attributes:
      label: Steps to reproduce
      description: How can we reproduce it?
      placeholder: |
        1. ...
        2. ...
        3. ...
    validations:
      required: true

  - type: textarea
    id: env
    attributes:
      label: Environment
      description: OS, Python version, sdetkit version, and anything relevant.
      placeholder: |
        - OS:
        - Python:
        - sdetkit:
        - CI runner (if any):
    validations:
      required: true
"""

_DEFAULT_FEATURE_TEMPLATE = """name: Feature request
description: Suggest an idea or improvement
title: "[Feature]: "
labels: ["enhancement", "needs-triage"]
body:
  - type: textarea
    id: problem-statement
    attributes:
      label: Problem statement
      description: What problem are you trying to solve?
    validations:
      required: true

  - type: textarea
    id: proposed-solution
    attributes:
      label: Proposed solution
      description: What would you like to see?
    validations:
      required: true

  - type: textarea
    id: acceptance-criteria
    attributes:
      label: Acceptance criteria
      description: List objective conditions for done.
      placeholder: |
        - [ ] Command/UX behavior is documented.
        - [ ] Tests cover the primary and error path.
        - [ ] Backward compatibility is maintained or migration notes are provided.
    validations:
      required: true

  - type: dropdown
    id: priority
    attributes:
      label: Priority
      options:
        - P0 (critical)
        - P1 (high)
        - P2 (normal)
        - P3 (nice-to-have)
    validations:
      required: true

  - type: input
    id: ownership
    attributes:
      label: Ownership
      description: Who will own or sponsor this request?
      placeholder: "@username or team"
    validations:
      required: true

  - type: textarea
    id: alternatives
    attributes:
      label: Alternatives considered
      description: Any alternatives you've considered?
    validations:
      required: false
"""

_DEFAULT_PR_TEMPLATE = """## Summary
-

## Why
-

## How
-

## Risk assessment
- Risk level: low / medium / high
- Primary risk area:

## Test evidence
- Commands run:
  - `python -m pytest -q ...`
- Attach key output snippets/artifacts:

## Rollback plan
- If this causes regressions, revert commit(s):
- Mitigation while rollback executes:

## Triage and ownership
- Reviewer owner:
- Target merge window:

## Checklist
- [ ] Tests added/updated
- [ ] `bash ci.sh` passes
- [ ] `bash quality.sh` passes
- [ ] Docs updated (if needed)
- [ ] Issue links / acceptance criteria mapped

- [ ] Premium guideline reference reviewed: `docs/premium-quality-gate.md`
"""

_DEFAULT_ISSUE_CONFIG = """blank_issues_enabled: false
contact_links:
  - name: Security report
    url: https://github.com/sherif69-sa/DevS69-sdetkit/security/policy
    about: Report vulnerabilities privately following SECURITY.md guidance.
  - name: Questions / discussion
    url: https://github.com/sherif69-sa/DevS69-sdetkit/discussions
    about: Please ask and answer questions here.
"""


def _extract_yaml_ids(text: str) -> set[str]:
    ids: set[str] = set()
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("id:"):
            ids.add(stripped.split(":", 1)[1].strip())
    return ids


def _compute_missing(actual: set[str], expected: set[str]) -> list[str]:
    return sorted(expected - actual)


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _template_result(name: str, path: Path, missing: list[str], total: int) -> dict[str, Any]:
    passed = total - len(missing)
    return {
        "name": name,
        "path": str(path),
        "ok": not missing,
        "coverage": f"{passed}/{total}",
        "missing": missing,
    }


def build_template_health(root: str = ".") -> dict[str, Any]:
    base = Path(root)

    bug_text = _read(base / _TEMPLATE_PATHS["bug"])
    feature_text = _read(base / _TEMPLATE_PATHS["feature"])
    pr_text = _read(base / _TEMPLATE_PATHS["pr"])
    cfg_text = _read(base / _TEMPLATE_PATHS["config"])

    bug_missing = _compute_missing(_extract_yaml_ids(bug_text), _BUG_REQUIRED_IDS)
    feature_missing = _compute_missing(_extract_yaml_ids(feature_text), _FEATURE_REQUIRED_IDS)

    pr_lower = pr_text.lower()
    pr_missing = sorted(h for h in _PR_REQUIRED_HEADINGS if h not in pr_lower)

    cfg_lower = cfg_text.lower()
    cfg_missing = sorted(token for token in _CONFIG_REQUIRED_TOKENS if token not in cfg_lower)

    templates = [
        _template_result("bug", _TEMPLATE_PATHS["bug"], bug_missing, len(_BUG_REQUIRED_IDS)),
        _template_result(
            "feature", _TEMPLATE_PATHS["feature"], feature_missing, len(_FEATURE_REQUIRED_IDS)
        ),
        _template_result("pr", _TEMPLATE_PATHS["pr"], pr_missing, len(_PR_REQUIRED_HEADINGS)),
        _template_result(
            "config", _TEMPLATE_PATHS["config"], cfg_missing, len(_CONFIG_REQUIRED_TOKENS)
        ),
    ]

    total_checks = sum(int(item["coverage"].split("/")[1]) for item in templates)
    passed_checks = sum(int(item["coverage"].split("/")[0]) for item in templates)
    score = round((passed_checks / total_checks) * 100, 1) if total_checks else 0.0

    return {
        "name": "day9-contribution-templates",
        "score": score,
        "total_checks": total_checks,
        "passed_checks": passed_checks,
        "templates": templates,
        "triage_sla": {
            "new_issue_first_response": "< 24h",
            "bug_repro_confirmation": "< 48h",
            "first_pr_review": "< 48h",
        },
        "actions": {
            "write_defaults": "sdetkit triage-templates --write-defaults",
            "validate_strict": "sdetkit triage-templates --format json --strict",
        },
    }


def write_default_templates(root: str = ".") -> list[str]:
    base = Path(root)
    writes = {
        _TEMPLATE_PATHS["bug"]: _DEFAULT_BUG_TEMPLATE,
        _TEMPLATE_PATHS["feature"]: _DEFAULT_FEATURE_TEMPLATE,
        _TEMPLATE_PATHS["pr"]: _DEFAULT_PR_TEMPLATE,
        _TEMPLATE_PATHS["config"]: _DEFAULT_ISSUE_CONFIG,
    }
    touched: list[str] = []
    for rel, body in writes.items():
        target = base / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
        touched.append(str(rel))
    return touched


def _render_text(payload: dict[str, Any]) -> str:
    lines = [
        "Day 9 contribution templates health",
        f"score: {payload['score']} ({payload['passed_checks']}/{payload['total_checks']})",
        "",
    ]
    for template in payload["templates"]:
        mark = "\u2705" if template["ok"] else "\u274c"
        lines.append(f"{mark} [{template['name']}] {template['coverage']} :: {template['path']}")
        if template["missing"]:
            for item in template["missing"]:
                lines.append(f"  - missing: {item}")
        lines.append("")
    lines.extend(
        [
            "triage SLA targets:",
            f"- new issue first response: {payload['triage_sla']['new_issue_first_response']}",
            f"- bug repro confirmation: {payload['triage_sla']['bug_repro_confirmation']}",
            f"- first PR review: {payload['triage_sla']['first_pr_review']}",
            "",
            "recommended actions:",
            f"- write defaults: {payload['actions']['write_defaults']}",
            f"- strict validation: {payload['actions']['validate_strict']}",
            "",
        ]
    )
    return "\n".join(lines)


def _render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Day 9 contribution templates health",
        "",
        f"- Score: **{payload['score']}** ({payload['passed_checks']}/{payload['total_checks']})",
        "",
        "| Template | Coverage | Status | Path |",
        "| --- | --- | --- | --- |",
    ]
    for template in payload["templates"]:
        status = "ok" if template["ok"] else "needs-fix"
        lines.append(
            f"| `{template['name']}` | {template['coverage']} | `{status}` | `{template['path']}` |"
        )

    lines.extend(["", "## Missing checks", ""])
    for template in payload["templates"]:
        missing = template["missing"]
        if not missing:
            lines.append(f"- `{template['name']}`: none")
        else:
            lines.append(f"- `{template['name']}`: " + ", ".join(f"`{m}`" for m in missing))

    lines.extend(["", "## Triage SLA targets", ""])
    for key, value in payload["triage_sla"].items():
        lines.append(f"- `{key}`: {value}")

    lines.extend(["", "## Recovery actions", ""])
    lines.append(f"- `{payload['actions']['write_defaults']}`")
    lines.append(f"- `{payload['actions']['validate_strict']}`")
    lines.append("")
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sdetkit triage-templates",
        description="Run Day 9 contribution template triage checks.",
    )
    p.add_argument("--format", choices=["text", "markdown", "json"], default="text")
    p.add_argument("--root", default=".", help="Repository root to inspect.")
    p.add_argument("--output", default="", help="Optional output file path.")
    p.add_argument(
        "--strict", action="store_true", help="Return non-zero if any requirement is missing."
    )
    p.add_argument(
        "--write-defaults",
        action="store_true",
        help="Write hardened default bug/feature/pr/config templates before reporting.",
    )
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(list(argv) if argv is not None else None)

    touched: list[str] = []
    if args.write_defaults:
        touched = write_default_templates(args.root)

    payload = build_template_health(args.root)
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
