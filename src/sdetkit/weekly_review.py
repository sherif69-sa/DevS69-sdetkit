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
    DayShipped(1, "Core positioning + role onboarding", "docs/day-1-ultra-upgrade-report.md", "docs/artifacts/day1-onboarding-sample.md", "python -m sdetkit onboarding --format text"),
    DayShipped(2, "60-second demo workflow", "docs/day-2-ultra-upgrade-report.md", "docs/artifacts/day2-demo-sample.md", "python -m sdetkit demo --execute --format text"),
    DayShipped(3, "Proof pack with runnable checks", "docs/day-3-ultra-upgrade-report.md", "docs/artifacts/day3-proof-sample.md", "python -m sdetkit proof --execute --strict --format text"),
    DayShipped(4, "Template/skill expansion run-all", "docs/day-4-ultra-upgrade-report.md", "docs/artifacts/day4-skills-sample.md", "python -m sdetkit agent templates run-all --output-dir .sdetkit/agent/template-runs"),
    DayShipped(5, "Cross-platform onboarding snippets", "docs/day-5-ultra-upgrade-report.md", "docs/artifacts/day5-platform-onboarding-sample.md", "python -m sdetkit onboarding --format text --platform all"),
    DayShipped(6, "Docs conversion QA gate", "docs/day-6-ultra-upgrade-report.md", "docs/artifacts/day6-conversion-qa-sample.md", "python -m sdetkit docs-qa --format text"),
)


@dataclass(frozen=True)
class WeeklyReview:
    week: int
    shipped: tuple[dict[str, object], ...]
    kpis: dict[str, int]
    next_week_focus: tuple[str, ...]


def build_weekly_review(repo_root: Path) -> WeeklyReview:
    shipped: list[dict[str, object]] = []
    for day in DAY1_TO_6:
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
        "days_planned": len(DAY1_TO_6),
        "completion_rate_percent": int((shipped_count / len(DAY1_TO_6)) * 100),
        "runnable_commands": len(DAY1_TO_6),
        "artifact_coverage": sum(1 for item in shipped if item["artifact_exists"]),
    }

    next_week_focus = (
        "Day 8: publish 10 curated good-first-issue tasks with clear acceptance criteria.",
        "Day 9: tighten issue/PR templates to reduce triage response time.",
        "Day 10: add first-contribution checklist from clone to first merged PR.",
    )

    return WeeklyReview(week=1, shipped=tuple(shipped), kpis=kpis, next_week_focus=next_week_focus)


def _render_text(review: WeeklyReview) -> str:
    lines = [
        "Day 7 weekly review #1",
        "",
        "What shipped (Day 1-6):",
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
            "",
            "Next-week focus:",
        ]
    )
    lines.extend(f"- {item}" for item in review.next_week_focus)
    return "\n".join(lines) + "\n"


def _render_markdown(review: WeeklyReview) -> str:
    lines = [
        "# Day 7 Weekly Review #1",
        "",
        "## What shipped (Day 1-6)",
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
            "",
            "## Next-week focus",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in review.next_week_focus)
    return "\n".join(lines) + "\n"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sdetkit weekly-review", description="Generate Day 7 weekly review summary.")
    p.add_argument("--root", default=".", help="Repository root path.")
    p.add_argument("--format", choices=["text", "json", "markdown"], default="text")
    p.add_argument("--output", default=None, help="Optional output path for the report.")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    review = build_weekly_review(Path(args.root).resolve())

    if args.format == "json":
        rendered = json.dumps(
            {
                "week": review.week,
                "shipped": list(review.shipped),
                "kpis": review.kpis,
                "next_week_focus": list(review.next_week_focus),
            },
            indent=2,
        ) + "\n"
    elif args.format == "markdown":
        rendered = _render_markdown(review)
    else:
        rendered = _render_text(review)

    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
