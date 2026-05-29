"""Read accepted-main DiagnosticSignalSnapshot history without granting authority."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sdetkit.diagnostic_signal_snapshot_history import (
    HISTORICAL_SNAPSHOT_AUTHORIZES_CURRENT_ACTION,
    HISTORY_RECORDED,
    RATE_STATUS,
    RETENTION_WORKFLOW,
    validate_record,
)

SCHEMA_VERSION = ".".join(
    ("sdetkit", "trusted", "diagnostic", "signal", "snapshot", "history", "v1")
)
DEFAULT_OUT_DIR = Path("build") / "pr-quality" / "trusted-diagnostic-signal-snapshot-history"
EVIDENCE_JSON = "trusted-diagnostic-signal-snapshot-history.json"
EVIDENCE_MD = "trusted-diagnostic-signal-snapshot-history.md"
COLLECTED = "collected"
TRUSTED_HISTORY_VERIFIED = "_".join(
    ("trusted", "diagnostic", "signal", "snapshot", "history", "verified")
)

JsonObject = dict[str, Any]


def _as_dict(value: Any) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _text(value: Any) -> str:
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
    expected = {
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
    for key, expected_value in expected.items():
        if boundary.get(key) is not expected_value:
            raise ValueError(f"{source} does not preserve no-authority boundary: {key}")


def verify_base_ancestry(
    *,
    repo_root: Path,
    selected_head_sha: str,
    base_sha: str,
) -> None:
    selected = _text(selected_head_sha)
    base = _text(base_sha)
    if not selected:
        raise ValueError("selected_head_sha is required")
    if not base:
        raise ValueError("base_sha is required")

    completed = subprocess.run(
        ["git", "-C", str(repo_root), "merge-base", "--is-ancestor", selected, base],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode == 1:
        raise ValueError(
            "selected diagnostic snapshot history head is not an ancestor of the PR base"
        )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or "git ancestry verification failed"
        raise ValueError(detail)


def build_trusted_snapshot_history_evidence(
    *,
    summary: Mapping[str, Any],
    records: list[Mapping[str, Any]],
    selected_retention_run_id: str,
    selected_head_sha: str,
    base_sha: str,
    base_ancestry_verified: bool,
) -> JsonObject:
    if not base_ancestry_verified:
        raise ValueError("diagnostic snapshot history base ancestry was not verified")
    if not records:
        raise ValueError("diagnostic snapshot history contains no records")
    for record in records:
        validate_record(record)

    if _text(summary.get("status")) != HISTORY_RECORDED:
        raise ValueError("diagnostic snapshot history summary status is not supported")
    if _int(summary.get("record_count")) != len(records):
        raise ValueError("diagnostic snapshot history summary count does not match JSONL records")
    if _text(summary.get("advisor_false_positive_rate_status")) != RATE_STATUS:
        raise ValueError("diagnostic snapshot history cannot claim an advisor false-positive rate")
    if summary.get("reviewed_false_positive_count") is not None:
        raise ValueError("diagnostic snapshot history cannot carry reviewed false-positive counts")
    if summary.get("reviewed_observation_count") is not None:
        raise ValueError("diagnostic snapshot history cannot carry reviewed observation counts")
    _assert_no_authority(
        _as_dict(summary.get("decision_boundary")),
        source="diagnostic snapshot history summary",
    )

    expected_quiet = sum(
        1
        for record in records
        if _as_dict(record.get("snapshot")).get("quiet_green_advisory_baseline") is True
    )
    expected_review = sum(
        1
        for record in records
        if _as_dict(record.get("snapshot")).get("review_signal_present") is True
    )
    expected_integration = sum(
        1
        for record in records
        if _as_dict(record.get("snapshot")).get("integration_proof_signal_present") is True
    )
    expected_counts = {
        "quiet_green_advisory_baseline_record_count": expected_quiet,
        "review_signal_record_count": expected_review,
        "integration_proof_signal_record_count": expected_integration,
    }
    for key, expected in expected_counts.items():
        if _int(summary.get(key)) != expected:
            raise ValueError("diagnostic snapshot history signal totals do not match records")

    selected_run = _text(selected_retention_run_id)
    selected_head = _text(selected_head_sha)
    latest = _as_dict(records[-1])
    latest_source = _as_dict(latest.get("source"))
    summary_latest = _as_dict(summary.get("latest_record"))
    if _text(latest_source.get("retention_run_id")) != selected_run:
        raise ValueError("selected retention run does not match latest JSONL record")
    if _text(latest_source.get("accepted_main_sha")) != selected_head:
        raise ValueError("selected accepted-main head does not match latest JSONL record")
    if _text(summary_latest.get("retention_run_id")) != selected_run:
        raise ValueError("selected retention run does not match latest summary record")
    if _text(summary_latest.get("accepted_main_sha")) != selected_head:
        raise ValueError("selected accepted-main head does not match latest summary record")

    latest_snapshot = _as_dict(latest.get("snapshot"))
    return {
        "schema_version": SCHEMA_VERSION,
        "collection_status": COLLECTED,
        "status": TRUSTED_HISTORY_VERIFIED,
        "source": {
            "workflow": RETENTION_WORKFLOW,
            "run_id": selected_run,
            "head_sha": selected_head,
            "base_sha": _text(base_sha),
            "base_ancestry_verified": True,
        },
        "history": {
            "record_count": len(records),
            **expected_counts,
            "latest_snapshot_status": _text(latest_snapshot.get("status")),
            "latest_primary_signal_kind": _text(latest_snapshot.get("primary_signal_kind")),
            "advisor_false_positive_rate_status": RATE_STATUS,
            "reviewed_false_positive_count": None,
            "reviewed_observation_count": None,
            "prior_history_is_read_only_input": True,
        },
        "decision_boundary": {
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
        },
    }


def render_markdown(evidence: Mapping[str, Any]) -> str:
    source = _as_dict(evidence.get("source"))
    history = _as_dict(evidence.get("history"))
    boundary = _as_dict(evidence.get("decision_boundary"))
    return "\n".join(
        [
            "## Trusted diagnostic signal snapshot history",
            "",
            "- Evidence type: `accepted_main_reporting_only_snapshot_history`",
            f"- Collection status: `{_text(evidence.get('collection_status'))}`",
            f"- Status: `{_text(evidence.get('status'))}`",
            f"- Source workflow: `{_text(source.get('workflow'))}`",
            f"- Latest accepted main head: `{_text(source.get('head_sha'))}`",
            f"- Base ancestry verified: `{str(_bool(source.get('base_ancestry_verified'))).lower()}`",
            f"- Records: `{_int(history.get('record_count'))}`",
            (
                "- Quiet-green advisory baseline records: "
                f"`{_int(history.get('quiet_green_advisory_baseline_record_count'))}`"
            ),
            f"- Review-signal records: `{_int(history.get('review_signal_record_count'))}`",
            (
                "- Integration-proof-signal records: "
                f"`{_int(history.get('integration_proof_signal_record_count'))}`"
            ),
            (
                "- Latest retained snapshot status: "
                f"`{_text(history.get('latest_snapshot_status'))}`"
            ),
            (
                "- Advisor false-positive rate status: "
                f"`{_text(history.get('advisor_false_positive_rate_status'))}`"
            ),
            "- Interpretation: accepted-main snapshot history shows advisory signal availability only; reviewed false-positive labels and a valid denominator are not present.",
            "",
            "### Boundary",
            "",
            f"- Reporting only: `{str(_bool(boundary.get('reporting_only'))).lower()}`",
            (
                "- Current PR decision input: "
                f"`{str(_bool(boundary.get('current_pr_decision_input'))).lower()}`"
            ),
            f"- Feeds RepoMemory: `{str(_bool(boundary.get('feeds_repo_memory'))).lower()}`",
            (
                "- Prior history is read-only input: "
                f"`{str(_bool(boundary.get('prior_history_is_read_only_input'))).lower()}`"
            ),
            (
                "- Proof commands executed: "
                f"`{str(_bool(boundary.get('proof_commands_executed'))).lower()}`"
            ),
            (
                "- Patch application allowed: "
                f"`{str(_bool(boundary.get('patch_application_allowed'))).lower()}`"
            ),
            f"- Automation allowed: `{str(_bool(boundary.get('automation_allowed'))).lower()}`",
            f"- Merge authorized: `{str(_bool(boundary.get('merge_authorized'))).lower()}`",
            (
                "- Semantic equivalence proven: "
                f"`{str(_bool(boundary.get('semantic_equivalence_proven'))).lower()}`"
            ),
            (
                "- Historical snapshot authorizes current action: "
                f"`{str(_bool(boundary.get(HISTORICAL_SNAPSHOT_AUTHORIZES_CURRENT_ACTION))).lower()}`"
            ),
            "",
        ]
    )


def write_evidence(evidence: Mapping[str, Any], *, out_dir: Path) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / EVIDENCE_JSON
    markdown_path = out_dir / EVIDENCE_MD
    json_path.write_text(
        json.dumps(dict(evidence), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    markdown_path.write_text(render_markdown(evidence), encoding="utf-8")
    return {
        "trusted_diagnostic_signal_snapshot_history_json": json_path.as_posix(),
        "trusted_diagnostic_signal_snapshot_history_markdown": markdown_path.as_posix(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m sdetkit.trusted_diagnostic_signal_snapshot_history"
    )
    parser.add_argument("--history-summary", type=Path, required=True)
    parser.add_argument("--history-jsonl", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--selected-retention-run-id", required=True)
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
        evidence = build_trusted_snapshot_history_evidence(
            summary=_read_json(args.history_summary),
            records=_read_jsonl(args.history_jsonl),
            selected_retention_run_id=args.selected_retention_run_id,
            selected_head_sha=args.selected_head_sha,
            base_sha=args.base_sha,
            base_ancestry_verified=True,
        )
        write_evidence(evidence, out_dir=args.out_dir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}", file=sys.stderr)
        return 2

    if args.format == "json":
        print(
            json.dumps(
                {
                    "artifacts_written": True,
                    "collection_status": COLLECTED,
                    "status": TRUSTED_HISTORY_VERIFIED,
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(f"status={TRUSTED_HISTORY_VERIFIED}")
        print(f"collection_status={COLLECTED}")
        print("artifacts_written=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
