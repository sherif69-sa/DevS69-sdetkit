from __future__ import annotations

import argparse
import json
from pathlib import Path


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _avg(a: float, b: float) -> float:
    return (a + b) / 2.0


def _status(score: float) -> str:
    return "strong" if score >= 90 else "watch" if score >= 75 else "blocked"


def build_scorecards(build_dir: Path) -> dict[str, object]:
    run = _read_json(build_dir / "impact-workflow-run.json")
    review = _read_json(build_dir / "impact-adaptive-review.json")
    criteria = _read_json(build_dir / "impact-criteria-report.json")

    steps = {item.get("step"): item for item in run.get("steps", []) if isinstance(item, dict)}
    heads = review.get("heads", {}) if isinstance(review.get("heads"), dict) else {}

    def step_completion(step: str) -> float:
        return float(steps.get(step, {}).get("completion_pct", 0))

    def head_score(name: str) -> float:
        return float(heads.get(name, {}).get("score", 0)) if isinstance(heads.get(name), dict) else 0.0

    criteria_pct = float(criteria.get("completion_pct", 0))

    scores: dict[str, dict[str, object]] = {}
    recipes = {
        "step_1": ("security_head", "reliability_head"),
        "step_2": ("velocity_head", "governance_head"),
        "step_3": ("observability_head", "reliability_head"),
    }

    for step, (h1, h2) in recipes.items():
        completion = step_completion(step)
        heads_avg = _avg(head_score(h1), head_score(h2))
        achieved = round((completion * 0.55) + (heads_avg * 0.35) + (criteria_pct * 0.10), 2)
        scores[step] = {
            "achieved_pct": achieved,
            "status": _status(achieved),
            "phase_readiness": steps.get(step, {}).get("phase_readiness", {}),
            "inputs": {
                "completion_pct": completion,
                "criteria_completion_pct": criteria_pct,
                h1: head_score(h1),
                h2: head_score(h2),
            },
        }

    return {
        "schema_version": "sdetkit.impact-step-scorecards.v1",
        "scorecards": scores,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build step_1/step_2/step_3 scorecards from impact artifacts.")
    parser.add_argument("--build-dir", default="build")
    parser.add_argument("--out", default="build/impact-step-scorecards.json")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    payload = build_scorecards(Path(args.build_dir))
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        s = payload["scorecards"]
        print(f"step scorecards: s1={s['step_1']['achieved_pct']} s2={s['step_2']['achieved_pct']} s3={s['step_3']['achieved_pct']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
