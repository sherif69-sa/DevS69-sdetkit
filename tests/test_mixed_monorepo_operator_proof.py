from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from sdetkit.mixed_monorepo_operator_proof import (
    DOCTOR_JSON,
    DOCTOR_MD,
    PROOF_JSON,
    PROOF_MD,
    REPO_MEMORY_JSON,
    WORKSPACE_FAILURES_JSON,
    build_mixed_monorepo_operator_proof,
    main,
    render_markdown,
)

FIXTURE = Path("tests/fixtures/adoption_repos/mixed_nested_workspaces")
FAILURES = Path("tests/fixtures/ci_failures/mixed_monorepo")
LOGS = (
    FAILURES / "admin/shared_test.log",
    FAILURES / "web/shared_test.log",
    FAILURES / "native/shared_test.log",
    FAILURES / "ambiguous/mixed_shared_test.log",
)
AUTHORITY_FIELDS = {
    "target_code_execution",
    "automation_allowed",
    "patch_application_allowed",
    "security_dismissal_allowed",
    "publication_authorized",
    "merge_authorized",
    "semantic_equivalence_proven",
}


def _proof_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "mixed-repo"
    shutil.copytree(FIXTURE, repo)
    cargo = repo / "crates/native/Cargo.toml"
    cargo.parent.mkdir(parents=True)
    cargo.write_text(
        '[package]\nname = "mixed-native"\nversion = "0.1.0"\nedition = "2021"\n',
        encoding="utf-8",
    )
    return repo


def _digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def test_complete_mixed_monorepo_operator_proof(tmp_path: Path) -> None:
    repo = _proof_repo(tmp_path)
    before = _digest(repo)
    out_dir = tmp_path / "proof"

    payload = build_mixed_monorepo_operator_proof(
        repo=repo,
        failure_logs=LOGS,
        evidence_root=FAILURES,
        out_dir=out_dir,
    )

    assert payload["schema_version"] == "sdetkit.mixed_monorepo_operator_proof.v1"
    assert payload["verification"]["ok"] is True
    assert set(payload["verification"]["checks"].values()) == {True}
    assert payload["repository_unchanged"] is True
    assert _digest(repo) == before

    definitions = payload["workspace_failure_bundle"]["summary"]["by_workspace"]
    assert definitions == {
        "apps/admin": 1,
        "apps/web": 1,
        "crates/native": 1,
        "unknown": 1,
    }
    assert payload["failure_vector_bundle"]["failure_vector_count"] == 4
    assert payload["doctor_report"]["status"] == "review_required"
    assert payload["doctor_report"]["failure_vector_evidence"]["failure_vector_count"] == 4
    assert payload["repo_memory_profile"]["profile_status"] == "observation_only"
    assert (
        payload["repo_memory_profile"]["command_profile"]["commands_executed_by_repo_memory"]
        is False
    )

    boundary = payload["authority_boundary"]
    assert set(boundary) == AUTHORITY_FIELDS
    assert set(boundary.values()) == {False}
    for name in (
        PROOF_JSON,
        PROOF_MD,
        WORKSPACE_FAILURES_JSON,
        DOCTOR_JSON,
        DOCTOR_MD,
        REPO_MEMORY_JSON,
    ):
        assert (out_dir / name).is_file(), name


def test_workspace_commands_and_failures_remain_distinct(tmp_path: Path) -> None:
    payload = build_mixed_monorepo_operator_proof(
        repo=_proof_repo(tmp_path),
        failure_logs=tuple(reversed(LOGS)),
        evidence_root=FAILURES,
        out_dir=tmp_path / "proof",
    )

    commands = payload["adoption_surface"]["recommended_proof_commands"]
    npm = [item for item in commands if item["command"] == "npm test"]
    assert [item["source"]["working_directory"] for item in npm] == [
        "apps/admin",
        "apps/web",
    ]
    assert all(item["auto_run_allowed"] is False for item in commands)

    failures = payload["workspace_failure_bundle"]["workspace_failures"]
    by_owner = {item["workspace_identity"]["path"]: item for item in failures}
    assert by_owner["apps/admin"]["evidence_source"] == "admin/shared_test.log"
    assert by_owner["apps/web"]["evidence_source"] == "web/shared_test.log"
    assert by_owner["crates/native"]["evidence_source"] == "native/shared_test.log"
    assert by_owner["unknown"]["ownership_confidence"] == "low"
    assert by_owner["unknown"]["failure_vector"]["failure_class"] == "unknown"
    assert all(item["safety_gate"]["review_first"] is True for item in failures)
    assert all(item["protected_verifier"]["decision"]["review_first"] is True for item in failures)


def test_operator_proof_is_serialization_deterministic(tmp_path: Path) -> None:
    repo = _proof_repo(tmp_path)
    first = build_mixed_monorepo_operator_proof(
        repo=repo,
        failure_logs=LOGS,
        evidence_root=FAILURES,
        out_dir=tmp_path / "first",
    )
    second = build_mixed_monorepo_operator_proof(
        repo=repo,
        failure_logs=tuple(reversed(LOGS)),
        evidence_root=FAILURES,
        out_dir=tmp_path / "second",
    )

    assert json.dumps(first, sort_keys=True, separators=(",", ":")) == json.dumps(
        second,
        sort_keys=True,
        separators=(",", ":"),
    )
    assert render_markdown(first) == render_markdown(second)


def test_cli_prints_sanitized_manifest(tmp_path: Path, capsys) -> None:
    repo = _proof_repo(tmp_path)
    argv = [
        "--repo",
        str(repo),
        "--evidence-root",
        str(FAILURES),
        "--out-dir",
        str(tmp_path / "proof"),
    ]
    for path in LOGS:
        argv.extend(["--failure-log", str(path)])

    assert main(argv) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["verification_ok"] is True
    assert set(output["authority_boundary"]) == AUTHORITY_FIELDS
    assert set(output["authority_boundary"].values()) == {False}
    assert "workspace_failure_bundle" not in output
