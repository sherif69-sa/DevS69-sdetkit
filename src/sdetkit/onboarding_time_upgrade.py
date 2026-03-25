from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/onboarding-optimization.md"
_SECTION_HEADER = "# Onboarding optimization"
_REQUIRED_SECTIONS = [
    "## Who should run onboarding-optimization",
    "## Three-minute success contract",
    "## Fast path commands",
    "## Time-to-first-success scoring",
    "## Execution evidence mode",
    "## Closeout checklist",
]
_REQUIRED_COMMANDS = [
    "python -m sdetkit onboarding-optimization --format json --strict",
    "python -m sdetkit onboarding-optimization --emit-pack-dir docs/artifacts/onboarding-optimization-pack --format json --strict",
    "python -m sdetkit onboarding-optimization --execute --evidence-dir docs/artifacts/onboarding-optimization-pack/evidence --format json --strict",
    "python scripts/check_day24_onboarding_time_upgrade_contract.py",
]
_EXECUTION_COMMANDS = [
    "python -m sdetkit onboarding --format text --platform all",
    "python -m sdetkit onboarding-optimization --format json --strict",
    "python scripts/check_day24_onboarding_time_upgrade_contract.py --skip-evidence",
]

_DAY24_DEFAULT_PAGE = """# Onboarding optimization

Onboarding optimization reduces time-to-first-success and standardizes a deterministic three-minute activation path.

## Who should run onboarding-optimization

- Maintainers improving contributor first-run experience.
- DevRel owners preparing launch-ready quick-start docs.
- Team leads reducing setup friction across Linux/macOS/Windows.

## Three-minute success contract

An onboarding-optimization pass means a new contributor can complete environment setup and run one successful `sdetkit` command in under three minutes with no hidden prerequisites.

## Fast path commands

```bash
python -m sdetkit onboarding-optimization --format json --strict
python -m sdetkit onboarding-optimization --emit-pack-dir docs/artifacts/onboarding-optimization-pack --format json --strict
python -m sdetkit onboarding-optimization --execute --evidence-dir docs/artifacts/onboarding-optimization-pack/evidence --format json --strict
python scripts/check_day24_onboarding_time_upgrade_contract.py
```

## Time-to-first-success scoring

Onboarding-optimization computes a weighted readiness score (0-100):

- Onboarding command and role/platform coverage: 40 points.
- Discoverability (README + docs index links): 20 points.
- Docs contract and quick-start consistency: 30 points.
- Evidence and strict validation lane: 10 points.

## Execution evidence mode

`--execute` runs the onboarding-optimization validation chain and stores deterministic logs in `--evidence-dir`.

## Closeout checklist

- [ ] `onboarding` command supports role and platform targeting.
- [ ] README links to onboarding-optimization integration and command examples.
- [ ] Docs index links the onboarding-optimization report and artifact references.
- [ ] Onboarding-optimization pack emitted with summary, checklist, and runbook.
"""

_SIGNALS = [
    {
        "check_id": "docs_page_exists",
        "category": "contract",
        "weight": 10,
        "evaluator": "page_exists",
    },
    {
        "check_id": "required_sections_present",
        "category": "contract",
        "weight": 15,
        "evaluator": "required_sections",
    },
    {
        "check_id": "required_commands_present",
        "category": "contract",
        "weight": 5,
        "evaluator": "required_commands",
    },
    {
        "check_id": "onboarding_role_support",
        "category": "onboarding",
        "weight": 15,
        "marker": "--role",
        "source": "onboarding_module",
    },
    {
        "check_id": "onboarding_platform_support",
        "category": "onboarding",
        "weight": 15,
        "marker": "--platform",
        "source": "onboarding_module",
    },
    {
        "check_id": "onboarding_quick_start_command",
        "category": "onboarding",
        "weight": 10,
        "marker": "python -m sdetkit doctor --format text",
        "source": "onboarding_module",
    },
    {
        "check_id": "readme_onboarding_optimization_link",
        "category": "discoverability",
        "weight": 10,
        "marker": "docs/onboarding-optimization.md",
        "source": "readme",
    },
    {
        "check_id": "docs_index_onboarding_optimization_link",
        "category": "discoverability",
        "weight": 10,
        "marker": "docs/onboarding-optimization.md",
        "source": "docs_index",
    },
    {
        "check_id": "readme_onboarding_command",
        "category": "discoverability",
        "weight": 10,
        "marker": "onboarding-optimization",
        "source": "readme",
    },
]

