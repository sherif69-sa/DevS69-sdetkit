from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sdetkit.flaky_test_registry_evidence import (
    SOURCE_SCHEMA_VERSION,
    build_flaky_test_registry_evidence,
    build_producer_vetted_fingerprint_registry_evidence,
    write_evidence,
)
from sdetkit.trusted_test_observation_classification import (
    SCHEMA_VERSION as CLASSIFICATION_SCHEMA_VERSION,
)
from sdetkit.trusted_test_observation_classification import (
    validate_classification_report,
)

SCHEMA_VERSION = "sdetkit.trusted_flaky_test_registry_producer.v1"
SOURCE_WORKFLOW = "RepoMemory Profile History"
SOURCE_CONNECTED = "trusted_main_source_connected"
NO_TEST_OBSERVATIONS = "no_test_observations_available"

CLASSIFICATION_NOT_SUPPLIED = "not_supplied_fail_closed"
CLASSIFICATION_EMPTY = "validated_empty_forwarded_to_registry"
CLASSIFICATION_ADVISORY = "validated_advisory_forwarded_to_registry"
PRODUCER_VETTED_OBSERVATIONS = "_".join(
    ("producer", "vetted", "flaky", "observations", "available")
)

DEFAULT_OUT_DIR = Path("build") / "trusted-flaky-test-registry"
PRODUCER_JSON = "trusted-flaky-test-registry-producer.json"
PRODUCER_MD = "trusted-flaky-test-registry-producer.md"

JsonObject = dict[str, Any]


