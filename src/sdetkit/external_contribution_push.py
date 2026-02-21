from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-external-contribution-push.md"
_TOP10_PATH = "docs/top-10-github-strategy.md"
_SECTION_HEADER = "# External contribution push (Day 26)"
_REQUIRED_SECTIONS = [
    "## Who should run Day 26",
    "## Starter-task spotlight contract",
    "## Launch checklist",
    "## First-response SLA",
    "## Activation scoring model",
    "## Execution evidence mode",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit external-contribution-push --format json --strict",
    "python -m sdetkit external-contribution-push --emit-pack-dir docs/artifacts/day26-external-contribution-pack --format json --strict",
    "python -m sdetkit external-contribution-push --execute --evidence-dir docs/artifacts/day26-external-contribution-pack/evidence --format json --strict",
    "python scripts/check_day26_external_contribution_push_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit external-contribution-push --format json --strict",
    "python scripts/check_day26_external_contribution_push_contract.py --skip-evidence",
]

_DAY26_DEFAULT_PAGE = """# External contribution push (Day 26)

Day 26 upgrades public contribution pull by spotlighting starter tasks with clear owners, response SLAs, and evidence-ready follow-up.

## Who should run Day 26

- Maintainers who want more first-time external contributions from open starter tasks.
- DevRel/community owners who promote contributor-friendly backlog slices.
- Engineering leads that need deterministic response and conversion metrics.

## Starter-task spotlight contract

A Day 26 pass means at least 10 starter tasks are publicly spotlighted with labels, acceptance criteria, and explicit maintainer response windows.

## Launch checklist

```bash
python -m sdetkit external-contribution-push --format json --strict
python -m sdetkit external-contribution-push --emit-pack-dir docs/artifacts/day26-external-contribution-pack --format json --strict
python -m sdetkit external-contribution-push --execute --evidence-dir docs/artifacts/day26-external-contribution-pack/evidence --format json --strict
python scripts/check_day26_external_contribution_push_contract.py
```

## First-response SLA

- Respond to new external contribution comments within 24 hours.
- Label every starter-task thread as `accepted`, `needs-info`, or `not-now`.
- Publish weekly conversion summary (opened -> active -> merged).

## Activation scoring model

Day 26 computes weighted readiness score (0-100):

- Docs contract + command lane completeness: 45 points.
- Discoverability links in README/docs index: 25 points.
- Top-10 roadmap alignment + starter-task language: 20 points.
- Evidence-lane readiness for strict validation: 10 points.

## Execution evidence mode

`--execute` runs deterministic Day 26 checks and writes logs to `--evidence-dir` for release review.
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
        "key": "readme_day26_link",
        "category": "discoverability",
        "weight": 10,
        "marker": "docs/integrations-external-contribution-push.md",
        "source": "readme",
    },
    {
        "key": "readme_day26_command",
        "category": "discoverability",
        "weight": 8,
        "marker": "external-contribution-push",
        "source": "readme",
    },
    {
        "key": "docs_index_day26_link",
        "category": "discoverability",
        "weight": 7,
        "marker": "day-26-ultra-upgrade-report.md",
        "source": "docs_index",
    },
    {
        "key": "top10_day26_alignment",
        "category": "strategy",
        "weight": 10,
        "marker": "Day 26 — External contribution push",
        "source": "top10",
    },
    {
        "key": "docs_mentions_starter_tasks",
        "category": "strategy",
        "weight": 10,
        "marker": "starter task",
        "source": "page",
    },
    {
        "key": "docs_mentions_response_sla",
        "category": "evidence",
        "weight": 10,
        "marker": "24 hours",
        "source": "page",
    },
]

_CRITICAL_FAILURE_KEYS = {
    "docs_page_exists",
    "required_sections_present",
    "required_commands_present",
    "top10_day26_alignment",
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


def build_external_contribution_push_summary(
    root: Path,
    *,
    readme_path: str = "README.md",
    docs_index_path: str = "docs/index.md",
    docs_page_path: str = _PAGE_PATH,
    top10_path: str = _TOP10_PATH,
) -> dict[str, Any]:
    checks = _evaluate_signals(
        root,
        page_text=_read(root / docs_page_path),
        readme_text=_read(root / readme_path),
        docs_index_text=_read(root / docs_index_path),
        top10_text=_read(root / top10_path),
    )

    total_weight = sum(int(item["weight"]) for item in checks)
    earned_weight = sum(int(item["weight"]) for item in checks if item["passed"])
    score = round((earned_weight / total_weight) * 100, 2) if total_weight else 0.0

    failed = [item for item in checks if not item["passed"]]
    critical_failures = [item["key"] for item in failed if item["key"] in _CRITICAL_FAILURE_KEYS]

    recommendations: list[str] = []
    if any(item["category"] == "contract" for item in failed):
        recommendations.append("Restore Day 26 docs contract sections and required command lane before launch.")
    if any(item["category"] == "discoverability" for item in failed):
        recommendations.append("Add Day 26 links and commands to README/docs index for external contributor visibility.")
    if any(item["category"] in {"strategy", "evidence"} for item in failed):
        recommendations.append("Align Day 26 outputs with starter-task spotlighting and 24-hour first-response SLA.")
    if not recommendations:
        recommendations.append("Day 26 external contribution push lane is healthy; keep weekly conversion summaries flowing.")

    return {
        "name": "day26-external-contribution-push",
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
        "Day 26 external contribution push summary",
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
    summary = out_dir / "day26-external-contribution-summary.json"
    scorecard = out_dir / "day26-external-contribution-scorecard.md"
    spotlight = out_dir / "day26-starter-task-spotlight.md"
    triage = out_dir / "day26-external-contribution-triage-board.md"
    validation = out_dir / "day26-validation-commands.md"

    summary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    scorecard.write_text(_render_text(payload) + "\n", encoding="utf-8")
    spotlight.write_text(
        "\n".join(
            [
                "# Day 26 starter-task spotlight plan",
                "",
                "## Public call-to-action",
                "Help wanted: pick one starter task and submit your first contribution this week.",
                "",
                "## Spotlight checklist",
                "- [ ] Link top 10 starter tasks with acceptance criteria.",
                "- [ ] Assign maintainer owner for each task.",
                "- [ ] Include setup prerequisites and expected completion time.",
                "",
                "## Promotion channels",
                "1. GitHub discussion",
                "2. X / LinkedIn post",
                "3. Community Discord/Slack announcement",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    triage.write_text(
        "\n".join(
            [
                "# Day 26 external contribution triage board",
                "",
                "| Starter task | Interest signal | Owner | Status | Response SLA |",
                "| --- | --- | --- | --- | --- |",
                "| Example: docs quickstart polish | 0 comments | @owner | needs-info | <=24h |",
                "",
                "First-response SLA: acknowledge every external contributor within 24 hours.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    validation.write_text(
        "\n".join(["# Day 26 validation commands", "", "```bash", *_REQUIRED_COMMANDS, "```"]) + "\n",
        encoding="utf-8",
    )

    return [str(path.relative_to(root)) for path in [summary, scorecard, spotlight, triage, validation]]


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
        "name": "day26-external-contribution-push-execution",
        "total_commands": len(_EXECUTION_COMMANDS),
        "results": results,
    }
    (evidence_dir / "day26-execution-summary.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sdetkit external-contribution-push",
        description="Day 26 external contribution push closeout lane.",
    )
    parser.add_argument("--root", default=".", help="Repository root path.")
    parser.add_argument("--readme", default="README.md", help="README path for discoverability checks.")
    parser.add_argument("--docs-index", default="docs/index.md", help="Docs index path for discoverability checks.")
    parser.add_argument("--top10", default=_TOP10_PATH, help="Top-10 roadmap strategy path.")
    parser.add_argument("--write-defaults", action="store_true", help="Create default Day 26 integration page.")
    parser.add_argument("--emit-pack-dir", default="", help="Optional output directory for generated Day 26 files.")
    parser.add_argument("--execute", action="store_true", help="Run Day 26 command chain and emit evidence logs.")
    parser.add_argument(
        "--evidence-dir",
        default="docs/artifacts/day26-external-contribution-pack/evidence",
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
        page.write_text(_DAY26_DEFAULT_PAGE, encoding="utf-8")

    payload = build_external_contribution_push_summary(
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
