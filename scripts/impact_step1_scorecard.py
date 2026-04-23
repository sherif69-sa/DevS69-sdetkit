from __future__ import annotations

import argparse
import json
from pathlib import Path


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_scorecard(build_dir: Path) -> dict[str, object]:
    run = _read_json(build_dir / "impact-workflow-run.json")
    review = _read_json(build_dir / "impact-adaptive-review.json")
    criteria = _read_json(build_dir / "impact-criteria-report.json")

    step1 = next((item for item in run.get("steps", []) if item.get("step") == "step_1"), {})
    readiness = step1.get("phase_readiness", {}) if isinstance(step1, dict) else {}

    completion = float(step1.get("completion_pct", 0) if isinstance(step1, dict) else 0)
    criteria_completion = float(criteria.get("completion_pct", 0))
    security_score = float(review.get("heads", {}).get("security_head", {}).get("score", 0))
    reliability_score = float(review.get("heads", {}).get("reliability_head", {}).get("score", 0))

    achieved = round((completion * 0.5) + (criteria_completion * 0.2) + (security_score * 0.15) + (reliability_score * 0.15), 2)

    return {
        "schema_version": "sdetkit.impact-step1-scorecard.v1",
        "step": "step_1",
        "achieved_pct": achieved,
        "inputs": {
            "step1_completion_pct": completion,
            "criteria_completion_pct": criteria_completion,
            "security_head_score": security_score,
            "reliability_head_score": reliability_score,
        },
        "phase_readiness": readiness,
        "status": "strong" if achieved >= 90 else "watch" if achieved >= 75 else "blocked",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build Step 1 achievement scorecard from impact artifacts.")
    parser.add_argument("--build-dir", default="build")
    parser.add_argument("--out", default="build/impact-step1-scorecard.json")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    payload = build_scorecard(Path(args.build_dir))
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"step1 scorecard: achieved_pct={payload['achieved_pct']} status={payload['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
