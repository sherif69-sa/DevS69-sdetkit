from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit.evidence_binding import build_bound_proof_chain, validate_evidence_binding
from sdetkit.protected_proof_chain import STAGE_ORDER

REPOSITORY = "owner/repo"
REVISION = "a" * 40


def _artifacts(root: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for stage in STAGE_ORDER:
        path = root / (f"{stage}.md" if stage == "pr_report" else f"{stage}.json")
        if stage == "pr_report":
            path.write_text("# PR report\n\nReview required.\n", encoding="utf-8")
        else:
            path.write_text(
                json.dumps(
                    {
                        "schema_version": f"test.{stage}.v1",
                        "automation_allowed": False,
                        "patch_application_allowed": False,
                        "merge_authorized": False,
                        "semantic_equivalence_proven": False,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
        result[stage] = path
    return result


def _write_claim(path: Path, **claims: object) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.update(claims)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def test_binding_accepts_matching_claims(tmp_path: Path) -> None:
    artifacts = _artifacts(tmp_path)
    _write_claim(
        artifacts["proof_result"],
        repository_full_name=REPOSITORY,
        current_head_sha=REVISION,
    )
    _write_claim(
        artifacts["verifier_result"],
        repo_full_name=REPOSITORY,
        head_sha=REVISION[:12],
    )

    validation = validate_evidence_binding(
        repository=REPOSITORY,
        revision=REVISION,
        artifacts=artifacts,
    )
    manifest = build_bound_proof_chain(
        repository=REPOSITORY,
        revision=REVISION,
        artifacts=artifacts,
    )

    assert validation["status"] == "passed"
    assert validation["claim_count"] == 4
    assert manifest["repository"] == REPOSITORY
    assert manifest["commit_sha"] == REVISION


@pytest.mark.parametrize(
    "claim",
    [
        {"repository_full_name": "different/repository"},
        {"current_head_sha": "b" * 40},
        {"head_sha": "invalid-sha-value"},
    ],
)
def test_binding_rejects_conflicting_claims(
    tmp_path: Path,
    claim: dict[str, object],
) -> None:
    artifacts = _artifacts(tmp_path)
    _write_claim(artifacts["proof_result"], **claim)

    with pytest.raises(ValueError, match="binding conflict"):
        build_bound_proof_chain(
            repository=REPOSITORY,
            revision=REVISION,
            artifacts=artifacts,
        )


def test_binding_ignores_nested_historical_claims(tmp_path: Path) -> None:
    artifacts = _artifacts(tmp_path)
    _write_claim(
        artifacts["trajectory"],
        historical_record={
            "repository_full_name": "different/repository",
            "head_sha": "b" * 40,
        },
    )

    validation = validate_evidence_binding(
        repository=REPOSITORY,
        revision=REVISION,
        artifacts=artifacts,
    )

    assert validation["status"] == "passed"
    assert validation["claim_count"] == 0
