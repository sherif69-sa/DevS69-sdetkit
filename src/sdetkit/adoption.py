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
    actions: list[dict[str, Any]] = []
    fit = "unknown"
    if fit_payload is None:
        actions.append(
            {
                "priority": "P0",
                "title": "Generate fit recommendation",
                "action": "make fit-check",
                "rationale": "fit artifact is missing so rollout depth cannot be selected confidently",
                "_score": 100,
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
                        "rationale": "higher-risk profile benefits from consistent CI gating before expanding rollout",
                        "_score": 80 if fit == "high" else 60,
                    }
                )
        else:
            actions.append(
                {
                    "priority": "P1",
                    "title": "Run lightweight lane only",
                    "action": "python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json",
                    "rationale": "low-risk profile can start with lower-overhead signal collection",
                    "_score": 40,
                }
            )

    if summary_payload is None:
        actions.append(
            {
                "priority": "P0",
                "title": "Generate reviewer decision artifacts",
                "action": "make gate-decision-summary && make gate-decision-summary-contract",
                "rationale": "review handoff cannot be trusted until the decision summary and contract both exist",
                "_score": 95,
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
                        "rationale": "shipping is currently blocked and remediation unblocks the control loop",
                        "_score": 98,
                    }
                )
        else:
            actions.append(
                {
                    "priority": "P2",
                    "title": "Attach decision summary to PR/release thread",
                    "action": "Link build/gate-decision-summary.md in reviewer handoff notes.",
                    "rationale": "decision already allows shipping; this improves traceability rather than unblocking risk",
                    "_score": 20,
                }
            )
            if fit in {"high", "medium"}:
                actions.append(
                    {
                        "priority": "P1",
                        "title": "Run adoption control-loop before merge",
                        "action": "make adoption-control-loop && make adoption-control-loop-contract",
                        "rationale": "risk profile indicates value in enforcing follow-up and contract evidence each cycle",
                        "_score": 55 if fit == "high" else 50,
                    }
                )
        if summary_payload.get("validation_errors"):
            actions.append(
                {
                    "priority": "P0",
                    "title": "Clear summary validation errors",
                    "action": "Run make gate-decision-summary-contract and resolve listed mismatches.",
                    "rationale": "contract mismatches undermine artifact reliability for reviewers and CI",
                    "_score": 97,
                }
            )

    actions.sort(
        key=lambda item: (
            {"P0": 0, "P1": 1, "P2": 2}.get(str(item.get("priority")), 9),
            -int(item.get("_score", 0)),
            str(item.get("title", "")),
        )
    )
    normalized: list[dict[str, str]] = []
    for item in actions:
        normalized.append(
            {
                "priority": str(item["priority"]),
                "title": str(item["title"]),
                "action": str(item["action"]),
                "rationale": str(item.get("rationale", "")),
            }
        )
    top = normalized[0] if normalized else {"priority": "P2", "title": "No action", "action": "none", "rationale": ""}
    return {
        "schema_version": "sdetkit.adoption_followup.v1",
        "fit": fit,
        "decision": decision,
        "next_command": top["action"],
        "recommendations": normalized,
    }


def _to_markdown(payload: dict[str, Any]) -> str:
    decision_note = {
        "NO-SHIP": "Release is currently blocked; prioritize remediation and contract consistency.",
        "SHIP": "Release is currently allowed; focus on reproducibility and evidence hygiene.",
        "NO-DATA": "Decision artifacts are missing; generate summary + contract outputs first.",
    }.get(str(payload.get("decision")), "Decision state unknown; verify gate artifacts.")
    lines = [
        "# Adoption follow-up",
        "",
        f"- Fit: `{payload['fit']}`",
        f"- Decision: `{payload['decision']}`",
        f"- Next command: `{payload['next_command']}`",
        f"- Why now: {decision_note}",
        "",
        "## Recommendations",
    ]
    for idx, rec in enumerate(payload["recommendations"], start=1):
        lines.append(f"{idx}. **[{rec['priority']}] {rec['title']}** — `{rec['action']}`")
        rationale = str(rec.get("rationale", "")).strip()
        if rationale:
            lines.append(f"   - Rationale: {rationale}")
    lines.append("")
    return "\n".join(lines)


def _append_history(payload: dict[str, Any], history_path: Path) -> dict[str, Any]:
    history_path.parent.mkdir(parents=True, exist_ok=True)
    stamped = {"generated_at": datetime.now(UTC).isoformat(), **payload}
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(stamped, sort_keys=True) + "\n")
    return stamped


def _build_history_rollup(
    history_path: Path,
    *,
    escalation_consecutive_no_ship: int,
    escalation_min_runs: int,
    escalation_min_p0_rate: float,
) -> dict[str, Any]:
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
    escalation_recommended = max_consecutive_no_ship >= escalation_consecutive_no_ship or (
        total_runs >= escalation_min_runs and p0_rate >= escalation_min_p0_rate
    )
    escalation_reason = "none"
    if max_consecutive_no_ship >= escalation_consecutive_no_ship:
        escalation_reason = "consecutive_no_ship"
    elif total_runs >= escalation_min_runs and p0_rate >= escalation_min_p0_rate:
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
        "thresholds": {
            "escalation_consecutive_no_ship": escalation_consecutive_no_ship,
            "escalation_min_runs": escalation_min_runs,
            "escalation_min_p0_rate": escalation_min_p0_rate,
        },
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
    parser.add_argument("--escalation-consecutive-no-ship", type=int, default=2)
    parser.add_argument("--escalation-min-runs", type=int, default=3)
    parser.add_argument("--escalation-min-p0-rate", type=float, default=0.5)
    args = parser.parse_args(argv)

    payload = build_followup(
        fit_payload=_load_optional(args.fit),
        summary_payload=_load_optional(args.summary),
    )
    if args.history is not None:
        payload = _append_history(payload, args.history)
    if args.history_rollup_out is not None and args.history is not None:
        rollup = _build_history_rollup(
            args.history,
            escalation_consecutive_no_ship=max(1, int(args.escalation_consecutive_no_ship)),
            escalation_min_runs=max(1, int(args.escalation_min_runs)),
            escalation_min_p0_rate=max(0.0, min(1.0, float(args.escalation_min_p0_rate))),
        )
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
