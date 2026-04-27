from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _load_optional(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def build_followup(
    *,
    fit_payload: dict[str, Any] | None,
    summary_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    actions: list[dict[str, str]] = []
    fit = "unknown"
    if fit_payload is None:
        actions.append(
            {
                "priority": "P0",
                "title": "Generate fit recommendation",
                "action": "make fit-check",
            }
        )
    else:
        fit = str(fit_payload.get("fit", "unknown"))
        if fit in {"high", "medium"}:
            actions.append(
                {
                    "priority": "P0",
                    "title": "Adopt canonical gate lane in CI",
                    "action": "python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json && python -m sdetkit gate release --format json --out build/release-preflight.json",
                }
            )
        else:
            actions.append(
                {
                    "priority": "P1",
                    "title": "Run lightweight lane only",
                    "action": "python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json",
                }
            )

    if summary_payload is None:
        actions.append(
            {
                "priority": "P0",
                "title": "Generate reviewer decision artifacts",
                "action": "make gate-decision-summary && make gate-decision-summary-contract",
            }
        )
        decision = "NO-DATA"
    else:
        decision = str(summary_payload.get("decision", "NO-DATA"))
        if decision == "NO-SHIP":
            actions.append(
                {
                    "priority": "P0",
                    "title": "Remediate first failing release step",
                    "action": "Inspect build/release-preflight.json failed_steps and fix first blocker before rerun.",
                }
            )
        else:
            actions.append(
                {
                    "priority": "P2",
                    "title": "Attach decision summary to PR/release thread",
                    "action": "Link build/gate-decision-summary.md in reviewer handoff notes.",
                }
            )
        if summary_payload.get("validation_errors"):
            actions.append(
                {
                    "priority": "P0",
                    "title": "Clear summary validation errors",
                    "action": "Run make gate-decision-summary-contract and resolve listed mismatches.",
                }
            )

    actions.sort(key=lambda item: {"P0": 0, "P1": 1, "P2": 2}.get(item["priority"], 9))
    top = actions[0] if actions else {"priority": "P2", "title": "No action", "action": "none"}
    return {
        "schema_version": "sdetkit.adoption_followup.v1",
        "fit": fit,
        "decision": decision,
        "next_command": top["action"],
        "recommendations": actions,
    }


def _to_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Adoption follow-up",
        "",
        f"- Fit: `{payload['fit']}`",
        f"- Decision: `{payload['decision']}`",
        f"- Next command: `{payload['next_command']}`",
        "",
        "## Recommendations",
    ]
    for idx, rec in enumerate(payload["recommendations"], start=1):
        lines.append(f"{idx}. **[{rec['priority']}] {rec['title']}** — `{rec['action']}`")
    lines.append("")
    return "\n".join(lines)


def _append_history(payload: dict[str, Any], history_path: Path) -> dict[str, Any]:
    history_path.parent.mkdir(parents=True, exist_ok=True)
    stamped = {"generated_at": datetime.now(UTC).isoformat(), **payload}
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(stamped, sort_keys=True) + "\n")
    return stamped


def _build_history_rollup(history_path: Path) -> dict[str, Any]:
    runs: list[dict[str, Any]] = []
    if history_path.exists():
        for line in history_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                runs.append(payload)
    decision_counts: dict[str, int] = {}
    fit_counts: dict[str, int] = {}
    p0_runs = 0
    consecutive_no_ship = 0
    max_consecutive_no_ship = 0
    for run in runs:
        decision = str(run.get("decision", "UNKNOWN"))
        decision_counts[decision] = decision_counts.get(decision, 0) + 1
        fit = str(run.get("fit", "unknown"))
        fit_counts[fit] = fit_counts.get(fit, 0) + 1
        recs = run.get("recommendations", [])
        if isinstance(recs, list) and any(
            isinstance(item, dict) and str(item.get("priority")) == "P0" for item in recs
        ):
            p0_runs += 1
        if decision == "NO-SHIP":
            consecutive_no_ship += 1
            max_consecutive_no_ship = max(max_consecutive_no_ship, consecutive_no_ship)
        else:
            consecutive_no_ship = 0
    latest = runs[-1] if runs else {}
    total_runs = len(runs)
    p0_rate = (p0_runs / total_runs) if total_runs else 0.0
    escalation_recommended = max_consecutive_no_ship >= 2 or (total_runs >= 3 and p0_rate >= 0.5)
    escalation_reason = "none"
    if max_consecutive_no_ship >= 2:
        escalation_reason = "consecutive_no_ship"
    elif total_runs >= 3 and p0_rate >= 0.5:
        escalation_reason = "high_p0_rate"
    return {
        "schema_version": "sdetkit.adoption_followup_history.v1",
        "total_runs": total_runs,
        "decision_counts": decision_counts,
        "fit_counts": fit_counts,
        "p0_recommendation_runs": p0_runs,
        "p0_recommendation_rate": round(p0_rate, 3),
        "max_consecutive_no_ship": max_consecutive_no_ship,
        "escalation_recommended": escalation_recommended,
        "escalation_reason": escalation_reason,
        "latest_next_command": latest.get("next_command", ""),
        "latest_generated_at": latest.get("generated_at", ""),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit adoption",
        description="Build prioritized adoption follow-up actions from fit and gate decision artifacts.",
    )
    parser.add_argument("--fit", type=Path, default=Path("build/sdetkit-fit-recommendation.json"))
    parser.add_argument("--summary", type=Path, default=Path("build/gate-decision-summary.json"))
    parser.add_argument("--format", choices=["json", "md"], default="json")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--history", type=Path, default=None)
    parser.add_argument("--history-rollup-out", type=Path, default=None)
    args = parser.parse_args(argv)

    payload = build_followup(
        fit_payload=_load_optional(args.fit),
        summary_payload=_load_optional(args.summary),
    )
    if args.history is not None:
        payload = _append_history(payload, args.history)
    if args.history_rollup_out is not None and args.history is not None:
        rollup = _build_history_rollup(args.history)
        args.history_rollup_out.parent.mkdir(parents=True, exist_ok=True)
        args.history_rollup_out.write_text(
            json.dumps(rollup, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    rendered = json.dumps(payload, indent=2, sort_keys=True) if args.format == "json" else _to_markdown(payload)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + ("\n" if not rendered.endswith("\n") else ""), encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
