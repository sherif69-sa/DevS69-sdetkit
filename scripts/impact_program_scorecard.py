from __future__ import annotations

import argparse
import json
from pathlib import Path


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _avg(*values: float) -> float:
    return sum(values) / len(values)


def build_scorecard(build_dir: Path) -> dict[str, object]:
    run = _read_json(build_dir / "impact-workflow-run.json")
    review = _read_json(build_dir / "impact-adaptive-review.json")
    criteria = _read_json(build_dir / "impact-criteria-report.json")

    steps = {item.get("step"): item for item in run.get("steps", []) if isinstance(item, dict)}
    heads = review.get("heads", {}) if isinstance(review.get("heads"), dict) else {}

    def head_score(name: str) -> float:
        return float(heads.get(name, {}).get("score", 0)) if isinstance(heads.get(name), dict) else 0.0

    criteria_pct = float(criteria.get("completion_pct", 0))

    step1_completion = float(steps.get("step_1", {}).get("completion_pct", 0))
    step2_completion = float(steps.get("step_2", {}).get("completion_pct", 0))
    step3_completion = float(steps.get("step_3", {}).get("completion_pct", 0))

    step1 = round((step1_completion * 0.55) + (_avg(head_score("security_head"), head_score("reliability_head")) * 0.35) + (criteria_pct * 0.10), 2)
    step2 = round((step2_completion * 0.55) + (_avg(head_score("velocity_head"), head_score("governance_head")) * 0.35) + (criteria_pct * 0.10), 2)
    step3 = round((step3_completion * 0.55) + (_avg(head_score("observability_head"), head_score("reliability_head")) * 0.35) + (criteria_pct * 0.10), 2)

    overall = round(_avg(step1, step2, step3), 2)
    return {
        "schema_version": "sdetkit.impact-program-scorecard.v1",
        "step_scores": {"step_1": step1, "step_2": step2, "step_3": step3},
        "overall_score": overall,
        "status": "strong" if overall >= 90 else "watch" if overall >= 75 else "blocked",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build multi-step impact program scorecard.")
    parser.add_argument("--build-dir", default="build")
    parser.add_argument("--out", default="build/impact-program-scorecard.json")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    payload = build_scorecard(Path(args.build_dir))
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"impact program scorecard: overall={payload['overall_score']} status={payload['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
