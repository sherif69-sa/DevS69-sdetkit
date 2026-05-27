from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = ".".join(("sdetkit", "repo", "memory", "profile", "history", "v2"))
LEGACY_RECORD_SCHEMA_VERSION = ".".join(
    ("sdetkit", "repo", "memory", "profile", "history", "record", "v1")
)
RECORD_SCHEMA_VERSION = ".".join(
    ("sdetkit", "repo", "memory", "profile", "history", "record", "v2")
)
DEFAULT_OUT_DIR = Path("build") / "repo-memory-history"
SUMMARY_JSON = "repo-memory-history-summary.json"
SUMMARY_MD = "repo-memory-history-summary.md"
HISTORY_JSONL = "repo-memory-profile-history.jsonl"

READ_ONLY_PROFILE_MODE = "_".join(("read", "only", "profile"))
LIVE_PROFILE_STATUS = "_".join(("live", "proof", "supported", "memory"))
AUTOMATION_ALLOWED = "_".join(("automation", "allowed"))
MERGE_AUTHORIZED = "_".join(("merge", "authorized"))
SEMANTIC_EQUIVALENCE_PROVEN = "_".join(("semantic", "equivalence", "proven"))
LIVE_CONTRACT_PROVEN = "_".join(("live", "contract", "proven"))
GIT_VERIFIED_SCENARIO_COUNT = "_".join(("git", "verified", "scenario", "count"))
EXPECTED_FAILED_SCENARIO_COUNT = "_".join(("expected", "failed", "scenario", "count"))
NETWORK_BOUNDARY_BLOCKED_SCENARIO_COUNT = "_".join(
    ("network", "boundary", "blocked", "scenario", "count")
)
ANTI_CHEAT_REJECTION_SCENARIO_COUNT = "_".join(("anti", "cheat", "rejection", "scenario", "count"))
CONTROLLED_VALIDATION_PASSED = "_".join(("controlled", "validation", "passed"))
CONTROLLED_VALIDATION_STATUS = "_".join(("controlled", "validation", "status"))
CONTROLLED_VALIDATION_RECORD_COUNT = "_".join(("controlled", "validation", "record", "count"))
CONTROLLED_VALIDATION_SCENARIO_COUNT = "_".join(("controlled", "validation", "scenario", "count"))
CONTROLLED_VALIDATION_PASSED_COUNT = "_".join(("controlled", "validation", "passed", "count"))
CONTROLLED_STRUCTURALLY_VERIFIED_COUNT = "_".join(
    ("controlled", "structurally", "verified", "count")
)
CONTROLLED_REVIEW_FIRST_COUNT = "_".join(("controlled", "review", "first", "count"))
CONTROLLED_CURRENT_PR_DECISION_INPUT = "_".join(
    ("controlled", "current", "pr", "decision", "input")
)

JsonObject = dict[str, Any]


def _as_dict(value: Any) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes"}


def _read_json(path: Path) -> JsonObject:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def _read_jsonl(path: Path) -> list[JsonObject]:
    if not path.exists():
        return []

    records: list[JsonObject] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError(f"expected JSON object on line {line_number} in {path}")
        records.append(payload)
    return records


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable_hash(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


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
            f"{source} expands authority and cannot enter read-only history: {', '.join(enabled)}"
        )