def _as_dict(value: Any) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _string(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _read_json(path: Path) -> JsonObject:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def _empty_classification_report() -> JsonObject:
    return {
        "schema_version": SOURCE_SCHEMA_VERSION,
        "tests": [],
        "summary": {
            "flaky": 0,
            "stable_failing": 0,
            "stable_passing": 0,
        },
    }


def _classification_handoff(
    classification_report: Mapping[str, Any] | None,
    *,
    producer_source_head_sha: str,
) -> JsonObject:
    if classification_report is None:
        return {
            "schema_version": CLASSIFICATION_SCHEMA_VERSION,
            "status": CLASSIFICATION_NOT_SUPPLIED,
            "record_count": 0,
            "fingerprint_count": 0,
            "flaky": 0,
            "stable_failing": 0,
            "stable_passing": 0,
            "insufficient_history": 0,
            "latest_source_run_id": "",
            "latest_source_head_sha": "",
            "input_read_only": True,
            "raw_test_identity_emitted": False,
            "forwarded_to_registry": False,
            "current_pr_decision_input": False,
        }

    validate_classification_report(classification_report)

    source = _as_dict(classification_report.get("source"))
    summary = _as_dict(classification_report.get("summary"))
    source_run_ids = [_string(item) for item in _as_list(source.get("source_run_ids"))]
    source_head_shas = [_string(item) for item in _as_list(source.get("source_head_shas"))]
    record_count = _int(source.get("record_count"))
    fingerprint_count = _int(summary.get("fingerprint_count"))

    latest_source_run_id = source_run_ids[-1] if record_count else ""
    latest_source_head_sha = source_head_shas[-1] if record_count else ""
    producer_head = _string(producer_source_head_sha)

    if record_count and latest_source_head_sha != producer_head:
        raise ValueError(
            "trusted classification latest source head sha must match producer source_head_sha"
        )

    status = CLASSIFICATION_EMPTY if fingerprint_count == 0 else CLASSIFICATION_ADVISORY

    return {
        "schema_version": CLASSIFICATION_SCHEMA_VERSION,
        "status": status,
        "record_count": record_count,
        "fingerprint_count": fingerprint_count,
        "flaky": _int(summary.get("flaky")),
        "stable_failing": _int(summary.get("stable_failing")),
        "stable_passing": _int(summary.get("stable_passing")),
        "insufficient_history": _int(summary.get("insufficient_history")),
        "latest_source_run_id": latest_source_run_id,
        "latest_source_head_sha": latest_source_head_sha,
        "input_read_only": True,
        "raw_test_identity_emitted": False,
        "forwarded_to_registry": True,
        "current_pr_decision_input": False,
    }


def build_trusted_registry_evidence(
    *,
    source_run_id: str,
    source_head_sha: str,
    classification_report: Mapping[str, Any] | None = None,
) -> JsonObject:
    run_id = _string(source_run_id)
    head_sha = _string(source_head_sha)
    if not run_id:
        raise ValueError("trusted flaky-test producer source_run_id is required")
    if not head_sha:
        raise ValueError("trusted flaky-test producer source_head_sha is required")

    handoff = _classification_handoff(
        classification_report,
        producer_source_head_sha=head_sha,
    )

    source_reference = f"{SOURCE_WORKFLOW}:run={run_id}:head={head_sha}"
    if classification_report is None:
        evidence = build_flaky_test_registry_evidence(
            classification_report=_empty_classification_report(),
            source_kind="trusted_main_artifact",
            source_reference=source_reference,
        )
    else:
        evidence = build_producer_vetted_fingerprint_registry_evidence(
            classification_report=classification_report,
            source_reference=source_reference,
        )

    entries = [_as_dict(item) for item in _as_list(evidence.get("entries"))]
    observation_count = sum(_int(item.get("observed_runs")) for item in entries)
    observation_status = PRODUCER_VETTED_OBSERVATIONS if entries else NO_TEST_OBSERVATIONS

    source = _as_dict(evidence.get("source"))
    source.update(
        {
            "workflow": SOURCE_WORKFLOW,
            "run_id": run_id,
            "head_sha": head_sha,
            "observation_status": observation_status,
            "observations_collected": bool(entries),
        }
    )
    evidence["source"] = source

    summary = _as_dict(evidence.get("summary"))
    summary.update(
        {
            "observation_status": observation_status,
            "observation_count": observation_count,
        }
    )
    evidence["summary"] = summary
    if classification_report is None:
        evidence["note"] = (
            "Trusted-main producer remains fail-closed because no dedicated "
            "classification artifact was supplied; registry entries remain empty."
        )
    else:
        evidence["note"] = (
            "Dedicated classification handoff status is "
            f"{handoff['status']}; producer-vetted flaky fingerprints are "
            "forwarded as advisory registry evidence without authority expansion."
        )
    return evidence


def build_producer_report(
    evidence: Mapping[str, Any],
    *,
    classification_report: Mapping[str, Any] | None = None,
    producer_source_head_sha: str = "",
) -> JsonObject:
    source = _as_dict(evidence.get("source"))
    summary = _as_dict(evidence.get("summary"))
    boundary = _as_dict(evidence.get("decision_boundary"))
    handoff = _classification_handoff(
        classification_report,
        producer_source_head_sha=producer_source_head_sha,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": SOURCE_CONNECTED,
        "source": dict(source),
        "registry": {
            "schema_version": _string(evidence.get("schema_version")),
            "collection_status": _string(evidence.get("collection_status")),
            "status": _string(evidence.get("status")),
            "entry_count": _int(summary.get("entry_count")),
            "identity_kind": _string(source.get("identity_kind")),
            "observation_status": _string(summary.get("observation_status")),
            "observation_count": _int(summary.get("observation_count")),
        },
        "classification_handoff": handoff,
        "decision_boundary": dict(boundary),
        "note": _string(evidence.get("note")),
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    source = _as_dict(report.get("source"))
    registry = _as_dict(report.get("registry"))
    handoff = _as_dict(report.get("classification_handoff"))
    boundary = _as_dict(report.get("decision_boundary"))
    return "\n".join(
        [
            "# Trusted-main flaky-test registry producer",
            "",
            f"- Status: `{_string(report.get('status'))}`",
            (f"- Source workflow: `{_string(source.get('workflow'))}`"),
            (f"- Source run id: `{_string(source.get('run_id'))}`"),
            (f"- Source head sha: `{_string(source.get('head_sha'))}`"),
            (f"- Observation status: `{_string(registry.get('observation_status'))}`"),
            (f"- Observation count: `{_int(registry.get('observation_count'))}`"),
            (f"- Registry entries: `{_int(registry.get('entry_count'))}`"),
            "",
            "## Dedicated classification handoff",
            "",
            (f"- Schema: `{_string(handoff.get('schema_version'))}`"),
            (f"- Status: `{_string(handoff.get('status'))}`"),
            (f"- Source records: `{_int(handoff.get('record_count'))}`"),
            (f"- Fingerprints: `{_int(handoff.get('fingerprint_count'))}`"),
            f"- Flaky: `{_int(handoff.get('flaky'))}`",
            (f"- Stable failing: `{_int(handoff.get('stable_failing'))}`"),
            (f"- Stable passing: `{_int(handoff.get('stable_passing'))}`"),
            (f"- Insufficient history: `{_int(handoff.get('insufficient_history'))}`"),
            (f"- Latest source run id: `{_string(handoff.get('latest_source_run_id'))}`"),
            (f"- Latest source head sha: `{_string(handoff.get('latest_source_head_sha'))}`"),
            (
                "- Raw test identity emitted: "
                f"`{str(bool(handoff.get('raw_test_identity_emitted'))).lower()}`"
            ),
            (
                "- Forwarded to registry: "
                f"`{str(bool(handoff.get('forwarded_to_registry'))).lower()}`"
            ),
            (
                "- Current PR decision input: "
                f"`{str(bool(handoff.get('current_pr_decision_input'))).lower()}`"
            ),
            "",
            "## Boundary",
            "",
            (
                "- Only producer-vetted fingerprint classifications are represented; "
                "registry evidence remains advisory and non-authoritative."
            ),
            (
                "- Automatic quarantine allowed: "
                f"`{str(bool(boundary.get('automatic_quarantine_allowed'))).lower()}`"
            ),
            (
                "- Automatic rerun allowed: "
                f"`{str(bool(boundary.get('automatic_rerun_allowed'))).lower()}`"
            ),
            (
                "- Current failure suppression allowed: "
                f"`{str(bool(boundary.get('current_failure_suppression_allowed'))).lower()}`"
            ),
            (f"- Automation allowed: `{str(bool(boundary.get('automation_allowed'))).lower()}`"),
            (f"- Merge authorized: `{str(bool(boundary.get('merge_authorized'))).lower()}`"),
            "",
        ]
    )


def write_artifacts(
    evidence: Mapping[str, Any],
    report: Mapping[str, Any],
    *,
    out_dir: Path,
) -> dict[str, str]:
    artifacts = write_evidence(evidence, out_dir=out_dir)
    producer_json = out_dir / PRODUCER_JSON
    producer_markdown = out_dir / PRODUCER_MD
    producer_json.write_text(
        json.dumps(dict(report), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    producer_markdown.write_text(
        render_markdown(report),
        encoding="utf-8",
    )
    artifacts["producer_json"] = producer_json.as_posix()
    artifacts["producer_markdown"] = producer_markdown.as_posix()
    return artifacts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=("python -m sdetkit.trusted_flaky_test_registry_producer")
    )
    parser.add_argument("--source-run-id", required=True)
    parser.add_argument("--source-head-sha", required=True)
    parser.add_argument(
        "--classification-report",
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
        classification_report = (
            _read_json(args.classification_report)
            if args.classification_report is not None
            else None
        )
        evidence = build_trusted_registry_evidence(
            source_run_id=args.source_run_id,
            source_head_sha=args.source_head_sha,
            classification_report=classification_report,
        )
        report = build_producer_report(
            evidence,
            classification_report=classification_report,
            producer_source_head_sha=args.source_head_sha,
        )
        artifacts = write_artifacts(
            evidence,
            report,
            out_dir=args.out_dir,
        )
    except (OSError, ValueError):
        print("error=trusted classification producer input rejected")
        return 2

    if args.format == "json":
        print(
            json.dumps(
                {
                    "status": SOURCE_CONNECTED,
                    "artifacts": artifacts,
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(f"status={SOURCE_CONNECTED}")
        for key, value in artifacts.items():
            print(f"{key}={value}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
