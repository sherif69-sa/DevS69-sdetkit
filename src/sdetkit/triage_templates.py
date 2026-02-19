from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

_TEMPLATE_PATHS = {
    "bug": Path(".github/ISSUE_TEMPLATE/bug_report.yml"),
    "feature": Path(".github/ISSUE_TEMPLATE/feature_request.yml"),
    "pr": Path(".github/PULL_REQUEST_TEMPLATE.md"),
}

_TEMPLATE_REQUIREMENTS: dict[str, list[str]] = {
    "bug": [
        "severity",
        "impact",
        "steps to reproduce",
        "expected behavior",
        "actual behavior",
        "environment",
    ],
    "feature": [
        "problem statement",
        "proposed solution",
        "acceptance criteria",
        "priority",
        "ownership",
    ],
    "pr": [
        "summary",
        "why",
        "how",
        "risk",
        "test evidence",
        "rollback",
    ],
}


def _read_template(name: str) -> str:
    path = _TEMPLATE_PATHS[name]
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").lower()


def build_template_health() -> dict[str, object]:
    templates: list[dict[str, object]] = []
    total_checks = 0
    passed_checks = 0

    for name, required_tokens in _TEMPLATE_REQUIREMENTS.items():
        body = _read_template(name)
        checks: list[dict[str, object]] = []
        for token in required_tokens:
            ok = token in body
            checks.append({"token": token, "ok": ok})
            total_checks += 1
            if ok:
                passed_checks += 1
        templates.append(
            {
                "name": name,
                "path": str(_TEMPLATE_PATHS[name]),
                "coverage": f"{sum(1 for c in checks if c['ok'])}/{len(checks)}",
                "checks": checks,
            }
        )

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
    }


def _render_text(payload: dict[str, object]) -> str:
    lines = [
        "Day 9 contribution templates health",
        f"score: {payload['score']} ({payload['passed_checks']}/{payload['total_checks']})",
        "",
    ]
    for template in payload["templates"]:
        lines.append(f"[{template['name']}] {template['coverage']} :: {template['path']}")
        for check in template["checks"]:
            mark = "✅" if check["ok"] else "❌"
            lines.append(f"  {mark} {check['token']}")
        lines.append("")
    lines.extend(
        [
            "triage SLA targets:",
            f"- new issue first response: {payload['triage_sla']['new_issue_first_response']}",
            f"- bug repro confirmation: {payload['triage_sla']['bug_repro_confirmation']}",
            f"- first PR review: {payload['triage_sla']['first_pr_review']}",
            "",
        ]
    )
    return "\n".join(lines)


def _render_markdown(payload: dict[str, object]) -> str:
    lines = [
        "# Day 9 contribution templates health",
        "",
        f"- Score: **{payload['score']}** ({payload['passed_checks']}/{payload['total_checks']})",
        "",
        "| Template | Coverage | Path |",
        "| --- | --- | --- |",
    ]
    for template in payload["templates"]:
        lines.append(f"| `{template['name']}` | {template['coverage']} | `{template['path']}` |")
    lines.extend(["", "## Triage SLA targets", ""])
    for key, value in payload["triage_sla"].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Missing token checks", ""])
    for template in payload["templates"]:
        missing = [c["token"] for c in template["checks"] if not c["ok"]]
        if not missing:
            lines.append(f"- `{template['name']}`: none")
        else:
            lines.append(f"- `{template['name']}`: " + ", ".join(f"`{m}`" for m in missing))
    lines.append("")
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sdetkit triage-templates",
        description="Run Day 9 contribution template triage checks.",
    )
    p.add_argument("--format", choices=["text", "markdown", "json"], default="text")
    p.add_argument("--output", default="", help="Optional output file path.")
    p.add_argument("--strict", action="store_true", help="Return non-zero if any requirement is missing.")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(list(argv) if argv is not None else None)
    payload = build_template_health()

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
