from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DayShipped:
    day: int
    title: str
    report_path: str
    artifact_path: str
    command: str


DAY1_TO_6: tuple[DayShipped, ...] = (
    DayShipped(
        1,
        "Core positioning + role onboarding",
        "docs/day-1-ultra-upgrade-report.md",
        "docs/artifacts/day1-onboarding-sample.md",
        "python -m sdetkit onboarding --format text",
    ),
    DayShipped(
        2,
        "60-second demo workflow",
        "docs/day-2-ultra-upgrade-report.md",
        "docs/artifacts/day2-demo-sample.md",
        "python -m sdetkit demo --execute --format text",
    ),
    DayShipped(
        3,
        "Proof pack with runnable checks",
        "docs/day-3-ultra-upgrade-report.md",
        "docs/artifacts/day3-proof-sample.md",
        "python -m sdetkit proof --execute --strict --format text",
    ),
    DayShipped(
        4,
        "Template/skill expansion run-all",
        "docs/day-4-ultra-upgrade-report.md",
        "docs/artifacts/day4-skills-sample.md",
        "python -m sdetkit agent templates run-all --output-dir .sdetkit/agent/template-runs",
    ),
    DayShipped(
        5,
        "Cross-platform onboarding snippets",
        "docs/day-5-ultra-upgrade-report.md",
        "docs/artifacts/day5-platform-onboarding-sample.md",
        "python -m sdetkit onboarding --format text --platform all",
    ),
    DayShipped(
        6,
        "Docs conversion QA gate",
        "docs/day-6-ultra-upgrade-report.md",
        "docs/artifacts/day6-conversion-qa-sample.md",
        "python -m sdetkit docs-qa --format text",
    ),
)

DAY8_TO_13: tuple[DayShipped, ...] = (
    DayShipped(
        8,
        "Good-first-issue accelerator pack",
        "docs/day-8-ultra-upgrade-report.md",
        "docs/artifacts/day8-good-first-issues-sample.md",
        "python -m sdetkit contributor-funnel --format markdown --output docs/artifacts/day8-good-first-issues-sample.md --strict",
    ),
    DayShipped(
        9,
        "Triage-ready issue + PR templates",
        "docs/day-9-ultra-upgrade-report.md",
        "docs/artifacts/day9-triage-templates-sample.md",
        "python -m sdetkit triage-templates --format markdown --output docs/artifacts/day9-triage-templates-sample.md --strict",
    ),
    DayShipped(
        10,
        "First-contribution checklist",
        "docs/day-10-ultra-upgrade-report.md",
        "docs/artifacts/day10-first-contribution-checklist-sample.md",
        "python -m sdetkit first-contribution --format markdown --output docs/artifacts/day10-first-contribution-checklist-sample.md --strict",
    ),
    DayShipped(
        11,
        "Docs navigation tune-up",
        "docs/day-11-ultra-upgrade-report.md",
        "docs/artifacts/day11-docs-navigation-sample.md",
        "python -m sdetkit docs-nav --format markdown --output docs/artifacts/day11-docs-navigation-sample.md --strict",
    ),
    DayShipped(
        12,
        "Startup/small-team workflow",
        "docs/day-12-ultra-upgrade-report.md",
        "docs/artifacts/day12-startup-use-case-sample.md",
        "python -m sdetkit startup-use-case --format markdown --output docs/artifacts/day12-startup-use-case-sample.md --strict",
    ),
    DayShipped(
        13,
        "Enterprise/regulated workflow",
        "docs/day-13-ultra-upgrade-report.md",
        "docs/artifacts/day13-enterprise-use-case-sample.md",
        "python -m sdetkit enterprise-use-case --format markdown --output docs/artifacts/day13-enterprise-use-case-sample.md --strict",
    ),
)

