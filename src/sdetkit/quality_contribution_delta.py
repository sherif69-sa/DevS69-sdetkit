from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from . import weekly_review

_REQUIRED_SIGNAL_KEYS = ("traffic", "stars", "discussions", "blocker_fixes")
_CONTRIBUTION_WEIGHTS = {
    "traffic": 0.35,
    "stars": 0.25,
    "discussions": 0.20,
    "blocker_fixes": 0.20,
}


def _load_signals(path: str) -> dict[str, int]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("signals file must contain a JSON object")
    validated: dict[str, int] = {}
    for key in _REQUIRED_SIGNAL_KEYS:
        value = payload.get(key)
        if not isinstance(value, int):
            raise ValueError(f"signals.{key} must be an integer")
        validated[key] = value
    return validated


def _delta_status(value: int) -> str:
    if value > 0:
        return "up"
    if value < 0:
        return "down"
    return "flat"


def _safe_pct_delta(current: int, previous: int) -> float:
    if previous == 0:
        return 100.0 if current > 0 else 0.0
    return round(((current - previous) / previous) * 100, 2)


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _build_recommendations(
    quality_deltas: dict[str, int], contribution_deltas: dict[str, int]
) -> list[str]:
    notes: list[str] = []
    if quality_deltas["completion_rate_percent"] < 0:
        notes.append(
            "Recover week-two completion rate by rerunning missing Day 8-13 closeout checks."
        )
    if quality_deltas["artifact_coverage"] < 0:
        notes.append(
            "Regenerate missing artifacts and attach pack evidence before sprint closeout."
        )
    if contribution_deltas["traffic"] < 0:
        notes.append(
            "Increase release-note and docs distribution cadence to recover traffic trend."
        )
    if contribution_deltas["stars"] < 0:
        notes.append("Refresh README CTA blocks and promote newcomer issues in community channels.")
    if contribution_deltas["discussions"] < 0:
        notes.append(
            "Run weekly office hours and prompt issue discussions with maintainer responses."
        )
    if contribution_deltas["blocker_fixes"] < 0:
        notes.append("Escalate blocker-fix SLA ownership and add a daily remediation checkpoint.")
    if not notes:
        notes.append(
            "All tracked deltas are stable or improving; preserve current operating cadence."
        )
    return notes


def _evaluate_gates(payload: dict[str, Any], thresholds: dict[str, int]) -> list[str]:
    failures: list[str] = []
    contribution_deltas = payload["contributions"]["deltas"]
    for key, minimum in thresholds.items():
        value = contribution_deltas[key]
        if value < minimum:
            failures.append(f"{key} delta {value:+d} fell below minimum {minimum:+d}")

    quality_deltas = payload["quality"]["deltas"]
    if quality_deltas["completion_rate_percent"] < 0:
        failures.append("completion_rate_percent delta fell below minimum +0")
    if quality_deltas["artifact_coverage"] < 0:
        failures.append("artifact_coverage delta fell below minimum +0")
    return failures


def build_delta_report(
    repo_root: Path, current_signals: dict[str, int], previous_signals: dict[str, int]
) -> dict[str, Any]:
    week1 = weekly_review.build_weekly_review(repo_root, week=1)
    week2 = weekly_review.build_weekly_review(repo_root, week=2)

    quality_deltas = {
        "completion_rate_percent": week2.kpis["completion_rate_percent"]
        - week1.kpis["completion_rate_percent"],
        "artifact_coverage": week2.kpis["artifact_coverage"] - week1.kpis["artifact_coverage"],
        "runnable_commands": week2.kpis["runnable_commands"] - week1.kpis["runnable_commands"],
    }
    contribution_deltas = {
        key: current_signals[key] - previous_signals[key] for key in _REQUIRED_SIGNAL_KEYS
    }
    contribution_pct_deltas = {
        key: _safe_pct_delta(current_signals[key], previous_signals[key])
        for key in _REQUIRED_SIGNAL_KEYS
    }

    quality_stability_score = round(
        _clamp(
            100
            + (quality_deltas["completion_rate_percent"] * 0.8)
            + (quality_deltas["artifact_coverage"] * 2.0)
            + (quality_deltas["runnable_commands"] * 4.0)
        ),
        2,
    )

    contribution_velocity_score = 0.0
    for key, weight in _CONTRIBUTION_WEIGHTS.items():
        contribution_velocity_score += (
            _clamp(50 + contribution_pct_deltas[key], 0.0, 100.0) * weight
        )
    contribution_velocity_score = round(contribution_velocity_score, 2)

    recommendations = _build_recommendations(quality_deltas, contribution_deltas)

    return {
        "name": "day17-quality-contribution-delta",
        "quality": {
            "week1": week1.kpis,
            "week2": week2.kpis,
            "deltas": quality_deltas,
            "delta_status": {key: _delta_status(value) for key, value in quality_deltas.items()},
            "stability_score": quality_stability_score,
        },
        "contributions": {
            "current": current_signals,
            "previous": previous_signals,
            "deltas": contribution_deltas,
            "delta_percent": contribution_pct_deltas,
            "delta_status": {
                key: _delta_status(value) for key, value in contribution_deltas.items()
            },
            "velocity_score": contribution_velocity_score,
        },
        "recommendations": recommendations,
    }


