from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("premerge gate payload must be a JSON object")
    return payload


def _extract_next_actions(payload: dict[str, Any], limit: int) -> list[str]:
    steps = payload.get("steps", [])
    if not isinstance(steps, list):
        return []

    actions: list[str] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        if step.get("id") != "enterprise_assessment":
            continue
        stdout = step.get("stdout")
        if not isinstance(stdout, str) or not stdout.strip():
            continue
        try:
            detail = json.loads(stdout)
        except json.JSONDecodeError:
            continue
        if not isinstance(detail, dict):
            continue
        action_board = detail.get("action_board", {})
        if not isinstance(action_board, dict):
            continue
        next_items = action_board.get("next", [])
        if not isinstance(next_items, list):
            continue
        for item in next_items:
            if not isinstance(item, dict):
                continue
            priority = str(item.get("priority", "P?"))
            action = str(item.get("action", "")).strip()
            check_id = str(item.get("check_id", ""))
            if action:
                suffix = f" ({check_id})" if check_id else ""
                actions.append(f"[{priority}] {action}{suffix}")
    return actions[: max(1, limit)]


def _suggest_fast_premerge(payload: dict[str, Any]) -> bool:
    steps = payload.get("steps", [])
    if not isinstance(steps, list):
        return False

    ship_step = next(
        (
            step
            for step in steps
            if isinstance(step, dict) and step.get("id") == "ship_readiness"
        ),
        None,
    )
    if not isinstance(ship_step, dict):
        return False

    stdout = ship_step.get("stdout")
    if not isinstance(stdout, str) or not stdout.strip():
        return False

    try:
        detail = json.loads(stdout)
    except json.JSONDecodeError:
        return False
    if not isinstance(detail, dict):
        return False

    runs = detail.get("runs", [])
    if isinstance(runs, list):
        for run in runs:
            if not isinstance(run, dict):
                continue
            if str(run.get("id", "")) != "gate_release":
                continue
            parsed = run.get("parsed_json")
            if not isinstance(parsed, dict):
                continue
            failed_steps = parsed.get("failed_steps", [])
            if not isinstance(failed_steps, list):
                continue
            if "doctor_release" not in failed_steps:
                continue
            if _contains_clean_tree_signal(parsed):
                return True
            if _doctor_release_report_indicates_clean_tree():
                return True

    blockers = detail.get("blockers", [])
    if not isinstance(blockers, list):
        return False

    for blocker in blockers:
        if not isinstance(blocker, dict):
            continue
        blocker_id = str(blocker.get("id", "")).lower()
        check_id = str(blocker.get("check_id", "")).lower()
        if "clean_tree" in blocker_id or "clean_tree" in check_id:
            return True
    return False


def _contains_clean_tree_signal(value: Any) -> bool:
    markers = (
        "clean_tree",
        "clean tree",
        "uncommitted change",
        "working tree",
        "git status --porcelain",
    )
    if isinstance(value, str):
        text = value.lower()
        return any(marker in text for marker in markers)
    if isinstance(value, dict):
        return any(_contains_clean_tree_signal(v) for v in value.values())
    if isinstance(value, list):
        return any(_contains_clean_tree_signal(v) for v in value)
    return False


def _doctor_release_report_indicates_clean_tree() -> bool:
    report_path = Path("build/doctor-release.json")
    if not report_path.exists():
        return False
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    if not isinstance(payload, dict):
        return False

    checks = payload.get("checks")
    if not isinstance(checks, dict):
        return False
    clean_tree = checks.get("clean_tree")
    if not isinstance(clean_tree, dict):
        return False
    if clean_tree.get("ok") is False:
        return True

    summary = clean_tree.get("summary", "")
    if isinstance(summary, str) and _contains_clean_tree_signal(summary):
        return True

    evidence = clean_tree.get("evidence", [])
    if isinstance(evidence, list) and _contains_clean_tree_signal(evidence):
        return True
    return False


def build_summary(payload: dict[str, Any], limit: int) -> dict[str, Any]:
    ok = bool(payload.get("ok", False))
    next_actions = _extract_next_actions(payload, limit)
    if ok:
        next_command = "make ops-weekly"
    elif _suggest_fast_premerge(payload):
        next_command = "make ops-premerge-fast"
    else:
        next_command = "make ops-premerge"
    return {
        "ok": ok,
        "next_command": next_command,
        "top_actions": next_actions,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print concise next actions after premerge gate")
    parser.add_argument(
        "--gate-json",
        type=Path,
        default=Path("build/premerge-release-room-gate.json"),
    )
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    payload = _load_json(args.gate_json)
    summary = build_summary(payload, args.limit)

    if args.format == "json":
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0

    print(f"OPS_PREMERGE_OK={summary['ok']}")
    print(f"OPS_NEXT_COMMAND={summary['next_command']}")
    print("OPS_TOP_ACTIONS=")
    if not summary["top_actions"]:
        print("1. No priority actions. Continue routine weekly lane.")
    else:
        for idx, action in enumerate(summary["top_actions"], start=1):
            print(f"{idx}. {action}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
