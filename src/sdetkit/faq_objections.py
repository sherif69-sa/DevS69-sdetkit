from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-faq-objections.md"

_SECTION_HEADER = "# FAQ and objections (Day 23)"
_REQUIRED_SECTIONS = [
    "## Who should run Day 23",
    "## When to use sdetkit",
    "## When not to use sdetkit",
    "## Top objections and responses",
    "## Fast verification commands",
    "## Escalation and rollout policy",
]

_REQUIRED_COMMANDS = [
    "python -m sdetkit faq-objections --format json --strict",
    "python -m sdetkit faq-objections --emit-pack-dir docs/artifacts/day23-faq-pack --format json --strict",
    "python -m sdetkit faq-objections --execute --evidence-dir docs/artifacts/day23-faq-pack/evidence --format json --strict",
    "python scripts/check_day23_faq_objections_contract.py",
]

_EXECUTION_COMMANDS = [
    "python -m sdetkit faq-objections --format json --strict",
    "python -m sdetkit faq-objections --emit-pack-dir docs/artifacts/day23-faq-pack --format json --strict",
    "python scripts/check_day23_faq_objections_contract.py --skip-evidence",
]

_DAY23_DEFAULT_PAGE = """# FAQ and objections (Day 23)

Day 23 turns recurring adoption blockers into deterministic answers that teams can validate before launches.

## Who should run Day 23

- Maintainers preparing public launch narratives and onboarding material.
- Developer advocates collecting recurring objections from discussions/issues.
- Platform leads deciding whether to standardize on sdetkit workflows.

## When to use sdetkit

Use sdetkit when you need deterministic, CLI-first quality and reliability workflows for CI and local checks.

- You want reproducible diagnostics and policy checks for contributors.
- You need artifact-driven evidence packs for leadership or compliance reviews.
- You want one command lane that scales from startup teams to regulated enterprise contexts.

## When not to use sdetkit

Avoid sdetkit as a first step if your team only needs one-off scripts and no governance evidence.

- You do not maintain a shared CI pipeline.
- You are not ready to enforce basic quality and security gates.
- You only need ad-hoc local checks without repeatability requirements.

## Top objections and responses

### Objection 1: "This looks heavy for small teams"

Response: start with `doctor`, `repo audit`, and `security gate` only. Expand to governance packs later.

### Objection 2: "We already have scripts"

Response: sdetkit provides deterministic contracts, evidence artifacts, and strict gates that ad-hoc scripts usually lack.

### Objection 3: "How do we prove this is production-ready?"

Response: run strict mode, emit a Day 23 FAQ pack, and attach execution logs as evidence in release reviews.

## Fast verification commands

```bash
python -m sdetkit faq-objections --format json --strict
python -m sdetkit faq-objections --emit-pack-dir docs/artifacts/day23-faq-pack --format json --strict
python -m sdetkit faq-objections --execute --evidence-dir docs/artifacts/day23-faq-pack/evidence --format json --strict
python scripts/check_day23_faq_objections_contract.py
```

## Escalation and rollout policy

- If strict mode fails, pause launch messaging and assign owners for missing FAQ guidance.
- If objections repeat for two sprints, add dedicated docs links and command examples.
- Require Day 23 pack attachment in release-readiness review for external promotions.
"""

_SIGNALS = [
    {
        "check_id": "docs_page_exists",
        "category": "coverage",
        "weight": 15,
        "evaluator": "page_exists",
    },
    {
        "check_id": "required_sections_present",
        "category": "coverage",
        "weight": 20,
        "evaluator": "required_sections",
    },
    {
        "check_id": "command_block_complete",
        "category": "operational",
        "weight": 15,
        "evaluator": "required_commands",
    },
    {
        "check_id": "when_to_use_clarity",
        "category": "adoption",
        "weight": 10,
        "marker": "## When to use sdetkit",
    },
    {
        "check_id": "when_not_to_use_clarity",
        "category": "adoption",
        "weight": 10,
        "marker": "## When not to use sdetkit",
    },
    {
        "check_id": "objection_responses",
        "category": "adoption",
        "weight": 10,
        "marker": "## Top objections and responses",
    },
    {
        "check_id": "readme_day23_link",
        "category": "discoverability",
        "weight": 8,
        "marker": "docs/integrations-faq-objections.md",
        "source": "readme",
    },
    {
        "check_id": "docs_index_day23",
        "category": "discoverability",
        "weight": 7,
        "marker": "day-23-ultra-upgrade-report.md",
        "source": "docs_index",
    },
    {
        "check_id": "release_narrative_alignment",
        "category": "operational",
        "weight": 5,
        "marker": "release-narrative",
        "source": "readme",
    },
]

