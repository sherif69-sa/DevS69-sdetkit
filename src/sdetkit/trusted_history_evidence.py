from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sdetkit.repo_memory_profile_history import (
    AUTOMATION_ALLOWED,
    LIVE_CONTRACT_PROVEN,
    MERGE_AUTHORIZED,
    SEMANTIC_EQUIVALENCE_PROVEN,
    validate_record,
)

SCHEMA_VERSION = ".".join(("sdetkit", "trusted", "history", "evidence", "v1"))
DEFAULT_OUT_DIR = Path("build") / "pr-quality" / "trusted-history"
EVIDENCE_JSON = "trusted-history-evidence.json"
EVIDENCE_MD = "trusted-history-evidence.md"

COLLECTED = "collected"
HISTORY_RECORDED = "_".join(("history", "recorded"))
TRUSTED_HISTORY_VERIFIED = "_".join(("trusted", "history", "verified"))
PRIOR_HISTORY_READ_ONLY = "_".join(("prior", "history", "is", "read", "only", "input"))
LIVE_PROVEN_RECORD_COUNT = "_".join(("live", "contract", "proven", "record", "count"))
ANTI_CHEAT_REJECTION_COUNT = "_".join(("anti", "cheat", "rejection", "scenario", "count"))
SOURCE_WORKFLOW = "RepoMemory Profile History"

JsonObject = dict[str, Any]


