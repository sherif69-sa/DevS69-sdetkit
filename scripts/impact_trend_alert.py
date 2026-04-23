from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

import fnmatch


HEADS = (
    "security_head",
    "reliability_head",
    "velocity_head",
    "governance_head",
    "observability_head",
)


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
            "schema_version": "sdetkit.impact-policy.v1",
            "head_regression_drop_threshold": 5.0,
            "fail_on_overall_regression": True,
            "fail_on_head_regression": True,
        }
    return json.loads(path.read_text(encoding="utf-8"))


def _recent_scores(db_path: Path, window: int) -> list[float]:
    if not db_path.is_file():
        return []
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT overall_score FROM impact_runs ORDER BY id DESC LIMIT ?",
            (window,),
        ).fetchall()
    return [float(row[0]) for row in rows]


def _streak(scores: list[float]) -> str:
    if len(scores) < 3:
        return "insufficient-data"
    newest, prev, older = scores[0], scores[1], scores[2]
    if newest > prev > older:
        return "improving"
    if newest < prev < older:
        return "regressing"
    return "flat"


def _head_regressions(db_path: Path, drop_threshold: float) -> list[dict[str, object]]:
    if not db_path.is_file():
        return []
    with sqlite3.connect(db_path) as conn:
        run_rows = conn.execute("SELECT id FROM impact_runs ORDER BY id DESC LIMIT 2").fetchall()
        if len(run_rows) < 2:
            return []
        newest, previous = int(run_rows[0][0]), int(run_rows[1][0])

        alerts: list[dict[str, object]] = []
        for head in HEADS:
            latest_row = conn.execute(
                "SELECT score FROM impact_head_scores WHERE run_id = ? AND head = ?",
                (newest, head),
            ).fetchone()
            previous_row = conn.execute(
                "SELECT score FROM impact_head_scores WHERE run_id = ? AND head = ?",
                (previous, head),
            ).fetchone()
            if latest_row is None or previous_row is None:
                continue
            delta = float(latest_row[0]) - float(previous_row[0])
            if delta < -drop_threshold:
                alerts.append({"head": head, "delta": round(delta, 2), "threshold": drop_threshold})
        return alerts


def evaluate(db_path: Path, window: int, policy: dict[str, object]) -> dict[str, object]:
    scores = _recent_scores(db_path, window)
    streak = _streak(scores)
    drop_threshold = float(policy.get("head_regression_drop_threshold", 5.0))
    head_alerts = _head_regressions(db_path, drop_threshold)

    overall_ok = not (bool(policy.get("fail_on_overall_regression", True)) and streak == "regressing")
    head_ok = not (bool(policy.get("fail_on_head_regression", True)) and len(head_alerts) > 0)
    ok = overall_ok and head_ok

    return {
        "schema_version": "sdetkit.impact-trend-alert.v2",
        "scores": scores,
        "streak": streak,
        "head_alerts": head_alerts,
        "policy": policy,
        "ok": ok,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate trend alert from impact intelligence DB.")
    parser.add_argument("--db-path", default="build/impact-intelligence.db")
    parser.add_argument("--policy", default="config/impact_policy.json")
    parser.add_argument("--window", type=int, default=3)
    parser.add_argument("--branch", default="")
    parser.add_argument("--out", default="build/impact-trend-alert.json")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    raw_policy = _read_policy(Path(args.policy))
    policy = resolve_policy_for_branch(raw_policy, args.branch) if args.branch else raw_policy
    payload = evaluate(Path(args.db_path), args.window, policy)
    payload["branch"] = args.branch
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"impact trend alert: streak={payload['streak']} head_alerts={len(payload['head_alerts'])} ok={payload['ok']}")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
