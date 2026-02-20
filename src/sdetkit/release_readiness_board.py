from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

_PAGE_PATH = "docs/integrations-release-readiness-board.md"

_SECTION_HEADER = "# Release readiness board (Day 19)"
_REQUIRED_SECTIONS = [
    "## Who should run Day 19",
    "## Score model",
    "## Fast verification commands",
    "## Execution evidence mode",
    "## Closeout checklist",
]

_REQUIRED_COMMANDS = [
    "python -m sdetkit release-readiness-board --format json --strict",
    "python -m sdetkit release-readiness-board --emit-pack-dir docs/artifacts/day19-release-readiness-pack --format json --strict",
    "python -m sdetkit release-readiness-board --execute --evidence-dir docs/artifacts/day19-release-readiness-pack/evidence --format json --strict",
    "python scripts/check_day19_release_readiness_board_contract.py",
]

_EXECUTION_COMMANDS = [
    "python -m sdetkit release-readiness-board --format json --strict",
    "python -m sdetkit release-readiness-board --emit-pack-dir docs/artifacts/day19-release-readiness-pack --format json --strict",
    "python scripts/check_day19_release_readiness_board_contract.py --skip-evidence",
]

_DAY19_DEFAULT_PAGE = """# Release readiness board (Day 19)

Day 19 composes Day 14 weekly trend health and Day 18 reliability posture into one release-candidate gate.

## Who should run Day 19

- Maintainers deciding if a release tag can be cut this week.
- Team leads running closeout meetings and action tracking.
- Contributors preparing evidence for release notes.

## Score model

- Day 18 reliability score weight: 70%
- Day 14 KPI score weight: 30%

## Fast verification commands

```bash
python -m sdetkit release-readiness-board --format json --strict
python -m sdetkit release-readiness-board --emit-pack-dir docs/artifacts/day19-release-readiness-pack --format json --strict
python -m sdetkit release-readiness-board --execute --evidence-dir docs/artifacts/day19-release-readiness-pack/evidence --format json --strict
python scripts/check_day19_release_readiness_board_contract.py
```

## Execution evidence mode

`--execute` runs the Day 19 command chain and writes deterministic logs into `--evidence-dir`.

## Closeout checklist

- [ ] Day 18 reliability gate status is `pass`.
- [ ] Day 14 KPI score meets threshold.
- [ ] Day 19 release score is reviewed by maintainers.
- [ ] Day 19 recommendations are tracked in backlog.
"""


_REQUIRED_DAY18_KEYS = ("summary",)
_REQUIRED_DAY18_SUMMARY_KEYS = ("reliability_score", "gate_status")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _require_keys(payload: dict[str, Any], keys: tuple[str, ...], label: str) -> None:
    for key in keys:
        if key not in payload:
            raise ValueError(f"{label} missing required key: {key}")


def _normalize_day14_summary(day14_summary: dict[str, Any]) -> tuple[float, str]:
    summary = day14_summary.get("summary")
    if isinstance(summary, dict):
        return float(summary.get("score", 0.0)), str(summary.get("status", "unknown"))

    kpis = day14_summary.get("kpis")
    if isinstance(kpis, dict):
        score = float(kpis.get("completion_rate_percent", 0.0))
        return score, "pass" if score >= 90 else "warn"

    raise ValueError(
        "day14 summary must include either summary.score or kpis.completion_rate_percent"
    )


def build_release_board(
    day18_summary: dict[str, Any],
    day14_summary: dict[str, Any],
) -> dict[str, Any]:
    _require_keys(day18_summary, _REQUIRED_DAY18_KEYS, "day18 summary")
    if not isinstance(day18_summary["summary"], dict):
        raise ValueError("day18 summary.summary must be an object")

    day18 = day18_summary["summary"]
    _require_keys(day18, _REQUIRED_DAY18_SUMMARY_KEYS, "day18 summary.summary")

    reliability_score = float(day18["reliability_score"])
    reliability_gate = str(day18["gate_status"])
    day14_score, day14_status = _normalize_day14_summary(day14_summary)

    release_score = round((reliability_score * 0.70) + (day14_score * 0.30), 2)
    strict_all_green = reliability_gate == "pass" and day14_score >= 90.0

    recommendations: list[str] = []
    if not strict_all_green:
        recommendations.append(
            "Resolve Day 18 reliability or Day 14 KPI gaps before cutting a release tag."
        )
    if release_score < 95:
        recommendations.append(
            "Raise release readiness score by improving reliability execution and KPI trend quality."
        )
    if strict_all_green and release_score >= 95:
        recommendations.append(
            "Release posture is strong; proceed with release candidate tagging and notes preparation."
        )

    return {
        "name": "day19-release-readiness-board",
        "inputs": {
            "day18": {
                "reliability_score": reliability_score,
                "gate_status": reliability_gate,
            },
            "day14": {
                "score": day14_score,
                "status": day14_status,
            },
        },
        "summary": {
            "release_score": release_score,
            "strict_all_green": strict_all_green,
            "gate_status": "pass" if strict_all_green and release_score >= 90 else "warn",
        },
        "recommendations": recommendations,
    }


def _render_text(payload: dict[str, Any]) -> str:
    lines = [
        "Day 19 release readiness board",
        "",
        f"Release score: {payload['summary']['release_score']}",
        f"Strict gates green: {payload['summary']['strict_all_green']}",
        f"Gate status: {payload['summary']['gate_status']}",
        "",
        "Recommendations:",
    ]
    lines.extend(f"- {row}" for row in payload["recommendations"])
    return "\n".join(lines) + "\n"


