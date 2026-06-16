from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.trusted_test_observation_history.v1"
RECORD_SCHEMA_VERSION = "sdetkit.trusted_test_observation_history.record.v1"
SOURCE_SCHEMA_VERSION = "sdetkit.trusted_test_observation_capture.v1"
SOURCE_STATUS = "trusted_main_observations_captured"

TRUSTED_WORKFLOW = "CI"
TRUSTED_JOB = "Full CI lane"
TRUSTED_EVENT = "push"
TRUSTED_REF = "refs/heads/main"

DEFAULT_OUT_DIR = Path("build") / "trusted-test-observation-history"
HISTORY_JSONL = "trusted-test-observation-history.jsonl"
SUMMARY_JSON = "trusted-test-observation-history-summary.json"
SUMMARY_MD = "trusted-test-observation-history-summary.md"

ALLOWED_OUTCOMES = {
    "passed",
    "failed",
    "error",
    "skipped",
}

JsonObject = dict[str, Any]


def _as_dict(value: Any) -> JsonObject:
    return dict(value) if isinstance(value, Mapping) else {}


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


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
    return _text(value).lower() in {
        "1",
        "true",
        "yes",
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable_hash(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(
        dict(payload),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _decision_boundary() -> JsonObject:
    return {
        "raw_observation_only": True,
        "flaky_classification_performed": False,
        "current_pr_decision_input": False,
        "automatic_quarantine_allowed": False,
        "automatic_rerun_allowed": False,
        "current_failure_suppression_allowed": False,
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }


def _assert_boundary(
    boundary: Mapping[str, Any],
    *,
    source: str,
) -> None:
    expected = _decision_boundary()
    for key, expected_value in expected.items():
        if _bool(boundary.get(key)) is not expected_value:
            raise ValueError(f"{source} has invalid authority boundary for {key}")


def _validate_fingerprint(value: Any) -> str:
    fingerprint = _text(value).lower()
    if len(fingerprint) != 64 or any(char not in "0123456789abcdef" for char in fingerprint):
        raise ValueError(
            "trusted test observation fingerprint must be a 64-character SHA-256 digest"
        )
    return fingerprint


def _normalise_observations(
    value: Any,
) -> list[JsonObject]:
    observations: list[JsonObject] = []
    seen: set[str] = set()

    for raw in _as_list(value):
        item = _as_dict(raw)
        fingerprint = _validate_fingerprint(item.get("test_fingerprint"))
        outcome = _text(item.get("outcome"))
        if outcome not in ALLOWED_OUTCOMES:
            raise ValueError("trusted test observation outcome is not supported")
        if fingerprint in seen:
            raise ValueError(
                "trusted test observation history record contains duplicate fingerprints"
            )
        if any(
            key in item
            for key in (
                "test_id",
                "classname",
                "name",
                "nodeid",
            )
        ):
            raise ValueError("raw test identity cannot enter trusted observation history")

        seen.add(fingerprint)
        observations.append(
            {
                "test_fingerprint": fingerprint,
                "outcome": outcome,
            }
        )

    if not observations:
        raise ValueError("trusted test observation report contains no observations")

    observations.sort(
        key=lambda item: (
            item["test_fingerprint"],
            item["outcome"],
        )
    )
    return observations


def _outcome_counts(
    observations: list[Mapping[str, Any]],
) -> Counter[str]:
    return Counter(_text(item.get("outcome")) for item in observations)


def _validate_counts(
    *,
    summary: Mapping[str, Any],
    observations: list[Mapping[str, Any]],
    source: str,
) -> None:
    counts = _outcome_counts(observations)
    observation_count = _int(summary.get("observation_count"))

    if observation_count != len(observations):
        raise ValueError(f"{source} observation count is inconsistent")

    for outcome in sorted(ALLOWED_OUTCOMES):
        if _int(summary.get(outcome)) != counts[outcome]:
            raise ValueError(f"{source} {outcome} count is inconsistent")

    if sum(counts.values()) != observation_count:
        raise ValueError(f"{source} outcome totals are inconsistent")


def validate_observation_report(
    report: Mapping[str, Any],
) -> None:
    if _text(report.get("schema_version")) != (SOURCE_SCHEMA_VERSION):
        raise ValueError("trusted test observation report schema is not supported")
    if _text(report.get("status")) != SOURCE_STATUS:
        raise ValueError("trusted test observation report status is not supported")

    source = _as_dict(report.get("source"))
    expected_source = {
        "workflow": TRUSTED_WORKFLOW,
        "job": TRUSTED_JOB,
        "event_name": TRUSTED_EVENT,
        "ref_name": TRUSTED_REF,
    }
    for key, expected in expected_source.items():
        if _text(source.get(key)) != expected:
            raise ValueError(f"trusted test observation source is not supported for {key}")

    if not _text(source.get("run_id")):
        raise ValueError("trusted test observation source run id is required")
    if not _text(source.get("head_sha")):
        raise ValueError("trusted test observation source head sha is required")
    if source.get("trusted_main") is not True:
        raise ValueError("trusted test observations require trusted main provenance")
    if source.get("input_read_only") is not True:
        raise ValueError("trusted test observation input must be read-only")
    if source.get("commands_executed_by_reader") is not False:
        raise ValueError("trusted test observation reader cannot execute commands")

    summary = _as_dict(report.get("summary"))
    if summary.get("flaky_classification_performed") is not False:
        raise ValueError("trusted observation history cannot consume classified input")
    if summary.get("raw_test_identity_emitted") is not False:
        raise ValueError("trusted observation history cannot consume raw test identities")

    observations = _normalise_observations(report.get("observations"))
    _validate_counts(
        summary=summary,
        observations=observations,
        source="trusted test observation report",
    )

    boundary = _as_dict(report.get("decision_boundary"))
    required_false = (
        "flaky_classification_performed",
        "automatic_quarantine_allowed",
        "automatic_rerun_allowed",
        "current_failure_suppression_allowed",
        "automation_allowed",
        "merge_authorized",
        "semantic_equivalence_proven",
    )
    if boundary.get("raw_observation_only") is not True:
        raise ValueError("trusted test observation report must be raw-observation-only")
    if any(boundary.get(key) is not False for key in required_false):
        raise ValueError("trusted test observation report expands authority")


def _stable_record_payload(
    record: Mapping[str, Any],
) -> JsonObject:
    return {
        "source_run_id": _text(record.get("source_run_id")),
        "source_head_sha": _text(record.get("source_head_sha")),
        "source_workflow": _text(record.get("source_workflow")),
        "source_job": _text(record.get("source_job")),
        "event_name": _text(record.get("event_name")),
        "ref_name": _text(record.get("ref_name")),
        "observation_count": _int(record.get("observation_count")),
        "passed": _int(record.get("passed")),
        "failed": _int(record.get("failed")),
        "error": _int(record.get("error")),
        "skipped": _int(record.get("skipped")),
        "observations": _normalise_observations(record.get("observations")),
        "decision_boundary": _decision_boundary(),
    }


def build_observation_history_record(
    report: Mapping[str, Any],
    *,
    source_run_id: str,
    source_head_sha: str,
    recorded_at_utc: str | None = None,
) -> JsonObject:
    validate_observation_report(report)

    source = _as_dict(report.get("source"))
    run_id = _text(source_run_id)
    head_sha = _text(source_head_sha)

    if not run_id:
        raise ValueError("source_run_id is required")
    if not head_sha:
        raise ValueError("source_head_sha is required")
    if run_id != _text(source.get("run_id")):
        raise ValueError("source_run_id does not match trusted observation report provenance")
    if head_sha != _text(source.get("head_sha")):
        raise ValueError("source_head_sha does not match trusted observation report provenance")

    observations = _normalise_observations(report.get("observations"))
    summary = _as_dict(report.get("summary"))

    stable = {
        "source_run_id": run_id,
        "source_head_sha": head_sha,
        "source_workflow": TRUSTED_WORKFLOW,
        "source_job": TRUSTED_JOB,
        "event_name": TRUSTED_EVENT,
        "ref_name": TRUSTED_REF,
        "observation_count": len(observations),
        "passed": _int(summary.get("passed")),
        "failed": _int(summary.get("failed")),
        "error": _int(summary.get("error")),
        "skipped": _int(summary.get("skipped")),
        "observations": observations,
        "decision_boundary": _decision_boundary(),
    }

    return {
        "schema_version": RECORD_SCHEMA_VERSION,
        "record_id": _stable_hash(stable),
        "recorded_at_utc": (_text(recorded_at_utc) or _utc_now()),
        **stable,
    }


def validate_observation_history_record(
    record: Mapping[str, Any],
) -> None:
    if _text(record.get("schema_version")) != (RECORD_SCHEMA_VERSION):
        raise ValueError("trusted observation history record schema is not supported")
    if not _text(record.get("recorded_at_utc")):
        raise ValueError("trusted observation history recorded_at_utc is required")

    stable = _stable_record_payload(record)

    for key, expected in (
        ("source_workflow", TRUSTED_WORKFLOW),
        ("source_job", TRUSTED_JOB),
        ("event_name", TRUSTED_EVENT),
        ("ref_name", TRUSTED_REF),
    ):
        if stable[key] != expected:
            raise ValueError(f"trusted observation history provenance is invalid for {key}")

    if not stable["source_run_id"]:
        raise ValueError("trusted observation history source run id is required")
    if not stable["source_head_sha"]:
        raise ValueError("trusted observation history source head sha is required")

    observations = list(stable["observations"])
    _validate_counts(
        summary=stable,
        observations=observations,
        source="trusted observation history record",
    )
    _assert_boundary(
        _as_dict(record.get("decision_boundary")),
        source="trusted observation history record",
    )

    expected_id = _stable_hash(stable)
    if _text(record.get("record_id")) != expected_id:
        raise ValueError("trusted observation history record id is inconsistent")


def merge_observation_history_records(
    prior_records: list[Mapping[str, Any]],
    record: Mapping[str, Any],
) -> tuple[list[JsonObject], bool]:
    validate_observation_history_record(record)

    records: list[JsonObject] = []
    seen_ids: set[str] = set()

    for prior in prior_records:
        validate_observation_history_record(prior)
        record_id = _text(prior.get("record_id"))
        if record_id in seen_ids:
            raise ValueError("trusted observation history contains duplicate prior record ids")
        seen_ids.add(record_id)
        records.append(dict(prior))

    current_id = _text(record.get("record_id"))
    appended = current_id not in seen_ids
    if appended:
        records.append(dict(record))

    return records, appended


def _read_json(path: Path) -> JsonObject:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def _read_jsonl(path: Path) -> list[JsonObject]:
    if not path.exists():
        raise ValueError("prior trusted observation history does not exist")

    records: list[JsonObject] = []
    for line_number, raw in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not raw.strip():
            continue
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError(f"expected JSON object on line {line_number} in {path}")
        records.append(payload)

    return records


def build_observation_history_summary(
    records: list[Mapping[str, Any]],
    *,
    appended: bool,
    history_path: Path,
    prior_history_collected: bool,
    prior_record_count: int,
) -> JsonObject:
    if prior_record_count < 0:
        raise ValueError("prior_record_count cannot be negative")
    if not prior_history_collected and prior_record_count != 0:
        raise ValueError("uncollected prior history cannot report prior records")

    expected_record_count = prior_record_count + (1 if appended else 0)
    if len(records) != expected_record_count:
        raise ValueError("trusted observation history record totals are inconsistent")

    fingerprint_outcomes: dict[str, list[str]] = defaultdict(list)
    source_run_ids: list[str] = []
    source_head_shas: list[str] = []
    totals: Counter[str] = Counter()

    for record in records:
        validate_observation_history_record(record)
        source_run_ids.append(_text(record.get("source_run_id")))
        source_head_shas.append(_text(record.get("source_head_sha")))
        for observation in _normalise_observations(record.get("observations")):
            fingerprint = _text(observation.get("test_fingerprint"))
            outcome = _text(observation.get("outcome"))
            fingerprint_outcomes[fingerprint].append(outcome)
            totals[outcome] += 1

    histories = [
        {
            "test_fingerprint": fingerprint,
            "runs_observed": len(outcomes),
            "outcomes": list(outcomes),
            "passed": outcomes.count("passed"),
            "failed": outcomes.count("failed"),
            "error": outcomes.count("error"),
            "skipped": outcomes.count("skipped"),
        }
        for fingerprint, outcomes in sorted(fingerprint_outcomes.items())
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "history_recorded",
        "history_path": history_path.as_posix(),
        "prior_history_collected": (prior_history_collected),
        "prior_record_count": prior_record_count,
        "record_count": len(records),
        "appended": appended,
        "source_run_ids": source_run_ids,
        "source_head_shas": source_head_shas,
        "fingerprint_count": len(histories),
        "observation_count": sum(totals.values()),
        "passed": totals["passed"],
        "failed": totals["failed"],
        "error": totals["error"],
        "skipped": totals["skipped"],
        "fingerprint_histories": histories,
        "raw_test_identity_emitted": False,
        "flaky_classification_performed": False,
        "current_pr_decision_input": False,
        "decision_boundary": _decision_boundary(),
        "recommended_next_action": (
            "Use only provenance-checked raw outcome "
            "history as input to a separate advisory "
            "classification handoff."
        ),
    }


def write_observation_history(
    records: list[Mapping[str, Any]],
    *,
    out_dir: Path,
) -> Path:
    for record in records:
        validate_observation_history_record(record)

    out_dir.mkdir(parents=True, exist_ok=True)
    history_path = out_dir / HISTORY_JSONL
    history_path.write_text(
        "".join(
            json.dumps(
                dict(record),
                sort_keys=True,
            )
            + "\n"
            for record in records
        ),
        encoding="utf-8",
    )
    return history_path


def render_observation_history_markdown(
    summary: Mapping[str, Any],
) -> str:
    boundary = _as_dict(summary.get("decision_boundary"))
    histories = [
        _as_dict(item) for item in _as_list(summary.get("fingerprint_histories")) if _as_dict(item)
    ]

    lines = [
        "# Trusted test observation history",
        "",
        f"- Schema: `{_text(summary.get('schema_version'))}`",
        f"- Status: `{_text(summary.get('status'))}`",
        f"- Records: `{_int(summary.get('record_count'))}`",
        (
            "- Prior history collected: "
            f"`{str(_bool(summary.get('prior_history_collected'))).lower()}`"
        ),
        f"- Appended: `{str(_bool(summary.get('appended'))).lower()}`",
        (f"- Fingerprints: `{_int(summary.get('fingerprint_count'))}`"),
        (f"- Observations: `{_int(summary.get('observation_count'))}`"),
        f"- Passed: `{_int(summary.get('passed'))}`",
        f"- Failed: `{_int(summary.get('failed'))}`",
        f"- Errors: `{_int(summary.get('error'))}`",
        f"- Skipped: `{_int(summary.get('skipped'))}`",
        "",
        "## Fingerprint histories",
        "",
    ]

    if histories:
        for item in histories:
            outcomes = ", ".join(_text(value) for value in _as_list(item.get("outcomes")))
            lines.append(
                "- fingerprint="
                f"`{_text(item.get('test_fingerprint'))}`, "
                f"runs=`{_int(item.get('runs_observed'))}`, "
                f"outcomes=`{outcomes}`"
            )
    else:
        lines.append("- none observed")

    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- Raw observation only: `true`",
            "- Raw test identity emitted: `false`",
            "- Flaky classification performed: `false`",
            "- Current PR decision input: `false`",
            (
                "- Automatic quarantine allowed: "
                f"`{str(_bool(boundary.get('automatic_quarantine_allowed'))).lower()}`"
            ),
            (
                "- Automatic rerun allowed: "
                f"`{str(_bool(boundary.get('automatic_rerun_allowed'))).lower()}`"
            ),
            (
                "- Current failure suppression allowed: "
                f"`{str(_bool(boundary.get('current_failure_suppression_allowed'))).lower()}`"
            ),
            (f"- Automation allowed: `{str(_bool(boundary.get('automation_allowed'))).lower()}`"),
            (
                "- Patch application allowed: "
                f"`{str(_bool(boundary.get('patch_application_allowed'))).lower()}`"
            ),
            (f"- Merge authorized: `{str(_bool(boundary.get('merge_authorized'))).lower()}`"),
            (
                "- Semantic equivalence proven: "
                f"`{str(_bool(boundary.get('semantic_equivalence_proven'))).lower()}`"
            ),
            "",
            (f"- Next: {_text(summary.get('recommended_next_action'))}"),
            "",
        ]
    )

    return "\n".join(lines)


def write_observation_history_summary(
    summary: Mapping[str, Any],
    *,
    out_dir: Path,
) -> dict[str, str]:
    if _text(summary.get("schema_version")) != (SCHEMA_VERSION):
        raise ValueError("trusted observation history summary schema is not supported")
    _assert_boundary(
        _as_dict(summary.get("decision_boundary")),
        source="trusted observation history summary",
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / SUMMARY_JSON
    markdown_path = out_dir / SUMMARY_MD

    json_path.write_text(
        json.dumps(
            dict(summary),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(
        render_observation_history_markdown(summary),
        encoding="utf-8",
    )

    return {
        "summary_json": json_path.as_posix(),
        "summary_markdown": markdown_path.as_posix(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=("python -m sdetkit.trusted_test_observation_history"))
    parser.add_argument(
        "--observation-report",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--source-run-id",
        required=True,
    )
    parser.add_argument(
        "--source-head-sha",
        required=True,
    )
    parser.add_argument(
        "--prior-history-jsonl",
        type=Path,
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        report = _read_json(args.observation_report)
        prior_records = _read_jsonl(args.prior_history_jsonl) if args.prior_history_jsonl else []
        prior_collected = args.prior_history_jsonl is not None
        record = build_observation_history_record(
            report,
            source_run_id=args.source_run_id,
            source_head_sha=args.source_head_sha,
        )
        records, appended = merge_observation_history_records(
            prior_records,
            record,
        )

        history_path = args.out_dir / HISTORY_JSONL
        summary = build_observation_history_summary(
            records,
            appended=appended,
            history_path=history_path,
            prior_history_collected=prior_collected,
            prior_record_count=len(prior_records),
        )
        written_history = write_observation_history(
            records,
            out_dir=args.out_dir,
        )
        artifacts = write_observation_history_summary(
            summary,
            out_dir=args.out_dir,
        )
    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        print(f"error={exc}")
        return 2

    output = {
        "status": summary["status"],
        "record_count": summary["record_count"],
        "appended": summary["appended"],
        "fingerprint_count": (summary["fingerprint_count"]),
        "flaky_classification_performed": False,
        "current_pr_decision_input": False,
        "artifacts": {
            "history_jsonl": (written_history.as_posix()),
            **artifacts,
        },
    }

    if args.format == "json":
        print(
            json.dumps(
                output,
                indent=2,
                sort_keys=True,
            )
        )
    else:
        for key, value in output.items():
            print(f"{key}={value}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