DAY15_TO_20: tuple[DayShipped, ...] = (
    DayShipped(
        15,
        "GitHub Actions integration quickstart",
        "docs/day-15-ultra-upgrade-report.md",
        "docs/artifacts/day15-github-actions-quickstart-sample.md",
        "python -m sdetkit github-actions-quickstart --format json --strict",
    ),
    DayShipped(
        16,
        "GitLab CI integration quickstart",
        "docs/day-16-ultra-upgrade-report.md",
        "docs/artifacts/day16-gitlab-ci-quickstart-sample.md",
        "python -m sdetkit gitlab-ci-quickstart --format json --strict",
    ),
    DayShipped(
        17,
        "Quality + contribution delta evidence",
        "docs/day-17-ultra-upgrade-report.md",
        "docs/artifacts/day17-quality-contribution-delta-sample.md",
        "python -m sdetkit quality-contribution-delta --current-signals-file docs/artifacts/day17-growth-signals.json --previous-signals-file docs/artifacts/day14-growth-signals.json --format json --strict",
    ),
    DayShipped(
        18,
        "Reliability evidence operating pack",
        "docs/day-18-ultra-upgrade-report.md",
        "docs/artifacts/day18-reliability-evidence-pack-sample.md",
        "python -m sdetkit reliability-evidence-pack --format json --strict",
    ),
    DayShipped(
        19,
        "Release readiness board",
        "docs/day-19-ultra-upgrade-report.md",
        "docs/artifacts/day19-release-readiness-board-sample.md",
        "python -m sdetkit release-readiness-board --format json --strict",
    ),
    DayShipped(
        20,
        "Release narrative storytelling pack",
        "docs/day-20-ultra-upgrade-report.md",
        "docs/artifacts/day20-release-narrative-sample.md",
        "python -m sdetkit weekly-review --week 3 --format markdown --signals-file docs/artifacts/day21-growth-signals.json --previous-signals-file docs/artifacts/day14-growth-signals.json --output docs/artifacts/day21-weekly-review-sample.md",
    ),
)

_GROWTH_KEYS = ("traffic", "stars", "discussions", "blocker_fixes")


@dataclass(frozen=True)
class WeeklyReview:
    week: int
    shipped: tuple[dict[str, object], ...]
    kpis: dict[str, int]
    next_week_focus: tuple[str, ...]
    growth_signals: dict[str, int] | None
    growth_deltas: dict[str, int] | None


def _validate_signals(signals: dict[str, int] | None) -> dict[str, int] | None:
    if signals is None:
        return None
    validated: dict[str, int] = {}
    for key in _GROWTH_KEYS:
        value = signals.get(key)
        if not isinstance(value, int):
            raise ValueError(f"signals.{key} must be an integer")
        validated[key] = value
    return validated


def _load_signals(path: str) -> dict[str, int]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("signals file must contain a JSON object")
    return _validate_signals(payload) or {}


def build_weekly_review(
    repo_root: Path,
    week: int = 1,
    signals: dict[str, int] | None = None,
    previous_signals: dict[str, int] | None = None,
) -> WeeklyReview:
    if week == 3:
        shipped_days = DAY15_TO_20
        next_week_focus = (
            "Day 22: strengthen trust signals across security and reliability entry points.",
            "Day 23: publish FAQ responses for recurring adoption objections.",
            "Day 24: cut onboarding time-to-first-success below three minutes.",
        )
    elif week == 2:
        shipped_days = DAY8_TO_13
        next_week_focus = (
            "Day 15: refine multi-channel distribution loop for documentation and demos.",
            "Day 16: publish adoption-ready workflow templates with copy/paste CI variants.",
            "Day 17: capture week-over-week quality + contribution deltas in one evidence pack.",
        )
    else:
        shipped_days = DAY1_TO_6
        next_week_focus = (
            "Day 8: publish 10 curated good-first-issue tasks with clear acceptance criteria.",
            "Day 9: tighten issue/PR templates to reduce triage response time.",
            "Day 10: add first-contribution checklist from clone to first merged PR.",
        )

    shipped: list[dict[str, object]] = []
    for day in shipped_days:
        report_exists = (repo_root / day.report_path).exists()
        artifact_exists = (repo_root / day.artifact_path).exists()
        shipped.append(
            {
                "day": day.day,
                "title": day.title,
                "report": day.report_path,
                "artifact": day.artifact_path,
                "command": day.command,
                "report_exists": report_exists,
                "artifact_exists": artifact_exists,
                "status": "shipped" if report_exists and artifact_exists else "incomplete",
            }
        )

    shipped_count = sum(1 for item in shipped if item["status"] == "shipped")
    kpis = {
        "days_completed": shipped_count,
        "days_planned": len(shipped_days),
        "completion_rate_percent": int((shipped_count / len(shipped_days)) * 100),
        "runnable_commands": len(shipped_days),
        "artifact_coverage": sum(1 for item in shipped if item["artifact_exists"]),
    }

    current = _validate_signals(signals)
    previous = _validate_signals(previous_signals)
    deltas = None
    if current and previous:
        deltas = {key: current[key] - previous[key] for key in _GROWTH_KEYS}

    return WeeklyReview(
        week=week,
        shipped=tuple(shipped),
        kpis=kpis,
        next_week_focus=next_week_focus,
        growth_signals=current,
        growth_deltas=deltas,
    )