def _controlled_validation_observation(profile: Mapping[str, Any]) -> JsonObject:
    controlled = _as_dict(profile.get("controlled_candidate_validation"))
    status = _text(controlled.get("status") or "not_collected")
    empty = {
        CONTROLLED_VALIDATION_STATUS: "not_collected",
        CONTROLLED_VALIDATION_SCENARIO_COUNT: 0,
        CONTROLLED_VALIDATION_PASSED_COUNT: 0,
        CONTROLLED_STRUCTURALLY_VERIFIED_COUNT: 0,
        CONTROLLED_REVIEW_FIRST_COUNT: 0,
        CONTROLLED_CURRENT_PR_DECISION_INPUT: False,
    }
    if not controlled or status == "not_collected":
        return empty
    if status != CONTROLLED_VALIDATION_PASSED:
        raise ValueError("controlled validation profile status is not supported")
    if _bool(controlled.get("current_pr_decision_input")):
        raise ValueError("controlled validation profile cannot influence a current PR decision")
    _assert_no_authority(
        _as_dict(controlled.get("decision_boundary")),
        source="controlled validation profile evidence",
    )

    scenario_count = _int(controlled.get("scenario_count"))
    passed_count = _int(controlled.get("passed_count"))
    structurally_verified = _int(controlled.get("structurally_verified_count"))
    review_first = _int(controlled.get("review_first_count"))
    if (
        scenario_count < 2
        or passed_count != scenario_count
        or structurally_verified < 1
        or review_first < 1
    ):
        raise ValueError("controlled validation profile totals are inconsistent")

    return {
        CONTROLLED_VALIDATION_STATUS: CONTROLLED_VALIDATION_PASSED,
        CONTROLLED_VALIDATION_SCENARIO_COUNT: scenario_count,
        CONTROLLED_VALIDATION_PASSED_COUNT: passed_count,
        CONTROLLED_STRUCTURALLY_VERIFIED_COUNT: structurally_verified,
        CONTROLLED_REVIEW_FIRST_COUNT: review_first,
        CONTROLLED_CURRENT_PR_DECISION_INPUT: False,
    }


def validate_profile(profile: Mapping[str, Any]) -> None:
    if _text(profile.get("memory_mode")) != READ_ONLY_PROFILE_MODE:
        raise ValueError("RepoMemory profile must use read_only_profile memory mode")
    _assert_no_authority(
        _as_dict(profile.get("decision_boundary")),
        source="RepoMemory profile",
    )
    _controlled_validation_observation(profile)


def validate_record(record: Mapping[str, Any]) -> None:
    schema = _text(record.get("schema_version"))
    if schema not in {LEGACY_RECORD_SCHEMA_VERSION, RECORD_SCHEMA_VERSION}:
        raise ValueError("history record schema is not supported")
    _assert_no_authority(
        _as_dict(record.get("decision_boundary")),
        source="RepoMemory history record",
    )

    controlled_keys = {
        CONTROLLED_VALIDATION_STATUS,
        CONTROLLED_VALIDATION_SCENARIO_COUNT,
        CONTROLLED_VALIDATION_PASSED_COUNT,
        CONTROLLED_STRUCTURALLY_VERIFIED_COUNT,
        CONTROLLED_REVIEW_FIRST_COUNT,
        CONTROLLED_CURRENT_PR_DECISION_INPUT,
    }
    if schema == LEGACY_RECORD_SCHEMA_VERSION:
        if any(key in record for key in controlled_keys):
            raise ValueError("legacy history record cannot carry controlled validation evidence")
        return

    status = _text(record.get(CONTROLLED_VALIDATION_STATUS) or "not_collected")
    if status not in {"not_collected", CONTROLLED_VALIDATION_PASSED}:
        raise ValueError("history record controlled validation status is not supported")
    if _bool(record.get(CONTROLLED_CURRENT_PR_DECISION_INPUT)):
        raise ValueError(
            "history record controlled validation cannot influence a current PR decision"
        )
    if status == "not_collected":
        if any(
            _int(record.get(key))
            for key in (
                CONTROLLED_VALIDATION_SCENARIO_COUNT,
                CONTROLLED_VALIDATION_PASSED_COUNT,
                CONTROLLED_STRUCTURALLY_VERIFIED_COUNT,
                CONTROLLED_REVIEW_FIRST_COUNT,
            )
        ):
            raise ValueError(
                "uncollected controlled validation record cannot carry scenario totals"
            )
        return

    scenario_count = _int(record.get(CONTROLLED_VALIDATION_SCENARIO_COUNT))
    if (
        scenario_count < 2
        or _int(record.get(CONTROLLED_VALIDATION_PASSED_COUNT)) != scenario_count
        or _int(record.get(CONTROLLED_STRUCTURALLY_VERIFIED_COUNT)) < 1
        or _int(record.get(CONTROLLED_REVIEW_FIRST_COUNT)) < 1
    ):
        raise ValueError("history record controlled validation totals are inconsistent")


