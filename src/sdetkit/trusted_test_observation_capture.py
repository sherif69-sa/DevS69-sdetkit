from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

SCHEMA_VERSION = "sdetkit.trusted_test_observation_capture.v1"
STATUS = "trusted_main_observations_captured"
TRUSTED_WORKFLOW = "CI"
TRUSTED_JOB = "Full CI lane"
TRUSTED_EVENT = "push"
TRUSTED_REF = "refs/heads/main"

DEFAULT_OUT_DIR = Path("build") / "trusted-test-observations"
OBSERVATIONS_JSON = "trusted-test-observations.json"
OBSERVATIONS_MD = "trusted-test-observations.md"

JsonObject = dict[str, Any]


def _text(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


def _validate_trusted_main_source(
    *,
    source_workflow: str,
    source_job: str,
    source_run_id: str,
    source_head_sha: str,
    event_name: str,
    ref_name: str,
) -> JsonObject:
    workflow = _text(source_workflow)
    job = _text(source_job)
    run_id = _text(source_run_id)
    head_sha = _text(source_head_sha)
    event = _text(event_name)
    ref = _text(ref_name)

    if workflow != TRUSTED_WORKFLOW:
        raise ValueError("trusted test observation workflow is not supported")
    if job != TRUSTED_JOB:
        raise ValueError("trusted test observation job is not supported")
    if event != TRUSTED_EVENT or ref != TRUSTED_REF:
        raise ValueError("trusted test observations require a main push source")
    if not run_id:
        raise ValueError("trusted test observation source_run_id is required")
    if not head_sha:
        raise ValueError("trusted test observation source_head_sha is required")

    return {
        "workflow": workflow,
        "job": job,
        "run_id": run_id,
        "head_sha": head_sha,
        "event_name": event,
        "ref_name": ref,
        "input_kind": "junit_xml",
        "identity_handling": "sha256_fingerprint_only",
        "input_read_only": True,
        "commands_executed_by_reader": False,
        "trusted_main": True,
    }


def _load_junit_root(path: Path) -> ET.Element:
    if not path.exists():
        raise ValueError("trusted test observation JUnit XML input does not exist")
    try:
        return ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise ValueError("trusted test observation JUnit XML is malformed") from exc


def _outcome(testcase: ET.Element) -> str:
    if testcase.find("failure") is not None:
        return "failed"
    if testcase.find("error") is not None:
        return "error"
    if testcase.find("skipped") is not None:
        return "skipped"
    return "passed"


def _observation(testcase: ET.Element) -> JsonObject:
    classname = _text(testcase.attrib.get("classname"))
    name = _text(testcase.attrib.get("name"))
    if not classname or not name:
        raise ValueError("trusted test observation testcase lacks classname or name")

    identity = f"{classname}::{name}"
    return {
        "test_fingerprint": hashlib.sha256(identity.encode("utf-8")).hexdigest(),
        "outcome": _outcome(testcase),
    }


def build_observation_report(
    *,
    junit_root: ET.Element,
    source_workflow: str,
    source_job: str,
    source_run_id: str,
    source_head_sha: str,
    event_name: str,
    ref_name: str,
) -> JsonObject:
    source = _validate_trusted_main_source(
        source_workflow=source_workflow,
        source_job=source_job,
        source_run_id=source_run_id,
        source_head_sha=source_head_sha,
        event_name=event_name,
        ref_name=ref_name,
    )

    observations = [_observation(testcase) for testcase in junit_root.iter("testcase")]
    if not observations:
        raise ValueError("trusted test observation JUnit XML contains no testcase observations")

    observations.sort(key=lambda item: item["test_fingerprint"])
    fingerprints = [item["test_fingerprint"] for item in observations]
    if len(fingerprints) != len(set(fingerprints)):
        raise ValueError("trusted test observation JUnit XML contains duplicate test identities")

    outcomes = Counter(str(item["outcome"]) for item in observations)

    return {
        "schema_version": SCHEMA_VERSION,
        "status": STATUS,
        "source": source,
        "observations": observations,
        "summary": {
            "observation_count": len(observations),
            "passed": outcomes["passed"],
            "failed": outcomes["failed"],
            "error": outcomes["error"],
            "skipped": outcomes["skipped"],
            "flaky_classification_performed": False,
            "raw_test_identity_emitted": False,
        },
        "decision_boundary": {
            "raw_observation_only": True,
            "raw_test_identity_emitted": False,
            "flaky_classification_performed": False,
            "automatic_quarantine_allowed": False,
            "automatic_rerun_allowed": False,
            "current_failure_suppression_allowed": False,
            "automation_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        },
        "note": (
            "This artifact records raw trusted-main test outcomes only. "
            "It does not classify flakiness or authorize action."
        ),
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    source = dict(report.get("source", {}))
    summary = dict(report.get("summary", {}))
    boundary = dict(report.get("decision_boundary", {}))
    return "\n".join(
        [
            "# Trusted-main test observations",
            "",
            f"- Status: `{_text(report.get('status'))}`",
            f"- Source workflow: `{_text(source.get('workflow'))}`",
            f"- Source job: `{_text(source.get('job'))}`",
            f"- Source head sha: `{_text(source.get('head_sha'))}`",
            f"- Observations: `{int(summary.get('observation_count', 0))}`",
            f"- Passed: `{int(summary.get('passed', 0))}`",
            f"- Failed: `{int(summary.get('failed', 0))}`",
            f"- Errors: `{int(summary.get('error', 0))}`",
            f"- Skipped: `{int(summary.get('skipped', 0))}`",
            f"- Identity handling: `{_text(source.get('identity_handling'))}`",
            "",
            "## Boundary",
            "",
            (
                "- Raw test identity emitted: "
                f"`{str(bool(boundary.get('raw_test_identity_emitted'))).lower()}`"
            ),
            (
                "- Flaky classification performed: "
                f"`{str(bool(boundary.get('flaky_classification_performed'))).lower()}`"
            ),
            (
                "- Current failure suppression allowed: "
                f"`{str(bool(boundary.get('current_failure_suppression_allowed'))).lower()}`"
            ),
            f"- Automation allowed: `{str(bool(boundary.get('automation_allowed'))).lower()}`",
            f"- Merge authorized: `{str(bool(boundary.get('merge_authorized'))).lower()}`",
            "",
        ]
    )


def write_report(report: Mapping[str, Any], *, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / OBSERVATIONS_JSON).write_text(
        json.dumps(dict(report), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / OBSERVATIONS_MD).write_text(render_markdown(report), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.trusted_test_observation_capture")
    parser.add_argument("--junit-xml", type=Path, required=True)
    parser.add_argument("--source-workflow", required=True)
    parser.add_argument("--source-job", required=True)
    parser.add_argument("--source-run-id", required=True)
    parser.add_argument("--source-head-sha", required=True)
    parser.add_argument("--event-name", required=True)
    parser.add_argument("--ref-name", required=True)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = build_observation_report(
            junit_root=_load_junit_root(args.junit_xml),
            source_workflow=args.source_workflow,
            source_job=args.source_job,
            source_run_id=args.source_run_id,
            source_head_sha=args.source_head_sha,
            event_name=args.event_name,
            ref_name=args.ref_name,
        )
        write_report(report, out_dir=args.out_dir)
    except (OSError, ValueError) as exc:
        print(f"error={exc}")
        return 2

    summary = dict(report["summary"])
    output = {
        "status": STATUS,
        "observation_count": int(summary["observation_count"]),
        "failed": int(summary["failed"]),
        "error": int(summary["error"]),
        "artifact_written": True,
    }
    if args.format == "json":
        print(json.dumps(output, indent=2, sort_keys=True))
    else:
        for key, value in output.items():
            print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
