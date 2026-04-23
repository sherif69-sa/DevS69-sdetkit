from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REQUIRED_KEYS = {
    "schema_version",
    "head_regression_drop_threshold",
    "fail_on_overall_regression",
    "fail_on_head_regression",
    "min_step_scores",
    "min_overall_program_score",
    "branch_overrides",
}


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_policy(policy: dict[str, object]) -> list[str]:
    errors: list[str] = []
    missing = REQUIRED_KEYS - set(policy.keys())
    if missing:
        errors.append(f"missing keys: {sorted(missing)}")

    threshold = policy.get("head_regression_drop_threshold")
    if not isinstance(threshold, (int, float)) or float(threshold) <= 0:
        errors.append("head_regression_drop_threshold must be > 0")

    min_overall = policy.get("min_overall_program_score")
    if not isinstance(min_overall, (int, float)) or not (0 <= float(min_overall) <= 100):
        errors.append("min_overall_program_score must be between 0 and 100")

    min_steps = policy.get("min_step_scores")
    if not isinstance(min_steps, dict):
        errors.append("min_step_scores must be an object")
    else:
        for name in ("step_1", "step_2", "step_3"):
            value = min_steps.get(name)
            if not isinstance(value, (int, float)) or not (0 <= float(value) <= 100):
                errors.append(f"min_step_scores.{name} must be between 0 and 100")

    overrides = policy.get("branch_overrides")
    if not isinstance(overrides, dict):
        errors.append("branch_overrides must be an object")
    else:
        for pattern, override in overrides.items():
            if not isinstance(pattern, str) or not pattern.strip():
                errors.append("branch override pattern must be a non-empty string")
            if not isinstance(override, dict):
                errors.append(f"branch override for {pattern} must be an object")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate impact policy schema and thresholds.")
    parser.add_argument("--policy", default="config/impact_policy.json")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    policy_path = Path(args.policy)
    if not policy_path.is_file():
        print(f"impact policy validate failed: missing policy {policy_path}", file=sys.stderr)
        return 1

    policy = _read_json(policy_path)
    errors = validate_policy(policy)
    payload = {
        "schema_version": "sdetkit.impact-policy-validation.v1",
        "ok": not errors,
        "policy": str(policy_path),
        "errors": errors,
    }

    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"impact policy validate: ok={payload['ok']} errors={len(errors)}")
        for err in errors:
            print(f"- {err}")

    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