def build_history_record(
    profile: Mapping[str, Any],
    *,
    source_run_id: str,
    source_head_sha: str,
    recorded_at_utc: str | None = None,
) -> JsonObject:
    validate_profile(profile)

    run_id = _text(source_run_id)
    head_sha = _text(source_head_sha)
    if not run_id:
        raise ValueError("source_run_id is required")
    if not head_sha:
        raise ValueError("source_head_sha is required")

    provenance = _as_dict(profile.get("proof_provenance"))
    controlled = _controlled_validation_observation(profile)
    boundary = {
        AUTOMATION_ALLOWED: False,
        MERGE_AUTHORIZED: False,
        SEMANTIC_EQUIVALENCE_PROVEN: False,
    }
    stable = {
        "source_run_id": run_id,
        "source_head_sha": head_sha,
        "profile_status": _text(profile.get("profile_status")),
        LIVE_CONTRACT_PROVEN: _bool(provenance.get(LIVE_CONTRACT_PROVEN)),
        "known_safe_candidate_count": _int(profile.get("known_safe_candidate_count")),
        "live_safe_candidate_count": _int(profile.get("live_safe_candidate_count")),
        GIT_VERIFIED_SCENARIO_COUNT: _int(provenance.get(GIT_VERIFIED_SCENARIO_COUNT)),
        EXPECTED_FAILED_SCENARIO_COUNT: _int(provenance.get(EXPECTED_FAILED_SCENARIO_COUNT)),
        NETWORK_BOUNDARY_BLOCKED_SCENARIO_COUNT: _int(
            provenance.get(NETWORK_BOUNDARY_BLOCKED_SCENARIO_COUNT)
        ),
        ANTI_CHEAT_REJECTION_SCENARIO_COUNT: _int(
            provenance.get(ANTI_CHEAT_REJECTION_SCENARIO_COUNT)
        ),
        CONTROLLED_VALIDATION_STATUS: _text(controlled.get(CONTROLLED_VALIDATION_STATUS)),
        CONTROLLED_VALIDATION_SCENARIO_COUNT: _int(
            controlled.get(CONTROLLED_VALIDATION_SCENARIO_COUNT)
        ),
        CONTROLLED_VALIDATION_PASSED_COUNT: _int(
            controlled.get(CONTROLLED_VALIDATION_PASSED_COUNT)
        ),
        CONTROLLED_STRUCTURALLY_VERIFIED_COUNT: _int(
            controlled.get(CONTROLLED_STRUCTURALLY_VERIFIED_COUNT)
        ),
        CONTROLLED_REVIEW_FIRST_COUNT: _int(controlled.get(CONTROLLED_REVIEW_FIRST_COUNT)),
        CONTROLLED_CURRENT_PR_DECISION_INPUT: False,
        "decision_boundary": boundary,
    }

    return {
        "schema_version": RECORD_SCHEMA_VERSION,
        "record_id": _stable_hash(stable),
        "recorded_at_utc": recorded_at_utc or _utc_now(),
        **stable,
    }


def merge_history_records(
    prior_records: list[Mapping[str, Any]],
    record: Mapping[str, Any],
) -> tuple[list[JsonObject], bool]:
    validate_record(record)
    records = [dict(item) for item in prior_records]
    for existing in records:
        validate_record(existing)

    record_id = _text(record.get("record_id"))
    existing_ids = {_text(item.get("record_id")) for item in records}
    appended = record_id not in existing_ids
    if appended:
        records.append(dict(record))

    return records, appended


