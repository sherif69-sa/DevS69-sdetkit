"""Retain provenance-checked read-only DiagnosticSignalSnapshot observations."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = ".".join(("sdetkit", "diagnostic", "signal", "snapshot", "history", "v1"))
RECORD_SCHEMA_VERSION = ".".join(
    ("sdetkit", "diagnostic", "signal", "snapshot", "history", "record", "v1")
)
SNAPSHOT_SCHEMA_VERSION = ".".join(("sdetkit", "diagnostic", "signal", "snapshot", "v1"))
DEFAULT_OUT_DIR = Path("build") / "repo-memory-history" / "diagnostic-signal-snapshots"
SUMMARY_JSON = "diagnostic-signal-snapshot-history-summary.json"
SUMMARY_MD = "diagnostic-signal-snapshot-history-summary.md"
HISTORY_JSONL = "diagnostic-signal-snapshot-history.jsonl"

HISTORY_RECORDED = "_".join(("diagnostic", "signal", "snapshot", "history", "recorded"))
QUIET_GREEN_STATUS = "_".join(("quiet", "green", "advisory", "baseline"))
OBSERVED_STATUS = "_".join(("diagnostic", "signal", "observed"))
RATE_STATUS = "_".join(("requires", "reviewed", "history"))
SOURCE_WORKFLOW = "PR Quality Comment"
RETENTION_WORKFLOW = "RepoMemory Profile History"
CURRENT_SNAPSHOT_TYPE = "_".join(("current", "pr", "reporting", "only"))
HISTORICAL_SNAPSHOT_AUTHORIZES_CURRENT_ACTION = "_".join(
    ("historical", "snapshot", "authorizes", "current", "action")
)

JsonObject = dict[str, Any]


def _as_dict(value: Any) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


def _required_bool(value: Any, *, key: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be a boolean")
    return value


def _required_count(value: Any, *, key: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{key} must be a non-negative integer")
    return value


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path | None) -> list[JsonObject]:
    if path is None or not path.exists():
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
    raw = json.dumps(dict(payload), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _history_boundary() -> JsonObject:
    return {
        "reporting_only": True,
        "current_pr_decision_input": False,
        "feeds_repo_memory": False,
        "proof_commands_executed": False,
        "patch_application_allowed": False,
        "automation_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
        HISTORICAL_SNAPSHOT_AUTHORIZES_CURRENT_ACTION: False,
        "prior_history_is_read_only_input": True,
    }


def _assert_no_authority(boundary: Mapping[str, Any], *, source: str) -> None:
    expected = {
        "reporting_only": True,
        "current_pr_decision_input": False,
        "feeds_repo_memory": False,
        "proof_commands_executed": False,
        "patch_application_allowed": False,
        "automation_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }
    for key, expected_value in expected.items():
        if boundary.get(key) is not expected_value:
            raise ValueError(f"{source} does not preserve no-authority boundary: {key}")


def _snapshot_observation(snapshot: Mapping[str, Any]) -> JsonObject:
    if _text(snapshot.get("schema_version")) != SNAPSHOT_SCHEMA_VERSION:
        raise ValueError("diagnostic signal snapshot schema is not supported")
    if _text(snapshot.get("snapshot_type")) != CURRENT_SNAPSHOT_TYPE:
        raise ValueError("only current_pr_reporting_only snapshots may enter history")

    status = _text(snapshot.get("status"))
    if status not in {QUIET_GREEN_STATUS, OBSERVED_STATUS}:
        raise ValueError("diagnostic signal snapshot status is not supported")

    quiet_green = _required_bool(
        snapshot.get("quiet_green_advisory_baseline"),
        key="quiet_green_advisory_baseline",
    )
    if quiet_green != (status == QUIET_GREEN_STATUS):
        raise ValueError("diagnostic signal snapshot status and quiet-green flag disagree")

    measurements = _as_dict(snapshot.get("measurements"))
    primary_signal_kind = _text(measurements.get("primary_signal_kind"))
    review_signal_present = _required_bool(
        measurements.get("review_signal_present"),
        key="review_signal_present",
    )
    integration_proof_signal_present = _required_bool(
        measurements.get("integration_proof_signal_present"),
        key="integration_proof_signal_present",
    )
    if review_signal_present != (primary_signal_kind == "review_signal"):
        raise ValueError("review signal presence does not match primary signal kind")
    if integration_proof_signal_present != (primary_signal_kind == "integration_proof"):
        raise ValueError("integration proof signal presence does not match primary signal kind")

    readiness = _as_dict(snapshot.get("kpi_readiness"))
    if _text(readiness.get("advisor_false_positive_rate_status")) != RATE_STATUS:
        raise ValueError(
            "snapshot cannot claim an advisor false-positive rate without reviewed history"
        )
    if readiness.get("reviewed_false_positive_count") is not None:
        raise ValueError(
            "snapshot cannot retain reviewed false-positive counts without reviewed history"
        )
    if readiness.get("reviewed_observation_count") is not None:
        raise ValueError(
            "snapshot cannot retain reviewed observation counts without reviewed history"
        )

    _assert_no_authority(
        _as_dict(snapshot.get("decision_boundary")),
        source="diagnostic signal snapshot",
    )

    return {
        "status": status,
        "quiet_green_advisory_baseline": quiet_green,
        "primary_signal_kind": primary_signal_kind,
        "review_signal_present": review_signal_present,
        "integration_proof_signal_present": integration_proof_signal_present,
        "evidence_graph_node_count": _required_count(
            measurements.get("evidence_graph_node_count"),
            key="evidence_graph_node_count",
        ),
        "diagnostic_worker_diagnosis_count": _required_count(
            measurements.get("diagnostic_worker_diagnosis_count"),
            key="diagnostic_worker_diagnosis_count",
        ),
        "runtime_guard_violation_count": _required_count(
            measurements.get("runtime_guard_violation_count"),
            key="runtime_guard_violation_count",
        ),
        "current_security_finding_count": _required_count(
            measurements.get("current_security_finding_count"),
            key="current_security_finding_count",
        ),
        "advisor_false_positive_rate_status": RATE_STATUS,
        "reviewed_false_positive_count": None,
        "reviewed_observation_count": None,
    }


def _select_merged_pr(payload: Any, *, accepted_main_sha: str, source_head_sha: str) -> JsonObject:
    candidates = payload if isinstance(payload, list) else [payload]
    matches = [
        _as_dict(item)
        for item in candidates
        if isinstance(item, dict)
        and _text(_as_dict(item).get("merged_at"))
        and _text(_as_dict(item).get("merge_commit_sha")) == accepted_main_sha
    ]
    if len(matches) != 1:
        raise ValueError("accepted-main SHA must map to exactly one merged pull request")

    merged_pr = matches[0]
    head = _as_dict(merged_pr.get("head"))
    if _text(head.get("sha")) != source_head_sha:
        raise ValueError("diagnostic snapshot source head does not match merged pull request head")
    if (
        not isinstance(merged_pr.get("number"), int)
        or isinstance(merged_pr.get("number"), bool)
        or int(merged_pr["number"]) < 1
    ):
        raise ValueError("merged pull request number is required")
    return merged_pr


def validate_record(record: Mapping[str, Any]) -> None:
    if _text(record.get("schema_version")) != RECORD_SCHEMA_VERSION:
        raise ValueError("diagnostic signal snapshot history record schema is not supported")
    source = _as_dict(record.get("source"))
    if _text(source.get("workflow")) != SOURCE_WORKFLOW:
        raise ValueError("snapshot history source workflow is not supported")
    if _text(source.get("retention_workflow")) != RETENTION_WORKFLOW:
        raise ValueError("snapshot history retention workflow is not supported")
    if _text(source.get("source_run_conclusion")) != "success":
        raise ValueError("only successful PR Quality snapshot runs may enter history")
    for key in ("source_run_id", "source_head_sha", "retention_run_id", "accepted_main_sha"):
        if not _text(source.get(key)):
            raise ValueError(f"snapshot history source is missing {key}")
    if (
        not isinstance(source.get("merged_pr_number"), int)
        or isinstance(source.get("merged_pr_number"), bool)
        or int(source["merged_pr_number"]) < 1
    ):
        raise ValueError("snapshot history record lacks merged PR number provenance")
    if source.get("merged_pr_verified") is not True:
        raise ValueError("snapshot history record lacks merged PR provenance")
    boundary = _as_dict(record.get("decision_boundary"))
    _assert_no_authority(
        boundary,
        source="diagnostic signal snapshot history record",
    )
    if boundary.get(HISTORICAL_SNAPSHOT_AUTHORIZES_CURRENT_ACTION) is not False:
        raise ValueError("historical snapshot cannot authorize a current action")
    if boundary.get("prior_history_is_read_only_input") is not True:
        raise ValueError("historical snapshot does not preserve read-only prior-history input")
    observation = _as_dict(record.get("snapshot"))
    status = _text(observation.get("status"))
    if status not in {QUIET_GREEN_STATUS, OBSERVED_STATUS}:
        raise ValueError("historical snapshot status is not supported")
    quiet_green = _required_bool(
        observation.get("quiet_green_advisory_baseline"),
        key="quiet_green_advisory_baseline",
    )
    if quiet_green != (status == QUIET_GREEN_STATUS):
        raise ValueError("historical snapshot status and quiet-green flag disagree")
    primary_signal_kind = _text(observation.get("primary_signal_kind"))
    review_signal_present = _required_bool(
        observation.get("review_signal_present"),
        key="review_signal_present",
    )
    integration_proof_signal_present = _required_bool(
        observation.get("integration_proof_signal_present"),
        key="integration_proof_signal_present",
    )
    if review_signal_present != (primary_signal_kind == "review_signal"):
        raise ValueError("historical review signal presence does not match primary signal kind")
    if integration_proof_signal_present != (primary_signal_kind == "integration_proof"):
        raise ValueError(
            "historical integration proof signal presence does not match primary signal kind"
        )
    if _text(observation.get("advisor_false_positive_rate_status")) != RATE_STATUS:
        raise ValueError("historical snapshot cannot claim an advisor false-positive rate")
    if observation.get("reviewed_false_positive_count") is not None:
        raise ValueError("historical snapshot cannot contain reviewed false-positive counts")
    if observation.get("reviewed_observation_count") is not None:
        raise ValueError("historical snapshot cannot contain reviewed observation counts")
    for key in (
        "evidence_graph_node_count",
        "diagnostic_worker_diagnosis_count",
        "runtime_guard_violation_count",
        "current_security_finding_count",
    ):
        _required_count(observation.get(key), key=key)

    observation_identity = {
        "source": {key: value for key, value in source.items() if key != "retention_run_id"},
        "snapshot": observation,
        "decision_boundary": boundary,
    }
    if _text(record.get("record_id")) != _stable_hash(observation_identity):
        raise ValueError(
            "diagnostic snapshot history record id does not match retained observation"
        )


def build_history_record(
    snapshot: Mapping[str, Any],
    *,
    associated_pr_payload: Any,
    source_run_id: str,
    source_run_conclusion: str,
    source_head_sha: str,
    retention_run_id: str,
    accepted_main_sha: str,
    recorded_at_utc: str | None = None,
) -> JsonObject:
    source_run = _text(source_run_id)
    source_head = _text(source_head_sha)
    retention_run = _text(retention_run_id)
    accepted_main = _text(accepted_main_sha)
    if not source_run or not source_head or not retention_run or not accepted_main:
        raise ValueError("snapshot history provenance fields are required")
    if _text(source_run_conclusion) != "success":
        raise ValueError("only successful PR Quality snapshot runs may enter history")

    merged_pr = _select_merged_pr(
        associated_pr_payload,
        accepted_main_sha=accepted_main,
        source_head_sha=source_head,
    )
    observation = _snapshot_observation(snapshot)
    source = {
        "workflow": SOURCE_WORKFLOW,
        "source_run_id": source_run,
        "source_run_conclusion": "success",
        "source_head_sha": source_head,
        "retention_workflow": RETENTION_WORKFLOW,
        "retention_run_id": retention_run,
        "accepted_main_sha": accepted_main,
        "merged_pr_number": int(merged_pr["number"]),
        "merged_pr_verified": True,
    }
    stable = {
        "source": source,
        "snapshot": observation,
        "decision_boundary": _history_boundary(),
    }
    observation_identity = {
        "source": {key: value for key, value in source.items() if key != "retention_run_id"},
        "snapshot": observation,
        "decision_boundary": _history_boundary(),
    }
    record = {
        "schema_version": RECORD_SCHEMA_VERSION,
        "record_id": _stable_hash(observation_identity),
        "recorded_at_utc": recorded_at_utc or _utc_now(),
        **stable,
    }
    validate_record(record)
    return record


def merge_history_records(
    prior_records: list[Mapping[str, Any]],
    record: Mapping[str, Any],
) -> tuple[list[JsonObject], bool]:
    validate_record(record)
    records = [dict(item) for item in prior_records]
    for existing in records:
        validate_record(existing)
    record_id = _text(record.get("record_id"))
    matching_indexes = [
        index for index, item in enumerate(records) if _text(item.get("record_id")) == record_id
    ]
    if len(matching_indexes) > 1:
        raise ValueError("diagnostic snapshot history contains duplicate observation identities")
    appended = not matching_indexes
    if appended:
        records.append(dict(record))
    else:
        # A retention workflow rerun republishes the same observation without
        # increasing advisory counts; refresh only its retention provenance so
        # readers can bind the downloaded artifact to the successful run.
        records[matching_indexes[0]] = dict(record)
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
    latest = _as_dict(records[-1]) if records else {}
    latest_source = _as_dict(latest.get("source"))
    latest_snapshot = _as_dict(latest.get("snapshot"))
    statuses = Counter(_text(_as_dict(item.get("snapshot")).get("status")) for item in records)
    return {
        "schema_version": SCHEMA_VERSION,
        "status": HISTORY_RECORDED,
        "history_path": history_path.as_posix(),
        "prior_history_collected": prior_history_collected,
        "prior_record_count": prior_record_count,
        "appended": appended,
        "record_count": len(records),
        "quiet_green_advisory_baseline_record_count": sum(
            1
            for item in records
            if _as_dict(item.get("snapshot")).get("quiet_green_advisory_baseline") is True
        ),
        "review_signal_record_count": sum(
            1
            for item in records
            if _as_dict(item.get("snapshot")).get("review_signal_present") is True
        ),
        "integration_proof_signal_record_count": sum(
            1
            for item in records
            if _as_dict(item.get("snapshot")).get("integration_proof_signal_present") is True
        ),
        "snapshot_status_counts": dict(sorted(statuses.items())),
        "advisor_false_positive_rate_status": RATE_STATUS,
        "reviewed_false_positive_count": None,
        "reviewed_observation_count": None,
        "latest_record": {
            "record_id": _text(latest.get("record_id")),
            "source_run_id": _text(latest_source.get("source_run_id")),
            "source_head_sha": _text(latest_source.get("source_head_sha")),
            "retention_run_id": _text(latest_source.get("retention_run_id")),
            "accepted_main_sha": _text(latest_source.get("accepted_main_sha")),
            "merged_pr_number": int(latest_source.get("merged_pr_number") or 0),
            "status": _text(latest_snapshot.get("status")),
            "primary_signal_kind": _text(latest_snapshot.get("primary_signal_kind")),
        },
        "decision_boundary": _history_boundary(),
    }


def render_markdown(summary: Mapping[str, Any]) -> str:
    latest = _as_dict(summary.get("latest_record"))
    boundary = _as_dict(summary.get("decision_boundary"))
    return "\n".join(
        [
            "# Diagnostic signal snapshot advisory history",
            "",
            f"- Status: `{_text(summary.get('status'))}`",
            f"- Prior history collected: `{str(summary.get('prior_history_collected') is True).lower()}`",
            f"- Records: `{int(summary.get('record_count') or 0)}`",
            (
                "- Quiet-green advisory baseline records: "
                f"`{int(summary.get('quiet_green_advisory_baseline_record_count') or 0)}`"
            ),
            f"- Review-signal records: `{int(summary.get('review_signal_record_count') or 0)}`",
            (
                "- Integration-proof-signal records: "
                f"`{int(summary.get('integration_proof_signal_record_count') or 0)}`"
            ),
            (
                "- Advisor false-positive rate status: "
                f"`{_text(summary.get('advisor_false_positive_rate_status'))}`"
            ),
            "",
            "## Latest retained snapshot",
            "",
            f"- Accepted main sha: `{_text(latest.get('accepted_main_sha'))}`",
            f"- Merged PR number: `{int(latest.get('merged_pr_number') or 0)}`",
            f"- Status: `{_text(latest.get('status'))}`",
            f"- Primary signal kind: `{_text(latest.get('primary_signal_kind'))}`",
            "",
            "## Boundary",
            "",
            f"- Reporting only: `{str(boundary.get('reporting_only') is True).lower()}`",
            (
                "- Current PR decision input: "
                f"`{str(boundary.get('current_pr_decision_input') is True).lower()}`"
            ),
            f"- Feeds RepoMemory: `{str(boundary.get('feeds_repo_memory') is True).lower()}`",
            f"- Automation allowed: `{str(boundary.get('automation_allowed') is True).lower()}`",
            f"- Merge authorized: `{str(boundary.get('merge_authorized') is True).lower()}`",
            (
                "- Historical snapshot authorizes current action: "
                f"`{str(boundary.get(HISTORICAL_SNAPSHOT_AUTHORIZES_CURRENT_ACTION) is True).lower()}`"
            ),
            "",
        ]
    )


def write_summary(summary: Mapping[str, Any], *, out_dir: Path) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / SUMMARY_JSON
    markdown_path = out_dir / SUMMARY_MD
    json_path.write_text(
        json.dumps(dict(summary), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    markdown_path.write_text(render_markdown(summary), encoding="utf-8")
    return {
        "history_summary_json": json_path.as_posix(),
        "history_summary_markdown": markdown_path.as_posix(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.diagnostic_signal_snapshot_history")
    parser.add_argument("--diagnostic-signal-snapshot", type=Path, required=True)
    parser.add_argument("--associated-pr-json", type=Path, required=True)
    parser.add_argument("--prior-history-jsonl", type=Path)
    parser.add_argument("--source-run-id", required=True)
    parser.add_argument("--source-run-conclusion", required=True)
    parser.add_argument("--source-head-sha", required=True)
    parser.add_argument("--retention-run-id", required=True)
    parser.add_argument("--accepted-main-sha", required=True)
    parser.add_argument("--recorded-at-utc")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        snapshot_payload = _read_json(args.diagnostic_signal_snapshot)
        associated_pr_payload = _read_json(args.associated_pr_json)
        if not isinstance(snapshot_payload, dict):
            raise ValueError("diagnostic signal snapshot must be a JSON object")
        if args.prior_history_jsonl is not None and not args.prior_history_jsonl.exists():
            raise ValueError(f"prior history input does not exist: {args.prior_history_jsonl}")
        record = build_history_record(
            snapshot_payload,
            associated_pr_payload=associated_pr_payload,
            source_run_id=args.source_run_id,
            source_run_conclusion=args.source_run_conclusion,
            source_head_sha=args.source_head_sha,
            retention_run_id=args.retention_run_id,
            accepted_main_sha=args.accepted_main_sha,
            recorded_at_utc=args.recorded_at_utc,
        )
        prior_records = _read_jsonl(args.prior_history_jsonl)
        records, appended = merge_history_records(prior_records, record)
        history_path = write_history_jsonl(records, out_dir=args.out_dir)
        summary = build_history_summary(
            records,
            appended=appended,
            history_path=history_path,
            prior_history_collected=args.prior_history_jsonl is not None,
            prior_record_count=len(prior_records),
        )
        artifacts = write_summary(summary, out_dir=args.out_dir)
        artifacts["history_jsonl"] = history_path.as_posix()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}", file=sys.stderr)
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