def _render_text(payload: dict[str, Any]) -> str:
    qd = payload["quality"]["deltas"]
    cd = payload["contributions"]["deltas"]
    cp = payload["contributions"]["delta_percent"]
    lines = [
        "Day 17 quality + contribution delta pack",
        "",
        "Quality week-over-week deltas:",
        f"- Completion rate delta: {qd['completion_rate_percent']:+d}",
        f"- Artifact coverage delta: {qd['artifact_coverage']:+d}",
        f"- Runnable commands delta: {qd['runnable_commands']:+d}",
        f"- Stability score: {payload['quality']['stability_score']}",
        "",
        "Contribution week-over-week deltas:",
        f"- Traffic delta: {cd['traffic']:+d} ({cp['traffic']:+.2f}%)",
        f"- Stars delta: {cd['stars']:+d} ({cp['stars']:+.2f}%)",
        f"- Discussions delta: {cd['discussions']:+d} ({cp['discussions']:+.2f}%)",
        f"- Blocker fixes delta: {cd['blocker_fixes']:+d} ({cp['blocker_fixes']:+.2f}%)",
        f"- Contribution velocity score: {payload['contributions']['velocity_score']}",
        "",
        "Recommendations:",
    ]
    lines.extend(f"- {item}" for item in payload["recommendations"])
    return "\n".join(lines) + "\n"


def _render_markdown(payload: dict[str, Any]) -> str:
    qd = payload["quality"]["deltas"]
    cd = payload["contributions"]["deltas"]
    cp = payload["contributions"]["delta_percent"]
    lines = [
        "# Day 17 quality + contribution delta pack",
        "",
        "## Quality deltas",
        "",
        f"- Completion rate delta: **{qd['completion_rate_percent']:+d}**",
        f"- Artifact coverage delta: **{qd['artifact_coverage']:+d}**",
        f"- Runnable commands delta: **{qd['runnable_commands']:+d}**",
        f"- Stability score: **{payload['quality']['stability_score']}**",
        "",
        "## Contribution deltas",
        "",
        f"- Traffic delta: **{cd['traffic']:+d} ({cp['traffic']:+.2f}%)**",
        f"- Stars delta: **{cd['stars']:+d} ({cp['stars']:+.2f}%)**",
        f"- Discussions delta: **{cd['discussions']:+d} ({cp['discussions']:+.2f}%)**",
        f"- Blocker fixes delta: **{cd['blocker_fixes']:+d} ({cp['blocker_fixes']:+.2f}%)**",
        f"- Contribution velocity score: **{payload['contributions']['velocity_score']}**",
        "",
        "## Recommendations",
        "",
    ]
    lines.extend(f"- {item}" for item in payload["recommendations"])
    return "\n".join(lines) + "\n"


