from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sdetkit.trusted_test_observation_history import (
    ALLOWED_OUTCOMES,
    RECORD_SCHEMA_VERSION,
    validate_observation_history_record,
)

SCHEMA_VERSION = "sdetkit.trusted_test_observation_classification.v1"
STATUS = "advisory_classification_recorded"
DEFAULT_OUT_DIR = Path("build") / "trusted-test-observation-classification"
CLASSIFICATION_JSON = "trusted-test-observation-classification.json"
CLASSIFICATION_MD = "trusted-test-observation-classification.md"

MINIMUM_DECISIVE_OBSERVATIONS = 2
DECISIVE_PASS_OUTCOMES = {"passed"}
DECISIVE_FAILURE_OUTCOMES = {"failed", "error"}
NON_DECISIVE_OUTCOMES = {"skipped"}
ALLOWED_CLASSIFICATIONS = {
    "flaky",
    "stable-failing",
    "stable-passing",
    "insufficient-history",
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


def _validate_fingerprint(value: Any) -> str:
    fingerprint = _text(value).lower()
    if len(fingerprint) != 64 or any(char not in "0123456789abcdef" for char in fingerprint):
        raise ValueError(
            "trusted observation classification requires a 64-character SHA-256 test fingerprint"
        )
    return fingerprint


def _decision_boundary() -> JsonObject:
    return {
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
    }


def _classification_policy() -> JsonObject:
    return {
        "minimum_decisive_observations": MINIMUM_DECISIVE_OBSERVATIONS,
        "decisive_pass_outcomes": sorted(DECISIVE_PASS_OUTCOMES),
        "decisive_failure_outcomes": sorted(DECISIVE_FAILURE_OUTCOMES),
        "non_decisive_outcomes": sorted(NON_DECISIVE_OUTCOMES),
        "flaky": "at least one decisive pass and at least one decisive failure",
        "stable_passing": "at least two decisive passes and no decisive failures",
        "stable_failing": "at least two decisive failures and no decisive passes",
        "insufficient_history": "fewer than two decisive observations",
    }


def _classification_for(*, passes: int, failures: int) -> str:
    decisive = passes + failures
    if decisive >= MINIMUM_DECISIVE_OBSERVATIONS and passes and failures:
        return "flaky"
    if decisive >= MINIMUM_DECISIVE_OBSERVATIONS and passes >= 2 and failures == 0:
        return "stable-passing"
    if decisive >= MINIMUM_DECISIVE_OBSERVATIONS and failures >= 2 and passes == 0:
        return "stable-failing"
    return "insufficient-history"


def read_observation_history_records(path: Path) -> list[JsonObject]:
    if not path.exists():
        raise ValueError("trusted observation history JSONL does not exist")

    records: list[JsonObject] = []
    seen_record_ids: set[str] = set()
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError(
                f"trusted observation history JSONL must contain objects; line={line_number}"
            )
        validate_observation_history_record(payload)
        record_id = _text(payload.get("record_id"))
        if record_id in seen_record_ids:
            raise ValueError("trusted observation history contains duplicate record ids")
        seen_record_ids.add(record_id)
        records.append(dict(payload))
    return records


def build_trusted_observation_classification(
    records: list[Mapping[str, Any]],
) -> JsonObject:
    seen_record_ids: set[str] = set()
    record_ids: list[str] = []
    source_run_ids: list[str] = []
    source_head_shas: list[str] = []
    provenance_by_fingerprint: dict[str, list[JsonObject]] = defaultdict(list)

    for raw_record in records:
        validate_observation_history_record(raw_record)
        record = dict(raw_record)
        record_id = _text(record.get("record_id"))
        if record_id in seen_record_ids:
            raise ValueError(
                "trusted observation classification input contains duplicate record ids"
            )
        seen_record_ids.add(record_id)
        record_ids.append(record_id)

        source_run_id = _text(record.get("source_run_id"))
        source_head_sha = _text(record.get("source_head_sha"))
        source_run_ids.append(source_run_id)
        source_head_shas.append(source_head_sha)

        for raw_observation in _as_list(record.get("observations")):
            observation = _as_dict(raw_observation)
            fingerprint = _validate_fingerprint(observation.get("test_fingerprint"))
            outcome = _text(observation.get("outcome"))
            if outcome not in ALLOWED_OUTCOMES:
                raise ValueError(
                    "trusted observation classification input contains an unsupported outcome"
                )
            provenance_by_fingerprint[fingerprint].append(
                {
                    "source_run_id": source_run_id,
                    "source_head_sha": source_head_sha,
                    "outcome": outcome,
                }
            )

    classifications: list[JsonObject] = []
    summary_counts: Counter[str] = Counter()
    for fingerprint in sorted(provenance_by_fingerprint):
        provenance = provenance_by_fingerprint[fingerprint]
        outcomes = [_text(item.get("outcome")) for item in provenance]
        passed = outcomes.count("passed")
        failed = outcomes.count("failed")
        error = outcomes.count("error")
        skipped = outcomes.count("skipped")
        decisive_failures = failed + error
        decisive_count = passed + decisive_failures
        classification = _classification_for(passes=passed, failures=decisive_failures)
        summary_counts[classification] += 1
        classifications.append(
            {
                "test_fingerprint": fingerprint,
                "classification": classification,
                "decision": (
                    "instability_context_only"
                    if classification == "flaky"
                    else "advisory_context_only"
                ),
                "review_first": True,
                "runs_observed": len(provenance),
                "decisive_observation_count": decisive_count,
                "passed": passed,
                "failed": failed,
                "error": error,
                "skipped": skipped,
                "observation_provenance": provenance,
                "automatic_quarantine_allowed": False,
                "automatic_rerun_allowed": False,
                "current_failure_suppression_allowed": False,
                "automation_allowed": False,
            }
        )

    report: JsonObject = {
        "schema_version": SCHEMA_VERSION,
        "status": STATUS,
        "source": {
            "history_record_schema": RECORD_SCHEMA_VERSION,
            "record_count": len(records),
            "record_ids": record_ids,
            "source_run_ids": source_run_ids,
            "source_head_shas": source_head_shas,
            "input_read_only": True,
            "commands_executed_by_reader": False,
            "per_observation_provenance_bound": True,
        },
        "policy": _classification_policy(),
        "summary": {
            "fingerprint_count": len(classifications),
            "flaky": summary_counts["flaky"],
            "stable_failing": summary_counts["stable-failing"],
            "stable_passing": summary_counts["stable-passing"],
            "insufficient_history": summary_counts["insufficient-history"],
            "classification_performed": True,
            "raw_test_identity_emitted": False,
            "current_pr_decision_input": False,
        },
        "classifications": classifications,
        "decision_boundary": _decision_boundary(),
        "recommended_next_action": (
            "Use this provenance-bound advisory artifact only through a "
            "separately audited producer handoff."
        ),
    }
    validate_classification_report(report)
    return report


def validate_classification_report(report: Mapping[str, Any]) -> None:
    if _text(report.get("schema_version")) != SCHEMA_VERSION:
        raise ValueError("trusted observation classification schema is not supported")
    if _text(report.get("status")) != STATUS:
        raise ValueError("trusted observation classification status is not supported")

    source = _as_dict(report.get("source"))
    if _text(source.get("history_record_schema")) != RECORD_SCHEMA_VERSION:
        raise ValueError("trusted observation classification source schema is not supported")
    if source.get("input_read_only") is not True:
        raise ValueError("trusted observation classification input must be read-only")
    if source.get("commands_executed_by_reader") is not False:
        raise ValueError("trusted observation classification reader cannot execute commands")
    if source.get("per_observation_provenance_bound") is not True:
        raise ValueError("trusted observation classification requires per-observation provenance")

    record_ids = [_text(item) for item in _as_list(source.get("record_ids"))]
    source_run_ids = [_text(item) for item in _as_list(source.get("source_run_ids"))]
    source_head_shas = [_text(item) for item in _as_list(source.get("source_head_shas"))]
    record_count = _int(source.get("record_count"))
    if not (record_count == len(record_ids) == len(source_run_ids) == len(source_head_shas)):
        raise ValueError(
            "trusted observation classification source provenance totals are inconsistent"
        )
    if len(set(record_ids)) != len(record_ids):
        raise ValueError("trusted observation classification contains duplicate source record ids")
    if any(not value for value in (*record_ids, *source_run_ids, *source_head_shas)):
        raise ValueError("trusted observation classification source provenance is incomplete")
    if _as_dict(report.get("policy")) != _classification_policy():
        raise ValueError("trusted observation classification policy is inconsistent")

    classifications = [_as_dict(item) for item in _as_list(report.get("classifications"))]
    if any(not item for item in classifications):
        raise ValueError("trusted observation classification contains a non-object entry")

    fingerprints: list[str] = []
    classification_counts: Counter[str] = Counter()
    allowed_source_pairs = set(zip(source_run_ids, source_head_shas, strict=True))

    for item in classifications:
        for forbidden_key in ("test_id", "classname", "name", "nodeid"):
            if forbidden_key in item:
                raise ValueError(
                    "raw test identity cannot enter trusted observation classification"
                )

        fingerprint = _validate_fingerprint(item.get("test_fingerprint"))
        fingerprints.append(fingerprint)
        classification = _text(item.get("classification"))
        if classification not in ALLOWED_CLASSIFICATIONS:
            raise ValueError(
                "trusted observation classification contains an unsupported classification"
            )
        classification_counts[classification] += 1

        provenance = [_as_dict(entry) for entry in _as_list(item.get("observation_provenance"))]
        if not provenance or any(not entry for entry in provenance):
            raise ValueError("trusted observation classification requires observation provenance")

        outcomes: list[str] = []
        for entry in provenance:
            if set(entry) != {"source_run_id", "source_head_sha", "outcome"}:
                raise ValueError(
                    "trusted observation classification provenance fields are inconsistent"
                )
            pair = (
                _text(entry.get("source_run_id")),
                _text(entry.get("source_head_sha")),
            )
            if pair not in allowed_source_pairs:
                raise ValueError(
                    "trusted observation classification provenance is not bound to source history"
                )
            outcome = _text(entry.get("outcome"))
            if outcome not in ALLOWED_OUTCOMES:
                raise ValueError(
                    "trusted observation classification provenance contains an unsupported outcome"
                )
            outcomes.append(outcome)

        passed = outcomes.count("passed")
        failed = outcomes.count("failed")
        error = outcomes.count("error")
        skipped = outcomes.count("skipped")
        decisive_failures = failed + error
        expected_classification = _classification_for(passes=passed, failures=decisive_failures)
        if classification != expected_classification:
            raise ValueError("trusted observation classification does not match its observations")
        if _int(item.get("runs_observed")) != len(provenance):
            raise ValueError("trusted observation classification run count is inconsistent")
        if _int(item.get("decisive_observation_count")) != (passed + decisive_failures):
            raise ValueError("trusted observation classification decisive count is inconsistent")
        for key, expected in (
            ("passed", passed),
            ("failed", failed),
            ("error", error),
            ("skipped", skipped),
        ):
            if _int(item.get(key)) != expected:
                raise ValueError(f"trusted observation classification {key} count is inconsistent")
        for key in (
            "automatic_quarantine_allowed",
            "automatic_rerun_allowed",
            "current_failure_suppression_allowed",
            "automation_allowed",
        ):
            if item.get(key) is not False:
                raise ValueError("trusted observation classification entry expands authority")
        if item.get("review_first") is not True:
            raise ValueError("trusted observation classification entry must remain review-first")

    if fingerprints != sorted(fingerprints):
        raise ValueError("trusted observation classification ordering is not deterministic")
    if len(set(fingerprints)) != len(fingerprints):
        raise ValueError("trusted observation classification contains duplicate fingerprints")

    summary = _as_dict(report.get("summary"))
    if _int(summary.get("fingerprint_count")) != len(classifications):
        raise ValueError("trusted observation classification summary count is inconsistent")
    for key, classification in (
        ("flaky", "flaky"),
        ("stable_failing", "stable-failing"),
        ("stable_passing", "stable-passing"),
        ("insufficient_history", "insufficient-history"),
    ):
        if _int(summary.get(key)) != classification_counts[classification]:
            raise ValueError(f"trusted observation classification summary {key} is inconsistent")
    if summary.get("classification_performed") is not True:
        raise ValueError("trusted observation classification summary must record classification")
    if summary.get("raw_test_identity_emitted") is not False:
        raise ValueError("trusted observation classification cannot emit raw test identity")
    if summary.get("current_pr_decision_input") is not False:
        raise ValueError(
            "trusted observation classification cannot influence the current PR decision"
        )
    if _as_dict(report.get("decision_boundary")) != _decision_boundary():
        raise ValueError("trusted observation classification authority boundary is inconsistent")


def render_classification_markdown(report: Mapping[str, Any]) -> str:
    validate_classification_report(report)
    source = _as_dict(report.get("source"))
    summary = _as_dict(report.get("summary"))
    boundary = _as_dict(report.get("decision_boundary"))
    classifications = [_as_dict(item) for item in _as_list(report.get("classifications"))]

    lines = [
        "# Trusted test observation classification",
        "",
        f"- Schema: `{_text(report.get('schema_version'))}`",
        f"- Status: `{_text(report.get('status'))}`",
        f"- Source records: `{_int(source.get('record_count'))}`",
        f"- Fingerprints: `{_int(summary.get('fingerprint_count'))}`",
        f"- Flaky: `{_int(summary.get('flaky'))}`",
        f"- Stable failing: `{_int(summary.get('stable_failing'))}`",
        f"- Stable passing: `{_int(summary.get('stable_passing'))}`",
        f"- Insufficient history: `{_int(summary.get('insufficient_history'))}`",
        "",
        "## Advisory classifications",
        "",
    ]
    if classifications:
        for item in classifications:
            lines.append(
                "- fingerprint="
                f"`{_text(item.get('test_fingerprint'))}`, "
                "classification="
                f"`{_text(item.get('classification'))}`, "
                "decisive_observations="
                f"`{_int(item.get('decisive_observation_count'))}`, "
                f"decision=`{_text(item.get('decision'))}`"
            )
    else:
        lines.append("- none observed")

    lines.extend(
        [
            "",
            "## Boundary",
            "",
            f"- Advisory only: `{str(bool(boundary.get('advisory_only'))).lower()}`",
            "- Raw test identity emitted: "
            f"`{str(bool(boundary.get('raw_test_identity_emitted'))).lower()}`",
            "- Current PR decision input: "
            f"`{str(bool(boundary.get('current_pr_decision_input'))).lower()}`",
            "- Automatic quarantine allowed: "
            f"`{str(bool(boundary.get('automatic_quarantine_allowed'))).lower()}`",
            "- Automatic rerun allowed: "
            f"`{str(bool(boundary.get('automatic_rerun_allowed'))).lower()}`",
            "- Current failure suppression allowed: "
            f"`{str(bool(boundary.get('current_failure_suppression_allowed'))).lower()}`",
            f"- Automation allowed: `{str(bool(boundary.get('automation_allowed'))).lower()}`",
            "- Patch application allowed: "
            f"`{str(bool(boundary.get('patch_application_allowed'))).lower()}`",
            f"- Merge authorized: `{str(bool(boundary.get('merge_authorized'))).lower()}`",
            "- Semantic equivalence proven: "
            f"`{str(bool(boundary.get('semantic_equivalence_proven'))).lower()}`",
            "",
        ]
    )
    return "\n".join(lines)


def write_classification_artifacts(report: Mapping[str, Any], *, out_dir: Path) -> dict[str, str]:
    validate_classification_report(report)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / CLASSIFICATION_JSON
    markdown_path = out_dir / CLASSIFICATION_MD
    json_path.write_text(
        json.dumps(dict(report), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_classification_markdown(report), encoding="utf-8")
    return {
        "classification_json": json_path.as_posix(),
        "classification_markdown": markdown_path.as_posix(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m sdetkit.trusted_test_observation_classification"
    )
    parser.add_argument("--history-jsonl", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        records = read_observation_history_records(args.history_jsonl)
        report = build_trusted_observation_classification(records)
        artifacts = write_classification_artifacts(report, out_dir=args.out_dir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}")
        return 2

    if args.format == "json":
        print(
            json.dumps(
                {"status": report["status"], "artifacts": artifacts},
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
