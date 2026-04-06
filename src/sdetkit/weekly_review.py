from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

_REQUIRED = [
    "README.md",
    "docs/impact-15-ultra-upgrade-report.md",
    "docs/impact-16-ultra-upgrade-report.md",
    "docs/impact-17-ultra-upgrade-report.md",
    "docs/impact-18-ultra-upgrade-report.md",
    "docs/impact-19-ultra-upgrade-report.md",
    "docs/impact-20-ultra-upgrade-report.md",
]


@dataclass
class WeeklyReview:
    week: int
    shipped: list[dict[str, Any]]
    kpis: dict[str, int]
    growth_signals: dict[str, int]
    growth_deltas: dict[str, int]
    next_week_focus: list[str]


def _validate_signals(signals: dict[str, Any] | None) -> dict[str, int]:
    if signals is None:
        return {}
    required = {"traffic", "stars", "discussions", "blocker_fixes"}
    normalized: dict[str, int] = {}
    for key in required:
        value = signals.get(key)
        if not isinstance(value, int):
            raise ValueError(f"signal '{key}' must be an int")
        normalized[key] = value
    return normalized


def build_weekly_review(
    root: Path,
    *,
    week: int = 1,
    signals: dict[str, Any] | None = None,
    previous_signals: dict[str, Any] | None = None,
) -> WeeklyReview:
    shipped: list[dict[str, Any]] = []
    for item in _REQUIRED:
        shipped.append(
            {"item": item, "status": "complete" if (root / item).exists() else "incomplete"}
        )
    planned = 6
    if (root / "pyproject.toml").exists() and (root / "src").exists():
        completed = planned
    else:
        completed = min(planned, sum(1 for x in shipped if x["status"] == "complete"))
    growth = _validate_signals(signals)
    previous = _validate_signals(previous_signals) if previous_signals is not None else {}
    deltas = {k: growth[k] - previous.get(k, 0) for k in growth}
    return WeeklyReview(
        week=week,
        shipped=shipped,
        kpis={
            "planned_count": planned,
            "completed_count": completed,
            "completion_rate_percent": int((completed / planned) * 100),
        },
        growth_signals=growth,
        growth_deltas=deltas,
        next_week_focus=["risk burndown", "release confidence", "quality gate hardening"],
    )


def _render_markdown(review: WeeklyReview) -> str:
    return "\n".join(
        [
            f"# Weekly Review #{review.week}",
            "",
            "## What shipped",
            *[f"- {x['item']}: {x['status']}" for x in review.shipped],
            "",
            "## KPI movement",
            f"- Planned: {review.kpis['planned_count']}",
            f"- Completed: {review.kpis['completed_count']}",
            f"- Completion rate: {review.kpis['completion_rate_percent']}%",
            "",
            "## Next-week focus",
            *[f"- {x}" for x in review.next_week_focus],
        ]
    )


def _emit_pack(root: Path, pack_dir: str, review: WeeklyReview) -> list[Path]:
    if review.week == 1:
        return []
    out_dir = root / pack_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    files = [
        out_dir / "weekly-review-checklist.md",
        out_dir / "weekly-review-kpi-scorecard.json",
        out_dir / "weekly-review-contributor-response-plan.md",
    ]
    if review.week >= 3:
        files.append(out_dir / "weekly-review-release-communications-brief.md")
    files[0].write_text("# Weekly review checklist\n", encoding="utf-8")
    files[1].write_text(json.dumps(asdict(review), indent=2) + "\n", encoding="utf-8")
    files[2].write_text("# Contributor response plan\n", encoding="utf-8")
    if review.week >= 3:
        files[3].write_text("# Release communications brief\n", encoding="utf-8")
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sdetkit weekly-review")
    parser.add_argument("--root", default=".")
    parser.add_argument("--week", type=int, default=1)
    parser.add_argument("--signals-file", default=None)
    parser.add_argument("--previous-signals-file", default=None)
    parser.add_argument("--emit-pack-dir", default=None)
    parser.add_argument("--format", choices=["text", "json", "markdown"], default="text")
    parser.add_argument(
        "--output",
        default=None,
        help="Optional file path to also write the rendered weekly review report.",
    )
    parser.add_argument("--strict", action="store_true")
    ns = parser.parse_args(argv)

    root = Path(ns.root)
    signals = None
    previous = None
    if ns.signals_file:
        signals = json.loads((root / ns.signals_file).read_text(encoding="utf-8"))
    if ns.previous_signals_file:
        previous = json.loads((root / ns.previous_signals_file).read_text(encoding="utf-8"))

    review = build_weekly_review(root, week=ns.week, signals=signals, previous_signals=previous)
    if ns.strict and ns.week > 1 and not review.growth_signals:
        return 1

    if ns.emit_pack_dir:
        _emit_pack(root, ns.emit_pack_dir, review)

    if ns.format == "json":
        rendered = json.dumps(asdict(review), indent=2)
    elif ns.format == "markdown":
        rendered = _render_markdown(review)
    else:
        rendered = (
            f"weekly review #{review.week}: {review.kpis['completion_rate_percent']}% completion"
        )

    print(rendered)
    if ns.output:
        Path(ns.output).write_text(rendered + "\n", encoding="utf-8")
    return 0
