from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit.protected_proof_chain import STAGE_ORDER, build_protected_proof_chain

REPOSITORY = "owner/repo"
COMMIT_SHA = "a" * 40


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


def _build(artifacts: dict[str, Path]) -> dict[str, object]:
    return build_protected_proof_chain(
        repository=REPOSITORY,
        commit_sha=COMMIT_SHA,
        artifacts=artifacts,
    )


def test_proof_chain_accepts_matching_embedded_identity(tmp_path: Path) -> None:
    artifacts = _artifacts(tmp_path)
    _write_claim(
        artifacts["proof_result"],
        repository_full_name=REPOSITORY,
        current_head_sha=COMMIT_SHA,
    )
    _write_claim(
        artifacts["verifier_result"],
        repo_full_name=REPOSITORY,
        head_sha=COMMIT_SHA[:12],
    )

    manifest = _build(artifacts)

    assert manifest["repository"] == REPOSITORY
    assert manifest["commit_sha"] == COMMIT_SHA


@pytest.mark.parametrize(
    "claim",
    [
        {"repository_full_name": "different/repository"},
        {"current_head_sha": "b" * 40},
        {"head_sha": "invalid-sha-value"},
    ],
)
def test_proof_chain_rejects_conflicting_embedded_identity(
    tmp_path: Path,
    claim: dict[str, object],
) -> None:
    artifacts = _artifacts(tmp_path)
    _write_claim(artifacts["proof_result"], **claim)

    with pytest.raises(ValueError, match="identity mismatch"):
        _build(artifacts)


def test_proof_chain_ignores_nested_historical_identity(tmp_path: Path) -> None:
    artifacts = _artifacts(tmp_path)
    _write_claim(
        artifacts["trajectory"],
        historical_record={
            "repository_full_name": "different/repository",
            "head_sha": "b" * 40,
        },
    )

    assert _build(artifacts)["status"] == "bound_review_first"