def _render_text(review: WeeklyReview) -> str:
    review_day = 21 if review.week == 3 else 14 if review.week == 2 else 7
    shipped_window = (
        "Day 15-20" if review.week == 3 else "Day 8-13" if review.week == 2 else "Day 1-6"
    )
    lines = [
        f"Day {review_day} weekly review #{review.week}",
        "",
        f"What shipped ({shipped_window}):",
    ]
    for item in review.shipped:
        mark = "✅" if item["status"] == "shipped" else "⚠️"
        lines.append(
            f"- {mark} Day {item['day']}: {item['title']} | report={item['report_exists']} artifact={item['artifact_exists']}"
        )

    lines.extend(
        [
            "",
            "KPI movement:",
            f"- Completion: {review.kpis['days_completed']}/{review.kpis['days_planned']} ({review.kpis['completion_rate_percent']}%)",
            f"- Runnable command paths: {review.kpis['runnable_commands']}",
            f"- Artifact coverage: {review.kpis['artifact_coverage']}/{review.kpis['days_planned']}",
        ]
    )

    if review.growth_signals:
        lines.extend(
            [
                "",
                f"Week-{review.week} growth signals:",
                f"- Traffic: {review.growth_signals['traffic']}",
                f"- Stars: {review.growth_signals['stars']}",
                f"- Discussions: {review.growth_signals['discussions']}",
                f"- Blocker fixes: {review.growth_signals['blocker_fixes']}",
            ]
        )
    if review.growth_deltas:
        lines.extend(
            [
                "",
                "Week-over-week deltas:",
                f"- Traffic: {review.growth_deltas['traffic']:+d}",
                f"- Stars: {review.growth_deltas['stars']:+d}",
                f"- Discussions: {review.growth_deltas['discussions']:+d}",
                f"- Blocker fixes: {review.growth_deltas['blocker_fixes']:+d}",
            ]
        )

    lines.extend(["", "Next-week focus:"])
    lines.extend(f"- {item}" for item in review.next_week_focus)
    return "\n".join(lines) + "\n"


def _render_markdown(review: WeeklyReview) -> str:
    review_day = 21 if review.week == 3 else 14 if review.week == 2 else 7
    shipped_window = (
        "Day 15-20" if review.week == 3 else "Day 8-13" if review.week == 2 else "Day 1-6"
    )
    lines = [
        f"# Day {review_day} Weekly Review #{review.week}",
        "",
        f"## What shipped ({shipped_window})",
        "",
        "| Day | Upgrade | Report | Artifact | Status |",
        "| --- | --- | --- | --- | --- |",
    ]

    for item in review.shipped:
        status = "shipped ✅" if item["status"] == "shipped" else "incomplete ⚠️"
        lines.append(
            f"| {item['day']} | {item['title']} | `{item['report']}` | `{item['artifact']}` | {status} |"
        )

    lines.extend(
        [
            "",
            "## KPI movement",
            "",
            f"- Completion rate: **{review.kpis['days_completed']}/{review.kpis['days_planned']} ({review.kpis['completion_rate_percent']}%)**",
            f"- Runnable command paths delivered: **{review.kpis['runnable_commands']}**",
            f"- Artifact coverage: **{review.kpis['artifact_coverage']}/{review.kpis['days_planned']}**",
        ]
    )

    if review.growth_signals:
        lines.extend(
            [
                "",
                f"## Week-{review.week} growth signals",
                "",
                f"- Traffic: **{review.growth_signals['traffic']}**",
                f"- Stars: **{review.growth_signals['stars']}**",
                f"- Discussions: **{review.growth_signals['discussions']}**",
                f"- Blocker fixes: **{review.growth_signals['blocker_fixes']}**",
            ]
        )

    if review.growth_deltas:
        lines.extend(
            [
                "",
                "## Week-over-week deltas",
                "",
                f"- Traffic: **{review.growth_deltas['traffic']:+d}**",
                f"- Stars: **{review.growth_deltas['stars']:+d}**",
                f"- Discussions: **{review.growth_deltas['discussions']:+d}**",
                f"- Blocker fixes: **{review.growth_deltas['blocker_fixes']:+d}**",
            ]
        )

    lines.extend(["", "## Next-week focus", ""])
    lines.extend(f"- {item}" for item in review.next_week_focus)
    return "\n".join(lines) + "\n"


