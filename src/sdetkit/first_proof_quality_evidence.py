"""Read-only first-proof quality evidence bundle.

The bundle projects three existing first-proof artifacts into one deterministic,
reviewer-facing report. It never refreshes source artifacts, mutates repository
state, authorizes merge, applies patches, dismisses security findings, or claims
semantic equivalence.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .report_provenance import (
    attach_provenance,
    build_input_provenance,
    check_report_path,
    render_freshness_text,
)

JsonObject = dict[str, Any]

SCHEMA_VERSION = "sdetkit.first_proof_quality_evidence.v1"
DEFAULT_ARTIFACT_DIR = Path("build/first-proof")
DEFAULT_OUT = Path("build/sdetkit/first-proof-quality-evidence.json")
DEFAULT_MARKDOWN_OUT = Path("build/sdetkit/first-proof-quality-evidence.md")
GENERATOR_SOURCE = "src/sdetkit/first_proof_quality_evidence.py"
SOURCE_ISSUE_NUMBER = 1843

_AUTHORITY_BOUNDARY: JsonObject = {
    "boundary_mode": "reporting_only",
    "reporting_only": True,
    "repo_mutation": False,
    "issue_mutation_allowed": False,
    "automation_allowed": False,
    "patch_application_allowed": False,
    "security_dismissal_allowed": False,
    "merge_authorized": False,
    "semantic_equivalence_proven": False,
}


@dataclass(frozen=True)
class SourceSpec:
    source_id: str
    filename: str
    expected_schema: str | None
    refresh_command: str


SOURCE_SPECS: tuple[SourceSpec, ...] = (
    SourceSpec(
        source_id="health_score",
        filename="health-score.json",
        expected_schema="1.0.0",
        refresh_command="make first-proof-health-score",
    ),
    SourceSpec(
        source_id="dashboard",
        filename="dashboard.json",
        expected_schema="1.0.0",
        refresh_command="make first-proof-dashboard",
    ),
    SourceSpec(
        source_id="readiness_threshold",
        filename="readiness-threshold.json",
        expected_schema=None,
        refresh_command="make first-proof-readiness-threshold",
    ),
)


def _input_bytes(path: Path) -> bytes:
    if not path.is_file():
        return b"missing\0"
    return b"present\0" + path.read_bytes()


def _source_path(artifact_dir: Path, spec: SourceSpec) -> Path:
    return artifact_dir / spec.filename


def first_proof_quality_input_provenance(
    *,
    repo_root: str | Path = ".",
    artifact_dir: str | Path = DEFAULT_ARTIFACT_DIR,
    current_head_sha: str | None = None,
    generated_at: str | None = None,
) -> JsonObject:
    root = Path(repo_root).resolve()
    artifact_root = Path(artifact_dir)
    if not artifact_root.is_absolute():
        artifact_root = root / artifact_root

    data_inputs = {
        f"first-proof/{spec.filename}": _input_bytes(_source_path(artifact_root, spec))
        for spec in SOURCE_SPECS
    }
    return build_input_provenance(
        schema_version=SCHEMA_VERSION,
        generator_source=GENERATOR_SOURCE,
        generator_bytes=Path(__file__).read_bytes(),
        data_inputs=data_inputs,
        root=root,
        source_issue_numbers=(SOURCE_ISSUE_NUMBER,),
        source_run_ids=(),
        input_artifact_schemas={
            spec.source_id: spec.expected_schema or "legacy-unversioned" for spec in SOURCE_SPECS
        },
        current_head_sha=current_head_sha,
        generated_at=generated_at,
    )


def _finding(
    *,
    finding_id: str,
    severity: str,
    summary: str,
    source_ids: Sequence[str],
    evidence: str,
) -> JsonObject:
    return {
        "finding_id": finding_id,
        "severity": severity,
        "summary": summary,
        "source_ids": list(source_ids),
        "evidence": evidence,
        "reporting_only": True,
        "safe_to_patch": False,
        "merge_authorized": False,
    }


def _load_source(
    *,
    artifact_root: Path,
    spec: SourceSpec,
    current_head_sha: str,
) -> tuple[JsonObject, JsonObject | None, list[JsonObject]]:
    path = _source_path(artifact_root, spec)
    relative_path = path.as_posix()
    findings: list[JsonObject] = []

    record: JsonObject = {
        "source_id": spec.source_id,
        "path": relative_path,
        "expected_schema_version": spec.expected_schema or "",
        "refresh_command": spec.refresh_command,
        "exists": path.is_file(),
        "state": "missing",
        "schema_version": "",
        "current_head_sha": "",
        "head_binding": "missing",
        "payload_status": "",
    }

    if not path.is_file():
        findings.append(
            _finding(
                finding_id=f"{spec.source_id}_missing",
                severity="partial",
                summary="Required first-proof evidence artifact is missing.",
                source_ids=(spec.source_id,),
                evidence=relative_path,
            )
        )
        return record, None, findings

    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        record["state"] = "invalid"
        findings.append(
            _finding(
                finding_id=f"{spec.source_id}_invalid_json",
                severity="blocking",
                summary="First-proof evidence artifact is not valid JSON.",
                source_ids=(spec.source_id,),
                evidence=f"{relative_path}:{type(exc).__name__}",
            )
        )
        return record, None, findings

    if not isinstance(loaded, dict):
        record["state"] = "invalid"
        findings.append(
            _finding(
                finding_id=f"{spec.source_id}_invalid_type",
                severity="blocking",
                summary="First-proof evidence artifact must contain a JSON object.",
                source_ids=(spec.source_id,),
                evidence=f"{relative_path}:{type(loaded).__name__}",
            )
        )
        return record, None, findings

    schema_version = str(loaded.get("schema_version") or "")
    record["schema_version"] = schema_version
    if spec.expected_schema is not None and schema_version != spec.expected_schema:
        record["state"] = "invalid_schema"
        findings.append(
            _finding(
                finding_id=f"{spec.source_id}_schema_mismatch",
                severity="blocking",
                summary="First-proof artifact schema does not match its producer contract.",
                source_ids=(spec.source_id,),
                evidence=(
                    f"expected={spec.expected_schema};observed={schema_version or 'missing'}"
                ),
            )
        )
    else:
        record["state"] = "present"

    provenance = loaded.get("input_provenance")
    provenance = provenance if isinstance(provenance, dict) else {}
    source_head = str(
        loaded.get("current_head_sha") or provenance.get("generated_from_head_sha") or ""
    )
    record["current_head_sha"] = source_head

    if not source_head:
        record["head_binding"] = "unbound"
        findings.append(
            _finding(
                finding_id=f"{spec.source_id}_head_unbound",
                severity="advisory",
                summary="Legacy source artifact does not record a Git HEAD.",
                source_ids=(spec.source_id,),
                evidence=relative_path,
            )
        )
    elif source_head != current_head_sha:
        record["head_binding"] = "stale"
        findings.append(
            _finding(
                finding_id=f"{spec.source_id}_head_stale",
                severity="partial",
                summary="Source artifact is bound to a different Git HEAD.",
                source_ids=(spec.source_id,),
                evidence=(f"recorded={source_head};current={current_head_sha}"),
            )
        )
    else:
        record["head_binding"] = "current"

    status_value = (
        loaded.get("status") or loaded.get("decision") or loaded.get("health_decision") or ""
    )
    record["payload_status"] = str(status_value)
    return record, loaded, findings


def _contradiction_findings(
    payloads: Mapping[str, JsonObject],
) -> list[JsonObject]:
    findings: list[JsonObject] = []
    health = payloads.get("health_score")
    dashboard = payloads.get("dashboard")
    threshold = payloads.get("readiness_threshold")

    if health is not None and dashboard is not None:
        health_score = health.get("score")
        dashboard_score = dashboard.get("health_score")
        if (
            health_score is not None
            and dashboard_score is not None
            and health_score != dashboard_score
        ):
            findings.append(
                _finding(
                    finding_id="health_score_contradiction",
                    severity="blocking",
                    summary="Dashboard health score contradicts the health-score artifact.",
                    source_ids=("health_score", "dashboard"),
                    evidence=(
                        f"health_score={health_score};dashboard_health_score={dashboard_score}"
                    ),
                )
            )

        health_decision = str(health.get("decision") or "")
        dashboard_decision = str(dashboard.get("health_decision") or "")
        if health_decision and dashboard_decision and health_decision != dashboard_decision:
            findings.append(
                _finding(
                    finding_id="health_decision_contradiction",
                    severity="blocking",
                    summary="Dashboard health decision contradicts the health-score artifact.",
                    source_ids=("health_score", "dashboard"),
                    evidence=(
                        f"health_decision={health_decision};"
                        f"dashboard_health_decision={dashboard_decision}"
                    ),
                )
            )

    if dashboard is not None and threshold is not None:
        dashboard_decision = str(dashboard.get("decision") or "")
        threshold_decision = str(threshold.get("decision") or "")
        if dashboard_decision and threshold_decision and dashboard_decision != threshold_decision:
            findings.append(
                _finding(
                    finding_id="readiness_decision_contradiction",
                    severity="blocking",
                    summary="Readiness-threshold decision contradicts the dashboard.",
                    source_ids=("dashboard", "readiness_threshold"),
                    evidence=(
                        f"dashboard_decision={dashboard_decision};"
                        f"threshold_decision={threshold_decision}"
                    ),
                )
            )

    if threshold is not None and threshold.get("ok") is False:
        errors = threshold.get("errors")
        findings.append(
            _finding(
                finding_id="readiness_threshold_failed",
                severity="blocking",
                summary="The existing readiness-threshold artifact reports failure.",
                source_ids=("readiness_threshold",),
                evidence=json.dumps(
                    errors if isinstance(errors, list) else [],
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            )
        )

    if dashboard is not None:
        decision = str(dashboard.get("decision") or "")
        if decision in {"", "NO-DATA"}:
            findings.append(
                _finding(
                    finding_id="dashboard_decision_not_available",
                    severity="partial",
                    summary="The first-proof dashboard has no reviewable decision.",
                    source_ids=("dashboard",),
                    evidence=decision or "missing",
                )
            )

    return findings


def build_first_proof_quality_evidence(
    *,
    repo_root: str | Path = ".",
    artifact_dir: str | Path = DEFAULT_ARTIFACT_DIR,
    current_head_sha: str | None = None,
    generated_at: str | None = None,
) -> JsonObject:
    root = Path(repo_root).resolve()
    artifact_root = Path(artifact_dir)
    if not artifact_root.is_absolute():
        artifact_root = root / artifact_root

    provenance = first_proof_quality_input_provenance(
        repo_root=root,
        artifact_dir=artifact_root,
        current_head_sha=current_head_sha,
        generated_at=generated_at,
    )
    head = str(provenance["generated_from_head_sha"])

    sources: list[JsonObject] = []
    payloads: dict[str, JsonObject] = {}
    findings: list[JsonObject] = []

    for spec in SOURCE_SPECS:
        source, loaded, source_findings = _load_source(
            artifact_root=artifact_root,
            spec=spec,
            current_head_sha=head,
        )
        sources.append(source)
        findings.extend(source_findings)
        if loaded is not None:
            payloads[spec.source_id] = loaded

    findings.extend(_contradiction_findings(payloads))
    findings.sort(
        key=lambda item: (
            str(item.get("severity", "")),
            str(item.get("finding_id", "")),
        )
    )

    finding_counts = Counter(str(item.get("severity") or "") for item in findings)
    source_state_counts = Counter(str(item.get("state") or "") for item in sources)
    head_binding_counts = Counter(str(item.get("head_binding") or "") for item in sources)

    if finding_counts.get("blocking", 0):
        status = "blocked"
    elif finding_counts.get("partial", 0) or finding_counts.get("advisory", 0):
        status = "review_required"
    else:
        status = "ready_for_human_review"

    payload: JsonObject = {
        "schema_version": SCHEMA_VERSION,
        "tool": "sdetkit.first_proof_quality_evidence",
        "status": status,
        "report_status": status,
        "artifact_dir": artifact_root.as_posix(),
        "source_count": len(sources),
        "source_state_counts": dict(sorted(source_state_counts.items())),
        "head_binding_counts": dict(sorted(head_binding_counts.items())),
        "sources": sources,
        "findings": findings,
        "finding_counts": {
            "blocking": finding_counts.get("blocking", 0),
            "partial": finding_counts.get("partial", 0),
            "advisory": finding_counts.get("advisory", 0),
        },
        "refresh_commands": [spec.refresh_command for spec in SOURCE_SPECS],
        "next_allowed_action": "human_first_proof_review",
        "reporting_only": True,
        "repo_mutation": False,
        "issue_mutation_allowed": False,
        "automation_allowed": False,
        "patch_application_allowed": False,
        "security_dismissal_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
        "authority_boundary": dict(_AUTHORITY_BOUNDARY),
    }
    return attach_provenance(payload, provenance)


def check_first_proof_quality_freshness(
    *,
    repo_root: str | Path = ".",
    artifact_dir: str | Path = DEFAULT_ARTIFACT_DIR,
    report_path: str | Path = DEFAULT_OUT,
    current_head_sha: str | None = None,
) -> JsonObject:
    current = first_proof_quality_input_provenance(
        repo_root=repo_root,
        artifact_dir=artifact_dir,
        current_head_sha=current_head_sha,
    )
    return check_report_path(
        report_path,
        current,
        expected_schema_version=SCHEMA_VERSION,
    )


def render_first_proof_quality_markdown(
    payload: Mapping[str, Any],
) -> str:
    finding_counts = payload.get("finding_counts")
    if not isinstance(finding_counts, dict):
        finding_counts = {}

    lines = [
        "# First-proof quality evidence",
        "",
        f"- schema_version: `{payload.get('schema_version', '')}`",
        f"- status: `{payload.get('status', '')}`",
        f"- generated_at: `{payload.get('generated_at', '')}`",
        f"- current_head_sha: `{payload.get('current_head_sha', '')}`",
        f"- source_count: `{payload.get('source_count', 0)}`",
        f"- blocking_findings: `{finding_counts.get('blocking', 0)}`",
        f"- partial_findings: `{finding_counts.get('partial', 0)}`",
        f"- advisory_findings: `{finding_counts.get('advisory', 0)}`",
        "- reporting_only: `true`",
        "- merge_authorized: `false`",
        "",
        "## Source artifacts",
        "",
        "| Source | State | Head binding | Schema | Refresh command |",
        "| --- | --- | --- | --- | --- |",
    ]

    raw_sources = payload.get("sources")
    if isinstance(raw_sources, list):
        for source in raw_sources:
            if not isinstance(source, dict):
                continue
            lines.append(
                "| `{source_id}` | `{state}` | `{head_binding}` | "
                "`{schema}` | `{refresh}` |".format(
                    source_id=source.get("source_id", ""),
                    state=source.get("state", ""),
                    head_binding=source.get("head_binding", ""),
                    schema=source.get("schema_version", "") or "unversioned",
                    refresh=source.get("refresh_command", ""),
                )
            )

    lines.extend(["", "## Findings", ""])
    raw_findings = payload.get("findings")
    if isinstance(raw_findings, list) and raw_findings:
        for finding in raw_findings:
            if not isinstance(finding, dict):
                continue
            lines.append(
                "- **{severity}** `{finding_id}` — {summary} Evidence: `{evidence}`".format(
                    severity=finding.get("severity", ""),
                    finding_id=finding.get("finding_id", ""),
                    summary=finding.get("summary", ""),
                    evidence=finding.get("evidence", ""),
                )
            )
    else:
        lines.append("- No findings.")

    lines.extend(["", "## Refresh commands", ""])
    raw_commands = payload.get("refresh_commands")
    if isinstance(raw_commands, list):
        for command in raw_commands:
            lines.append(f"- `{command}`")

    lines.extend(
        [
            "",
            "## Authority boundary",
            "",
            "- reporting_only: `true`",
            "- repo_mutation: `false`",
            "- issue_mutation_allowed: `false`",
            "- automation_allowed: `false`",
            "- patch_application_allowed: `false`",
            "- security_dismissal_allowed: `false`",
            "- merge_authorized: `false`",
            "- semantic_equivalence_proven: `false`",
            "",
            (
                "_This bundle reports first-proof evidence only. It does not "
                "refresh source artifacts or authorize merge._"
            ),
        ]
    )
    return "\n".join(lines)


def write_first_proof_quality_evidence(
    *,
    repo_root: str | Path = ".",
    artifact_dir: str | Path = DEFAULT_ARTIFACT_DIR,
    out: str | Path = DEFAULT_OUT,
    markdown_out: str | Path = DEFAULT_MARKDOWN_OUT,
    current_head_sha: str | None = None,
    generated_at: str | None = None,
) -> JsonObject:
    payload = build_first_proof_quality_evidence(
        repo_root=repo_root,
        artifact_dir=artifact_dir,
        current_head_sha=current_head_sha,
        generated_at=generated_at,
    )
    out_path = Path(out)
    markdown_path = Path(markdown_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(
        render_first_proof_quality_markdown(payload) + "\n",
        encoding="utf-8",
    )
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sdetkit first-proof-quality-evidence")
    parser.add_argument("--root", default=".")
    parser.add_argument(
        "--artifact-dir",
        default=DEFAULT_ARTIFACT_DIR.as_posix(),
    )
    parser.add_argument("--out", default=DEFAULT_OUT.as_posix())
    parser.add_argument(
        "--markdown-out",
        default=DEFAULT_MARKDOWN_OUT.as_posix(),
    )
    parser.add_argument("--check-freshness", action="store_true")
    parser.add_argument("--format", choices=("json", "text"), default="json")
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.check_freshness:
        freshness = check_first_proof_quality_freshness(
            repo_root=args.root,
            artifact_dir=args.artifact_dir,
            report_path=args.out,
        )
        if args.format == "json":
            sys.stdout.write(json.dumps(freshness, indent=2, sort_keys=True) + "\n")
        else:
            sys.stdout.write(render_freshness_text(freshness) + "\n")
        return 0 if freshness["fresh"] else 1

    payload = write_first_proof_quality_evidence(
        repo_root=args.root,
        artifact_dir=args.artifact_dir,
        out=args.out,
        markdown_out=args.markdown_out,
    )
    if args.format == "json":
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(render_first_proof_quality_markdown(payload) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
