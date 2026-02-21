from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-community-activation.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_SECTION_HEADER = "# Community activation (Day 25)"
_REQUIRED_SECTIONS = [
    "## Who should run Day 25",
    "## Roadmap-voting discussion contract",
    "## Launch checklist",
    "## Feedback triage SLA",
    "## Activation scoring model",
    "## Execution evidence mode",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit community-activation --format json --strict",
    "python -m sdetkit community-activation --emit-pack-dir docs/artifacts/day25-community-pack --format json --strict",
    "python -m sdetkit community-activation --execute --evidence-dir docs/artifacts/day25-community-pack/evidence --format json --strict",
    "python scripts/check_day25_community_activation_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit community-activation --format json --strict",
    "python scripts/check_day25_community_activation_contract.py --skip-evidence",
]

_DAY25_DEFAULT_PAGE = """# Community activation (Day 25)

Day 25 converts passive roadmap readers into active contributors through a deterministic roadmap-voting and feedback loop.

## Who should run Day 25

- Maintainers preparing priorities for the next sprint or release train.
- DevRel/community managers collecting qualitative and quantitative roadmap feedback.
- Engineering leads that need transparent prioritization signals for backlog decisions.

## Roadmap-voting discussion contract

Day 25 is complete when a public roadmap-voting thread is opened, tagged, and linked from docs so contributors can vote and comment on priority items.

## Launch checklist

```bash
python -m sdetkit community-activation --format json --strict
python -m sdetkit community-activation --emit-pack-dir docs/artifacts/day25-community-pack --format json --strict
python -m sdetkit community-activation --execute --evidence-dir docs/artifacts/day25-community-pack/evidence --format json --strict
python scripts/check_day25_community_activation_contract.py
```

## Feedback triage SLA

- Triage new roadmap votes/comments within 48 hours.
- Label each item as `accepted`, `needs-info`, or `not-now`.
- Publish weekly summary of wins, blockers, and next actions.

## Activation scoring model

Day 25 computes weighted readiness score (0-100):

- Docs contract + command lane completeness: 45 points.
- Discoverability links in README/docs index: 25 points.
- Top-10 roadmap alignment marker coverage: 20 points.
- Evidence-lane readiness for strict validation: 10 points.

## Execution evidence mode

`--execute` runs deterministic Day 25 checks and writes logs to `--evidence-dir` for release review.
"""

_SIGNALS = [
    {"key": "docs_page_exists", "category": "contract", "weight": 15, "evaluator": "page_exists"},
    {
        "key": "required_sections_present",
        "category": "contract",
        "weight": 20,
        "evaluator": "required_sections",
    },
    {
        "key": "required_commands_present",
        "category": "contract",
        "weight": 10,
        "evaluator": "required_commands",
    },
    {
        "key": "readme_day25_link",
        "category": "discoverability",
        "weight": 10,
        "marker": "docs/integrations-community-activation.md",
        "source": "readme",
    },
    {
        "key": "readme_day25_command",
        "category": "discoverability",
        "weight": 8,
        "marker": "community-activation",
        "source": "readme",
    },
    {
        "key": "docs_index_day25_link",
        "category": "discoverability",
        "weight": 7,
        "marker": "day-25-ultra-upgrade-report.md",
        "source": "docs_index",
    },
    {
        "key": "top10_day25_alignment",
        "category": "strategy",
        "weight": 20,
        "marker": "Day 25 — Community activation",
        "source": "top10",
    },
    {
        "key": "docs_mentions_roadmap_voting",
        "category": "strategy",
        "weight": 10,
        "marker": "roadmap-voting",
        "source": "page",
    },
]