def _emit_week2_pack(base: Path, out_dir: str, review: WeeklyReview) -> list[str]:
    root = base / out_dir
    root.mkdir(parents=True, exist_ok=True)

    checklist = root / "day14-closeout-checklist.md"
    checklist.write_text(
        "\n".join(
            [
                "# Day 14 closeout checklist",
                "",
                "- [ ] Run `sdetkit weekly-review --week 2 --format text` and verify all Day 8-13 items are shipped.",
                "- [ ] Refresh markdown artifact and attach it to the status update.",
                "- [ ] Update growth signals JSON (traffic, stars, discussions, blocker_fixes).",
                "- [ ] Review blocker-fix owners and confirm SLA commitments for next sprint.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    scorecard = root / "day14-kpi-scorecard.json"
    scorecard.write_text(
        json.dumps(
            {
                "week": review.week,
                "kpis": review.kpis,
                "growth_signals": review.growth_signals,
                "growth_deltas": review.growth_deltas,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    action_plan = root / "day14-blocker-action-plan.md"
    action_plan.write_text(
        "\n".join(
            [
                "# Day 14 blocker action plan",
                "",
                "| Blocker | Owner | Target date | Mitigation |",
                "| --- | --- | --- | --- |",
                "| Missing contributor responses | Maintainer on-call | +2 days | tighten template auto-labeling and triage SLA reminders |",
                "| Slow docs feedback turnaround | Docs owner | +3 days | schedule twice-weekly docs office-hours review |",
                "| CI flake investigation backlog | QE lead | +5 days | split flaky jobs, add retry visibility and quarantine workflow |",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    return [str(path.relative_to(base)) for path in (checklist, scorecard, action_plan)]


def _emit_week3_pack(base: Path, out_dir: str, review: WeeklyReview) -> list[str]:
    root = base / out_dir
    root.mkdir(parents=True, exist_ok=True)

    checklist = root / "day21-closeout-checklist.md"
    checklist.write_text(
        "\n".join(
            [
                "# Day 21 closeout checklist",
                "",
                "- [ ] Run `sdetkit weekly-review --week 3 --format text --signals-file docs/artifacts/day21-growth-signals.json --previous-signals-file docs/artifacts/day14-growth-signals.json` and verify all Day 15-20 items are shipped.",
                "- [ ] Refresh markdown artifact and attach it to sprint closeout notes.",
                "- [ ] Publish external contributor response summary with owners and SLA.",
                "- [ ] Confirm Day 22 trust-signal backlog priorities are assigned.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    scorecard = root / "day21-kpi-scorecard.json"
    scorecard.write_text(
        json.dumps(
            {
                "week": review.week,
                "kpis": review.kpis,
                "growth_signals": review.growth_signals,
                "growth_deltas": review.growth_deltas,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    discussions = review.growth_signals["discussions"] if review.growth_signals else "n/a"
    stars = review.growth_signals["stars"] if review.growth_signals else "n/a"
    blocker_fixes = review.growth_signals["blocker_fixes"] if review.growth_signals else "n/a"
    discussions_delta = review.growth_deltas["discussions"] if review.growth_deltas else "n/a"
    stars_delta = review.growth_deltas["stars"] if review.growth_deltas else "n/a"
    blocker_fixes_delta = review.growth_deltas["blocker_fixes"] if review.growth_deltas else "n/a"

    contributor_plan = root / "day21-contributor-response-plan.md"
    contributor_plan.write_text(
        "\n".join(
            [
                "# Day 21 contributor response plan",
                "",
                "| Signal | Current | Delta vs week 2 | Owner | Next action |",
                "| --- | --- | --- | --- | --- |",
                f"| Discussions | {discussions} | {discussions_delta} | Community manager | answer open threads and tag good-first-issue candidates |",
                f"| Stars | {stars} | {stars_delta} | Maintainer on-call | post release highlights and triage incoming watchers |",
                f"| Blocker fixes | {blocker_fixes} | {blocker_fixes_delta} | QE lead | prioritize unresolved failures before Day 22 hardening |",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    traffic_delta = f"{review.growth_deltas['traffic']:+d}" if review.growth_deltas else "n/a"
    discussions_delta_fmt = (
        f"{review.growth_deltas['discussions']:+d}" if review.growth_deltas else "n/a"
    )

    narrative_brief = root / "day21-release-narrative-brief.md"
    narrative_brief.write_text(
        "\n".join(
            [
                "# Day 21 release narrative brief",
                "",
                "## Storyline",
                "",
                "Week 3 converts integration work into a measurable release lane with deterministic evidence and contributor-response visibility.",
                "",
                "## KPI highlights",
                "",
                f"- Completion: {review.kpis['days_completed']}/{review.kpis['days_planned']} ({review.kpis['completion_rate_percent']}%)",
                f"- Traffic delta: {traffic_delta}",
                f"- Discussions delta: {discussions_delta_fmt}",
                "",
                "## Messaging channels",
                "",
                "- Engineering sync: share week-3 scorecard + next-week trust-signal focus.",
                "- OSS community post: publish contributor-response plan and open Day 22-24 asks.",
                "- Release notes: link Day 18/19/21 artifacts for non-maintainer context.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    return [
        str(path.relative_to(base))
        for path in (checklist, scorecard, contributor_plan, narrative_brief)
    ]


def _emit_pack(base: Path, out_dir: str, review: WeeklyReview) -> list[str]:
    if review.week == 2:
        return _emit_week2_pack(base, out_dir, review)
    if review.week == 3:
        return _emit_week3_pack(base, out_dir, review)
    return []


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sdetkit weekly-review", description="Generate day-based weekly review summaries."
    )
    p.add_argument("--root", default=".", help="Repository root path.")
    p.add_argument(
        "--week",
        type=int,
        choices=[1, 2, 3],
        default=1,
        help="Weekly review window (1=Day 1-6, 2=Day 8-13, 3=Day 15-20).",
    )
    p.add_argument(
        "--signals-file",
        default="",
        help="Optional JSON file with week growth signals: traffic, stars, discussions, blocker_fixes.",
    )
    p.add_argument(
        "--previous-signals-file",
        default="",
        help="Optional previous-week JSON signal file to compute week-over-week deltas.",
    )
    p.add_argument(
        "--emit-pack-dir",
        default="",
        help="Optional output directory to emit week closeout pack files (week 2 and week 3).",
    )
    p.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero if shipped coverage is incomplete (or growth signals are missing for week 2/3).",
    )
    p.add_argument("--format", choices=["text", "json", "markdown"], default="text")
    p.add_argument("--output", default=None, help="Optional output path for the report.")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    signals = _load_signals(args.signals_file) if args.signals_file else None
    previous_signals = (
        _load_signals(args.previous_signals_file) if args.previous_signals_file else None
    )

    review = build_weekly_review(
        Path(args.root).resolve(),
        week=args.week,
        signals=signals,
        previous_signals=previous_signals,
    )

    payload: dict[str, object] = {
        "week": review.week,
        "shipped": list(review.shipped),
        "kpis": review.kpis,
        "next_week_focus": list(review.next_week_focus),
    }

    if review.growth_signals:
        payload["growth_signals"] = review.growth_signals
    if review.growth_deltas:
        payload["growth_deltas"] = review.growth_deltas

    if args.emit_pack_dir:
        payload["pack_files"] = _emit_pack(Path(args.root).resolve(), args.emit_pack_dir, review)

    if args.format == "json":
        rendered = json.dumps(payload, indent=2) + "\n"
    elif args.format == "markdown":
        rendered = _render_markdown(review)
    else:
        rendered = _render_text(review)

    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")

    if args.strict:
        has_incomplete = any(item["status"] != "shipped" for item in review.shipped)
        missing_signals = args.week in (2, 3) and review.growth_signals is None
        if has_incomplete or missing_signals:
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
