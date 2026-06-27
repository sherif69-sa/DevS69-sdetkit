from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.public_repo_trial_matrix_report.v1"
ACCEPTED_MATRIX_SCHEMA = "sdetkit.public_repo_trial_matrix.v1"
DEFAULT_OUT = Path("build/sdetkit/public-repo-trial-matrix-report.json")
GENERATOR_SOURCE = "src/sdetkit/adoption_public_repo_trial_matrix_report.py"

AUTHORITY_FIELDS = (
    "automation_allowed",
    "patch_application_allowed",
    "merge_authorized",
    "semantic_equivalence_proven",
)
SOURCE_SAFETY_FIELDS = (
    "source_code_vendored",
    "dependency_install_performed",
    "target_tests_executed",
    "target_repo_mutated",
    "target_pr_or_issue_opened",
    "endorsement_claimed",
)


def _authority_boundary() -> dict[str, bool]:
    return {field: False for field in AUTHORITY_FIELDS}


def _load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _git_head_sha(root: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def _display_path(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _validate_matrix(matrix: dict[str, Any]) -> list[dict[str, Any]]:
    schema = str(matrix.get("schema_version", "")).strip()
    if schema != ACCEPTED_MATRIX_SCHEMA:
        raise ValueError(
            "unsupported public repo trial matrix schema: "
            f"{schema or '<missing>'}; expected {ACCEPTED_MATRIX_SCHEMA}"
        )

    for field in SOURCE_SAFETY_FIELDS:
        if matrix.get(field) is not False:
            raise ValueError(f"source safety field must be false: {field}")

    boundary = matrix.get("authority_boundary")
    if not isinstance(boundary, dict):
        raise ValueError("source matrix authority_boundary must be an object")
    for field in AUTHORITY_FIELDS:
        if boundary.get(field) is not False:
            raise ValueError(f"source authority field must be false: {field}")

    raw_trials = matrix.get("trials")
    if not isinstance(raw_trials, list):
        raise ValueError("source matrix trials must be a list")

    trials: list[dict[str, Any]] = []
    required_strings = (
        "repo_full_name",
        "repo_url",
        "license_id",
        "expected_primary_language",
    )
    required_bools = (
        "eligibility_allowed_for_read_only_trial",
        "prior_single_repo_trial",
    )
    for index, item in enumerate(raw_trials):
        if not isinstance(item, dict):
            raise ValueError(f"trial {index} must be an object")
        for field in required_strings:
            if not isinstance(item.get(field), str) or not str(item[field]).strip():
                raise ValueError(f"trial {index} missing string field: {field}")
        for field in required_bools:
            if not isinstance(item.get(field), bool):
                raise ValueError(f"trial {index} missing boolean field: {field}")
        trials.append(
            {
                "repo_full_name": str(item["repo_full_name"]).strip(),
                "repo_url": str(item["repo_url"]).strip(),
                "license_id": str(item["license_id"]).strip(),
                "expected_primary_language": str(item["expected_primary_language"]).strip(),
                "eligibility_allowed_for_read_only_trial": bool(
                    item["eligibility_allowed_for_read_only_trial"]
                ),
                "prior_single_repo_trial": bool(item["prior_single_repo_trial"]),
            }
        )
    return sorted(trials, key=lambda trial: trial["repo_full_name"])


def build_public_repo_trial_matrix_report(
    matrix_json: str | Path,
    *,
    root: str | Path = ".",
    current_head_sha: str | None = None,
) -> dict[str, Any]:
    root_path = Path(root).resolve()
    matrix_path = Path(matrix_json).resolve()
    matrix_bytes = matrix_path.read_bytes()
    matrix = _load_json_object(matrix_path)
    trials = _validate_matrix(matrix)
    head_sha = (
        _git_head_sha(root_path) if current_head_sha is None else str(current_head_sha).strip()
    )

    digest = hashlib.sha256()
    digest.update(SCHEMA_VERSION.encode("utf-8"))
    digest.update(b"\0")
    digest.update(head_sha.encode("utf-8"))
    digest.update(b"\0")
    digest.update(matrix_bytes)

    eligible_count = sum(1 for trial in trials if trial["eligibility_allowed_for_read_only_trial"])
    prior_count = sum(1 for trial in trials if trial["prior_single_repo_trial"])
    new_candidate_count = sum(
        1
        for trial in trials
        if trial["eligibility_allowed_for_read_only_trial"] and not trial["prior_single_repo_trial"]
    )
    report_status = (
        "ready_for_human_review" if trials and eligible_count == len(trials) else "review_required"
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "report_status": report_status,
        "input_provenance": {
            "input_digest_algorithm": "sha256",
            "input_digest": digest.hexdigest(),
            "matrix_path": _display_path(root_path, matrix_path),
            "matrix_sha256": hashlib.sha256(matrix_bytes).hexdigest(),
            "matrix_schema_version": str(matrix.get("schema_version", "")),
            "generator_schema_version": SCHEMA_VERSION,
            "generator_source": GENERATOR_SOURCE,
            "current_head_sha": head_sha,
            "current_head_bound": bool(head_sha),
        },
        "source_matrix": {
            "matrix_name": str(matrix.get("matrix_name", "")).strip(),
            "trial_mode": str(matrix.get("trial_mode", "")).strip(),
            "schema_version": str(matrix.get("schema_version", "")).strip(),
            "recommended_next_upgrade_after_matrix": str(
                matrix.get("recommended_next_upgrade_after_matrix", "")
            ).strip(),
            "source_safety": {field: bool(matrix.get(field)) for field in SOURCE_SAFETY_FIELDS},
        },
        "summary": {
            "trial_count": len(trials),
            "eligible_trial_count": eligible_count,
            "prior_single_repo_trial_count": prior_count,
            "new_read_only_trial_candidate_count": new_candidate_count,
            "all_trials_eligible": bool(trials) and eligible_count == len(trials),
        },
        "trials": trials,
        "operator_summary": {
            "status": report_status,
            "headline": (
                f"{len(trials)} recorded public repository trial candidates; "
                f"{new_candidate_count} remain new read-only candidates."
            ),
            "recommended_next_action": (
                "Review the recorded matrix evidence and select any next read-only trial manually."
            ),
        },
        "rules": {
            "source_matrix_only": True,
            "target_repos_read": False,
            "install_dependencies": False,
            "target_tests_executed": False,
            "target_repo_mutation": False,
            "target_pr_or_issue_opened": False,
            "endorsement_claim": False,
            "review_first": True,
        },
        "reporting_only": True,
        "repo_mutation": False,
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
        "authority_boundary": _authority_boundary(),
    }


def render_public_repo_trial_matrix_report_markdown(payload: dict[str, Any]) -> str:
    provenance = payload["input_provenance"]
    summary = payload["summary"]
    source = payload["source_matrix"]
    lines = [
        "# SDETKit public repository trial matrix report",
        "",
        f"- report_status: {payload['report_status']}",
        f"- source_matrix_schema: {source['schema_version']}",
        f"- source_matrix_name: {source['matrix_name']}",
        f"- trial_mode: {source['trial_mode']}",
        f"- trial_count: {summary['trial_count']}",
        f"- eligible_trial_count: {summary['eligible_trial_count']}",
        (
            "- new_read_only_trial_candidate_count: "
            f"{summary['new_read_only_trial_candidate_count']}"
        ),
        f"- input_digest: `{provenance['input_digest']}`",
        f"- current_head_sha: `{provenance['current_head_sha']}`",
        "- review_first: true",
        "- reporting_only: true",
        "",
        "## Recorded trials",
        "",
    ]
    trials = payload.get("trials")
    if not isinstance(trials, list) or not trials:
        lines.append("- none")
    else:
        for trial in trials:
            lines.extend(
                [
                    f"- `{trial['repo_full_name']}`",
                    f"  - license_id: {trial['license_id']}",
                    (
                        "  - eligibility_allowed_for_read_only_trial: "
                        f"{str(trial['eligibility_allowed_for_read_only_trial']).lower()}"
                    ),
                    (
                        "  - prior_single_repo_trial: "
                        f"{str(trial['prior_single_repo_trial']).lower()}"
                    ),
                ]
            )
    lines.extend(
        [
            "",
            "## Authority boundary",
            "",
            "- target_repos_read: false",
            "- install_dependencies: false",
            "- target_tests_executed: false",
            "- target_repo_mutation: false",
            "- target_pr_or_issue_opened: false",
            "- endorsement_claim: false",
            "- automation_allowed: false",
            "- patch_application_allowed: false",
            "- merge_authorized: false",
            "- semantic_equivalence_proven: false",
            "",
        ]
    )
    return "\n".join(lines)


def write_public_repo_trial_matrix_report_artifacts(
    *,
    matrix_json: str | Path,
    out: str | Path = DEFAULT_OUT,
    markdown_out: str | Path | None = None,
    root: str | Path = ".",
    current_head_sha: str | None = None,
) -> dict[str, Any]:
    payload = build_public_repo_trial_matrix_report(
        matrix_json,
        root=root,
        current_head_sha=current_head_sha,
    )
    out_path = Path(out)
    markdown_path = Path(markdown_out) if markdown_out else out_path.with_suffix(".md")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(
        render_public_repo_trial_matrix_report_markdown(payload) + "\n",
        encoding="utf-8",
    )
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit adoption-public-trial-matrix-report",
        description=(
            "Render a reporting-only operator summary from a recorded "
            "public repository trial matrix."
        ),
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--matrix-json", required=True)
    parser.add_argument("--out", default=DEFAULT_OUT.as_posix())
    parser.add_argument("--markdown-out", default="")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    ns = parser.parse_args(list(argv) if argv is not None else None)
    payload = write_public_repo_trial_matrix_report_artifacts(
        matrix_json=ns.matrix_json,
        out=ns.out,
        markdown_out=ns.markdown_out or None,
        root=ns.root,
    )
    if ns.format == "json":
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(render_public_repo_trial_matrix_report_markdown(payload) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
