from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sdetkit import post_merge_verification as post_merge
from sdetkit import release_readiness_evidence_package as release

ROOT = Path(__file__).resolve().parents[1]
RECIPE_PATH = ROOT / "docs/release-evidence-recipes.md"
RELEASE_SAMPLE_PATH = ROOT / "docs/examples/release-readiness-evidence-package.sample.json"
POST_MERGE_SAMPLE_PATH = ROOT / "docs/examples/post-merge-verification.sample.json"
HANDOFF_PATH = ROOT / "docs/release-readiness-evidence-handoff.md"
ARTIFACT_REFERENCE_PATH = ROOT / "docs/artifact-reference.md"
SHOWCASE_PATH = ROOT / "docs/evidence-showcase.md"
MKDOCS_PATH = ROOT / "mkdocs.yml"

FIXED_GENERATED_AT = "2026-01-01T00:00:00Z"
RELEASE_HEAD_SHA = "1" * 40
PREVIOUS_MAIN_SHA = "1" * 40
PR_HEAD_SHA = "2" * 40
MERGE_COMMIT_SHA = "3" * 40


def serialize_sample(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _digest(character: str) -> str:
    return character * 64


def _provenance(
    *,
    schema_version: str,
    generator_source: str,
    head_sha: str,
    input_digests: Mapping[str, str],
    input_count: int,
    source_issue_numbers: list[int] | None = None,
    source_run_ids: list[int] | None = None,
    input_artifact_schemas: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    issue_numbers = list(source_issue_numbers or [])
    run_ids = list(source_run_ids or [])
    return {
        "digest_algorithm": "sha256",
        "input_digest": _digest("0"),
        "input_count": input_count,
        "generator_schema_version": schema_version,
        "generator_source": generator_source,
        "generator_sha256": _digest("4"),
        "generated_at": FIXED_GENERATED_AT,
        "generated_from_head_sha": head_sha,
        "source_issue_count": len(issue_numbers),
        "source_issue_numbers": issue_numbers,
        "source_run_ids": run_ids,
        "input_digests": dict(input_digests),
        "input_artifact_schemas": dict(input_artifact_schemas or {}),
    }


def _release_evidence_item(
    *,
    evidence_id: str,
    title: str,
    source: str,
    command: str,
    detected: bool,
) -> dict[str, Any]:
    return {
        "id": evidence_id,
        "title": title,
        "source": source,
        "detected": detected,
        "status": "present" if detected else "missing",
        "command": command,
        "human_review_required": True,
        "safe_to_publish": False,
        "release_authorized": False,
        "reporting_only": True,
    }


def build_release_sample() -> dict[str, Any]:
    items = [
        _release_evidence_item(
            evidence_id="package_build_command",
            title="Package build command",
            source="Makefile and release workflow",
            command="python -m build",
            detected=True,
        ),
        _release_evidence_item(
            evidence_id="twine_metadata_check",
            title="Twine metadata check",
            source="Makefile and release workflow",
            command="python -m twine check dist/*",
            detected=True,
        ),
        _release_evidence_item(
            evidence_id="wheel_contents_check",
            title="Wheel contents check",
            source="Makefile and release workflow",
            command=("python -m check_wheel_contents --ignore W009 dist/*.whl"),
            detected=True,
        ),
        _release_evidence_item(
            evidence_id="wheel_smoke_install",
            title="Wheel smoke install",
            source="Makefile and release workflow",
            command=("python -m pip install --force-reinstall dist/*.whl && sdetkit --help"),
            detected=True,
        ),
        _release_evidence_item(
            evidence_id="release_preflight",
            title="Release preflight",
            source="Makefile and release workflow",
            command="python scripts/release_preflight.py",
            detected=True,
        ),
        _release_evidence_item(
            evidence_id="release_provenance_attestation",
            title="Release provenance attestation",
            source="release workflow",
            command="actions/attest-build-provenance",
            detected=True,
        ),
        _release_evidence_item(
            evidence_id="release_diagnostics_upload",
            title="Release diagnostics upload",
            source="release workflow",
            command="upload release diagnostics",
            detected=True,
        ),
        _release_evidence_item(
            evidence_id="post_publish_or_rollback_plan",
            title="Post-publish or rollback verification plan",
            source="release verification plan",
            command="make release-verify-plan",
            detected=False,
        ),
    ]

    handoff = {
        "collection_status": "collected",
        "available": True,
        "reason": ("Trusted PR Quality decision was collected and verified."),
        "summary_path": "evidence/pr-review-summary.md",
        "manifest_path": "evidence/handoff-manifest.json",
        "head_sha": RELEASE_HEAD_SHA,
        "head_matches": True,
        "review_state": "ready",
        "first_blocker": "none",
        "next_action": "review_and_decide",
        "required_checks": "clear",
        "security_posture": "clear",
        "merge_posture": ("automated_proof_complete_human_decision_required"),
        "release_review_blocking": False,
        "reporting_only": True,
        "safe_to_publish": False,
        "release_authorized": False,
        "publish_authorized": False,
        "merge_authorized": False,
        "source_digests": {
            "pr_quality_summary": _digest("5"),
            "pr_quality_handoff_manifest": _digest("6"),
        },
        "authority_boundary": dict(release._PR_QUALITY_AUTHORITY_BOUNDARY),
    }

    input_digests = {
        ".github/workflows/release.yml": _digest("7"),
        "Makefile": _digest("8"),
        "docs/artifact-reference.md": _digest("9"),
        "docs/release-readiness-evidence-handoff.md": _digest("a"),
        "pr_quality_summary": _digest("b"),
        "pr_quality_handoff_manifest": _digest("c"),
    }
    provenance = _provenance(
        schema_version=release.SCHEMA_VERSION,
        generator_source=release.GENERATOR_SOURCE,
        head_sha=RELEASE_HEAD_SHA,
        input_digests=input_digests,
        input_count=12,
        input_artifact_schemas={
            "pr_quality_handoff_manifest": ("sdetkit.pr_quality_publisher_handoff.v1")
        },
    )

    payload: dict[str, Any] = {
        "schema_version": release.SCHEMA_VERSION,
        "tool": "sdetkit.release_readiness_evidence_package",
        "status": "review_required",
        "report_status": "review_required",
        "reporting_only": True,
        "review_first": True,
        "repo_mutation": False,
        "issue_mutation_allowed": False,
        "automation_allowed": False,
        "patch_application_allowed": False,
        "security_dismissal_allowed": False,
        "safe_to_publish": False,
        "release_authorized": False,
        "publish_authorized": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
        "authority_boundary": dict(release._AUTHORITY_BOUNDARY),
        "summary": {
            "required_evidence_count": len(items),
            "present_evidence_count": 7,
            "missing_evidence_count": 1,
            "status": "review_required",
            "next_allowed_action": "human_release_review",
            "pr_quality_collection_status": "collected",
            "pr_quality_release_review_blocking": False,
        },
        "pr_quality_handoff": handoff,
        "required_human_evidence": list(release._REQUIRED_EVIDENCE),
        "blocked_actions": [
            "automatic_release",
            "automatic_publish",
            "automatic_tag_mutation",
            "automatic_security_dismissal",
            "semantic_equivalence_claim",
        ],
        "evidence_items": items,
        "proof_commands": list(release._PROOF_COMMANDS),
        "next_allowed_action": "human_release_review",
        "generated_at": FIXED_GENERATED_AT,
        "current_head_sha": RELEASE_HEAD_SHA,
        "source_issue_numbers": [],
        "source_run_ids": [],
        "input_digests": input_digests,
        "input_provenance": provenance,
    }
    return payload


def build_post_merge_sample() -> dict[str, Any]:
    input_digests = {
        "evidence:commit_status": _digest("5"),
        "evidence:pr": _digest("6"),
        "evidence:review_threads": _digest("7"),
        "evidence:security": _digest("8"),
        "previous_main_sha": _digest("9"),
    }
    provenance = _provenance(
        schema_version=post_merge.SCHEMA_VERSION,
        generator_source=post_merge.GENERATOR_SOURCE,
        head_sha=MERGE_COMMIT_SHA,
        input_digests=input_digests,
        input_count=11,
        source_issue_numbers=[1234],
        source_run_ids=[5678],
    )

    artifacts = {
        name: {
            "name": name,
            "path": f"evidence/{filename}",
            "collection_status": "collected",
            "available": True,
            "reason": "",
        }
        for name, filename in post_merge.EVIDENCE_FILES.items()
    }

    payload: dict[str, Any] = {
        "schema_version": post_merge.SCHEMA_VERSION,
        "tool": "sdetkit.post_merge_verification",
        "status": "verified",
        "report_status": "passed",
        "previous_main_sha": PREVIOUS_MAIN_SHA,
        "pr_number": 1234,
        "pr_head_sha": PR_HEAD_SHA,
        "pr_base_sha": PREVIOUS_MAIN_SHA,
        "merge_commit_sha": MERGE_COMMIT_SHA,
        "merge_relation": "exact_merge_commit",
        "merged": True,
        "pr_state": "closed",
        "changed_paths": [
            "src/example.py",
            "tests/test_example.py",
        ],
        "protected_path_drift": [],
        "git": {
            "collection_status": "collected",
            "available": True,
            "reason": "",
        },
        "ci": {
            "collection_status": "collected",
            "available": True,
            "state": "success",
            "contexts": {
                "ci": "success",
                "maintenance-autopilot": "success",
            },
        },
        "ghas_review_threads": {
            "collection_status": "collected",
            "available": True,
            "current_count": 0,
            "outdated_count": 0,
            "resolved_count": 0,
            "state_counts": {
                "current": 0,
                "outdated": 0,
                "resolved": 0,
                "unavailable": 0,
            },
        },
        "local_security": {
            "collection_status": "collected",
            "available": True,
            "finding_count": 2,
            "info_count": 2,
            "blocking_finding_count": 0,
            "warn_count": 0,
            "error_count": 0,
        },
        "input_artifacts": artifacts,
        "reporting_only": True,
        "repo_mutation": False,
        "issue_mutation_allowed": False,
        "automation_allowed": False,
        "patch_application_allowed": False,
        "workflow_rerun_allowed": False,
        "security_dismissal_allowed": False,
        "release_authorized": False,
        "publish_authorized": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
        "authority_boundary": dict(post_merge.AUTHORITY_BOUNDARY),
        "next_allowed_action": "human_post_merge_review",
        "generated_at": FIXED_GENERATED_AT,
        "current_head_sha": MERGE_COMMIT_SHA,
        "source_issue_numbers": [1234],
        "source_run_ids": [5678],
        "input_digests": input_digests,
        "input_provenance": provenance,
    }
    return payload


def _walk_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        strings: list[str] = []
        for key, item in value.items():
            strings.extend(_walk_strings(str(key)))
            strings.extend(_walk_strings(item))
        return strings
    if isinstance(value, list):
        strings = []
        for item in value:
            strings.extend(_walk_strings(item))
        return strings
    return []


def test_checked_in_samples_match_canonical_builders() -> None:
    assert RELEASE_SAMPLE_PATH.read_text(encoding="utf-8") == (
        serialize_sample(build_release_sample())
    )
    assert POST_MERGE_SAMPLE_PATH.read_text(encoding="utf-8") == (
        serialize_sample(build_post_merge_sample())
    )


def test_release_sample_preserves_schema_and_authority() -> None:
    payload = build_release_sample()

    assert payload["schema_version"] == release.SCHEMA_VERSION
    assert payload["status"] == "review_required"
    assert payload["report_status"] == "review_required"
    assert payload["summary"]["missing_evidence_count"] == 1
    assert payload["pr_quality_handoff"]["collection_status"] == "collected"

    for key in (
        "repo_mutation",
        "issue_mutation_allowed",
        "automation_allowed",
        "patch_application_allowed",
        "security_dismissal_allowed",
        "safe_to_publish",
        "release_authorized",
        "publish_authorized",
        "merge_authorized",
        "semantic_equivalence_proven",
    ):
        assert payload[key] is False, key


def test_post_merge_sample_keeps_info_non_blocking() -> None:
    payload = build_post_merge_sample()

    assert payload["schema_version"] == post_merge.SCHEMA_VERSION
    assert payload["status"] == "verified"
    assert payload["merge_relation"] == "exact_merge_commit"
    assert payload["local_security"]["finding_count"] == 2
    assert payload["local_security"]["info_count"] == 2
    assert payload["local_security"]["blocking_finding_count"] == 0
    assert payload["local_security"]["warn_count"] == 0
    assert payload["local_security"]["error_count"] == 0
    assert payload["protected_path_drift"] == []

    for key in (
        "repo_mutation",
        "issue_mutation_allowed",
        "automation_allowed",
        "patch_application_allowed",
        "workflow_rerun_allowed",
        "security_dismissal_allowed",
        "release_authorized",
        "publish_authorized",
        "merge_authorized",
        "semantic_equivalence_proven",
    ):
        assert payload[key] is False, key


def test_samples_are_sanitized_and_low_entropy() -> None:
    payloads = [build_release_sample(), build_post_merge_sample()]
    all_strings = "\n".join(string for payload in payloads for string in _walk_strings(payload))

    forbidden = (
        r"gh[pousr]_[A-Za-z0-9_]{20,}",
        r"/home/[^/\s]+",
        r"/Users/[^/\s]+",
        r"[A-Za-z]:\\Users\\",
        r"sherif69-sa",
        r"DevS69-sdetkit",
        r"github\.com/",
        r"private-user-images",
    )
    for pattern in forbidden:
        assert re.search(pattern, all_strings) is None, pattern

    for payload in payloads:
        assert payload["generated_at"] == FIXED_GENERATED_AT
        for value in _walk_strings(payload):
            if value.startswith(("http://", "https://")):
                assert value.startswith("https://example.invalid/")


def test_recipe_navigation_and_cross_links() -> None:
    recipe = RECIPE_PATH.read_text(encoding="utf-8")
    handoff = HANDOFF_PATH.read_text(encoding="utf-8")
    artifact_reference = ARTIFACT_REFERENCE_PATH.read_text(encoding="utf-8")
    showcase = SHOWCASE_PATH.read_text(encoding="utf-8")
    mkdocs = MKDOCS_PATH.read_text(encoding="utf-8")

    assert recipe.count("examples/release-readiness-evidence-package.sample.json") == 1
    assert recipe.count("examples/post-merge-verification.sample.json") == 1

    release_sample_link = (
        "[`release-readiness-evidence-package.sample.json`]"
        "(examples/release-readiness-evidence-package.sample.json)"
    )
    post_merge_sample_link = (
        "[`post-merge-verification.sample.json`](examples/post-merge-verification.sample.json)"
    )

    for text in (artifact_reference, showcase):
        assert text.count("release-evidence-recipes.md") == 1
        assert text.count(release_sample_link) == 1
        assert text.count(post_merge_sample_link) == 1

    assert handoff.count("release-evidence-recipes.md") == 1
    assert mkdocs.count("release-evidence-recipes.md") == 1


def test_recipe_covers_commands_states_and_authority() -> None:
    recipe = RECIPE_PATH.read_text(encoding="utf-8")

    required_tokens = (
        "release-readiness-evidence-package",
        "--pr-quality-summary",
        "--pr-quality-handoff-manifest",
        "post-merge-verification",
        "--evidence-dir",
        "--previous-main-sha",
        "--check-freshness",
        "collected",
        "missing",
        "malformed",
        "stale",
        "digest_mismatch",
        "review_required",
        "unavailable",
        "verified",
        "reporting-only",
        "does not collect GitHub evidence",
    )
    for token in required_tokens:
        assert token in recipe, token
