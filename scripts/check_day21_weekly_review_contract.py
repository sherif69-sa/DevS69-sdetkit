from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    required = [
        ROOT / "docs/day-20-ultra-upgrade-report.md",
        ROOT / "docs/day-21-ultra-upgrade-report.md",
        ROOT / "docs/artifacts/day20-release-narrative-sample.md",
        ROOT / "docs/artifacts/day21-growth-signals.json",
        ROOT / "docs/artifacts/day21-weekly-review-sample.md",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    if missing:
        raise SystemExit(f"Missing Day 21 contract files: {', '.join(missing)}")

    weekly_review = (ROOT / "src/sdetkit/weekly_review.py").read_text(encoding="utf-8")
    if "choices=[1, 2, 3]" not in weekly_review:
        raise SystemExit("weekly-review parser must support --week 3")
    if "def _emit_week3_pack" not in weekly_review:
        raise SystemExit("weekly-review must implement a week-3 closeout pack emitter")

    cli_doc = (ROOT / "docs/cli.md").read_text(encoding="utf-8")
    if "Day 21/week 3" not in cli_doc:
        raise SystemExit("docs/cli.md must document Day 21 week 3 support")
    if "day21-weekly-pack" not in cli_doc:
        raise SystemExit("docs/cli.md must include week-3 emit-pack example")

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    if "day21-weekly-pack" not in readme:
        raise SystemExit("README.md must include week-3 emit-pack usage")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