def _emit_pack(repo_root: Path, out_dir: str, payload: dict[str, Any]) -> list[str]:
    root = repo_root / out_dir
    root.mkdir(parents=True, exist_ok=True)

    summary = root / "day17-delta-summary.json"
    summary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    quality_md = root / "day17-quality-scorecard.md"
    quality_md.write_text(
        "\n".join(
            [
                "# Day 17 quality scorecard",
                "",
                f"- Completion rate delta: {payload['quality']['deltas']['completion_rate_percent']:+d}",
                f"- Artifact coverage delta: {payload['quality']['deltas']['artifact_coverage']:+d}",
                f"- Runnable commands delta: {payload['quality']['deltas']['runnable_commands']:+d}",
                f"- Stability score: {payload['quality']['stability_score']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    action_plan = root / "day17-contribution-action-plan.md"
    action_plan.write_text(
        "\n".join(
            [
                "# Day 17 contribution action plan",
                "",
                "| Signal | Delta | Delta % | Action |",
                "| --- | --- | --- | --- |",
                f"| Traffic | {payload['contributions']['deltas']['traffic']:+d} | {payload['contributions']['delta_percent']['traffic']:+.2f}% | keep release-note distribution and docs resharing cadence |",
                f"| Stars | {payload['contributions']['deltas']['stars']:+d} | {payload['contributions']['delta_percent']['stars']:+.2f}% | continue CTA placement in onboarding/docs pages |",
                f"| Discussions | {payload['contributions']['deltas']['discussions']:+d} | {payload['contributions']['delta_percent']['discussions']:+.2f}% | run weekly office-hours and issue triage prompts |",
                f"| Blocker fixes | {payload['contributions']['deltas']['blocker_fixes']:+d} | {payload['contributions']['delta_percent']['blocker_fixes']:+.2f}% | preserve owner + SLA tracking in weekly sync |",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    checklist = root / "day17-remediation-checklist.md"
    checklist.write_text(
        "\n".join(
            [
                "# Day 17 remediation checklist",
                "",
                "- [ ] Review quality stability score and confirm no downward regression.",
                "- [ ] Review contribution velocity score and assign owner for any negative signal.",
                "- [ ] Attach day17-delta-summary.json to weekly closeout update.",
                "- [ ] Record SLA owner and due date for each recommendation item.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    return [
        str(path.relative_to(repo_root)) for path in (summary, quality_md, action_plan, checklist)
    ]


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sdetkit quality-contribution-delta",
        description="Build Day 17 week-over-week quality and contribution delta evidence.",
    )
    p.add_argument("--root", default=".", help="Repository root path.")
    p.add_argument(
        "--current-signals-file", required=True, help="Current-week growth signal JSON file."
    )
    p.add_argument(
        "--previous-signals-file", required=True, help="Previous-week growth signal JSON file."
    )
    p.add_argument(
        "--emit-pack-dir",
        default="",
        help="Optional output directory for Day 17 evidence pack files.",
    )
    p.add_argument(
        "--strict", action="store_true", help="Return non-zero when strict delta gates fail."
    )
    p.add_argument(
        "--min-traffic-delta", type=int, default=0, help="Strict gate minimum for traffic delta."
    )
    p.add_argument(
        "--min-stars-delta", type=int, default=0, help="Strict gate minimum for stars delta."
    )
    p.add_argument(
        "--min-discussions-delta",
        type=int,
        default=0,
        help="Strict gate minimum for discussions delta.",
    )
    p.add_argument(
        "--min-blocker-fixes-delta",
        type=int,
        default=0,
        help="Strict gate minimum for blocker_fixes delta.",
    )
    p.add_argument("--format", choices=["text", "json", "markdown"], default="text")
    p.add_argument("--output", default=None, help="Optional output path for rendered report.")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    repo_root = Path(args.root).resolve()
    current = _load_signals(args.current_signals_file)
    previous = _load_signals(args.previous_signals_file)
    payload = build_delta_report(repo_root, current, previous)

    thresholds = {
        "traffic": args.min_traffic_delta,
        "stars": args.min_stars_delta,
        "discussions": args.min_discussions_delta,
        "blocker_fixes": args.min_blocker_fixes_delta,
    }
    strict_failures = _evaluate_gates(payload, thresholds)
    if strict_failures:
        payload["strict_failures"] = strict_failures

    if args.emit_pack_dir:
        payload["pack_files"] = _emit_pack(repo_root, args.emit_pack_dir, payload)

    if args.format == "json":
        rendered = json.dumps(payload, indent=2) + "\n"
    elif args.format == "markdown":
        rendered = _render_markdown(payload)
    else:
        rendered = _render_text(payload)

    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")

    if args.strict and strict_failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
