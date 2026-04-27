from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _priority(level: str) -> int:
    return {"P0": 0, "P1": 1, "P2": 2, "P3": 3}.get(level, 9)


def _load_history(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _append_history(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, sort_keys=True) + "\n")


def _build_history_rollup(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    ship = sum(1 for row in rows if row.get("decision") == "SHIP")
    no_ship = sum(1 for row in rows if row.get("decision") != "SHIP")
    breach_count = sum(1 for row in rows if bool(row.get("threshold_breach", False)))
    ship_rate = (ship / total) if total else 0.0

    action_counts: dict[str, int] = {}
    for row in rows:
        recs = row.get("recommendations")
        if not isinstance(recs, list):
            continue
        for rec in recs:
            if not isinstance(rec, dict):
                continue
            title = rec.get("title")
            if isinstance(title, str):
                action_counts[title] = action_counts.get(title, 0) + 1
    top_actions = sorted(action_counts.items(), key=lambda kv: kv[1], reverse=True)[:5]

    return {
        "schema_version": "sdetkit.real-workflow-followup-history-rollup.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "summary": {
            "total_runs": total,
            "ship_runs": ship,
            "no_ship_runs": no_ship,
            "threshold_breach_runs": breach_count,
            "ship_rate": ship_rate,
            "top_recurring_recommendations": [
                {"title": title, "count": count} for title, count in top_actions
            ],
        },
    }


def build_followup(
    summary: dict[str, Any],
    rollup: dict[str, Any],
    threshold: dict[str, Any],
    release_preflight: dict[str, Any],
) -> dict[str, Any]:
    decision = str(summary.get("decision", "NO-SHIP"))
    failed_steps = summary.get("failed_steps", [])
    if not isinstance(failed_steps, list):
        failed_steps = []

    top_failed = []
    rollup_summary = rollup.get("summary", {}) if isinstance(rollup, dict) else {}
    if isinstance(rollup_summary, dict):
        top_failed = rollup_summary.get("top_failed_steps", [])
    if not isinstance(top_failed, list):
        top_failed = []

    breach = bool(threshold.get("breach", False)) if isinstance(threshold, dict) else False
    release_failed_steps = []
    release_recommendations = []
    if isinstance(release_preflight, dict):
        failed_steps_payload = release_preflight.get("failed_steps", [])
        if isinstance(failed_steps_payload, list):
            release_failed_steps = [step for step in failed_steps_payload if isinstance(step, str)]
        recommendations_payload = release_preflight.get("recommendations", [])
        if isinstance(recommendations_payload, list):
            release_recommendations = [
                rec for rec in recommendations_payload if isinstance(rec, str)
            ]

    recs: list[dict[str, str]] = []
    if decision != "SHIP":
        recs.append(
            {
                "priority": "P0",
                "title": "Recover to SHIP on the failing gate",
                "action": "Run `make ops-daily` after fixing the first failing step and do not merge until decision is SHIP.",
            }
        )

    if failed_steps:
        first_failed = failed_steps[0]
        recs.append(
            {
                "priority": "P1",
                "title": "Resolve first failing step",
                "action": f"Focus on `{first_failed}` first; it is blocking deterministic release confidence.",
            }
        )

    for item in top_failed[:3]:
        if not isinstance(item, dict):
            continue
        step = item.get("step")
        count = item.get("count")
        if isinstance(step, str) and isinstance(count, int):
            recs.append(
                {
                    "priority": "P2",
                    "title": f"Reduce recurring failures in {step}",
                    "action": f"{step} failed {count} times in recent history; add a targeted regression check before pre-merge.",
                }
            )

    if breach:
        recs.append(
            {
                "priority": "P0",
                "title": "Threshold breach escalation",
                "action": "Run `make owner-escalation-payload` and assign an owner with SLA before the next release window.",
            }
        )

    if "doctor_release" in release_failed_steps:
        recs.append(
            {
                "priority": "P0",
                "title": "Unblock release doctor checks",
                "action": "Doctor release checks are failing (often clean-tree). Commit/stash changes, then rerun `make ops-daily`.",
            }
        )
    if release_recommendations:
        recs.append(
            {
                "priority": "P1",
                "title": "Apply release preflight recommendation",
                "action": release_recommendations[0],
            }
        )

    if decision == "SHIP" and not breach:
        recs.append(
            {
                "priority": "P3",
                "title": "Proceed to pre-merge verification",
                "action": "Run `make ops-premerge` and publish release-room evidence before merge/tag.",
            }
        )

    recs.sort(key=lambda item: _priority(item.get("priority", "P9")))

    return {
        "schema_version": "sdetkit.real-workflow-followup.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "decision": decision,
        "threshold_breach": breach,
        "recommendations": recs,
        "next_command": "make ops-daily" if decision != "SHIP" else "make ops-premerge",
    }


