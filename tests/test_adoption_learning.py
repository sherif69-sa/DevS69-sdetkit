from __future__ import annotations

import json
from pathlib import Path

from sdetkit.adoption_learning import (
    SCHEMA_VERSION,
    build_adoption_learning_payload,
    render_adoption_learning_text,
)
from sdetkit.adoption_surface import write_adoption_surface_artifact


def _write(path: Path, text: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_adoption_learning_records_fixture_strengths_and_boundaries(tmp_path: Path) -> None:
    _write(tmp_path / "pyproject.toml", '[project]\ndependencies = ["pytest"]\n')
    _write(tmp_path / "requirements-test.txt", "pytest==9.0.3\n")
    _write(tmp_path / ".pre-commit-config.yaml", "repos: []\n")
    _write(
        tmp_path / "Makefile",
        ".PHONY: proof-after-format\nproof-after-format:\n\tpython -m pre_commit run -a\n",
    )
    _write(tmp_path / "mkdocs.yml", "site_name: Example\n")
    _write(
        tmp_path / ".github" / "workflows" / "security.yml",
        "steps:\n  - uses: github/codeql-action/init@abc\n"
        "  - uses: actions/dependency-review-action@abc\n",
    )

    payload = build_adoption_learning_payload(tmp_path)

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["target"] == "external_repo"
    assert payload["recommended_next_upgrade"] == "fixture repo matrix"
    assert "python project detected" in payload["detected_strengths"]
    assert "pytest proof command detected" in payload["detected_strengths"]
    assert "mkdocs documentation proof detected" in payload["detected_strengths"]
    assert "fixture repo matrix" in payload["upgrade_candidates"]
    assert "public repo eligibility screen" in payload["upgrade_candidates"]
    assert payload["authority_boundary"] == {
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False


def test_adoption_learning_records_current_repo_self_baseline() -> None:
    payload = build_adoption_learning_payload(Path("."), trial_name="self_adoption_baseline")

    assert payload["trial_name"] == "self_adoption_baseline"
    assert payload["target"] == "current_sdetkit_repo"
    assert "python" in payload["observed_surfaces"]["detected_languages"]
    assert "pytest" in payload["observed_surfaces"]["test_runners"]
    assert "github_actions" in payload["observed_surfaces"]["ci_systems"]
    assert "make proof-after-format" in payload["observed_surfaces"]["recommended_proof_commands"]
    assert "fixture repo matrix" in payload["upgrade_candidates"]
    assert "add fixture repo matrix for non-Python repo shapes" not in payload["learning_gaps"]
    assert payload["recommended_next_upgrade"] == "public repo eligibility screen"
    assert payload["authority_boundary"]["automation_allowed"] is False
    assert payload["authority_boundary"]["patch_application_allowed"] is False


def test_adoption_learning_cli_dispatch_writes_text_summary(
    tmp_path: Path,
    capsys,
) -> None:
    _write(tmp_path / "pyproject.toml", '[project]\ndependencies = ["pytest"]\n')
    _write(tmp_path / "requirements-test.txt", "pytest==9.0.3\n")
    out = tmp_path / "adoption-learning.json"

    from sdetkit.cli import main as cli_main

    rc = cli_main(
        [
            "adoption-learning",
            "--root",
            str(tmp_path),
            "--out",
            str(out),
            "--format",
            "text",
        ]
    )

    assert rc == 0
    stdout = capsys.readouterr().out
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == SCHEMA_VERSION
    assert "adoption_learning_status=recorded" in stdout
    assert "recommended_next_upgrade=fixture repo matrix" in stdout
    assert "- automation_allowed=false" in stdout
    assert "- patch_application_allowed=false" in stdout


def test_adoption_learning_can_reuse_existing_surface_artifact(tmp_path: Path) -> None:
    _write(tmp_path / "pyproject.toml", '[project]\ndependencies = ["pytest"]\n')
    _write(tmp_path / "requirements-test.txt", "pytest==9.0.3\n")
    surface = tmp_path / "adoption-surface.json"
    write_adoption_surface_artifact(repo_root=tmp_path, out=surface)

    from sdetkit.adoption_learning import write_adoption_learning_artifact

    out = tmp_path / "adoption-learning.json"
    payload = write_adoption_learning_artifact(
        repo_root=Path("/unused/when/surface-json-is-provided"),
        surface_json=surface,
        out=out,
        trial_name="surface_reuse",
    )

    assert payload["trial_name"] == "surface_reuse"
    assert payload["observed_surfaces"]["detected_languages"] == ["python"]
    assert json.loads(out.read_text(encoding="utf-8"))["schema_version"] == SCHEMA_VERSION


def test_adoption_learning_text_renderer_keeps_next_upgrade_visible() -> None:
    payload = build_adoption_learning_payload(Path("."))

    text = render_adoption_learning_text(payload)

    assert "recommended_next_upgrade=public repo eligibility screen" in text
    assert "learning_gaps:" in text
    assert "- semantic_equivalence_proven=false" in text
