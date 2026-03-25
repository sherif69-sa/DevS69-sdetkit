from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/reliability-evidence-pack.md"

_SECTION_HEADER = "# Reliability evidence pack"
_REQUIRED_SECTIONS = [
    "## Who this pack is for",
    "## Reliability score model",
    "## Fast verification commands",
    "## Execution evidence mode",
    "## Closeout checklist",
]

_REQUIRED_COMMANDS = [
    "python -m sdetkit reliability-evidence-pack --format json --strict",
    "python -m sdetkit reliability-evidence-pack --emit-pack-dir docs/artifacts/reliability-evidence-pack --format json --strict",
    "python -m sdetkit reliability-evidence-pack --execute --evidence-dir docs/artifacts/reliability-evidence-pack/evidence --format json --strict",
    "python scripts/check_day18_reliability_evidence_pack_contract.py",
]

_REQUIRED_DAY17_KEYS = ("name", "quality", "contributions")

_DAY18_DEFAULT_PAGE = """# Reliability evidence pack

Operational recipe for rolling GitHub Actions onboarding, GitLab CI onboarding, and contribution-quality-report evidence into one reliability-evidence signal.

## Who this pack is for

- Maintainers publishing a weekly reliability summary.
- Engineering leads who need one deterministic pass/fail review checkpoint.
- Contributors who need actionable evidence before tagging release candidates.

## Reliability score model

The reliability score uses weighted GitHub Actions onboarding and GitLab CI onboarding execution quality plus contribution-quality-report stability and velocity.

- GitHub Actions onboarding score weight: 25%
- GitLab CI onboarding score weight: 25%
- Contribution-quality velocity score weight: 20%
- Contribution-quality stability score weight: 20%
- GitHub Actions onboarding pass-rate weight: 5%
- GitLab CI onboarding pass-rate weight: 5%

## Fast verification commands

```bash
python -m sdetkit reliability-evidence-pack --format json --strict
python -m sdetkit reliability-evidence-pack --emit-pack-dir docs/artifacts/reliability-evidence-pack --format json --strict
python -m sdetkit reliability-evidence-pack --execute --evidence-dir docs/artifacts/reliability-evidence-pack/evidence --format json --strict
python scripts/check_day18_reliability_evidence_pack_contract.py
```

## Execution evidence mode

`--execute` runs the reliability-evidence command chain and writes deterministic logs for each command into `--evidence-dir`.

## Closeout checklist

- [ ] GitHub Actions onboarding execution summary is green.
- [ ] GitLab CI onboarding execution summary is green.
- [ ] Contribution-quality-report strict failures are empty.
- [ ] Reliability score meets minimum threshold.
- [ ] Reliability-evidence pack is attached to review notes.
"""


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _load_json(path: str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _require_keys(payload: dict[str, Any], keys: tuple[str, ...], source: str) -> None:
    for key in keys:
        if key not in payload:
            raise ValueError(f"{source} missing required key: {key}")


def _normalize_execution_summary(summary: dict[str, Any], label: str) -> dict[str, float | bool]:
    if {"score", "strict", "checks_passed", "checks_total"}.issubset(summary):
        checks_passed = float(summary["checks_passed"])
        checks_total = float(summary["checks_total"])
        score = float(summary["score"])
        strict = bool(summary["strict"])
    elif {"passed_commands", "total_commands", "failed_commands"}.issubset(summary):
        checks_passed = float(summary["passed_commands"])
        checks_total = float(summary["total_commands"])
        score = round((checks_passed / checks_total) * 100, 2) if checks_total else 0.0
        strict = int(summary["failed_commands"]) == 0
    else:
        raise ValueError(
            f"{label} summary must include score/strict/checks_* keys or passed_commands/total_commands/failed_commands keys"
        )
    return {
        "score": score,
        "strict": strict,
        "checks_passed": checks_passed,
        "checks_total": checks_total,
    }


def build_reliability_pack(
    day15_summary: dict[str, Any],
    day16_summary: dict[str, Any],
    day17_summary: dict[str, Any],
) -> dict[str, Any]:
    day15 = _normalize_execution_summary(day15_summary, "day15")
    day16 = _normalize_execution_summary(day16_summary, "day16")
    _require_keys(day17_summary, _REQUIRED_DAY17_KEYS, "day17 summary")

    day15_pass_rate = round((float(day15["checks_passed"]) / float(day15["checks_total"])) * 100, 2)
    day16_pass_rate = round((float(day16["checks_passed"]) / float(day16["checks_total"])) * 100, 2)
    day17_velocity = float(day17_summary["contributions"]["velocity_score"])
    day17_stability = float(day17_summary["quality"]["stability_score"])

    reliability_score = round(
        (float(day15["score"]) * 0.25)
        + (float(day16["score"]) * 0.25)
        + (day17_velocity * 0.20)
        + (day17_stability * 0.20)
        + (day15_pass_rate * 0.05)
        + (day16_pass_rate * 0.05),
        2,
    )

    strict_all_green = (
        bool(day15["strict"])
        and bool(day16["strict"])
        and not bool(day17_summary.get("strict_failures"))
    )
    recommendations: list[str] = []
    if not strict_all_green:
        recommendations.append(
            "Resolve strict-gate failures before publishing the weekly reliability update."
        )
    if day17_velocity < 70:
        recommendations.append(
            "Raise contribution velocity with targeted docs and release distribution this week."
        )
    if day17_stability < 95:
        recommendations.append(
            "Recover quality stability by re-running quality deltas and closing artifact gaps."
        )
    if reliability_score >= 95 and strict_all_green:
        recommendations.append(
            "Reliability posture is strong; keep current CI and review cadence."
        )

    return {
        "name": "reliability-evidence-pack",
        "inputs": {
            "day15": {
                "score": float(day15["score"]),
                "strict": bool(day15["strict"]),
                "pass_rate": day15_pass_rate,
            },
            "day16": {
                "score": float(day16["score"]),
                "strict": bool(day16["strict"]),
                "pass_rate": day16_pass_rate,
            },
            "day17": {
                "velocity_score": day17_velocity,
                "stability_score": day17_stability,
                "strict_failures": list(day17_summary.get("strict_failures", [])),
            },
        },
        "summary": {
            "reliability_score": reliability_score,
            "strict_all_green": strict_all_green,
            "gate_status": "pass" if strict_all_green and reliability_score >= 90 else "warn",
        },
        "recommendations": recommendations,
    }


def _render_text(payload: dict[str, Any]) -> str:
    lines = [
        "Reliability evidence pack",
        "",
        f"Reliability score: {payload['summary']['reliability_score']}",
        f"Strict gates green: {payload['summary']['strict_all_green']}",
        f"Gate status: {payload['summary']['gate_status']}",
        "",
        "Recommendations:",
    ]
    lines.extend(f"- {note}" for note in payload["recommendations"])
    return "\n".join(lines) + "\n"


def _render_markdown(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Reliability evidence pack",
            "",
            f"- Reliability score: **{payload['summary']['reliability_score']}**",
            f"- Strict gates green: **{payload['summary']['strict_all_green']}**",
            f"- Gate status: **{payload['summary']['gate_status']}**",
            "",
            "## Recommendations",
            *[f"- {note}" for note in payload["recommendations"]],
            "",
        ]
    )