def _as_dict(value: Any) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _string(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _bool(value: Any) -> bool:
    return value is True


def _read_json(path: Path) -> JsonObject:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def _read_jsonl(path: Path) -> list[JsonObject]:
    records: list[JsonObject] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError(f"expected JSON object on line {line_number} in {path}")
        records.append(payload)
    return records


def _assert_no_authority(boundary: Mapping[str, Any], *, source: str) -> None:
    enabled = [
        key
        for key in (
            AUTOMATION_ALLOWED,
            MERGE_AUTHORIZED,
            SEMANTIC_EQUIVALENCE_PROVEN,
        )
        if _bool(boundary.get(key))
    ]
    if enabled:
        raise ValueError(
            f"{source} expands authority and cannot be displayed as trusted history: "
            f"{', '.join(enabled)}"
        )


def verify_base_ancestry(
    *,
    repo_root: Path,
    selected_head_sha: str,
    base_sha: str,
) -> None:
    selected = _string(selected_head_sha)
    base = _string(base_sha)
    if not selected:
        raise ValueError("selected_head_sha is required")
    if not base:
        raise ValueError("base_sha is required")

    completed = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "merge-base",
            "--is-ancestor",
            selected,
            base,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode == 1:
        raise ValueError("selected trusted history head is not an ancestor of the PR base")
    if completed.returncode != 0:
        detail = completed.stderr.strip() or "git ancestry verification failed"
        raise ValueError(detail)


def build_trusted_history_evidence(
    *,
    summary: Mapping[str, Any],
    records: list[Mapping[str, Any]],
    selected_run_id: str,
    selected_head_sha: str,
    base_sha: str,
    base_ancestry_verified: bool,
) -> JsonObject:
    if not base_ancestry_verified:
        raise ValueError("trusted history base ancestry was not verified")
    if not records:
        raise ValueError("trusted history contains no records")

    for record in records:
        validate_record(record)

    payload = _as_dict(summary)
    latest = _as_dict(payload.get("latest_record"))
    boundary = _as_dict(payload.get("decision_boundary"))
    selected_run = _string(selected_run_id)
    selected_head = _string(selected_head_sha)

    if _string(payload.get("status")) != HISTORY_RECORDED:
        raise ValueError("trusted history summary status is not history_recorded")
    if _int(payload.get("record_count")) != len(records):
        raise ValueError("trusted history summary count does not match JSONL records")
    if _int(payload.get(LIVE_PROVEN_RECORD_COUNT)) < 1:
        raise ValueError("trusted history contains no live-contract-proven records")
    if not _bool(boundary.get(PRIOR_HISTORY_READ_ONLY)):
        raise ValueError("trusted history does not preserve read-only prior-history input")
    _assert_no_authority(boundary, source="trusted history summary")

    last = _as_dict(records[-1])
    if _string(latest.get("source_run_id")) != selected_run:
        raise ValueError("trusted history selected run does not match latest summary record")
    if _string(latest.get("source_head_sha")) != selected_head:
        raise ValueError("trusted history selected head does not match latest summary record")
    if _string(last.get("source_run_id")) != selected_run:
        raise ValueError("trusted history selected run does not match latest JSONL record")
    if _string(last.get("source_head_sha")) != selected_head:
        raise ValueError("trusted history selected head does not match latest JSONL record")
    if not _bool(latest.get(LIVE_CONTRACT_PROVEN)):
        raise ValueError("trusted history latest record lacks live-contract proof")

    return {
        "schema_version": SCHEMA_VERSION,
        "collection_status": COLLECTED,
        "status": TRUSTED_HISTORY_VERIFIED,
        "source": {
            "workflow": SOURCE_WORKFLOW,
            "run_id": selected_run,
            "head_sha": selected_head,
            "base_sha": _string(base_sha),
            "base_ancestry_verified": True,
        },
        "history": {
            "record_count": len(records),
            "live_contract_proven_record_count": _int(payload.get(LIVE_PROVEN_RECORD_COUNT)),
            "anti_cheat_rejection_scenario_count": _int(payload.get(ANTI_CHEAT_REJECTION_COUNT)),
            "latest_accepted_main_head": selected_head,
            "latest_live_contract_proven": True,
            "prior_history_is_read_only_input": True,
        },
        "decision_boundary": {
            "reporting_only": True,
            "proof_commands_executed_by_reader": False,
            AUTOMATION_ALLOWED: False,
            MERGE_AUTHORIZED: False,
            SEMANTIC_EQUIVALENCE_PROVEN: False,
        },
    }


def render_markdown(evidence: Mapping[str, Any]) -> str:
    source = _as_dict(evidence.get("source"))
    history = _as_dict(evidence.get("history"))
    boundary = _as_dict(evidence.get("decision_boundary"))
    return "\n".join(
        [
            "# Trusted RepoMemory history evidence",
            "",
            f"- Collection status: `{_string(evidence.get('collection_status'))}`",
            f"- Status: `{_string(evidence.get('status'))}`",
            f"- Source workflow: `{_string(source.get('workflow'))}`",
            f"- Source run id: `{_string(source.get('run_id'))}`",
            f"- Latest accepted main head: `{_string(history.get('latest_accepted_main_head'))}`",
            (
                "- Base ancestry verified: "
                f"`{str(_bool(source.get('base_ancestry_verified'))).lower()}`"
            ),
            f"- Records: `{_int(history.get('record_count'))}`",
            (
                "- Live-contract-proven records: "
                f"`{_int(history.get('live_contract_proven_record_count'))}`"
            ),
            (
                "- Prior history is read-only input: "
                f"`{str(_bool(history.get('prior_history_is_read_only_input'))).lower()}`"
            ),
            "",
            "## Boundary",
            "",
            (
                "- Proof commands executed by reader: "
                f"`{str(_bool(boundary.get('proof_commands_executed_by_reader'))).lower()}`"
            ),
            (f"- Automation allowed: `{str(_bool(boundary.get(AUTOMATION_ALLOWED))).lower()}`"),
            (f"- Merge authorized: `{str(_bool(boundary.get(MERGE_AUTHORIZED))).lower()}`"),
            (
                "- Semantic equivalence proven: "
                f"`{str(_bool(boundary.get(SEMANTIC_EQUIVALENCE_PROVEN))).lower()}`"
            ),
            "",
        ]
    )


def write_evidence(evidence: Mapping[str, Any], *, out_dir: Path) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / EVIDENCE_JSON
    markdown_path = out_dir / EVIDENCE_MD
    json_path.write_text(
        json.dumps(dict(evidence), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown(evidence), encoding="utf-8")
    return {
        "trusted_history_evidence_json": json_path.as_posix(),
        "trusted_history_evidence_markdown": markdown_path.as_posix(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.trusted_history_evidence")
    parser.add_argument("--history-summary", type=Path, required=True)
    parser.add_argument("--history-jsonl", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--selected-run-id", required=True)
    parser.add_argument("--selected-head-sha", required=True)
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        verify_base_ancestry(
            repo_root=args.repo_root,
            selected_head_sha=args.selected_head_sha,
            base_sha=args.base_sha,
        )
        evidence = build_trusted_history_evidence(
            summary=_read_json(args.history_summary),
            records=_read_jsonl(args.history_jsonl),
            selected_run_id=args.selected_run_id,
            selected_head_sha=args.selected_head_sha,
            base_sha=args.base_sha,
            base_ancestry_verified=True,
        )
        write_evidence(evidence, out_dir=args.out_dir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}")
        return 2

    if args.format == "json":
        print(
            json.dumps(
                {
                    "status": evidence["status"],
                    "collection_status": evidence["collection_status"],
                    "record_count": evidence["history"]["record_count"],
                    "evidence_written": True,
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(f"status: {evidence['status']}")
        print(f"collection_status: {evidence['collection_status']}")
        print(f"record_count: {evidence['history']['record_count']}")
        print("evidence_written: true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
