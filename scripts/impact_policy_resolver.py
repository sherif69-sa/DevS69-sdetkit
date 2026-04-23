from __future__ import annotations

import fnmatch


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
