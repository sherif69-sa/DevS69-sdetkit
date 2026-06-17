from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sdetkit.trusted_test_observation_classification import (
    SCHEMA_VERSION as TRUSTED_CLASSIFICATION_SCHEMA_VERSION,
)
from sdetkit.trusted_test_observation_classification import (
    validate_classification_report,
)

SCHEMA_VERSION = "sdetkit.flaky_test_registry_evidence.v1"
SOURCE_SCHEMA_VERSION = "sdetkit.intelligence.flake.v1"
DEFAULT_OUT_DIR = Path("build") / "flaky-test-registry"
EVIDENCE_JSON = "flaky-test-registry-evidence.json"
EVIDENCE_MD = "flaky-test-registry-evidence.md"
EVIDENCE_KEYS = {
    "json": "_".join(("flaky", "test", "registry", "evidence", "json")),
    "markdown": "_".join(("flaky", "test", "registry", "evidence", "markdown")),
}


COLLECTED = "collected"
STATUS = "advisory_registry_collected"
TRUSTED_SOURCE_IDENTITY_KIND = "fingerprint_only"
VALID_SOURCE_KINDS = {
    "operator_review_input",
    "trusted_main_artifact",
}

JsonObject = dict[str, Any]


def _as_dict(value: Any) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


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


def build_flaky_test_registry_evidence(
    *,
    classification_report: Mapping[str, Any],
    source_kind: str,
    source_reference: str,
) -> JsonObject:
    if source_kind not in VALID_SOURCE_KINDS:
        raise ValueError(f"unsupported flaky-test evidence source kind: {source_kind}")

    source_reference_value = _string(source_reference)
    if not source_reference_value:
        raise ValueError("flaky-test evidence source reference is required")

    if _string(classification_report.get("schema_version")) != SOURCE_SCHEMA_VERSION:
        raise ValueError("unsupported flaky-test classification report schema")

    raw_tests = classification_report.get("tests")
    if not isinstance(raw_tests, list):
        raise ValueError("flaky-test classification report must contain a tests array")

    entries: list[JsonObject] = []
    allowed_classifications = {"flaky", "stable-failing", "stable-passing"}

    for raw_item in raw_tests:
        if not isinstance(raw_item, dict):
            raise ValueError("flaky-test classification report contains a non-object entry")

        item = raw_item
        classification = _string(item.get("classification"))
        if classification not in allowed_classifications:
            raise ValueError(f"unsupported flaky-test classification: {classification}")
        if classification != "flaky":
            continue

        test_id = _string(item.get("test_id"))
        fingerprint = _string(item.get("fingerprint"))
        runs = _int(item.get("runs"))
        failures = _int(item.get("failures"))
        passes = _int(item.get("passes"))

        if not test_id or not fingerprint:
            raise ValueError("flaky-test entry requires test_id and fingerprint")
        if runs < 2 or failures < 1 or passes < 1:
            raise ValueError("flaky-test entry does not prove mixed pass/fail observations")

        entries.append(
            {
                "test_id": test_id,
                "fingerprint": fingerprint,
                "classification": "flaky",
                "observed_runs": runs,
                "observed_failures": failures,
                "observed_passes": passes,
                "decision": "instability_context_only",
                "review_first": True,
                "automatic_quarantine_allowed": False,
                "automatic_rerun_allowed": False,
                "current_failure_suppression_allowed": False,
                "automation_allowed": False,
            }
        )

    entries.sort(key=lambda item: (str(item["test_id"]), str(item["fingerprint"])))

    return {
        "schema_version": SCHEMA_VERSION,
        "collection_status": COLLECTED,
        "status": STATUS,
        "source": {
            "kind": source_kind,
            "reference": source_reference_value,
            "classification_schema": SOURCE_SCHEMA_VERSION,
            "input_read_only": True,
            "commands_executed_by_reader": False,
        },
        "summary": {
            "entry_count": len(entries),
            "flaky_test_count": len(entries),
        },
        "entries": entries,
        "decision_boundary": {
            "advisory_only": True,
            "automatic_quarantine_allowed": False,
            "automatic_rerun_allowed": False,
            "current_failure_suppression_allowed": False,
            "automation_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
            "reason": (
                "Flaky-test history is advisory context only; current failures "
                "remain active until independently diagnosed and proven."
            ),
        },
    }