_CRITICAL_FAILURE_KEYS = {
    "docs_page_exists",
    "required_sections_present",
    "required_commands_present",
    "onboarding_role_support",
    "onboarding_platform_support",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _evaluate_signals(
    root: Path,
    *,
    page_text: str,
    readme_text: str,
    docs_index_text: str,
    onboarding_module_text: str,
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
            missing = [
                section
                for section in [_SECTION_HEADER, *_REQUIRED_SECTIONS]
                if section not in page_text
            ]
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
            elif source == "onboarding_module":
                corpus = onboarding_module_text
            passed = bool(marker) and marker in corpus
            evidence = marker

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


def build_onboarding_time_summary(
    root: Path,
    *,
    readme_path: str = "README.md",
    docs_index_path: str = "docs/index.md",
    docs_page_path: str = _PAGE_PATH,
    onboarding_module_path: str = "src/sdetkit/onboarding.py",
) -> dict[str, Any]:
    checks = _evaluate_signals(
        root,
        page_text=_read(root / docs_page_path),
        readme_text=_read(root / readme_path),
        docs_index_text=_read(root / docs_index_path),
        onboarding_module_text=_read(root / onboarding_module_path),
    )
    total_weight = sum(item["weight"] for item in checks)
    earned_weight = sum(item["weight"] for item in checks if item["passed"])
    score = round((earned_weight / total_weight) * 100, 2) if total_weight else 0.0

    failed = [item for item in checks if not item["passed"]]
    critical_failures = [
        item["check_id"] for item in failed if item["check_id"] in _CRITICAL_FAILURE_KEYS
    ]

    recommendations: list[str] = []
    if any(item["category"] == "contract" for item in failed):
        recommendations.append(
            "Repair onboarding-optimization docs contract sections and command lane before review."
        )
    if any(item["category"] == "onboarding" for item in failed):
        recommendations.append(
            "Restore role/platform onboarding guidance to keep first success under three minutes."
        )
    if any(item["category"] == "discoverability" for item in failed):
        recommendations.append(
            "Link onboarding-optimization guidance from README and docs index for faster adoption."
        )
    if not recommendations:
        recommendations.append(
            "Onboarding-optimization is healthy; keep execution evidence attached to releases."
        )

    return {
        "name": "onboarding-optimization",
        "summary": {
            "onboarding_score": score,
            "readiness": "strong" if score >= 90 and not critical_failures else "review",
            "weighted_points": {"earned": earned_weight, "total": total_weight},
            "failed_checks": len(failed),
            "critical_failures": critical_failures,
        },
        "checks": checks,
        "recommendations": recommendations,
        "inputs": {
            "readme": readme_path,
            "docs_index": docs_index_path,
            "docs_page": docs_page_path,
            "onboarding_module": onboarding_module_path,
        },
    }


def _render_text(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    points = summary["weighted_points"]
    lines = [
        "Onboarding optimization",
        "",
        f"Onboarding score: {summary['onboarding_score']}",
        f"Readiness: {summary['readiness']}",
        f"Weighted points: {points['earned']}/{points['total']}",
        f"Failed checks: {summary['failed_checks']}",
        "",
        "Checks:",
    ]
    for item in payload["checks"]:
        lines.append(
            f"- [{'x' if item['passed'] else ' '}] {item['check_id']} ({item['category']}, w={item['weight']})"
        )
    return "\n".join(lines)


def emit_pack(root: Path, out_dir: Path, payload: dict[str, Any]) -> list[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = out_dir / "onboarding-optimization-summary.json"
    scorecard = out_dir / "onboarding-optimization-scorecard.md"
    checklist = out_dir / "onboarding-optimization-checklist.md"
    runbook = out_dir / "onboarding-optimization-runbook.md"
    validation = out_dir / "onboarding-optimization-validation-commands.md"

    summary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    scorecard.write_text(_render_text(payload) + "\n", encoding="utf-8")
    checklist.write_text(
        "\n".join(
            [
                "# Onboarding optimization checklist",
                "",
                "- [ ] Docs contract page includes all required sections.",
                "- [ ] README links the onboarding-optimization page and command lane.",
                "- [ ] Docs index links docs/onboarding-optimization.md.",
                "- [ ] onboarding command retains role + platform selectors.",
                "- [ ] Execution evidence artifacts attached to release thread.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    runbook.write_text(
        "\n".join(
            [
                "# Onboarding optimization runbook",
                "",
                "1. Run `python -m sdetkit onboarding --platform all --format text`.",
                "2. Run `python -m sdetkit onboarding-optimization --format json --strict`.",
                "3. Emit the onboarding-optimization pack and attach it to release-readiness notes.",
                "4. Capture first-success timing and keep the median below three minutes.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    validation.write_text(
        "\n".join(["# Onboarding optimization validation commands", "", "```bash", *_REQUIRED_COMMANDS, "```"])
        + "\n",
        encoding="utf-8",
    )

    return [
        str(path.relative_to(root)) for path in [summary, scorecard, checklist, runbook, validation]
    ]


def execute_commands(root: Path, evidence_dir: Path, timeout_sec: int) -> dict[str, Any]:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    for command in _EXECUTION_COMMANDS:
        argv = shlex.split(command)
        if argv and argv[0] == "python":
            argv[0] = sys.executable
        proc = subprocess.run(argv, cwd=root, text=True, capture_output=True, timeout=timeout_sec)
        results.append(
            {
                "command": command,
                "returncode": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            }
        )
    payload = {
        "name": "onboarding-optimization-execution",
        "total_commands": len(_EXECUTION_COMMANDS),
        "results": results,
    }
    (evidence_dir / "onboarding-optimization-execution-summary.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sdetkit onboarding-optimization",
        description="Onboarding optimization readiness workflow.",
    )
    parser.add_argument("--root", default=".", help="Repository root path.")
    parser.add_argument(
        "--readme", default="README.md", help="README path for discoverability checks."
    )
    parser.add_argument(
        "--docs-index", default="docs/index.md", help="Docs index path for discoverability checks."
    )
    parser.add_argument(
        "--write-defaults", action="store_true", help="Create default onboarding optimization page."
    )
    parser.add_argument(
        "--emit-pack-dir", default="", help="Optional output directory for generated onboarding-optimization files."
    )
    parser.add_argument(
        "--execute", action="store_true", help="Run onboarding-optimization command chain and emit evidence logs."
    )
    parser.add_argument(
        "--evidence-dir",
        default="docs/artifacts/onboarding-optimization-pack/evidence",
        help="Output directory for execution evidence logs.",
    )
    parser.add_argument(
        "--timeout-sec", type=int, default=120, help="Per-command timeout used by --execute."
    )
    parser.add_argument(
        "--min-score", type=float, default=90.0, help="Minimum score for strict pass."
    )
    parser.add_argument(
        "--strict", action="store_true", help="Fail when score or critical checks are not ready."
    )
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    return parser


def main(argv: list[str] | None = None) -> int:
    ns = build_parser().parse_args(argv)
    root = Path(ns.root).resolve()
    page = root / _PAGE_PATH

    if ns.write_defaults:
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(_DAY24_DEFAULT_PAGE, encoding="utf-8")

    payload = build_onboarding_time_summary(
        root, readme_path=ns.readme, docs_index_path=ns.docs_index
    )
    page_text = _read(page)
    missing_sections = [
        section for section in [_SECTION_HEADER, *_REQUIRED_SECTIONS] if section not in page_text
    ]
    missing_commands = [command for command in _REQUIRED_COMMANDS if command not in page_text]
    payload["strict_failures"] = [*missing_sections, *missing_commands]

    if ns.emit_pack_dir:
        payload["emitted_pack_files"] = emit_pack(root, root / ns.emit_pack_dir, payload)
    if ns.execute:
        payload["execution"] = execute_commands(root, root / ns.evidence_dir, ns.timeout_sec)

    strict_failed = (
        bool(payload["strict_failures"])
        or payload["summary"]["onboarding_score"] < ns.min_score
        or bool(payload["summary"]["critical_failures"])
    )

    if ns.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(_render_text(payload))

    return 1 if ns.strict and strict_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
