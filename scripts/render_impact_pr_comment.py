from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

RUNBOOKS = {
    "security_head": "docs/toolkit-reliability-slo.md",
    "reliability_head": "docs/determinism-checklist.md",
    "velocity_head": "docs/recommended-ci-flow.md",
    "governance_head": "docs/repo-tour.md",
    "observability_head": "docs/artifacts/adaptive-ops-summary-latest.md",
}


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _status_emoji(status: str) -> str:
    mapping = {"strong": "🟢", "watch": "🟡", "critical": "🔴"}
    return mapping.get(status, "⚪")


def _recent_scores(build_dir: Path, limit: int) -> list[float]:
    db_path = build_dir / "impact-intelligence.db"
    if not db_path.is_file():
        return []
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT overall_score FROM impact_runs ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [float(row[0]) for row in rows]


def _score_delta(build_dir: Path) -> float | None:
    scores = _recent_scores(build_dir, 2)
    if len(scores) < 2:
        return None
    return round(scores[0] - scores[1], 2)


def _three_run_streak(build_dir: Path) -> str:
    scores = _recent_scores(build_dir, 3)
    if len(scores) < 3:
        return "insufficient-data"
    newest, prev, older = scores[0], scores[1], scores[2]
    if newest > prev > older:
        return "improving"
    if newest < prev < older:
        return "regressing"
    return "flat"


def render_comment(build_dir: Path) -> str:
    guard = _read_json(build_dir / "impact-release-guard.json")
    review = _read_json(build_dir / "impact-adaptive-review.json")
    next_plan = _read_json(build_dir / "impact-next-plan.json")
    trend_path = build_dir / "impact-trend-alert.json"
    trend = (
        _read_json(trend_path)
        if trend_path.is_file()
        else {"streak": "insufficient-data", "ok": True}
    )
    step1_path = build_dir / "impact-step1-scorecard.json"
    step1 = (
        _read_json(step1_path) if step1_path.is_file() else {"achieved_pct": 0, "status": "unknown"}
    )
    program_path = build_dir / "impact-program-scorecard.json"
    program = (
        _read_json(program_path)
        if program_path.is_file()
        else {"overall_score": 0, "status": "unknown"}
    )
    step_cards_path = build_dir / "impact-step-scorecards.json"
    step_cards = _read_json(step_cards_path) if step_cards_path.is_file() else {"scorecards": {}}

    now_actions = next_plan.get("now", [])
    if not isinstance(now_actions, list):
        now_actions = []

    status = str(review.get("status", "unknown"))
    emoji = _status_emoji(status)
    delta = _score_delta(build_dir)
    delta_text = "n/a" if delta is None else (f"{delta:+.2f}")
    streak = _three_run_streak(build_dir)
    trend_gate = "pass" if trend.get("ok", True) else "alert"
    weakest_head = str(review.get("weakest_head", "unknown"))
    runbook = RUNBOOKS.get(weakest_head, "docs/index.md")
    step1_pct = step1.get("achieved_pct", 0)
    step1_status = step1.get("status", "unknown")
    program_overall = program.get("overall_score", 0)
    program_status = program.get("status", "unknown")
    cards = (
        step_cards.get("scorecards", {}) if isinstance(step_cards.get("scorecards"), dict) else {}
    )
    step2_pct = (
        cards.get("step_2", {}).get("achieved_pct", 0)
        if isinstance(cards.get("step_2"), dict)
        else 0
    )
    step2_status = (
        cards.get("step_2", {}).get("status", "unknown")
        if isinstance(cards.get("step_2"), dict)
        else "unknown"
    )
    step3_pct = (
        cards.get("step_3", {}).get("achieved_pct", 0)
        if isinstance(cards.get("step_3"), dict)
        else 0
    )
    step3_status = (
        cards.get("step_3", {}).get("status", "unknown")
        if isinstance(cards.get("step_3"), dict)
        else "unknown"
    )

    lines = [
        "## Impact Release Control Summary",
        "",
        f"- Release guard: **{'PASS' if guard.get('ok') else 'BLOCKED'}**",
        f"- Guard reason: `{guard.get('reason', 'unknown')}`",
        f"- Adaptive score: `{review.get('overall_score', 0)}`",
        f"- Adaptive status: {emoji} `{status}`",
        f"- Score delta (vs previous run): `{delta_text}`",
        f"- 3-run streak: `{streak}`",
        f"- Trend gate: `{trend_gate}`",
        f"- Weakest head: `{weakest_head}`",
        f"- Suggested runbook: `{runbook}`",
        f"- Phase 1-2 achievement: `{step1_pct}%` (`{step1_status}`)",
        f"- Program achieved: `{program_overall}` (`{program_status}`)",
        f"- Phase 3-4 achievement: `{step2_pct}%` (`{step2_status}`)",
        f"- Phase 5-6 achievement: `{step3_pct}%` (`{step3_status}`)",
        "",
        "### Immediate Actions",
    ]

    if now_actions:
        for item in now_actions[:5]:
            lines.append(f"- [ ] {item}")
    else:
        lines.append("- [ ] No immediate blockers from current run.")

    if trend.get("ok") is False:
        lines.extend(["", "> ⚠️ Trend alert: score is regressing across recent runs."])

    lines.extend(
        [
            "",
            "### Artifacts",
            "- `build/impact-release-guard.json`",
            "- `build/impact-adaptive-review.json`",
            "- `build/impact-next-plan.json`",
            "- `build/impact-intelligence.db`",
            "- `build/impact-trend-alert.json`",
            "- `build/impact-step1-scorecard.json`",
            "- `build/impact-program-scorecard.json`",
            "- `build/impact-step-scorecards.json`",
        ]
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render PR-comment markdown from impact artifacts."
    )
    parser.add_argument("--build-dir", default="build")
    parser.add_argument("--out", default="build/impact-pr-comment.md")
    args = parser.parse_args(argv)

    text = render_comment(Path(args.build_dir))
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
