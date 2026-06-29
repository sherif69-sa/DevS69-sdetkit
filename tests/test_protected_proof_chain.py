from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from sdetkit.protected_proof_chain import (
    STAGE_ORDER,
    build_protected_proof_chain,
    verify_protected_proof_chain,
    write_protected_proof_chain,
)

REPOSITORY = "owner/repo"
COMMIT_SHA = "a" * 40


def _artifacts(root: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for stage in STAGE_ORDER:
        path = root / (f"{stage}.md" if stage == "pr_report" else f"{stage}.json")
        path.parent.mkdir(parents=True, exist_ok=True)
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


def _build(artifacts: dict[str, Path]) -> dict[str, object]:
    return build_protected_proof_chain(
        repository=REPOSITORY,
        commit_sha=COMMIT_SHA,
        artifacts=artifacts,
    )


def _verify(
    manifest: dict[str, object],
    artifacts: dict[str, Path],
    repository: str = REPOSITORY,
    commit_sha: str = COMMIT_SHA,
) -> dict[str, object]:
    return verify_protected_proof_chain(
        manifest,
        artifacts=artifacts,
        expected_repository=repository,
        expected_commit_sha=commit_sha,
    )


def test_proof_chain_is_deterministic_and_review_first(tmp_path: Path) -> None:
    artifacts = _artifacts(tmp_path)
    first = _build(artifacts)
    second = _build(artifacts)

    assert first == second
    assert first["stage_order"] == list(STAGE_ORDER)
    assert first["separation_of_duties"]["worker_may_self_certify"] is False
    assert first["separation_of_duties"]["verifier_result_required"] is True
    assert all(value is False for value in first["decision_boundary"].values())
    assert _verify(first, artifacts)["ok"] is True


def test_proof_chain_detects_artifact_tampering(tmp_path: Path) -> None:
    artifacts = _artifacts(tmp_path)
    manifest = _build(artifacts)
    artifacts["proof_result"].write_text(
        '{"schema_version":"tampered","automation_allowed":false}\n',
        encoding="utf-8",
    )

    result = _verify(manifest, artifacts)

    assert result["ok"] is False
    assert {item["stage"] for item in result["mismatches"]} == {
        "manifest.entries",
        "manifest.chain_id",
    }


@pytest.mark.parametrize("enabled", [True, 1, "true", "yes", "authorized"])
def test_proof_chain_rejects_json_authority_expansion(
    tmp_path: Path,
    enabled: object,
) -> None:
    artifacts = _artifacts(tmp_path)
    artifacts["verifier_result"].write_text(
        json.dumps(
            {
                "schema_version": "test.verifier.v1",
                "nested": {"merge_authorized": enabled},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="attempted to expand authority"):
        _build(artifacts)


def test_proof_chain_rejects_markdown_authority_expansion(tmp_path: Path) -> None:
    artifacts = _artifacts(tmp_path)
    artifacts["pr_report"].write_text(
        "# PR report\n\nmerge_authorized: `true`\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="pr_report:markdown:merge_authorized"):
        _build(artifacts)


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("status", "verified"),
        ("stage_order", ["verifier_result"]),
        ("decision_boundary", {"merge_authorized": True}),
    ],
)
def test_proof_chain_detects_manifest_tampering(
    tmp_path: Path,
    field: str,
    replacement: object,
) -> None:
    artifacts = _artifacts(tmp_path)
    manifest = _build(artifacts)
    tampered = copy.deepcopy(manifest)
    tampered[field] = replacement

    result = _verify(tampered, artifacts)

    assert result["ok"] is False
    assert f"manifest.{field}" in {item["stage"] for item in result["mismatches"]}


def test_proof_chain_binds_external_identity_and_required_stages(tmp_path: Path) -> None:
    artifacts = _artifacts(tmp_path)
    manifest = _build(artifacts)
    mismatch = _verify(manifest, artifacts, "other/repo", "b" * 40)
    assert mismatch["ok"] is False
    assert {item["stage"] for item in mismatch["mismatches"]} >= {
        "manifest.repository",
        "manifest.commit_sha",
        "manifest.chain_id",
    }

    artifacts.pop("trajectory")
    with pytest.raises(ValueError, match="missing=trajectory"):
        _build(artifacts)


def test_proof_chain_writes_reviewable_outputs(tmp_path: Path) -> None:
    payload = _build(_artifacts(tmp_path))
    json_path = tmp_path / "out" / "chain.json"
    markdown_path = tmp_path / "out" / "chain.md"
    write_protected_proof_chain(payload, json_path=json_path, markdown_path=markdown_path)

    assert json.loads(json_path.read_text(encoding="utf-8"))["chain_id"] == payload["chain_id"]
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "worker proof result and protected verifier result are separate" in markdown
    assert "merge_authorized: `false`" in markdown