def build_producer_vetted_fingerprint_registry_evidence(
    *,
    classification_report: Mapping[str, Any],
    source_reference: str,
) -> JsonObject:
    source_reference_value = _string(source_reference)
    if not source_reference_value:
        raise ValueError("flaky-test evidence source reference is required")

    validate_classification_report(classification_report)

    entries: list[JsonObject] = []
    for raw_item in _as_list(classification_report.get("classifications")):
        item = _as_dict(raw_item)
        if _string(item.get("classification")) != "flaky":
            continue

        provenance = [
            dict(_as_dict(entry)) for entry in _as_list(item.get("observation_provenance"))
        ]
        entries.append(
            {
                "test_fingerprint": _string(item.get("test_fingerprint")),
                "classification": "flaky",
                "observed_runs": _int(item.get("runs_observed")),
                "decisive_observation_count": _int(item.get("decisive_observation_count")),
                "observed_passes": _int(item.get("passed")),
                "observed_failures": _int(item.get("failed")) + _int(item.get("error")),
                "observed_errors": _int(item.get("error")),
                "observed_skipped": _int(item.get("skipped")),
                "observation_provenance": provenance,
                "decision": "instability_context_only",
                "review_first": True,
                "current_pr_decision_input": False,
                "automatic_quarantine_allowed": False,
                "automatic_rerun_allowed": False,
                "current_failure_suppression_allowed": False,
                "automation_allowed": False,
                "patch_application_allowed": False,
                "merge_authorized": False,
                "semantic_equivalence_proven": False,
            }
        )

    entries.sort(key=lambda item: str(item["test_fingerprint"]))
    summary = _as_dict(classification_report.get("summary"))

    return {
        "schema_version": SCHEMA_VERSION,
        "collection_status": COLLECTED,
        "status": STATUS,
        "source": {
            "kind": "trusted_main_artifact",
            "reference": source_reference_value,
            "classification_schema": TRUSTED_CLASSIFICATION_SCHEMA_VERSION,
            "identity_kind": TRUSTED_SOURCE_IDENTITY_KIND,
            "input_read_only": True,
            "commands_executed_by_reader": False,
            "producer_vetted": True,
            "raw_test_identity_emitted": False,
        },
        "summary": {
            "entry_count": len(entries),
            "flaky_test_count": len(entries),
            "classification_fingerprint_count": _int(summary.get("fingerprint_count")),
        },
        "entries": entries,
        "decision_boundary": {
            "advisory_only": True,
            "raw_test_identity_emitted": False,
            "current_pr_decision_input": False,
            "automatic_quarantine_allowed": False,
            "automatic_rerun_allowed": False,
            "current_failure_suppression_allowed": False,
            "automation_allowed": False,
            "patch_application_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
            "reason": (
                "Producer-vetted flaky fingerprints are advisory context only; "
                "current failures remain active until independently diagnosed and proven."
            ),
        },
    }


def render_markdown(evidence: Mapping[str, Any]) -> str:
    source = _as_dict(evidence.get("source"))
    summary = _as_dict(evidence.get("summary"))
    boundary = _as_dict(evidence.get("decision_boundary"))
    entries = [_as_dict(item) for item in _as_list(evidence.get("entries"))]

    lines = [
        "# Flaky-test registry evidence",
        "",
        f"- Schema: `{_string(evidence.get('schema_version'))}`",
        f"- Status: `{_string(evidence.get('status'))}`",
        f"- Source kind: `{_string(source.get('kind'))}`",
        f"- Input read-only: `{str(bool(source.get('input_read_only'))).lower()}`",
        f"- Entries: `{_int(summary.get('entry_count'))}`",
        "",
        "## Instability context",
        "",
    ]

    if entries:
        for entry in entries:
            test_id = _string(entry.get("test_id"))
            identity_label = "test" if test_id else "fingerprint"
            identity = test_id or _string(entry.get("test_fingerprint"))
            lines.append(
                f"- {identity_label}=`{identity}`, "
                f"runs=`{_int(entry.get('observed_runs'))}`, "
                f"failures=`{_int(entry.get('observed_failures'))}`, "
                f"passes=`{_int(entry.get('observed_passes'))}`, "
                "decision=`instability_context_only`"
            )
    else:
        lines.append("- none observed")

    lines.extend(
        [
            "",
            "## Boundary",
            "",
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
            (
                "- Semantic equivalence proven: "
                f"`{str(bool(boundary.get('semantic_equivalence_proven'))).lower()}`"
            ),
            "",
        ]
    )
    return "\n".join(lines)


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
        EVIDENCE_KEYS["json"]: json_path.as_posix(),
        EVIDENCE_KEYS["markdown"]: markdown_path.as_posix(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.flaky_test_registry_evidence")
    parser.add_argument("--classification-report", type=Path, required=True)
    parser.add_argument(
        "--source-kind",
        choices=sorted(VALID_SOURCE_KINDS),
        required=True,
    )
    parser.add_argument("--source-reference", default="")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        evidence = build_flaky_test_registry_evidence(
            classification_report=_read_json(args.classification_report),
            source_kind=args.source_kind,
            source_reference=args.source_reference,
        )
        artifacts = write_evidence(evidence, out_dir=args.out_dir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}")
        return 2

    if args.format == "json":
        print(
            json.dumps(
                {
                    "status": "written",
                    "artifacts": artifacts,
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print("flaky_test_registry_evidence_written=true")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
