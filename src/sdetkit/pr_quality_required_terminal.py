from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from sdetkit._pr_quality_required_terminal_merge import (
    merge_required_terminal_snapshot_into_checks,
    snapshot_covers_expected,
)
from sdetkit._pr_quality_required_terminal_snapshot import (
    JsonObject,
    _context_list,
    _integer,
    _string,
    classify_required_terminal_snapshot,
    collect_required_terminal_snapshot,
    time,
)

__all__ = [
    "classify_required_terminal_snapshot",
    "collect_and_merge_terminal_snapshot_from_environment",
    "collect_required_terminal_snapshot",
    "merge_required_terminal_snapshot_into_checks",
    "time",
]


def _required_context_contract_path() -> Path:
    configured = _string(os.environ.get("SDETKIT_REQUIRED_CHECKS_CONTRACT"))
    return Path(configured or "docs/contracts/required-checks.v1.json")


def _required_contexts_from_contract(path: Path) -> list[str]:
    try:
        payload: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, dict):
        return []
    return _context_list(payload.get("contexts", []))


def _resolve_required_contexts(checks_payload: JsonObject) -> tuple[list[str], str, str]:
    direct = _context_list(checks_payload.get("required_contexts", []))
    if direct:
        return direct, "checks_payload", ""
    contract_path = _required_context_contract_path()
    fallback = _required_contexts_from_contract(contract_path)
    if fallback:
        return fallback, "repository_contract", str(contract_path)
    return [], "unavailable", str(contract_path)


def collect_and_merge_terminal_snapshot_from_environment(
    *,
    checks_json: Path,
    out_dir: Path,
) -> JsonObject | None:
    if os.environ.get("GITHUB_ACTIONS", "").lower() != "true":
        return None
    repository = _string(os.environ.get("GITHUB_REPOSITORY"))
    if not repository:
        owner = _string(os.environ.get("REPOSITORY_OWNER"))
        name = _string(os.environ.get("REPOSITORY_NAME"))
        repository = f"{owner}/{name}" if owner and name else ""
    head_sha = _string(os.environ.get("HEAD_SHA"))
    pr_number = _integer(os.environ.get("PR_NUMBER"))
    token_name = "GH_" + "TOKEN"
    if not repository or not head_sha or pr_number <= 0 or not os.environ.get(token_name):
        return None

    payload = json.loads(checks_json.read_text(encoding="utf-8"))
    checks_payload = payload if isinstance(payload, dict) else {}
    expected_contexts, required_contexts_source, contract_path = _resolve_required_contexts(
        checks_payload
    )
    checks_payload["required_contexts"] = expected_contexts
    checks_payload["required_contexts_source"] = required_contexts_source
    if contract_path:
        checks_payload["required_contexts_contract_path"] = contract_path

    snapshot_path = out_dir / "terminal-workflow-snapshot.json"
    snapshot: JsonObject = {}
    if snapshot_path.exists():
        candidate = json.loads(snapshot_path.read_text(encoding="utf-8"))
        if isinstance(candidate, dict) and snapshot_covers_expected(
            candidate,
            head_sha=head_sha,
            expected_contexts=expected_contexts,
        ):
            snapshot = candidate

    if not snapshot:
        snapshot = collect_required_terminal_snapshot(
            repository=repository,
            pr_number=pr_number,
            head_sha=head_sha,
            expected_contexts=expected_contexts,
            current_workflow=_string(os.environ.get("GITHUB_WORKFLOW") or "PR Quality Comment"),
            timeout_seconds=max(
                _integer(os.environ.get("SDETKIT_TERMINAL_TIMEOUT_SECONDS")) or 600,
                1,
            ),
            poll_interval_seconds=max(
                _integer(os.environ.get("SDETKIT_TERMINAL_POLL_INTERVAL_SECONDS")) or 15,
                1,
            ),
            required_stable_polls=max(
                _integer(os.environ.get("SDETKIT_TERMINAL_STABLE_POLLS")) or 2,
                2,
            ),
        )
        snapshot["required_contexts_source"] = required_contexts_source
        if contract_path:
            snapshot["required_contexts_contract_path"] = contract_path
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_text(
            json.dumps(snapshot, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    merged = merge_required_terminal_snapshot_into_checks(checks_payload, snapshot)
    checks_json.write_text(
        json.dumps(merged, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return snapshot
