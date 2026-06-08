from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sdetkit.adoption_learning import build_adoption_learning_payload
from sdetkit.adoption_surface import (
    discover_adoption_surface,
    render_adoption_surface_report,
    write_adoption_surface_artifact,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _snapshot_tree(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        rel = path.relative_to(root).as_posix()
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _make_owned_external_repo(root: Path) -> None:
    _write(root / "pyproject.toml", '[project]\ndependencies = ["pytest"]\n')
    _write(root / "requirements-test.txt", "pytest==9.0.3\n")
    _write(
        root / ".git" / "config",
        '[remote "origin"]\n    url = https://token@example.com/org/owned-demo.git\n',
    )


def test_local_external_root_surface_is_read_only_and_not_current_repo(
    tmp_path: Path,
) -> None:
    external_root = tmp_path / "owned_external_repo"
    _make_owned_external_repo(external_root)
    before = _snapshot_tree(external_root)
    out = tmp_path / "artifacts" / "adoption-surface.json"

    summary = write_adoption_surface_artifact(repo_root=external_root, out=out)

    assert _snapshot_tree(external_root) == before
    assert out.is_file()
    assert not out.is_relative_to(external_root)
    assert summary["adoption_surface_json"] == out.as_posix()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["repo_root"] == external_root.as_posix()
    assert payload["repo_identity"] == {
        "name": "owned_external_repo",
        "is_current_sdetkit_repo": False,
        "git_detected": True,
        "remote_url": "https://example.com/org/owned-demo.git",
    }
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False
    assert all(
        command["auto_run_allowed"] is False for command in payload["recommended_proof_commands"]
    )


def test_local_external_root_report_keeps_operator_boundary(tmp_path: Path) -> None:
    external_root = tmp_path / "owned_external_repo"
    _make_owned_external_repo(external_root)

    report = render_adoption_surface_report(discover_adoption_surface(external_root))

    assert "# SDETKit adoption readiness report" in report
    assert "- name: owned_external_repo" in report
    assert "- is_current_sdetkit_repo: false" in report
    assert "- git_detected: true" in report
    assert "- remote_url: https://example.com/org/owned-demo.git" in report
    assert "- python (high)" in report
    assert "auto_run_allowed=false" in report
    assert "- patch_application_allowed: false" in report


def test_local_external_root_cli_dispatch_writes_artifact_outside_target(
    tmp_path: Path,
    capsys,
) -> None:
    external_root = tmp_path / "owned_external_repo"
    _make_owned_external_repo(external_root)
    before = _snapshot_tree(external_root)
    out = tmp_path / "artifacts" / "adoption-surface.json"

    from sdetkit.cli import main as cli_main

    rc = cli_main(
        [
            "adoption-surface",
            "--root",
            str(external_root),
            "--out",
            str(out),
            "--format",
            "text",
        ]
    )

    assert rc == 0
    stdout = capsys.readouterr().out
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert _snapshot_tree(external_root) == before
    assert "adoption_surface_json=" in stdout
    assert payload["repo_identity"]["is_current_sdetkit_repo"] is False
    assert payload["repo_identity"]["remote_url"] == "https://example.com/org/owned-demo.git"


def test_self_learning_advances_to_public_repo_eligibility_after_local_smoke() -> None:
    payload = build_adoption_learning_payload(Path("."))

    assert payload["recommended_next_upgrade"] == "first permissive public repo read-only trial"
    assert "add local external-root smoke before public repo trials" not in payload["learning_gaps"]
    assert (
        "add public repo eligibility screen before using third-party repos"
        not in payload["learning_gaps"]
    )
    assert "run first permissive public repo read-only trial" in payload["learning_gaps"]
    assert payload["authority_boundary"]["automation_allowed"] is False
    assert payload["authority_boundary"]["patch_application_allowed"] is False