def _emit_pack(path: str, payload: dict[str, Any], base: Path) -> list[str]:
    out_dir = base / path
    out_dir.mkdir(parents=True, exist_ok=True)

    summary_path = out_dir / "reliability-evidence-summary.json"
    summary_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    scorecard_path = out_dir / "reliability-evidence-scorecard.md"
    scorecard_path.write_text(_render_markdown(payload), encoding="utf-8")

    checklist_path = out_dir / "reliability-evidence-checklist.md"
    checklist_path.write_text(
        "\n".join(
            [
                "# Reliability evidence checklist",
                "",
                "- [ ] Day 15 GitHub Actions quickstart strict gate still green.",
                "- [ ] Day 16 GitLab CI quickstart strict gate still green.",
                "- [ ] Contribution-quality-report strict gates are green.",
                "- [ ] Reliability score is reviewed in weekly review.",
                "- [ ] Recommendations are tracked in planning backlog.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    validation_path = out_dir / "reliability-evidence-validation-commands.md"
    validation_path.write_text(
        "\n".join(["# Reliability evidence validation commands", "", "```bash", *_REQUIRED_COMMANDS, "```", ""]),
        encoding="utf-8",
    )

    return [
        str(summary_path.relative_to(base)),
        str(scorecard_path.relative_to(base)),
        str(checklist_path.relative_to(base)),
        str(validation_path.relative_to(base)),
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

    summary = root / "reliability-evidence-execution-summary.json"
    payload = {
        "name": "reliability-evidence-execution",
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


def _write_defaults(base: Path) -> list[str]:
    path = base / _PAGE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_DAY18_DEFAULT_PAGE, encoding="utf-8")
    return [str(path.relative_to(base))]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sdetkit reliability-evidence-pack",
        description="Build reliability evidence by combining release-quality and contribution signals.",
    )
    parser.add_argument(
        "--root", default=".", help="Repository root where docs and artifacts live."
    )
    parser.add_argument(
        "--day15-summary",
        default="docs/artifacts/day15-github-pack/evidence/day15-execution-summary.json",
    )
    parser.add_argument(
        "--day16-summary",
        default="docs/artifacts/day16-gitlab-pack/evidence/day16-execution-summary.json",
    )
    parser.add_argument(
        "--day17-summary",
        default="docs/artifacts/contribution-quality-report-pack/contribution-quality-report-summary.json",
    )
    parser.add_argument("--min-reliability-score", type=float, default=90.0)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument(
        "--write-defaults",
        action="store_true",
        help="Write default reliability evidence docs page.",
    )
    parser.add_argument("--emit-pack-dir", default="")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute reliability-evidence validation commands and capture evidence.",
    )
    parser.add_argument(
        "--evidence-dir",
        default="",
        help="Output directory for reliability command execution logs.",
    )
    parser.add_argument("--timeout-sec", type=int, default=120)
    parser.add_argument("--format", choices=["text", "markdown", "json"], default="text")
    parser.add_argument("--output", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    ns = _build_parser().parse_args(argv)
    base = Path(ns.root).resolve()

    touched = _write_defaults(base) if ns.write_defaults else []
    page_text = _read(base / _PAGE_PATH)

    missing = []
    if _SECTION_HEADER not in page_text:
        missing.append(_SECTION_HEADER)
    missing.extend(section for section in _REQUIRED_SECTIONS if section not in page_text)
    missing.extend(cmd for cmd in _REQUIRED_COMMANDS if cmd not in page_text)

    try:
        day15_summary = _load_json(str(base / ns.day15_summary))
        day16_summary = _load_json(str(base / ns.day16_summary))
        day17_summary = _load_json(str(base / ns.day17_summary))
        payload = build_reliability_pack(day15_summary, day16_summary, day17_summary)
    except (OSError, ValueError, json.JSONDecodeError, KeyError, TypeError) as exc:
        print(str(exc))
        return 2

    payload["page"] = _PAGE_PATH
    payload["missing"] = missing
    payload["score"] = round(
        (
            (len(_REQUIRED_SECTIONS) + len(_REQUIRED_COMMANDS) + 1 - len(missing))
            / (len(_REQUIRED_SECTIONS) + len(_REQUIRED_COMMANDS) + 1)
        )
        * 100,
        2,
    )
    payload["touched_files"] = touched

    strict_failures: list[str] = []
    if missing:
        strict_failures.append(f"reliability page missing {len(missing)} required items")
    if not payload["summary"]["strict_all_green"]:
        strict_failures.append("strict status is not green across day15/day16/day17 inputs")
    if float(payload["summary"]["reliability_score"]) < float(ns.min_reliability_score):
        strict_failures.append(
            f"reliability_score {payload['summary']['reliability_score']} is below minimum {ns.min_reliability_score}"
        )

    emitted: list[str] = []
    if ns.emit_pack_dir:
        emitted.extend(_emit_pack(ns.emit_pack_dir, payload, base))

    if ns.execute:
        commands = [
            "python -m sdetkit reliability-evidence-pack --format json --strict",
            "python scripts/check_day18_reliability_evidence_pack_contract.py --skip-evidence",
            "python -m pytest -q tests/test_cli_help_lists_subcommands.py",
        ]
        results = _execute_commands(commands, timeout_sec=ns.timeout_sec)
        evidence_dir = ns.evidence_dir or (
            ns.emit_pack_dir + "/evidence" if ns.emit_pack_dir else ""
        )
        payload["executed_commands"] = results
        if evidence_dir:
            emitted.extend(_write_execution_evidence(base, evidence_dir, results))
        if any(not row.get("ok") for row in results):
            strict_failures.append("execution mode detected failed command(s)")

    payload["emitted_files"] = emitted
    payload["strict_failures"] = strict_failures

    if ns.format == "json":
        rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    elif ns.format == "markdown":
        rendered = _render_markdown(payload)
    else:
        rendered = _render_text(payload)

    if ns.output:
        (base / ns.output).write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")

    if ns.strict and strict_failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