_CRITICAL_FAILURE_KEYS = {
    "docs_page_exists",
    "required_sections_present",
    "required_commands_present",
    "top10_day25_alignment",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _evaluate_signals(
    root: Path,
    *,
    page_text: str,
    readme_text: str,
    docs_index_text: str,
    top10_text: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    page_path = root / _PAGE_PATH

    for signal in _SIGNALS:
        evaluator = signal.get("evaluator")

        if evaluator == "page_exists":
            passed = page_path.exists()
            evidence: Any = str(page_path)
        elif evaluator == "required_sections":
            missing = [section for section in [_SECTION_HEADER, *_REQUIRED_SECTIONS] if section not in page_text]
            passed = not missing
            evidence = {"missing_sections": missing}
        elif evaluator == "required_commands":
            missing = [command for command in _REQUIRED_COMMANDS if command not in page_text]
            passed = not missing
            evidence = {"missing_commands": missing}
        else:
            marker = str(signal.get("marker", ""))
            source = str(signal.get("source", "page"))
            corpus = page_text
            if source == "readme":
                corpus = readme_text
            elif source == "docs_index":
                corpus = docs_index_text
            elif source == "top10":
                corpus = top10_text
            passed = bool(marker) and marker in corpus
            evidence = marker

        rows.append(
            {
                "key": str(signal["key"]),
                "category": str(signal["category"]),
                "weight": int(signal["weight"]),
                "passed": bool(passed),
                "evidence": evidence,
            }
        )

    return rows


def build_community_activation_summary(
    root: Path,
    *,
    readme_path: str = "README.md",
    docs_index_path: str = "docs/index.md",
    docs_page_path: str = _PAGE_PATH,
    top10_path: str = _TOP10_PATH,
) -> dict[str, Any]:
    page_text = _read(root / docs_page_path)
    readme_text = _read(root / readme_path)
    docs_index_text = _read(root / docs_index_path)
    top10_text = _read(root / top10_path)
    checks = _evaluate_signals(
        root,
        page_text=page_text,
        readme_text=readme_text,
        docs_index_text=docs_index_text,
        top10_text=top10_text,
    )

    total_weight = sum(int(item["weight"]) for item in checks)
    earned_weight = sum(int(item["weight"]) for item in checks if item["passed"])
    score = round((earned_weight / total_weight) * 100, 2) if total_weight else 0.0

    failed = [item for item in checks if not item["passed"]]
    critical_failures = [item["key"] for item in failed if item["key"] in _CRITICAL_FAILURE_KEYS]

    recommendations: list[str] = []
    if any(item["category"] == "contract" for item in failed):
        recommendations.append("Restore Day 25 docs contract sections and required command lane before launch.")
    if any(item["category"] == "discoverability" for item in failed):
        recommendations.append("Add Day 25 links and command snippets to README/docs index for contributor visibility.")
    if any(item["category"] == "strategy" for item in failed):
        recommendations.append("Align Day 25 outputs with top-10 roadmap activation objective and roadmap-voting messaging.")
    if not recommendations:
        recommendations.append("Day 25 community activation lane is healthy; keep weekly voting summaries flowing.")

    return {
        "name": "day25-community-activation",
        "inputs": {
            "readme": readme_path,
            "docs_index": docs_index_path,
            "docs_page": docs_page_path,
            "top10": top10_path,
        },
        "checks": checks,
        "summary": {
            "activation_score": score,
            "total_checks": len(checks),
            "failed_checks": [item["key"] for item in failed],
            "critical_failures": critical_failures,
            "recommendations": recommendations,
        },
    }


def _render_text(payload: dict[str, Any]) -> str:
    lines = [
        "Day 25 community activation summary",
        f"score={payload['summary']['activation_score']}",
        f"failed={','.join(payload['summary']['failed_checks']) or 'none'}",
        f"critical={','.join(payload['summary']['critical_failures']) or 'none'}",
        "",
        "Checks:",
    ]
    for item in payload["checks"]:
        lines.append(f"- [{'x' if item['passed'] else ' '}] {item['key']} ({item['category']}, w={item['weight']})")
    return "\n".join(lines)


def emit_pack(root: Path, out_dir: Path, payload: dict[str, Any]) -> list[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = out_dir / "day25-community-summary.json"
    scorecard = out_dir / "day25-community-scorecard.md"
    discussion = out_dir / "day25-roadmap-vote-discussion-template.md"
    triage = out_dir / "day25-feedback-triage-board.md"
    validation = out_dir / "day25-validation-commands.md"

    summary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    scorecard.write_text(_render_text(payload) + "\n", encoding="utf-8")
    discussion.write_text(
        "\n".join(
            [
                "# Day 25 roadmap-voting discussion template",
                "",
                "## Title",
                "Roadmap voting: help prioritize the next sdetkit upgrades",
                "",
                "## Prompt",
                "Vote on the top 3 roadmap items that would most improve your team workflow.",
                "",
                "## Candidate items",
                "1. CI integration accelerators",
                "2. Security and compliance automation",
                "3. Contributor onboarding improvements",
                "4. Release and communication tooling",
                "",
                "## Response format",
                "- Priority #1:",
                "- Priority #2:",
                "- Priority #3:",
                "- Optional context:",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    triage.write_text(
        "\n".join(
            [
                "# Day 25 feedback triage board",
                "",
                "| Feedback item | Votes | Owner | Status | Decision date |",
                "| --- | ---: | --- | --- | --- |",
                "| Example: Improve docs nav for first-time users | 0 | @owner | needs-info | YYYY-MM-DD |",
                "",
                "Triage SLA: respond within 48h and classify as `accepted`, `needs-info`, or `not-now`.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    validation.write_text(
        "\n".join(["# Day 25 validation commands", "", "```bash", *_REQUIRED_COMMANDS, "```"]) + "\n",
        encoding="utf-8",
    )

    return [str(path.relative_to(root)) for path in [summary, scorecard, discussion, triage, validation]]


def execute_commands(root: Path, evidence_dir: Path, timeout_sec: int) -> dict[str, Any]:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    for command in _EXECUTION_COMMANDS:
        proc = subprocess.run(
            shlex.split(command), cwd=root, text=True, capture_output=True, timeout=timeout_sec
        )
        results.append(
            {
                "command": command,
                "returncode": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            }
        )
    payload = {
        "name": "day25-community-activation-execution",
        "total_commands": len(_EXECUTION_COMMANDS),
        "results": results,
    }
    (evidence_dir / "day25-execution-summary.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sdetkit community-activation",
        description="Day 25 community activation and roadmap-voting closeout lane.",
    )
    parser.add_argument("--root", default=".", help="Repository root path.")
    parser.add_argument("--readme", default="README.md", help="README path for discoverability checks.")
    parser.add_argument("--docs-index", default="docs/index.md", help="Docs index path for discoverability checks.")
    parser.add_argument("--top10", default=_TOP10_PATH, help="Top-10 roadmap strategy path.")
    parser.add_argument("--write-defaults", action="store_true", help="Create default Day 25 integration page.")
    parser.add_argument("--emit-pack-dir", default="", help="Optional output directory for generated Day 25 files.")
    parser.add_argument("--execute", action="store_true", help="Run Day 25 command chain and emit evidence logs.")
    parser.add_argument(
        "--evidence-dir",
        default="docs/artifacts/day25-community-pack/evidence",
        help="Output directory for execution evidence logs.",
    )
    parser.add_argument("--timeout-sec", type=int, default=120, help="Per-command timeout used by --execute.")
    parser.add_argument("--min-score", type=float, default=90.0, help="Minimum score for strict pass.")
    parser.add_argument("--strict", action="store_true", help="Fail when score or critical checks are not ready.")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    return parser


def main(argv: list[str] | None = None) -> int:
    ns = build_parser().parse_args(argv)
    root = Path(ns.root).resolve()
    page = root / _PAGE_PATH

    if ns.write_defaults:
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(_DAY25_DEFAULT_PAGE, encoding="utf-8")

    payload = build_community_activation_summary(
        root,
        readme_path=ns.readme,
        docs_index_path=ns.docs_index,
        top10_path=ns.top10,
    )
    page_text = _read(page)
    missing_sections = [section for section in [_SECTION_HEADER, *_REQUIRED_SECTIONS] if section not in page_text]
    missing_commands = [command for command in _REQUIRED_COMMANDS if command not in page_text]
    payload["strict_failures"] = [*missing_sections, *missing_commands]

    if ns.emit_pack_dir:
        payload["emitted_pack_files"] = emit_pack(root, root / ns.emit_pack_dir, payload)
    if ns.execute:
        payload["execution"] = execute_commands(root, root / ns.evidence_dir, ns.timeout_sec)

    strict_failed = (
        bool(payload["strict_failures"])
        or payload["summary"]["activation_score"] < ns.min_score
        or bool(payload["summary"]["critical_failures"])
    )

    if ns.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(_render_text(payload))

    return 1 if ns.strict and strict_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