_CRITICAL_FAILURE_KEYS = {
    "docs_page_exists",
    "required_sections_present",
    "command_block_complete",
    "when_to_use_clarity",
    "when_not_to_use_clarity",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _evaluate_signals(
    root: Path, page_text: str, readme_text: str, docs_index_text: str
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    page_path = root / _PAGE_PATH

    for signal in _SIGNALS:
        evaluator = signal.get("evaluator")
        key = str(signal["check_id"])

        if evaluator == "page_exists":
            passed = page_path.exists()
            evidence: Any = str(page_path)
        elif evaluator == "required_sections":
            missing = [section for section in _REQUIRED_SECTIONS if section not in page_text]
            passed = not missing
            evidence = {"missing_sections": missing}
        elif evaluator == "required_commands":
            missing = [command for command in _REQUIRED_COMMANDS if command not in page_text]
            passed = not missing
            evidence = {"missing_commands": missing}
        else:
            marker = signal.get("marker")
            marker_str = marker if isinstance(marker, str) else ""
            source = signal.get("source", "page")
            if source == "readme":
                corpus = readme_text
            elif source == "docs_index":
                corpus = docs_index_text
            else:
                corpus = page_text
            passed = bool(marker_str) and marker_str in corpus
            evidence = marker_str

        rows.append(
            {
                "check_id": key,
                "category": signal["category"],
                "weight": int(str(signal["weight"])),
                "passed": bool(passed),
                "evidence": evidence,
            }
        )

    return rows


def build_faq_objections_summary(
    root: Path,
    *,
    readme_path: str = "README.md",
    docs_index_path: str = "docs/index.md",
    docs_page_path: str = _PAGE_PATH,
) -> dict[str, Any]:
    page_text = _read(root / docs_page_path)
    readme_text = _read(root / readme_path)
    docs_index_text = _read(root / docs_index_path)
    checks = _evaluate_signals(root, page_text, readme_text, docs_index_text)

    total_weight = sum(int(item["weight"]) for item in checks)
    earned_weight = sum(int(item["weight"]) for item in checks if item["passed"])
    score = round((earned_weight / total_weight) * 100, 2) if total_weight else 0.0

    failed = [item for item in checks if not item["passed"]]
    critical_failures = [
        item["check_id"] for item in failed if item["check_id"] in _CRITICAL_FAILURE_KEYS
    ]

    by_category: dict[str, dict[str, int]] = {}
    for item in checks:
        category = str(item["category"])
        slot = by_category.setdefault(category, {"passed": 0, "total": 0})
        slot["total"] += 1
        if item["passed"]:
            slot["passed"] += 1

    recommendations: list[str] = []
    if any(item["category"] == "coverage" for item in failed):
        recommendations.append(
            "Restore the Day 23 FAQ docs contract sections and command lane before promotion."
        )
    if any(item["category"] == "adoption" for item in failed):
        recommendations.append(
            "Clarify when to use and when not to use sdetkit to reduce onboarding objections."
        )
    if any(item["category"] == "discoverability" for item in failed):
        recommendations.append(
            "Link the Day 23 FAQ guide from README and docs index for fast objection handling."
        )
    if not recommendations:
        recommendations.append(
            "FAQ objections lane is healthy; keep objections refreshed from real issue/discussion trends."
        )

    return {
        "name": "day23-faq-objections",
        "inputs": {
            "readme": readme_path,
            "docs_index": docs_index_path,
            "docs_page": docs_page_path,
        },
        "summary": {
            "faq_score": score,
            "objection_readiness": "strong" if score >= 90 and not critical_failures else "review",
            "weighted_points": {"earned": earned_weight, "total": total_weight},
            "category_coverage": by_category,
            "failed_checks": len(failed),
            "critical_failures": critical_failures,
        },
        "checks": checks,
        "recommendations": recommendations,
    }


def _render_text(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    points = summary["weighted_points"]
    lines = [
        "Day 23 FAQ objections",
        "",
        f"FAQ score: {summary['faq_score']}",
        f"Readiness: {summary['objection_readiness']}",
        f"Weighted points: {points['earned']}/{points['total']}",
        f"Failed checks: {summary['failed_checks']}",
    ]
    if summary["critical_failures"]:
        lines.append(f"Critical failures: {', '.join(summary['critical_failures'])}")
    lines.append("")
    lines.append("Checks:")
    for item in payload["checks"]:
        lines.append(
            f"- [{'x' if item['passed'] else ' '}] {item['check_id']} ({item['category']}, w={item['weight']})"
        )
    lines.append("")
    lines.append("Recommendations:")
    for rec in payload["recommendations"]:
        lines.append(f"- {rec}")
    return "\n".join(lines)


def _render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    points = summary["weighted_points"]
    lines = [
        "# Day 23 FAQ and objections summary",
        "",
        f"- FAQ score: **{summary['faq_score']}**",
        f"- Readiness: **{summary['objection_readiness']}**",
        f"- Weighted points: **{points['earned']}/{points['total']}**",
        f"- Failed checks: **{summary['failed_checks']}**",
        "",
        "## Checks",
        "",
        "| Check | Category | Weight | Status |",
        "| --- | --- | ---: | --- |",
    ]
    for item in payload["checks"]:
        status = "\u2705" if item["passed"] else "\u274c"
        lines.append(f"| `{item['check_id']}` | {item['category']} | {item['weight']} | {status} |")

    lines.extend(["", "## Recommendations", ""])
    for rec in payload["recommendations"]:
        lines.append(f"- {rec}")
    return "\n".join(lines)


def emit_pack(root: Path, out_dir: Path, payload: dict[str, Any]) -> list[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = out_dir / "day23-faq-summary.json"
    scorecard = out_dir / "day23-faq-scorecard.md"
    matrix = out_dir / "day23-objection-response-matrix.md"
    playbook = out_dir / "day23-adoption-playbook.md"
    validation = out_dir / "day23-validation-commands.md"

    summary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    scorecard.write_text(_render_markdown(payload) + "\n", encoding="utf-8")

    matrix_lines = [
        "# Day 23 objection response matrix",
        "",
        "| Objection | Response | Verification command |",
        "| --- | --- | --- |",
        "| This is too heavy for small teams | Start with doctor + repo + security lanes only. | `python -m sdetkit doctor --json` |",
        "| We already have scripts | Keep scripts, then enforce deterministic strict gates + artifacts with sdetkit. | `python -m sdetkit faq-objections --format json --strict` |",
        "| How do we prove readiness? | Emit Day 23 FAQ pack and attach evidence summary in release review. | `python -m sdetkit faq-objections --emit-pack-dir docs/artifacts/day23-faq-pack --format json --strict` |",
    ]
    matrix.write_text("\n".join(matrix_lines) + "\n", encoding="utf-8")

    playbook_lines = [
        "# Day 23 adoption objection playbook",
        "",
        "1. Collect objections from issues, PR reviews, and contributor onboarding notes.",
        "2. Map each objection to one deterministic command and one docs page.",
        "3. Run strict checks before launch posts or roadmap announcements.",
        "4. Attach day23-faq-summary.json and execution evidence in review threads.",
        "5. Revisit unresolved objections weekly and update this pack.",
    ]
    playbook.write_text("\n".join(playbook_lines) + "\n", encoding="utf-8")

    validation_lines = ["# Day 23 validation commands", "", "```bash", *_REQUIRED_COMMANDS, "```"]
    validation.write_text("\n".join(validation_lines) + "\n", encoding="utf-8")

    return [
        str(path.relative_to(root)) for path in [summary, scorecard, matrix, playbook, validation]
    ]


def execute_commands(root: Path, evidence_dir: Path, timeout_sec: int) -> dict[str, Any]:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []

    for command in _EXECUTION_COMMANDS:
        argv = shlex.split(command)
        if argv and argv[0] == "python":
            argv[0] = sys.executable
        proc = subprocess.run(
            argv,
            cwd=root,
            text=True,
            capture_output=True,
            timeout=timeout_sec,
        )
        results.append(
            {
                "command": command,
                "returncode": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            }
        )

    summary = evidence_dir / "day23-execution-summary.json"
    payload = {
        "name": "day23-faq-objections-execution",
        "total_commands": len(_EXECUTION_COMMANDS),
        "results": results,
    }
    summary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def _write_default_page(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_DAY23_DEFAULT_PAGE, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sdetkit faq-objections",
        description="Day 23 FAQ and objections lane for adoption blockers.",
    )
    parser.add_argument("--root", default=".", help="Repository root.")
    parser.add_argument("--readme", default="README.md", help="README path relative to root.")
    parser.add_argument(
        "--docs-index", default="docs/index.md", help="Docs index path relative to root."
    )
    parser.add_argument(
        "--docs-page",
        default=_PAGE_PATH,
        help="Day 23 FAQ page path relative to root.",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format.",
    )
    parser.add_argument("--output", default=None, help="Write rendered output to path.")
    parser.add_argument(
        "--write-defaults",
        action="store_true",
        help="Create/overwrite the Day 23 FAQ docs page with defaults.",
    )
    parser.add_argument("--strict", action="store_true", help="Fail if critical checks fail.")
    parser.add_argument(
        "--min-faq-score",
        type=float,
        default=85.0,
        help="Minimum score required in strict mode.",
    )
    parser.add_argument(
        "--emit-pack-dir",
        default=None,
        help="Emit Day 23 FAQ pack into this directory relative to root.",
    )
    parser.add_argument(
        "--execute", action="store_true", help="Execute deterministic Day 23 command chain."
    )
    parser.add_argument(
        "--evidence-dir",
        default="docs/artifacts/day23-faq-pack/evidence",
        help="Evidence directory for --execute.",
    )
    parser.add_argument(
        "--timeout-sec",
        type=int,
        default=180,
        help="Per-command timeout in seconds for --execute.",
    )
    return parser


def _strict_failures(payload: dict[str, Any], min_score: float) -> list[str]:
    summary = payload["summary"]
    failures: list[str] = []
    if summary["faq_score"] < min_score:
        failures.append(f"faq_score {summary['faq_score']} is below min-faq-score {min_score}")
    if summary["critical_failures"]:
        failures.append("critical failures: " + ", ".join(summary["critical_failures"]))
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(argv)

    root = Path(ns.root).resolve()
    docs_page = root / ns.docs_page

    if ns.write_defaults:
        _write_default_page(docs_page)

    payload = build_faq_objections_summary(
        root,
        readme_path=ns.readme,
        docs_index_path=ns.docs_index,
        docs_page_path=ns.docs_page,
    )

    if ns.emit_pack_dir:
        emitted = emit_pack(root, root / ns.emit_pack_dir, payload)
        payload["emitted_pack_files"] = emitted

    if ns.execute:
        execution = execute_commands(root, root / ns.evidence_dir, ns.timeout_sec)
        payload["execution"] = execution

    failures: list[str] = []
    if ns.strict:
        failures = _strict_failures(payload, ns.min_faq_score)
        payload["strict_failures"] = failures

    rendered = (
        json.dumps(payload, indent=2, sort_keys=True)
        if ns.format == "json"
        else _render_markdown(payload)
        if ns.format == "markdown"
        else _render_text(payload)
    )

    if ns.output:
        out = root / ns.output
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