def write_history_jsonl(records: list[Mapping[str, Any]], *, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    history_path = out_dir / HISTORY_JSONL
    history_path.write_text(
        "".join(json.dumps(dict(item), sort_keys=True) + "\n" for item in records),
        encoding="utf-8",
    )
    return history_path


def build_history_summary(
    records: list[Mapping[str, Any]],
    *,
    appended: bool,
    history_path: Path,
    prior_history_collected: bool,
    prior_record_count: int,
) -> JsonObject:
    for record in records:
        validate_record(record)

    statuses = Counter(_text(item.get("profile_status")) for item in records)
    latest = dict(records[-1]) if records else {}
    live_records = [item for item in records if _bool(item.get(LIVE_CONTRACT_PROVEN))]
    controlled_records = [
        item
        for item in records
        if _text(item.get(CONTROLLED_VALIDATION_STATUS)) == CONTROLLED_VALIDATION_PASSED
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "history_recorded",
        "history_path": history_path.as_posix(),
        "prior_history_collected": prior_history_collected,
        "prior_record_count": prior_record_count,
        "appended": appended,
        "record_count": len(records),
        "live_contract_proven_record_count": len(live_records),
        CONTROLLED_VALIDATION_RECORD_COUNT: len(controlled_records),
        CONTROLLED_VALIDATION_SCENARIO_COUNT: sum(
            _int(item.get(CONTROLLED_VALIDATION_SCENARIO_COUNT)) for item in controlled_records
        ),
        CONTROLLED_STRUCTURALLY_VERIFIED_COUNT: sum(
            _int(item.get(CONTROLLED_STRUCTURALLY_VERIFIED_COUNT)) for item in controlled_records
        ),
        CONTROLLED_REVIEW_FIRST_COUNT: sum(
            _int(item.get(CONTROLLED_REVIEW_FIRST_COUNT)) for item in controlled_records
        ),
        "profile_status_counts": dict(sorted(statuses.items())),
        "known_safe_candidate_total": sum(
            _int(item.get("known_safe_candidate_count")) for item in records
        ),
        "live_safe_candidate_total": sum(
            _int(item.get("live_safe_candidate_count")) for item in records
        ),
        ANTI_CHEAT_REJECTION_SCENARIO_COUNT: sum(
            _int(item.get(ANTI_CHEAT_REJECTION_SCENARIO_COUNT)) for item in records
        ),
        "latest_record": {
            "record_id": _text(latest.get("record_id")),
            "source_run_id": _text(latest.get("source_run_id")),
            "source_head_sha": _text(latest.get("source_head_sha")),
            "profile_status": _text(latest.get("profile_status")),
            LIVE_CONTRACT_PROVEN: _bool(latest.get(LIVE_CONTRACT_PROVEN)),
            CONTROLLED_VALIDATION_STATUS: _text(
                latest.get(CONTROLLED_VALIDATION_STATUS) or "not_collected"
            ),
            CONTROLLED_VALIDATION_SCENARIO_COUNT: _int(
                latest.get(CONTROLLED_VALIDATION_SCENARIO_COUNT)
            ),
            CONTROLLED_CURRENT_PR_DECISION_INPUT: _bool(
                latest.get(CONTROLLED_CURRENT_PR_DECISION_INPUT)
            ),
        },
        "decision_boundary": {
            AUTOMATION_ALLOWED: False,
            MERGE_AUTHORIZED: False,
            SEMANTIC_EQUIVALENCE_PROVEN: False,
            "prior_history_is_read_only_input": True,
            "controlled_validation_is_advisory_only": True,
            "reason": (
                "RepoMemory profile history records proven read-only outcomes only; "
                "it does not authorize remediation."
            ),
        },
    }


def render_markdown(summary: Mapping[str, Any]) -> str:
    latest = _as_dict(summary.get("latest_record"))
    boundary = _as_dict(summary.get("decision_boundary"))
    lines = [
        "# RepoMemory profile history",
        "",
        f"- Status: `{_text(summary.get('status'))}`",
        (
            "- Prior history collected: "
            f"`{str(_bool(summary.get('prior_history_collected'))).lower()}`"
        ),
        f"- Prior records: `{_int(summary.get('prior_record_count'))}`",
        f"- Record appended: `{str(_bool(summary.get('appended'))).lower()}`",
        f"- Records: `{_int(summary.get('record_count'))}`",
        (
            "- Live-contract-proven records: "
            f"`{_int(summary.get('live_contract_proven_record_count'))}`"
        ),
        (
            "- Anti-cheat rejection scenario total: "
            f"`{_int(summary.get(ANTI_CHEAT_REJECTION_SCENARIO_COUNT))}`"
        ),
        (
            "- Controlled validation records: "
            f"`{_int(summary.get(CONTROLLED_VALIDATION_RECORD_COUNT))}`"
        ),
        (
            "- Controlled validation scenario total: "
            f"`{_int(summary.get(CONTROLLED_VALIDATION_SCENARIO_COUNT))}`"
        ),
        (
            "- Controlled structurally verified scenario total: "
            f"`{_int(summary.get(CONTROLLED_STRUCTURALLY_VERIFIED_COUNT))}`"
        ),
        (
            "- Controlled review-first scenario total: "
            f"`{_int(summary.get(CONTROLLED_REVIEW_FIRST_COUNT))}`"
        ),
        "",
        "## Latest record",
        "",
        f"- Record id: `{_text(latest.get('record_id'))}`",
        f"- Source run id: `{_text(latest.get('source_run_id'))}`",
        f"- Source head sha: `{_text(latest.get('source_head_sha'))}`",
        f"- Profile status: `{_text(latest.get('profile_status'))}`",
        (f"- Live contract proven: `{str(_bool(latest.get(LIVE_CONTRACT_PROVEN))).lower()}`"),
        (
            "- Controlled validation status: "
            f"`{_text(latest.get(CONTROLLED_VALIDATION_STATUS) or 'not_collected')}`"
        ),
        (
            "- Controlled validation scenarios: "
            f"`{_int(latest.get(CONTROLLED_VALIDATION_SCENARIO_COUNT))}`"
        ),
        (
            "- Controlled validation current PR decision input: "
            f"`{str(_bool(latest.get(CONTROLLED_CURRENT_PR_DECISION_INPUT))).lower()}`"
        ),
        "",
        "## Boundary",
        "",
        f"- Automation allowed: `{str(_bool(boundary.get(AUTOMATION_ALLOWED))).lower()}`",
        f"- Merge authorized: `{str(_bool(boundary.get(MERGE_AUTHORIZED))).lower()}`",
        (
            "- Semantic equivalence proven: "
            f"`{str(_bool(boundary.get(SEMANTIC_EQUIVALENCE_PROVEN))).lower()}`"
        ),
        (
            "- Prior history is read-only input: "
            f"`{str(_bool(boundary.get('prior_history_is_read_only_input'))).lower()}`"
        ),
        (
            "- Controlled validation is advisory only: "
            f"`{str(_bool(boundary.get('controlled_validation_is_advisory_only'))).lower()}`"
        ),
        "- History executes proof commands: `false`",
        "",
    ]
    return "\n".join(lines)


def write_summary(summary: Mapping[str, Any], *, out_dir: Path) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / SUMMARY_JSON
    markdown_path = out_dir / SUMMARY_MD
    json_path.write_text(
        json.dumps(dict(summary), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown(summary), encoding="utf-8")
    return {
        "history_summary_json": json_path.as_posix(),
        "history_summary_markdown": markdown_path.as_posix(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.repo_memory_profile_history")
    parser.add_argument("--profile-json", type=Path, required=True)
    parser.add_argument("--prior-history-jsonl", type=Path)
    parser.add_argument("--source-run-id", required=True)
    parser.add_argument("--source-head-sha", required=True)
    parser.add_argument("--recorded-at-utc")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        record = build_history_record(
            _read_json(args.profile_json),
            source_run_id=args.source_run_id,
            source_head_sha=args.source_head_sha,
            recorded_at_utc=args.recorded_at_utc,
        )
        prior_history_collected = args.prior_history_jsonl is not None
        if prior_history_collected and not args.prior_history_jsonl.exists():
            raise ValueError(f"prior history input does not exist: {args.prior_history_jsonl}")
        prior_records = (
            _read_jsonl(args.prior_history_jsonl) if args.prior_history_jsonl is not None else []
        )
        records, appended = merge_history_records(prior_records, record)
        history_path = write_history_jsonl(records, out_dir=args.out_dir)
        summary = build_history_summary(
            records,
            appended=appended,
            history_path=history_path,
            prior_history_collected=prior_history_collected,
            prior_record_count=len(prior_records),
        )
        artifacts = write_summary(summary, out_dir=args.out_dir)
        artifacts["history_jsonl"] = history_path.as_posix()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}")
        return 2

    if args.format == "json":
        print(
            json.dumps(
                {
                    "status": summary["status"],
                    "record_count": summary["record_count"],
                    "appended": summary["appended"],
                    "artifacts": artifacts,
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        for key, value in artifacts.items():
            print(f"{key}: {value}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