def _render_markdown(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Day 19 release readiness board",
            "",
            f"- Release score: **{payload['summary']['release_score']}**",
            f"- Strict gates green: **{payload['summary']['strict_all_green']}**",
            f"- Gate status: **{payload['summary']['gate_status']}**",
            "",
            "## Recommendations",
            *[f"- {row}" for row in payload["recommendations"]],
            "",
        ]
    )


def _emit_pack(path: str, payload: dict[str, Any], root: Path) -> list[str]:
    out_dir = root / path
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = out_dir / "day19-release-readiness-summary.json"
    scorecard = out_dir / "day19-release-readiness-scorecard.md"
    checklist = out_dir / "day19-release-readiness-checklist.md"
    validation = out_dir / "day19-validation-commands.md"
    decision = out_dir / "day19-release-decision.md"

    summary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    scorecard.write_text(_render_markdown(payload), encoding="utf-8")
    checklist.write_text(
        "\n".join(
            [
                "# Day 19 release readiness closeout checklist",
                "",
                "- [ ] Day 18 reliability gate status is pass.",
                "- [ ] Day 14 KPI status is pass.",
                "- [ ] Release score is reviewed in closeout meeting.",
                "- [ ] Recommendations are assigned and tracked.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    validation.write_text(
        "\n".join(["# Day 19 validation commands", "", "```bash", *_REQUIRED_COMMANDS, "```", ""]),
        encoding="utf-8",
    )
    decision.write_text(
        "\n".join(
            [
                "# Day 19 release decision",
                "",
                f"- Gate status: **{payload['summary']['gate_status']}**",
                f"- Release score: **{payload['summary']['release_score']}**",
                f"- Strict all green: **{payload['summary']['strict_all_green']}**",
                "",
                "Use this file as the final go/no-go note in release closeout.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    return [
        str(summary.relative_to(root)),
        str(scorecard.relative_to(root)),
        str(checklist.relative_to(root)),
        str(validation.relative_to(root)),
        str(decision.relative_to(root)),
    ]


def _execute_commands(commands: list[str], timeout_sec: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
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
            rows.append(
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
            rows.append(
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
    return rows


def _write_execution_evidence(
    root: Path,
    evidence_dir: str,
    rows: list[dict[str, Any]],
) -> list[str]:
    out = root / evidence_dir
    out.mkdir(parents=True, exist_ok=True)
    summary = out / "day19-execution-summary.json"
    payload = {
        "name": "day19-release-readiness-execution",
        "total_commands": len(rows),
        "passed_commands": len([r for r in rows if r["ok"]]),
        "failed_commands": len([r for r in rows if not r["ok"]]),
        "results": rows,
    }
    summary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    emitted = [summary]
    for row in rows:
        log = out / f"command-{row['index']:02d}.log"
        log.write_text(
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
        emitted.append(log)

    return [str(path.relative_to(root)) for path in emitted]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sdetkit release-readiness-board",
        description="Build Day 19 release readiness signal from Day 18 and Day 14 summaries.",
    )
    parser.add_argument("--root", default=".")
    parser.add_argument(
        "--day18-summary",
        default="docs/artifacts/day18-reliability-pack/day18-reliability-summary.json",
    )
    parser.add_argument(
        "--day14-summary",
        default="docs/artifacts/day14-weekly-pack/day14-kpi-scorecard.json",
    )
    parser.add_argument("--min-release-score", type=float, default=90.0)
    parser.add_argument("--write-defaults", action="store_true")
    parser.add_argument("--emit-pack-dir", default="")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument(
        "--evidence-dir",
        default="docs/artifacts/day19-release-readiness-pack/evidence",
    )
    parser.add_argument("--timeout-sec", type=int, default=120)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--format", choices=["text", "json", "markdown"], default="text")
    parser.add_argument("--output", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    root = Path(args.root).resolve()

    if args.write_defaults:
        page_path = root / _PAGE_PATH
        page_path.parent.mkdir(parents=True, exist_ok=True)
        page_path.write_text(_DAY19_DEFAULT_PAGE, encoding="utf-8")

    page_text = _read(root / _PAGE_PATH)
    missing_sections = [
        section for section in [_SECTION_HEADER, *_REQUIRED_SECTIONS] if section not in page_text
    ]
    missing_commands = [command for command in _REQUIRED_COMMANDS if command not in page_text]

    payload = build_release_board(
        _load_json(root / args.day18_summary),
        _load_json(root / args.day14_summary),
    )
    payload["score"] = 100.0 if not (missing_sections or missing_commands) else 0.0
    payload["strict_failures"] = [*missing_sections, *missing_commands]

    if args.emit_pack_dir:
        payload["emitted_pack_files"] = _emit_pack(args.emit_pack_dir, payload, root)
    if args.execute:
        payload["execution_artifacts"] = _write_execution_evidence(
            root,
            args.evidence_dir,
            _execute_commands(_EXECUTION_COMMANDS, args.timeout_sec),
        )

    strict_failed = (
        payload["summary"]["release_score"] < args.min_release_score
        or not payload["summary"]["strict_all_green"]
        or bool(payload["strict_failures"])
    )

    if args.format == "json":
        output = json.dumps(payload, indent=2, sort_keys=True)
    elif args.format == "markdown":
        output = _render_markdown(payload)
    else:
        output = _render_text(payload)

    if args.output:
        out = root / args.output
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(output if output.endswith("\n") else output + "\n", encoding="utf-8")
    else:
        print(output, end="" if output.endswith("\n") else "\n")

    return 1 if args.strict and strict_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
