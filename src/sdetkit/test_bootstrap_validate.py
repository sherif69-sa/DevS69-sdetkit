from __future__ import annotations

import argparse
import json
from pathlib import Path

from .test_bootstrap import build_test_bootstrap_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate test bootstrap prerequisites (Python version and required test modules)."
        )
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when prerequisites are not met.",
    )
    parser.add_argument(
        "--out",
        default="",
        help="Optional output file path. When set, writes rendered output to this file.",
    )
    return parser.parse_args()


def render_text(report: dict[str, object]) -> str:
    py = report["python"]
    deps = report["dependencies"]
    lines = [
        f"[bootstrap] python: {py['current']} (required: {py['required']})",
        f"[bootstrap] dependencies present: {deps['all_present']}",
    ]
    missing = deps["missing_modules"]
    if missing:
        lines.append(f"[bootstrap] missing modules: {', '.join(missing)}")
        lines.append(f"[bootstrap] remediation: {report['remediation']}")
    if not py["supported"]:
        lines.append("[bootstrap] unsupported Python runtime detected.")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    report = build_test_bootstrap_report()
    ok = bool(report["ok"])

    rendered = (
        json.dumps(report, indent=2, sort_keys=True)
        if args.format == "json"
        else render_text(report)
    )
    print(rendered)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered + "\n", encoding="utf-8")
    return 0 if (ok or not args.strict) else 2


if __name__ == "__main__":
    raise SystemExit(main())
