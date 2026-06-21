from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.adoption_learning_report.v2"

AUTHORITY_FIELDS = (
    "automation_allowed",
    "patch_application_allowed",
    "merge_authorized",
    "semantic_equivalence_proven",
)

ACCEPTED_MATRIX_SCHEMA = "sdetkit.adoption_real_world_learning_matrix.v1"
ACCEPTED_REPO_MEMORY_SCHEMAS = ("sdetkit.repo_memory.v6",)
INPUT_DIGEST_ALGORITHM = "sha256"
GENERATOR_SOURCE_LABEL = "src/sdetkit/adoption_learning_report.py"


def _update_input_digest(hasher: Any, label: str, content: bytes) -> None:
    label_bytes = label.encode("utf-8")
    hasher.update(len(label_bytes).to_bytes(8, "big"))
    hasher.update(label_bytes)
    hasher.update(len(content).to_bytes(8, "big"))
    hasher.update(content)


def _display_input_path(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _git_head_sha(root: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return ""
    return completed.stdout.strip()


def _source_schema(path: Path) -> str:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return ""
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("schema_version", "")).strip()


def adoption_learning_input_provenance(
    matrix_json: str | Path,
    *,
    root: str | Path = ".",
    repo_memory_profile: str | Path | None = None,
    generator_path: str | Path | None = None,
    current_head_sha: str | None = None,
) -> dict[str, Any]:
    repo_root = Path(root).resolve()
    matrix_path = Path(matrix_json).resolve()
    profile_path = Path(repo_memory_profile).resolve() if repo_memory_profile else None
    generator = (
        Path(generator_path).resolve() if generator_path is not None else Path(__file__).resolve()
    )
    head_sha = _git_head_sha(repo_root) if current_head_sha is None else current_head_sha

    matrix_content = matrix_path.read_bytes() if matrix_path.is_file() else b"<missing>"
    profile_content = (
        profile_path.read_bytes()
        if profile_path is not None and profile_path.is_file()
        else b"<not-provided>"
        if profile_path is None
        else b"<missing>"
    )
    generator_content = generator.read_bytes() if generator.is_file() else b"<missing>"

    inputs = [
        ("accepted_matrix_schema", ACCEPTED_MATRIX_SCHEMA.encode("utf-8")),
        (
            "accepted_repo_memory_schemas",
            "\n".join(ACCEPTED_REPO_MEMORY_SCHEMAS).encode("utf-8"),
        ),
        ("current_head_sha", head_sha.encode("utf-8")),
        ("generator_schema_version", SCHEMA_VERSION.encode("utf-8")),
        (GENERATOR_SOURCE_LABEL, generator_content),
        ("source_matrix", matrix_content),
        ("repo_memory_profile", profile_content),
    ]
    hasher = hashlib.sha256()
    for label, content in sorted(inputs, key=lambda item: item[0]):
        _update_input_digest(hasher, label, content)

    return {
        "digest_algorithm": INPUT_DIGEST_ALGORITHM,
        "input_digest": hasher.hexdigest(),
        "input_count": len(inputs),
        "generator_schema_version": SCHEMA_VERSION,
        "generator_source": GENERATOR_SOURCE_LABEL,
        "matrix_path": _display_input_path(repo_root, matrix_path),
        "matrix_sha256": hashlib.sha256(matrix_content).hexdigest(),
        "matrix_schema_version": _source_schema(matrix_path),
        "repo_memory_profile_connected": profile_path is not None,
        "repo_memory_profile_path": (
            _display_input_path(repo_root, profile_path) if profile_path is not None else ""
        ),
        "repo_memory_profile_sha256": hashlib.sha256(profile_content).hexdigest(),
        "repo_memory_profile_schema_version": (
            _source_schema(profile_path) if profile_path is not None else ""
        ),
        "accepted_matrix_schema": ACCEPTED_MATRIX_SCHEMA,
        "accepted_repo_memory_schemas": list(ACCEPTED_REPO_MEMORY_SCHEMAS),
        "current_head_sha": head_sha,
        "current_head_available": bool(head_sha),
    }


def _source_relationships(provenance: dict[str, Any]) -> dict[str, Any]:
    profile_connected = bool(provenance.get("repo_memory_profile_connected"))
    profile_schema = str(provenance.get("repo_memory_profile_schema_version", ""))
    matrix_schema = str(provenance.get("matrix_schema_version", ""))
    return {
        "matrix_schema_version": matrix_schema,
        "accepted_matrix_schema": ACCEPTED_MATRIX_SCHEMA,
        "matrix_schema_accepted": matrix_schema == ACCEPTED_MATRIX_SCHEMA,
        "repo_memory_profile_connected": profile_connected,
        "repo_memory_profile_schema_version": profile_schema,
        "accepted_repo_memory_schemas": list(ACCEPTED_REPO_MEMORY_SCHEMAS),
        "repo_memory_profile_schema_accepted": (
            not profile_connected or profile_schema in ACCEPTED_REPO_MEMORY_SCHEMAS
        ),
        "current_head_sha": str(provenance.get("current_head_sha", "")),
        "current_head_bound": bool(provenance.get("current_head_available")),
    }


def validate_adoption_learning_report_freshness(
    payload: dict[str, Any],
    *,
    matrix_json: str | Path,
    root: str | Path = ".",
    repo_memory_profile: str | Path | None = None,
    generator_path: str | Path | None = None,
    current_head_sha: str | None = None,
) -> dict[str, Any]:
    current = adoption_learning_input_provenance(
        matrix_json,
        root=root,
        repo_memory_profile=repo_memory_profile,
        generator_path=generator_path,
        current_head_sha=current_head_sha,
    )
    expected_relationships = _source_relationships(current)
    reasons: list[str] = []

    recorded = payload.get("input_provenance")
    if not isinstance(recorded, dict):
        recorded = {}
        reasons.append("missing_input_provenance")

    for field in (
        "digest_algorithm",
        "input_digest",
        "input_count",
        "generator_schema_version",
        "generator_source",
        "matrix_path",
        "matrix_sha256",
        "matrix_schema_version",
        "repo_memory_profile_connected",
        "repo_memory_profile_path",
        "repo_memory_profile_sha256",
        "repo_memory_profile_schema_version",
        "accepted_matrix_schema",
        "accepted_repo_memory_schemas",
        "current_head_sha",
        "current_head_available",
    ):
        if recorded.get(field) != current.get(field):
            reasons.append(f"{field}_mismatch")

    schema_valid = payload.get("schema_version") == SCHEMA_VERSION
    if not schema_valid:
        reasons.append("schema_version_mismatch")

    relationships = payload.get("source_relationships")
    if not isinstance(relationships, dict):
        relationships = {}
        reasons.append("missing_source_relationships")
    for field, expected in expected_relationships.items():
        if relationships.get(field) != expected:
            reasons.append(f"source_relationships_{field}_mismatch")

    source_schema_valid = bool(
        expected_relationships["matrix_schema_accepted"]
        and expected_relationships["repo_memory_profile_schema_accepted"]
    )
    if not source_schema_valid:
        reasons.append("source_schema_not_accepted")

    current_head_valid = bool(
        current["current_head_available"]
        and recorded.get("current_head_sha") == current["current_head_sha"]
    )
    if not current_head_valid:
        reasons.append("current_head_mismatch")

    authority_valid = True
    for field in AUTHORITY_FIELDS:
        if payload.get(field) is not False:
            authority_valid = False
            reasons.append(f"{field}_mismatch")

    boundary = payload.get("authority_boundary")
    if not isinstance(boundary, dict):
        authority_valid = False
        reasons.append("missing_authority_boundary")
    else:
        for field in AUTHORITY_FIELDS:
            if boundary.get(field) is not False:
                authority_valid = False
                reasons.append(f"authority_boundary_{field}_mismatch")

    rules = payload.get("rules")
    expected_rules = {
        "source_matrix_only": not bool(current["repo_memory_profile_connected"]),
        "repo_memory_profile_read": bool(current["repo_memory_profile_connected"]),
        "repo_memory_profile_authoritative": False,
        "target_repos_read": False,
        "install_dependencies": False,
        "target_tests_executed": False,
        "target_repo_mutation": False,
        "target_pr_or_issue_opened": False,
        "endorsement_claim": False,
        "review_first": True,
    }
    if not isinstance(rules, dict):
        authority_valid = False
        reasons.append("missing_rules")
    else:
        for field, expected in expected_rules.items():
            if rules.get(field) is not expected:
                authority_valid = False
                reasons.append(f"rules_{field}_mismatch")

    reasons = sorted(set(reasons))
    fresh = not reasons
    return {
        "status": "fresh" if fresh else "stale",
        "fresh": fresh,
        "schema_valid": schema_valid,
        "source_schema_valid": source_schema_valid,
        "current_head_valid": current_head_valid,
        "authority_valid": authority_valid,
        "reasons": reasons,
        "recorded_input_digest": recorded.get("input_digest", ""),
        "current_input_digest": current["input_digest"],
        "recorded_head_sha": recorded.get("current_head_sha", ""),
        "current_head_sha": current["current_head_sha"],
        "reporting_only": True,
        "repo_mutation": False,
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }


def check_adoption_learning_report_freshness(
    *,
    report_path: str | Path,
    matrix_json: str | Path,
    root: str | Path = ".",
    repo_memory_profile: str | Path | None = None,
    generator_path: str | Path | None = None,
    current_head_sha: str | None = None,
) -> dict[str, Any]:
    path = Path(report_path)
    if not path.is_file():
        result = validate_adoption_learning_report_freshness(
            {},
            matrix_json=matrix_json,
            root=root,
            repo_memory_profile=repo_memory_profile,
            generator_path=generator_path,
            current_head_sha=current_head_sha,
        )
        result["reasons"] = sorted(set([*result["reasons"], "report_missing"]))
        result["status"] = "stale"
        result["fresh"] = False
        return result

    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        result = validate_adoption_learning_report_freshness(
            {},
            matrix_json=matrix_json,
            root=root,
            repo_memory_profile=repo_memory_profile,
            generator_path=generator_path,
            current_head_sha=current_head_sha,
        )
        result["reasons"] = sorted(set([*result["reasons"], "report_invalid_json"]))
        result["status"] = "stale"
        result["fresh"] = False
        return result

    if not isinstance(loaded, dict):
        result = validate_adoption_learning_report_freshness(
            {},
            matrix_json=matrix_json,
            root=root,
            repo_memory_profile=repo_memory_profile,
            generator_path=generator_path,
            current_head_sha=current_head_sha,
        )
        result["reasons"] = sorted(set([*result["reasons"], "report_not_object"]))
        result["status"] = "stale"
        result["fresh"] = False
        return result

    return validate_adoption_learning_report_freshness(
        loaded,
        matrix_json=matrix_json,
        root=root,
        repo_memory_profile=repo_memory_profile,
        generator_path=generator_path,
        current_head_sha=current_head_sha,
    )


def render_adoption_learning_freshness_text(payload: dict[str, Any]) -> str:
    reasons = payload.get("reasons", [])
    reason_text = ",".join(str(reason) for reason in reasons) if reasons else "none"
    return "\n".join(
        [
            f"freshness_status={payload.get('status', 'stale')}",
            f"fresh={str(bool(payload.get('fresh', False))).lower()}",
            f"schema_valid={str(bool(payload.get('schema_valid', False))).lower()}",
            f"source_schema_valid={str(bool(payload.get('source_schema_valid', False))).lower()}",
            f"current_head_valid={str(bool(payload.get('current_head_valid', False))).lower()}",
            f"authority_valid={str(bool(payload.get('authority_valid', False))).lower()}",
            f"freshness_reasons={reason_text}",
            f"recorded_input_digest={payload.get('recorded_input_digest', '')}",
            f"current_input_digest={payload.get('current_input_digest', '')}",
            f"recorded_head_sha={payload.get('recorded_head_sha', '')}",
            f"current_head_sha={payload.get('current_head_sha', '')}",
            "reporting_only=true",
            "repo_mutation=false",
            "automation_allowed=false",
            "patch_application_allowed=false",
            "merge_authorized=false",
            "semantic_equivalence_proven=false",
        ]
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


def _repo_memory_profile_summary(profile_path: str | Path | None) -> dict[str, Any]:
    if not profile_path:
        return {
            "connected": False,
            "path": "",
            "schema_version": "",
            "profile_status": "not_provided",
            "memory_mode": "",
            "review_first": True,
            "authoritative_for_adoption_report": False,
            "authority_boundary": _authority_boundary(),
        }

    resolved = Path(profile_path).resolve()
    profile = _load_json_object(resolved)

    return {
        "connected": True,
        "path": resolved.as_posix(),
        "schema_version": str(profile.get("schema_version", "")).strip(),
        "profile_status": str(profile.get("profile_status", "unknown")).strip(),
        "memory_mode": str(profile.get("memory_mode", "")).strip(),
        "review_first": True,
        "authoritative_for_adoption_report": False,
        "authority_boundary": _authority_boundary(),
    }


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


def build_adoption_learning_report(
    matrix_json: str | Path,
    *,
    repo_memory_profile: str | Path | None = None,
    root: str | Path = ".",
    current_head_sha: str | None = None,
) -> dict[str, Any]:
    matrix_path = Path(matrix_json).resolve()
    matrix = _load_json_object(matrix_path)
    repo_memory_summary = _repo_memory_profile_summary(repo_memory_profile)
    provenance = adoption_learning_input_provenance(
        matrix_path,
        root=root,
        repo_memory_profile=repo_memory_profile,
        current_head_sha=current_head_sha,
    )
    source_relationships = _source_relationships(provenance)

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
        "input_provenance": provenance,
        "source_relationships": source_relationships,
        "source_matrix": matrix_path.as_posix(),
        "source_matrix_schema_version": str(matrix.get("schema_version", "")),
        "source_matrix_status": matrix_status,
        "source_repo_count": repo_count,
        "candidate_count": len(prioritized),
        "top_candidate": top_candidate,
        "prioritized_upgrade_candidates": prioritized,
        "repo_memory_profile": repo_memory_summary,
        "operator_summary": {
            "status": "review_first_learning_report_generated",
            "next_action": (
                top_candidate["next_pr_title"]
                if top_candidate
                else "No upgrade candidates found in the source matrix."
            ),
        },
        "rules": {
            "source_matrix_only": not repo_memory_summary["connected"],
            "repo_memory_profile_read": repo_memory_summary["connected"],
            "repo_memory_profile_authoritative": False,
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
    provenance = payload.get("input_provenance")
    if not isinstance(provenance, dict):
        provenance = {}
    relationships = payload.get("source_relationships")
    if not isinstance(relationships, dict):
        relationships = {}
    lines = [
        "# SDETKit adoption learning report",
        "",
        f"- source_matrix_status: {payload['source_matrix_status']}",
        f"- source_repo_count: {payload['source_repo_count']}",
        f"- candidate_count: {payload['candidate_count']}",
        f"- input_digest: `{provenance.get('input_digest', '')}`",
        f"- current_head_sha: `{provenance.get('current_head_sha', '')}`",
        f"- matrix_schema_accepted: {str(bool(relationships.get('matrix_schema_accepted'))).lower()}",
        "- repo_memory_profile_schema_accepted: "
        f"{str(bool(relationships.get('repo_memory_profile_schema_accepted'))).lower()}",
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

    repo_memory = payload.get("repo_memory_profile")
    if not isinstance(repo_memory, dict):
        repo_memory = {}
    lines.extend(
        [
            "",
            "## RepoMemory profile",
            "",
            f"- connected: {str(repo_memory.get('connected', False)).lower()}",
            f"- profile_status: {repo_memory.get('profile_status', 'unknown')}",
            "- authoritative_for_adoption_report: false",
        ]
    )

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
    repo_memory_profile: str | Path | None = None,
    root: str | Path = ".",
    current_head_sha: str | None = None,
) -> dict[str, Any]:
    payload = build_adoption_learning_report(
        matrix_json,
        repo_memory_profile=repo_memory_profile,
        root=root,
        current_head_sha=current_head_sha,
    )
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
    parser.add_argument("--root", default=".")
    parser.add_argument("--matrix-json", required=True)
    parser.add_argument("--repo-memory-profile", default="")
    parser.add_argument("--out", default="build/sdetkit/adoption-learning-report.json")
    parser.add_argument("--markdown-out", default="")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    parser.add_argument(
        "--check-freshness",
        action="store_true",
        help="Check the existing report against matrix/profile inputs, accepted schemas, and current Git head without rewriting it.",
    )
    ns = parser.parse_args(list(argv) if argv is not None else None)

    if ns.check_freshness:
        freshness = check_adoption_learning_report_freshness(
            report_path=ns.out,
            matrix_json=ns.matrix_json,
            root=ns.root,
            repo_memory_profile=ns.repo_memory_profile or None,
        )
        if ns.format == "json":
            sys.stdout.write(json.dumps(freshness, indent=2, sort_keys=True) + "\n")
        else:
            sys.stdout.write(render_adoption_learning_freshness_text(freshness) + "\n")
        return 0 if freshness["fresh"] else 1

    payload = write_adoption_learning_report_artifacts(
        matrix_json=ns.matrix_json,
        out=ns.out,
        markdown_out=ns.markdown_out or None,
        repo_memory_profile=ns.repo_memory_profile or None,
        root=ns.root,
    )

    if ns.format == "json":
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(render_adoption_learning_report_markdown(payload) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