def render_markdown(payload: dict[str, Any]) -> str:
    decision = payload.get("decision", "NO-SHIP")
    breach = payload.get("threshold_breach", False)
    lines = [
        "# Real workflow follow-up",
        "",
        f"- Decision: **{decision}**",
        f"- Threshold breach: **{breach}**",
        f"- Suggested next command: `{payload.get('next_command', 'make ops-daily')}`",
        "",
        "## Recommendations",
    ]
    recs = payload.get("recommendations", [])
    if not isinstance(recs, list) or not recs:
        lines.append("- No follow-up actions generated.")
        return "\n".join(lines) + "\n"

    for idx, rec in enumerate(recs, start=1):
        if not isinstance(rec, dict):
            continue
        lines.append(
            f"{idx}. [{rec.get('priority', 'P?')}] **{rec.get('title', 'Action')}** — {rec.get('action', '')}"
        )

    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate real workflow follow-up recommendations")
    parser.add_argument(
        "--summary", type=Path, default=Path("build/first-proof/first-proof-summary.json")
    )
    parser.add_argument(
        "--rollup", type=Path, default=Path("build/first-proof/first-proof-learning-rollup.json")
    )
    parser.add_argument(
        "--threshold", type=Path, default=Path("build/first-proof/weekly-threshold-check.json")
    )
    parser.add_argument(
        "--release-preflight",
        type=Path,
        default=Path("build/first-proof/release-preflight.json"),
    )
    parser.add_argument("--out-json", type=Path, default=Path("build/ops/followup.json"))
    parser.add_argument("--out-md", type=Path, default=Path("build/ops/followup.md"))
    parser.add_argument("--history", type=Path, default=Path("build/ops/followup-history.jsonl"))
    parser.add_argument(
        "--history-rollup-out", type=Path, default=Path("build/ops/followup-history-rollup.json")
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    summary = _read_json(args.summary)
    rollup = _read_json(args.rollup)
    threshold = _read_json(args.threshold)
    release_preflight = _read_json(args.release_preflight)

    payload = build_followup(summary, rollup, threshold, release_preflight)
    markdown = render_markdown(payload)

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.out_md.write_text(markdown, encoding="utf-8")
    _append_history(args.history, payload)
    history_rows = _load_history(args.history)
    history_rollup = _build_history_rollup(history_rows)
    args.history_rollup_out.parent.mkdir(parents=True, exist_ok=True)
    args.history_rollup_out.write_text(
        json.dumps(history_rollup, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    if args.format == "json":
        print(
            json.dumps(
                {
                    "ok": True,
                    "out_json": str(args.out_json),
                    "out_md": str(args.out_md),
                    "history": str(args.history),
                    "history_rollup": str(args.history_rollup_out),
                    "history_total_runs": history_rollup["summary"]["total_runs"],
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(f"follow-up json: {args.out_json}")
        print(f"follow-up md: {args.out_md}")
        print(f"follow-up history: {args.history}")
        print(f"follow-up history rollup: {args.history_rollup_out}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
