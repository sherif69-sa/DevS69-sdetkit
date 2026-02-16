from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .registry import checks_for_mode
from .types import CheckResult, MaintenanceContext

SCHEMA_VERSION = "1.0"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00+00:00"


class StderrLogger:
    def info(self, message: str) -> None:
        print(message, file=sys.stderr)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sdetkit maintenance")
    parser.add_argument("--format", choices=["text", "json", "md"], default="text")
    parser.add_argument("--out", default=None)
    parser.add_argument("--mode", choices=["quick", "full"], default="quick")
    parser.add_argument("--fix", action="store_true")
    parser.add_argument("--deterministic", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    return parser


def _render_text(report: dict[str, Any]) -> str:
    failing = [name for name, item in report["checks"].items() if not item["ok"]]
    lines = [
        f"maintenance score: {report['score']}",
        f"overall: {'PASS' if report['ok'] else 'FAIL'}",
        "checks:",
    ]
    for name in sorted(report["checks"]):
        check = report["checks"][name]
        lines.append(f"- {'OK' if check['ok'] else 'FAIL'} {name}: {check['summary']}")
    if failing:
        lines.append("failing checks: " + ", ".join(sorted(failing)))
    return "\n".join(lines) + "\n"


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "## Maintenance Report",
        f"- overall: {'PASS' if report['ok'] else 'FAIL'}",
        f"- score: {report['score']}",
        f"- mode: {report['meta']['mode']}",
        "",
        "| Check | Status | Summary |",
        "| --- | --- | --- |",
    ]
    for name in sorted(report["checks"]):
        check = report["checks"][name]
        lines.append(f"| `{name}` | {'PASS' if check['ok'] else 'FAIL'} | {check['summary']} |")
    lines.append("")
    lines.append("### Recommendations")
    for rec in report["recommendations"]:
        lines.append(f"- {rec}")
    return "\n".join(lines) + "\n"


def _write_output(path: str | None, content: str) -> None:
    if not path:
        return
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")


def _deterministic_generated_at(env: dict[str, str]) -> str:
    epoch = env.get("SOURCE_DATE_EPOCH")
    if epoch is None:
        return DETERMINISTIC_GENERATED_AT
    try:
        return datetime.fromtimestamp(int(epoch), UTC).isoformat()
    except (TypeError, ValueError, OSError, OverflowError):
        return DETERMINISTIC_GENERATED_AT


def _build_report(ctx: MaintenanceContext, *, deterministic: bool = False) -> dict[str, Any]:
    started = time.monotonic()
    checks: dict[str, dict[str, Any]] = {}
    crashes = False
    for name, runner in checks_for_mode(ctx.mode):
        try:
            result: CheckResult = runner(ctx)
        except Exception as exc:
            crashes = True
            result = CheckResult(
                ok=False,
                summary=f"check crashed: {exc}",
                details={"error": repr(exc)},
                actions=[],
            )
        checks[name] = result.as_dict()
    passed = sum(1 for item in checks.values() if item["ok"])
    total = len(checks)
    score = 100 if total == 0 else round((passed / total) * 100)
    recommendations = [
        f"Review failing checks: {', '.join(sorted(name for name, item in checks.items() if not item['ok']))}."
    ]
    if all(item["ok"] for item in checks.values()):
        recommendations = ["All maintenance checks passed."]
    report = {
        "ok": all(item["ok"] for item in checks.values()),
        "score": score,
        "checks": checks,
        "recommendations": recommendations,
        "meta": {
            "schema_version": SCHEMA_VERSION,
            "generated_at": _deterministic_generated_at(ctx.env)
            if deterministic
            else datetime.now(UTC).isoformat(),
            "mode": ctx.mode,
            "fix": ctx.fix,
            "python": ctx.python_exe,
            "duration_seconds": 0.0 if deterministic else round(time.monotonic() - started, 3),
            "had_crash": crashes,
        },
    }
    return report


def _print_summary(report: dict[str, Any]) -> None:
    failing = [name for name, item in report["checks"].items() if not item["ok"]]
    if failing:
        print(f"Score: {report['score']} | Failing: {', '.join(sorted(failing))}")
    else:
        print(f"Score: {report['score']} | Failing: none")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        ns = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code
        if isinstance(code, int):
            return code
        if code is None:
            return 0
        return 2

    ctx = MaintenanceContext(
        repo_root=Path.cwd(),
        python_exe=sys.executable,
        mode=ns.mode,
        fix=bool(ns.fix),
        env=dict(os.environ),
        logger=StderrLogger(),
    )

    try:
        report = _build_report(ctx, deterministic=bool(ns.deterministic))
        rendered = {
            "json": json.dumps(report, sort_keys=True),
            "text": _render_text(report),
            "md": _render_markdown(report),
        }[ns.format]
        _write_output(ns.out, rendered)
        if ns.format == "json":
            print(rendered)
        elif not ns.quiet:
            print(_render_text(report), end="")
        if ns.format != "json" and ns.out and not ns.quiet:
            _print_summary(report)
        if ns.out and ns.format == "json" and not ns.quiet:
            _print_summary(report)
        return 0 if report["ok"] else 1
    except Exception as exc:
        print(f"maintenance execution error: {exc}", file=sys.stderr)
        return 2
