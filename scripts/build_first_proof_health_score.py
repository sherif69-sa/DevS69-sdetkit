from __future__ import annotations

import argparse
import json
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a compact first-proof health score from deterministic artifacts."
    )
    parser.add_argument("--summary", required=True, help="Path to first-proof-summary.json")
    parser.add_argument("--out-json", required=True, help="Output JSON score artifact path")
    parser.add_argument("--out-md", required=True, help="Output Markdown score summary path")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser


def _calculate_score(summary: dict) -> tuple[int, list[str]]:
    score = 100
    reasons: list[str] = []

    if not summary.get("ok", False):
        score -= 50
        reasons.append("first-proof summary not ok (-50)")

    failed_steps = summary.get("failed_steps") or []
    if failed_steps:
        penalty = min(30, 10 * len(failed_steps))
        score -= penalty
        reasons.append(f"failed steps={len(failed_steps)} (-{penalty})")

    doctor_step = next((s for s in summary.get("steps", []) if s.get("name") == "doctor"), None)
    if doctor_step is not None and int(doctor_step.get("returncode", 1)) != 0:
        score -= 20
        reasons.append("doctor failed (-20)")

    score = max(0, min(100, score))
    return score, reasons


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    summary_path = Path(args.summary)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    score, reasons = _calculate_score(summary)
    decision = "GREEN" if score >= 85 else "YELLOW" if score >= 60 else "RED"
    payload = {
        "schema_version": "1.0.0",
        "score": score,
        "decision": decision,
        "reason_count": len(reasons),
        "reasons": reasons,
        "source_summary": str(summary_path),
    }

    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(f"{json.dumps(payload, indent=2, sort_keys=True)}\n", encoding="utf-8")

    md_lines = [
        "# First-Proof Health Score",
        "",
        f"- score: **{score}/100**",
        f"- decision: **{decision}**",
        f"- source: `{summary_path}`",
        "",
        "## Reasons",
    ]
    if reasons:
        md_lines.extend([f"- {r}" for r in reasons])
    else:
        md_lines.append("- No penalties applied.")
    Path(args.out_md).write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"first-proof-health-score: {score}/100 ({decision})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
