#!/usr/bin/env python3
"""Build adaptive operations summary from generated artifacts."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path


def _latest_artifact(artifacts_dir: Path, prefix: str) -> Path | None:
    matches = sorted(artifacts_dir.glob(f"{prefix}*.json"))
    return matches[-1] if matches else None


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _md_summary(payload: dict) -> str:
    scenario = payload["scenario_db"]
    postcheck = payload["postcheck"]
    doctor = postcheck.get("doctor") or {}
    triage = postcheck.get("first_run_triage") or {}

    lines = [
        "# Adaptive Ops Summary",
        "",
        f"Generated at: {payload['generated_at_utc']}",
        "",
        "## Scenario coverage",
        f"- Total scenarios: **{scenario['summary'].get('total_scenarios', 0)}**",
        f"- Meets target: **{scenario['summary'].get('meets_target', False)}**",
        "",
        "## Postcheck status",
        f"- OK: **{postcheck.get('summary', {}).get('ok', False)}**",
        f"- Required failures: **{postcheck.get('summary', {}).get('failed_required', 0)}**",
        f"- Warnings: **{postcheck.get('summary', {}).get('failed_warn', 0)}**",
        "",
        "## Doctor snapshot",
        f"- Doctor OK: **{doctor.get('ok')}**",
        f"- Doctor score: **{doctor.get('score')}**",
        f"- Failed checks: **{doctor.get('failed_checks')}**",
        "",
        "## First-run triage hints",
        f"- Hint count: **{triage.get('hint_count', 0)}**",
    ]

    hints = triage.get("priority_hints", [])
    if isinstance(hints, list) and hints:
        lines.append("")
        for row in hints[:10]:
            if isinstance(row, dict):
                lines.append(f"- {row.get('source', 'unknown')}: {row.get('hint', '')}")

    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifacts-dir", default="docs/artifacts")
    ap.add_argument("--out-md", default="docs/artifacts/adaptive-ops-summary-latest.md")
    ap.add_argument("--out-json", default="docs/artifacts/adaptive-ops-summary-latest.json")
    args = ap.parse_args()

    artifacts_dir = Path(args.artifacts_dir)
    scenario_path = _latest_artifact(artifacts_dir, "adaptive-scenario-database-")
    postcheck_path = _latest_artifact(artifacts_dir, "adaptive-postcheck-")
    if scenario_path is None or postcheck_path is None:
        missing = []
        if scenario_path is None:
            missing.append("adaptive-scenario-database-*.json")
        if postcheck_path is None:
            missing.append("adaptive-postcheck-*.json")
        raise SystemExit(f"missing required artifacts: {', '.join(missing)}")

    payload = {
        "schema_version": "sdetkit.adaptive-ops-summary.v1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "scenario_db_path": scenario_path.as_posix(),
        "postcheck_path": postcheck_path.as_posix(),
        "scenario_db": _read_json(scenario_path),
        "postcheck": _read_json(postcheck_path),
    }

    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    out_md = Path(args.out_md)
    out_md.write_text(_md_summary(payload), encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": True,
                "scenario_total": payload["scenario_db"]["summary"].get("total_scenarios", 0),
                "postcheck_ok": payload["postcheck"]["summary"].get("ok", False),
                "out_md": out_md.as_posix(),
                "out_json": out_json.as_posix(),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
