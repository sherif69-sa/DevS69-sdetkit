from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def _render_md(payload: dict[str, Any]) -> str:
    rollup = payload.get("first_proof_rollup", {})
    summary = rollup.get("summary", {}) if isinstance(rollup, dict) else {}
    adaptive = payload.get("adaptive_postcheck", {})
    adaptive_summary = adaptive.get("summary", {}) if isinstance(adaptive, dict) else {}

    lines = ["# First-Proof Control Tower", ""]
    lines.append(f"- Generated at: `{payload.get('generated_at', 'unknown')}`")
    lines.append(f"- Rollup present: `{bool(payload.get('first_proof_rollup_present', False))}`")
    lines.append(f"- Adaptive postcheck present: `{bool(payload.get('adaptive_postcheck_present', False))}`")
    lines.append("")
    lines.append("## First-Proof Trend")
    lines.append(f"- Total runs: `{int(summary.get('total_runs', 0))}`")
    lines.append(f"- SHIP rate: `{float(summary.get('ship_rate', 0.0)):.2f}`")

    top_failed = summary.get("top_failed_steps", [])
    if isinstance(top_failed, list) and top_failed:
        lines.append("- Top failed steps:")
        for row in top_failed[:5]:
            if isinstance(row, dict):
                lines.append(f"  - `{row.get('step', 'unknown')}`: `{int(row.get('count', 0))}`")

    actions = (rollup.get("adaptive_reviewer", {}) if isinstance(rollup, dict) else {}).get("actions", [])
    if isinstance(actions, list) and actions:
        lines.append("- Adaptive actions:")
        for action in actions[:5]:
            lines.append(f"  - {action}")

    lines.append("")
    lines.append("## Adaptive Postcheck")
    if isinstance(adaptive_summary, dict) and adaptive_summary:
        lines.append(f"- OK: `{bool(adaptive_summary.get('ok', False))}`")
        lines.append(f"- Confidence score: `{int(adaptive_summary.get('confidence_score', 0))}`")
        lines.append(f"- Failed required: `{int(adaptive_summary.get('failed_required', 0))}`")
        lines.append(f"- Failed warn: `{int(adaptive_summary.get('failed_warn', 0))}`")
    else:
        lines.append("- Adaptive postcheck summary not available yet.")

    lines.append("")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build first-proof + adaptive reviewer control tower summary.")
    parser.add_argument(
        "--first-proof-rollup",
        type=Path,
        default=Path("build/first-proof/first-proof-learning-rollup.json"),
    )
    parser.add_argument(
        "--adaptive-postcheck",
        type=Path,
        default=Path("build/adaptive-postcheck-min.json"),
    )
    parser.add_argument("--out-json", type=Path, default=Path("build/first-proof/control-tower.json"))
    parser.add_argument("--out-md", type=Path, default=Path("build/first-proof/control-tower.md"))
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    rollup = _read_json(args.first_proof_rollup)
    adaptive = _read_json(args.adaptive_postcheck)

    payload = {
        "schema_version": "sdetkit.first-proof-control-tower.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "first_proof_rollup_present": isinstance(rollup, dict),
        "adaptive_postcheck_present": isinstance(adaptive, dict),
        "first_proof_rollup": rollup,
        "adaptive_postcheck": adaptive,
    }

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.out_md.write_text(_render_md(payload), encoding="utf-8")

    result = {
        "ok": isinstance(rollup, dict),
        "out_json": str(args.out_json),
        "out_md": str(args.out_md),
        "first_proof_rollup_present": isinstance(rollup, dict),
        "adaptive_postcheck_present": isinstance(adaptive, dict),
    }

    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"control tower json: {args.out_json}")
        print(f"control tower md: {args.out_md}")
        print(f"first-proof rollup present: {result['first_proof_rollup_present']}")
        print(f"adaptive postcheck present: {result['adaptive_postcheck_present']}")

    return 0 if isinstance(rollup, dict) else 1


if __name__ == "__main__":
    raise SystemExit(main())
