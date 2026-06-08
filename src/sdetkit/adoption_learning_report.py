from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.adoption_learning_report.v1"

AUTHORITY_FIELDS = (
    "automation_allowed",
    "patch_application_allowed",
    "merge_authorized",
    "semantic_equivalence_proven",
)

HIGH_LEVERAGE_CLASSES = {
    "weak_proof_command_mapping",
    "unsupported_test_runner",
    "unsupported_ci_provider",
    "integration_runner_bug",
}

CLASS_WEIGHTS = {
    "integration_runner_bug": 100,
    "weak_proof_command_mapping": 90,
    "unsupported_test_runner": 80,
    "unsupported_ci_provider": 70,
    "unsupported_package_manager": 60,
    "unsupported_language": 50,
    "monorepo_shape_gap": 45,
    "review_first_unknown": 40,
    "missed_security_surface": 35,
    "artifact_path_gap": 30,
}


def _authority_boundary() -> dict[str, bool]:
    return {field: False for field in AUTHORITY_FIELDS}


def _load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted({str(item) for item in value if str(item).strip()})


def _int_value(value: object, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _candidate_score(candidate: dict[str, Any]) -> int:
    classification = str(candidate.get("classification", "")).strip()
    frequency = _int_value(candidate.get("frequency_across_matrix"))
    return CLASS_WEIGHTS.get(classification, 10) + frequency * 10


def _priority(candidate: dict[str, Any]) -> str:
    classification = str(candidate.get("classification", "")).strip()
    frequency = _int_value(candidate.get("frequency_across_matrix"))
    if classification == "integration_runner_bug":
        return "P0"
    if frequency >= 3 or classification in HIGH_LEVERAGE_CLASSES:
        return "P1"
    return "P2"


def _next_pr_title(candidate: dict[str, Any]) -> str:
    title = str(candidate.get("upgrade_candidate_title", "")).strip()
    if title:
        return title
    classification = str(candidate.get("classification", "unknown")).strip() or "unknown"
    return f"feat(adoption): prioritize {classification} from real-world learning evidence"


def _candidate_summary(candidate: dict[str, Any], *, rank: int) -> dict[str, Any]:
    classification = str(candidate.get("classification", "unknown")).strip() or "unknown"
    owner_files = _strings(candidate.get("owner_files"))
    proof_needed = _strings(candidate.get("proof_needed"))
    observed_in_repos = _strings(candidate.get("observed_in_repos"))

    return {
        "rank": rank,
        "classification": classification,
        "priority": _priority(candidate),
        "ranking_score": _candidate_score(candidate),
        "next_pr_title": _next_pr_title(candidate),
        "observed_in_repos": observed_in_repos,
        "frequency_across_matrix": _int_value(candidate.get("frequency_across_matrix")),
        "owner_files": owner_files,
        "reason_from_real_repo": str(candidate.get("reason_from_real_repo", "")).strip(),
        "proof_needed": proof_needed,
        "review_first": True,
        "safe_to_patch": False,
        "recommended_next_action": (
            "Open one focused PR for this candidate, add fixture-backed coverage, "
            "run focused proof, then run make proof-after-format."
        ),
    }


def build_adoption_learning_report(matrix_json: str | Path) -> dict[str, Any]:
    matrix_path = Path(matrix_json).resolve()
    matrix = _load_json_object(matrix_path)

    raw_candidates = matrix.get("upgrade_candidates")
    if not isinstance(raw_candidates, list):
        raw_candidates = []

    candidate_objects = [item for item in raw_candidates if isinstance(item, dict)]
    ordered_candidates = sorted(
        candidate_objects,
        key=lambda item: (-_candidate_score(item), str(item.get("classification", ""))),
    )
    prioritized = [
        _candidate_summary(candidate, rank=index)
        for index, candidate in enumerate(ordered_candidates, 1)
    ]

    top_candidate = prioritized[0] if prioritized else None
    repo_count = _int_value(matrix.get("repo_count"))
    matrix_status = str(matrix.get("matrix_status", "unknown"))

    return {
        "schema_version": SCHEMA_VERSION,
        "source_matrix": matrix_path.as_posix(),
        "source_matrix_schema_version": str(matrix.get("schema_version", "")),
        "source_matrix_status": matrix_status,
        "source_repo_count": repo_count,
        "candidate_count": len(prioritized),
        "top_candidate": top_candidate,
        "prioritized_upgrade_candidates": prioritized,
        "operator_summary": {
            "status": "review_first_learning_report_generated",
            "next_action": (
                top_candidate["next_pr_title"]
                if top_candidate
                else "No upgrade candidates found in the source matrix."
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
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
        "authority_boundary": _authority_boundary(),
    }


def render_adoption_learning_report_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# SDETKit adoption learning report",
        "",
        f"- source_matrix_status: {payload['source_matrix_status']}",
        f"- source_repo_count: {payload['source_repo_count']}",
        f"- candidate_count: {payload['candidate_count']}",
        "- review_first: true",
        "- safe_to_patch: false",
        "",
        "## Prioritized upgrade candidates",
        "",
    ]

    candidates = payload.get("prioritized_upgrade_candidates")
    if not isinstance(candidates, list) or not candidates:
        lines.append("- none")
    else:
        for candidate in candidates:
            lines.append(
                "{rank}. {title}".format(
                    rank=candidate["rank"],
                    title=candidate["next_pr_title"],
                )
            )
            lines.append(f"   - classification: {candidate['classification']}")
            lines.append(f"   - priority: {candidate['priority']}")
            lines.append(f"   - ranking_score: {candidate['ranking_score']}")
            lines.append(f"   - frequency_across_matrix: {candidate['frequency_across_matrix']}")
            lines.append("   - review_first: true")
            lines.append("   - safe_to_patch: false")

    lines.extend(
        [
            "",
            "## Authority boundary",
            "",
            "- automation_allowed: false",
            "- patch_application_allowed: false",
            "- merge_authorized: false",
            "- semantic_equivalence_proven: false",
            "",
        ]
    )
    return "\n".join(lines)


def write_adoption_learning_report_artifacts(
    *,
    matrix_json: str | Path,
    out: str | Path,
    markdown_out: str | Path | None = None,
) -> dict[str, Any]:
    payload = build_adoption_learning_report(matrix_json)
    out_path = Path(out)
    markdown_path = Path(markdown_out) if markdown_out else out_path.with_suffix(".md")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)

    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(
        render_adoption_learning_report_markdown(payload) + "\n",
        encoding="utf-8",
    )
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit adoption-learning-report",
        description="Prioritize review-first upgrade candidates from an adoption matrix artifact.",
    )
    parser.add_argument("--matrix-json", required=True)
    parser.add_argument("--out", default="build/sdetkit/adoption-learning-report.json")
    parser.add_argument("--markdown-out", default="")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    ns = parser.parse_args(list(argv) if argv is not None else None)

    payload = write_adoption_learning_report_artifacts(
        matrix_json=ns.matrix_json,
        out=ns.out,
        markdown_out=ns.markdown_out or None,
    )

    if ns.format == "json":
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(render_adoption_learning_report_markdown(payload) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
