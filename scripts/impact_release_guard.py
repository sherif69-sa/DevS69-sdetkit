from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import fnmatch


REQUIRED_FILES = (
    "impact-workflow-run.json",
    "impact-next-plan.json",
    "impact-adaptive-review.json",
    "impact-criteria-report.json",
    "impact-trend-alert.json",
    "impact-program-scorecard.json",
)


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_policy_for_branch(policy: dict[str, object], branch: str) -> dict[str, object]:
    resolved = dict(policy)
    overrides = policy.get("branch_overrides", {})
    if not isinstance(overrides, dict):
        return resolved

    for pattern, override in overrides.items():
        if not isinstance(pattern, str) or not isinstance(override, dict):
            continue
        if fnmatch.fnmatch(branch, pattern):
            merged = dict(resolved)
            for key, value in override.items():
                if key == "min_step_scores" and isinstance(value, dict) and isinstance(merged.get(key), dict):
                    merged_steps = dict(merged[key])
                    merged_steps.update(value)
                    merged[key] = merged_steps
                else:
                    merged[key] = value
            resolved = merged
    return resolved


def _read_policy(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {
            "min_step_scores": {"step_1": 85.0, "step_2": 85.0, "step_3": 85.0},
            "min_overall_program_score": 85.0,
        }
    return _read_json(path)


def evaluate_release_guard(build_dir: Path, policy_path: Path, branch: str) -> dict[str, object]:
    missing: list[str] = []
    for name in REQUIRED_FILES:
        if not (build_dir / name).is_file():
            missing.append(name)

    checks: dict[str, dict[str, object]] = {}
    if missing:
        for name in missing:
            checks[f"file:{name}"] = {"ok": False, "detail": "missing"}
        return {
            "schema_version": "sdetkit.impact-release-guard.v2",
            "ok": False,
            "reason": "missing_artifacts",
            "checks": checks,
        }

    raw_policy = _read_policy(policy_path)
    policy = resolve_policy_for_branch(raw_policy, branch) if branch else raw_policy
    run = _read_json(build_dir / "impact-workflow-run.json")
    next_plan = _read_json(build_dir / "impact-next-plan.json")
    review = _read_json(build_dir / "impact-adaptive-review.json")
    criteria = _read_json(build_dir / "impact-criteria-report.json")
    trend = _read_json(build_dir / "impact-trend-alert.json")
    program = _read_json(build_dir / "impact-program-scorecard.json")

    checks["run_ok"] = {"ok": bool(run.get("ok", False)), "detail": "impact workflow run status"}
    checks["next_plan_ready"] = {
        "ok": next_plan.get("status") == "ready",
        "detail": str(next_plan.get("status")),
    }
    checks["criteria_ok"] = {"ok": bool(criteria.get("ok", False)), "detail": "criteria alignment"}
    checks["trend_ok"] = {"ok": bool(trend.get("ok", False)), "detail": str(trend.get("streak", "unknown"))}
    checks["review_quality"] = {
        "ok": float(review.get("overall_score", 0)) >= 80,
        "detail": f"overall_score={review.get('overall_score', 0)}",
    }

    min_overall = float(policy.get("min_overall_program_score", 85.0))
    checks["program_overall_threshold"] = {
        "ok": float(program.get("overall_score", 0)) >= min_overall,
        "detail": f"score={program.get('overall_score', 0)} min={min_overall}",
    }

    step_scores = program.get("step_scores", {}) if isinstance(program.get("step_scores"), dict) else {}
    min_steps = policy.get("min_step_scores", {}) if isinstance(policy.get("min_step_scores"), dict) else {}
    for step_name in ("step_1", "step_2", "step_3"):
        score = float(step_scores.get(step_name, 0))
        minimum = float(min_steps.get(step_name, 85.0))
        checks[f"{step_name}_threshold"] = {"ok": score >= minimum, "detail": f"score={score} min={minimum}"}

    ok = all(item["ok"] for item in checks.values())
    return {
        "schema_version": "sdetkit.impact-release-guard.v2",
        "ok": ok,
        "reason": "release_ready" if ok else "blocked",
        "checks": checks,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Release-grade guard for impact workflow artifacts.")
    parser.add_argument("--build-dir", default="build")
    parser.add_argument("--policy", default="config/impact_policy.json")
    parser.add_argument("--out", default="build/impact-release-guard.json")
    parser.add_argument("--branch", default="")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    payload = evaluate_release_guard(Path(args.build_dir), Path(args.policy), args.branch)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"impact release guard: ok={payload['ok']} reason={payload['reason']}")

    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
