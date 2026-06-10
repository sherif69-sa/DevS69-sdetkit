from __future__ import annotations

import json
from pathlib import Path

from sdetkit import product_maturity_radar as radar_module
from sdetkit.product_maturity_radar import (
    SCHEMA_VERSION,
    build_product_maturity_radar,
    write_product_maturity_radar,
)


def _write(path: Path, content: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _fixture_repo(root: Path) -> None:
    _write(
        root / "README.md",
        "SDETKit product proof and gate fast gate release doctor.\n",
    )
    _write(
        root / "pyproject.toml",
        """
[project]
name = "sdetkit"
requires-python = ">=3.10"

[project.optional-dependencies]
test = ["pytest"]

[project.scripts]
sdetkit = "sdetkit.cli:main"

[tool.setuptools.package-data]
sdetkit = ["data/*.json"]
""",
    )
    _write(root / "CHANGELOG.md", "# Changelog\n")
    _write(root / "SECURITY.md", "# Security\n")
    _write(root / "docs" / "index.md", "# Docs\n")
    _write(root / "docs" / "start-here-5-minutes.md", "# Start\n")
    _write(root / "docs" / "cli.md", "# CLI\n")
    _write(root / "docs" / "artifact-reference.md", "stable-json\n")
    _write(root / "docs" / "live-adoption-product-proof.md", "# Product proof\n")
    _write(root / "docs" / "security.md", "# Security\n")
    _write(root / "docs" / "project" / "release-process.md", "# Release\n")
    _write(root / "docs" / "policy-and-baselines.md", "# Policy\n")
    _write(root / "docs" / "remediation-cookbook.md", "# Remediation\n")
    for index in range(12):
        _write(root / "docs" / f"guide-{index}.md", "# Guide\n")

    _write(root / "mkdocs.yml", "site_name: demo\n")
    _write(root / ".github" / "workflows" / "ci.yml", "name: ci\n")
    _write(root / "examples" / "kits" / "intelligence" / "failure-fix-playbook.md", "# Fix\n")

    for filename in [
        "artifact_evidence.py",
        "check_intelligence.py",
        "current_head_failure_bundle.py",
        "diagnostic_vector_engine.py",
        "reliability_spine_alignment.py",
        "adoption_external_integration.py",
        "adoption_real_world_learning_matrix.py",
        "adoption_learning_report.py",
        "workflow_governance_report.py",
        "repo_memory.py",
        "replayable_benchmark_harness.py",
        "pr_quality_action_report.py",
    ]:
        _write(root / "src" / "sdetkit" / filename, "safe_to_patch = False\n")

    for filename in [
        "test_check_intelligence.py",
        "test_current_head_failure_bundle.py",
        "test_pr_quality_current_head_failure_bundle.py",
        "test_adoption_learning_report.py",
        "test_adoption_real_world_learning_matrix.py",
        "test_workflow_governance_report.py",
        "test_repo_memory.py",
        "test_trajectory_store.py",
    ]:
        _write(root / "tests" / filename, "def test_demo():\n    assert True\n")


def _ranked_radar_candidates(payload: dict) -> list[dict]:
    for key in (
        "ranked_upgrade_candidates",
        "ranked_candidates",
        "upgrade_candidates",
        "candidates",
    ):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    raise AssertionError(f"No ranked candidate list found in payload keys: {sorted(payload)}")


def test_product_maturity_radar_builds_repo_wide_surface_report(tmp_path: Path) -> None:
    _fixture_repo(tmp_path)

    payload = build_product_maturity_radar(tmp_path)

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["surface_count"] == 9
    assert payload["candidate_count"] >= 1
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False
    assert payload["rules"]["advisory_only"] is True
    assert payload["rules"]["repo_mutation"] is False
    assert payload["rules"]["review_first"] is True

    surfaces = {surface["name"]: surface for surface in payload["surfaces"]}
    assert set(surfaces) == {
        "adoption",
        "diagnosis",
        "docs",
        "evidence",
        "learning",
        "packaging",
        "remediation",
        "security_release",
        "workflow",
    }
    assert surfaces["adoption"]["indicators"]["real_world_matrix"] == "yes"
    assert surfaces["workflow"]["indicators"]["workflow_governance_report"] == "yes"
    assert surfaces["packaging"]["indicators"]["console_scripts"] == "yes"

    candidates = payload["ranked_upgrade_candidates"]
    assert candidates
    assert all(candidate["review_first"] is True for candidate in candidates)
    assert all(candidate["safe_to_patch"] is False for candidate in candidates)


def test_product_maturity_radar_writes_json_and_markdown(tmp_path: Path) -> None:
    _fixture_repo(tmp_path)
    out = tmp_path / "build" / "product-maturity-radar.json"

    payload = write_product_maturity_radar(repo_root=tmp_path, out=out)

    markdown = out.with_suffix(".md")
    assert out.is_file()
    assert markdown.is_file()
    assert json.loads(out.read_text(encoding="utf-8"))["schema_version"] == SCHEMA_VERSION
    assert "# SDETKit product maturity radar" in markdown.read_text(encoding="utf-8")
    assert payload["surface_count"] == 9


def test_product_maturity_radar_cli_dispatch(tmp_path: Path, capsys) -> None:
    _fixture_repo(tmp_path)
    out = tmp_path / "build" / "product-maturity-radar.json"

    from sdetkit.cli import main as cli_main

    rc = cli_main(
        [
            "product-maturity-radar",
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
    assert "# SDETKit product maturity radar" in stdout
    assert "repo_mutation: false" in stdout
    assert out.is_file()
    assert out.with_suffix(".md").is_file()


def test_product_maturity_radar_marks_review_first_unsafe_candidates_as_blocked(
    tmp_path: Path,
) -> None:
    _fixture_repo(tmp_path)

    payload = build_product_maturity_radar(tmp_path)
    workflow = next(
        candidate
        for candidate in _ranked_radar_candidates(payload)
        if candidate["classification"] == "workflow_governance_followup"
    )

    assert workflow["accepted_on_main"] is False
    assert workflow["review_first"] is True
    assert workflow["safe_to_patch"] is False
    assert workflow["ranking_status"] == "blocked_review_first_candidate"

    markdown = radar_module.render_product_maturity_radar_markdown(payload)
    assert "ranking_status: `blocked_review_first_candidate`" in markdown
    assert "blocked_by: `human_review_evidence_required`" in markdown


def test_product_maturity_radar_marks_accepted_candidates_from_git_history(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _fixture_repo(tmp_path)

    before = build_product_maturity_radar(tmp_path)
    candidate_title = before["ranked_upgrade_candidates"][0]["upgrade_candidate_title"]

    def fake_accepted_candidate_history(root: Path) -> set[str]:
        assert root == tmp_path.resolve()
        return {candidate_title.lower()}

    monkeypatch.setattr(
        "sdetkit.product_maturity_radar._accepted_candidate_history",
        fake_accepted_candidate_history,
    )

    payload = build_product_maturity_radar(tmp_path)
    accepted = [
        candidate
        for candidate in _ranked_radar_candidates(payload)
        if candidate.get("accepted_on_main") is True
    ]

    assert accepted
    assert accepted[0]["upgrade_candidate_title"] == candidate_title
    assert accepted[0]["ranking_status"] == "accepted_on_main"
    assert accepted[0]["ranking_score"] < before["ranked_upgrade_candidates"][0]["ranking_score"]
    assert all(candidate["safe_to_patch"] is False for candidate in accepted)


def test_product_maturity_radar_matches_accepted_candidate_title_drift() -> None:
    assert radar_module._candidate_accepted_on_main(
        "docs(product): refresh README and docs map for real-world learning lanes",
        {"docs(product): refresh real-world learning lanes"},
    )

    assert radar_module._candidate_accepted_on_main(
        "security: refresh anti-hijack and release threat model",
        {"security: add release anti-hijack threat model"},
    )

    assert radar_module._candidate_accepted_on_main(
        "feat(packaging): publish stable versus hidden command surface report",
        {"feat(packaging): add public command surface report"},
    )

    assert not radar_module._candidate_accepted_on_main(
        "ci: continue workflow hardening from governance report findings",
        {"ci: explain workflow permission findings"},
    )
