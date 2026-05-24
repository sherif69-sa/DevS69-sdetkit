from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sdetkit.flaky_test_registry_evidence import (
    SOURCE_SCHEMA_VERSION,
    build_flaky_test_registry_evidence,
    write_evidence,
)

SCHEMA_VERSION = "sdetkit.trusted_flaky_test_registry_producer.v1"
SOURCE_WORKFLOW = "RepoMemory Profile History"
SOURCE_CONNECTED = "trusted_main_source_connected"
NO_TEST_OBSERVATIONS = "no_test_observations_available"

DEFAULT_OUT_DIR = Path("build") / "trusted-flaky-test-registry"
PRODUCER_JSON = "trusted-flaky-test-registry-producer.json"
PRODUCER_MD = "trusted-flaky-test-registry-producer.md"

JsonObject = dict[str, Any]


def _as_dict(value: Any) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _string(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


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


def build_trusted_registry_evidence(
    *,
    source_run_id: str,
    source_head_sha: str,
) -> JsonObject:
    run_id = _string(source_run_id)
    head_sha = _string(source_head_sha)
    if not run_id:
        raise ValueError("trusted flaky-test producer source_run_id is required")
    if not head_sha:
        raise ValueError("trusted flaky-test producer source_head_sha is required")

    evidence = build_flaky_test_registry_evidence(
        classification_report=_empty_classification_report(),
        source_kind="trusted_main_artifact",
        source_reference=f"{SOURCE_WORKFLOW}:run={run_id}:head={head_sha}",
    )

    source = _as_dict(evidence.get("source"))
    source.update(
        {
            "workflow": SOURCE_WORKFLOW,
            "run_id": run_id,
            "head_sha": head_sha,
            "observation_status": NO_TEST_OBSERVATIONS,
            "observations_collected": False,
        }
    )
    evidence["source"] = source

    summary = _as_dict(evidence.get("summary"))
    summary.update(
        {
            "observation_status": NO_TEST_OBSERVATIONS,
            "observation_count": 0,
        }
    )
    evidence["summary"] = summary
    evidence["note"] = (
        "Trusted-main producer is connected, but no per-test observation "
        "history source is available; no flaky-test entries are claimed."
    )
    return evidence


def build_producer_report(evidence: Mapping[str, Any]) -> JsonObject:
    source = _as_dict(evidence.get("source"))
    summary = _as_dict(evidence.get("summary"))
    boundary = _as_dict(evidence.get("decision_boundary"))
    return {
        "schema_version": SCHEMA_VERSION,
        "status": SOURCE_CONNECTED,
        "source": dict(source),
        "registry": {
            "schema_version": _string(evidence.get("schema_version")),
            "collection_status": _string(evidence.get("collection_status")),
            "status": _string(evidence.get("status")),
            "entry_count": int(summary.get("entry_count", 0)),
            "observation_status": _string(summary.get("observation_status")),
            "observation_count": int(summary.get("observation_count", 0)),
        },
        "decision_boundary": dict(boundary),
        "note": _string(evidence.get("note")),
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    source = _as_dict(report.get("source"))
    registry = _as_dict(report.get("registry"))
    boundary = _as_dict(report.get("decision_boundary"))
    return "\n".join(
        [
            "# Trusted-main flaky-test registry producer",
            "",
            f"- Status: `{_string(report.get('status'))}`",
            f"- Source workflow: `{_string(source.get('workflow'))}`",
            f"- Source run id: `{_string(source.get('run_id'))}`",
            f"- Source head sha: `{_string(source.get('head_sha'))}`",
            f"- Observation status: `{_string(registry.get('observation_status'))}`",
            f"- Observation count: `{int(registry.get('observation_count', 0))}`",
            f"- Registry entries: `{int(registry.get('entry_count', 0))}`",
            "",
            "## Boundary",
            "",
            "- No flaky-test observations are claimed without a trusted observation source.",
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
    producer_markdown.write_text(render_markdown(report), encoding="utf-8")
    artifacts["producer_json"] = producer_json.as_posix()
    artifacts["producer_markdown"] = producer_markdown.as_posix()
    return artifacts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.trusted_flaky_test_registry_producer")
    parser.add_argument("--source-run-id", required=True)
    parser.add_argument("--source-head-sha", required=True)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        evidence = build_trusted_registry_evidence(
            source_run_id=args.source_run_id,
            source_head_sha=args.source_head_sha,
        )
        report = build_producer_report(evidence)
        artifacts = write_artifacts(evidence, report, out_dir=args.out_dir)
    except (OSError, ValueError) as exc:
        print(f"error={exc}")
        return 2

    if args.format == "json":
        print(
            json.dumps(
                {
                    "status": report["status"],
                    "artifacts": artifacts,
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(f"status={report['status']}")
        for key, value in artifacts.items():
            print(f"{key}={value}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
