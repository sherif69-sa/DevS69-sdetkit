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
    assert workflow["blocked_by"] == "human_review_evidence_required"
    assert workflow["blocker_source_report"] == "sdetkit.workflow_governance_report"
    assert workflow["blocker_playbook"] == "docs/ci/workflow-permission-review-playbook.md"
    assert workflow["next_allowed_action"] == "collect_human_review_evidence"

    summary = radar_module._operator_summary([workflow])
    assert summary["next_action"] == "collect_human_review_evidence"
    assert summary["top_candidate"] == workflow["upgrade_candidate_title"]
    assert summary["top_candidate_classification"] == "workflow_governance_followup"
    assert summary["top_candidate_ranking_status"] == "blocked_review_first_candidate"
    assert summary["blocked_by"] == "human_review_evidence_required"
    assert summary["blocker_source_report"] == "sdetkit.workflow_governance_report"
    assert summary["blocker_playbook"] == "docs/ci/workflow-permission-review-playbook.md"
    assert "reviewer decision" in workflow["required_evidence"]
    assert "automatic_permission_reduction" in workflow["blocked_actions"]
    assert "semantic_equivalence_claim" in workflow["blocked_actions"]

    payload_actionability = payload["actionability_summary"]
    assert payload_actionability["patch_ready_candidate_count"] == 0
    assert payload_actionability["blocked_review_first_candidate_count"] >= 1
    assert payload_actionability["has_patch_ready_candidate"] is False

    actionability = radar_module._actionability_summary([workflow])
    assert actionability["status"] == "blocked_review_first_candidate"
    assert actionability["patch_ready_candidate_count"] == 0
    assert actionability["blocked_review_first_candidate_count"] == 1
    assert actionability["accepted_on_main_candidate_count"] == 0
    assert actionability["has_patch_ready_candidate"] is False
    assert actionability["next_allowed_action"] == "collect_human_review_evidence"
    assert actionability["automation_allowed"] is False
    assert actionability["patch_application_allowed"] is False
    assert actionability["merge_authorized"] is False
    assert actionability["semantic_equivalence_proven"] is False

    single_candidate_payload = {
        **payload,
        "ranked_upgrade_candidates": [workflow],
        "candidate_count": 1,
        "actionability_summary": actionability,
        "operator_summary": radar_module._operator_summary([workflow]),
    }
    markdown = radar_module.render_product_maturity_radar_markdown(single_candidate_payload)
    assert "## Actionability summary" in markdown
    assert "patch_ready_candidate_count: `0`" in markdown
    assert "blocked_review_first_candidate_count: `1`" in markdown
    assert "next_allowed_action: `collect_human_review_evidence`" in markdown
    assert "ranking_status: `blocked_review_first_candidate`" in markdown
    assert "blocked_by: `human_review_evidence_required`" in markdown
    assert "next_allowed_action: `collect_human_review_evidence`" in markdown
    assert "blocker_source_report: `sdetkit.workflow_governance_report`" in markdown
    assert "blocker_playbook: `docs/ci/workflow-permission-review-playbook.md`" in markdown


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


def _dependency_report_payload(
    *,
    schema_version: str,
    head: str,
    input_digest: str = "a" * 64,
) -> dict:
    return {
        "schema_version": schema_version,
        "current_head_sha": head,
        "input_provenance": {
            "digest_algorithm": "sha256",
            "input_digest": input_digest,
            "input_count": 1,
            "generator_schema_version": schema_version,
            "generator_source": "fixture.py",
            "generator_sha256": "b" * 64,
            "generated_at": "2026-06-23T00:00:00Z",
            "generated_from_head_sha": head,
            "source_issue_count": 0,
            "source_issue_numbers": [],
            "source_run_ids": [],
            "input_digests": {"fixture": "c" * 64},
            "input_artifact_schemas": {},
        },
        "source_issue_numbers": [],
        "source_run_ids": [],
        "automation_allowed": False,
        "patch_application_allowed": False,
        "security_dismissal_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }


def _write_dependency_reports(
    root: Path,
    *,
    stale_dependency: str = "",
) -> list[str]:
    overrides: list[str] = []
    head, _ = radar_module._resolve_radar_head(root)
    for dependency_id, spec in radar_module.REPORT_DEPENDENCY_SPECS.items():
        path = root / str(spec["path"])
        dependency_head = "f" * 40 if dependency_id == stale_dependency else head
        payload = _dependency_report_payload(
            schema_version=str(spec["schema_version"]),
            head=dependency_head,
        )
        _write(path, json.dumps(payload))
        overrides.append(f"{dependency_id}={path}")
    return overrides


def test_product_maturity_radar_v2_is_partial_without_dependency_reports(
    tmp_path: Path,
) -> None:
    _fixture_repo(tmp_path)
    payload = build_product_maturity_radar(tmp_path)

    assert payload["schema_version"].endswith(".v2")
    assert payload["projection_status"] == "partial"
    assert payload["projection_only"] is True
    assert payload["source_authority"] is False
    assert payload["dependency_status"]["missing_dependency_count"] == len(
        radar_module.REPORT_DEPENDENCY_SPECS
    )
    assert payload["dependency_status"]["valid_for_projection"] is True
    assert len(payload["current_head_sha"]) == 40
    assert len(payload["input_provenance"]["input_digest"]) == 64
    assert set(payload["claim_sources"]) == {
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
    assert all("claim_sources" in surface for surface in payload["surfaces"])
    assert all("claim_sources" in candidate for candidate in payload["ranked_upgrade_candidates"])


def test_product_maturity_radar_accepts_current_report_dependencies(
    tmp_path: Path,
) -> None:
    _fixture_repo(tmp_path)
    overrides = _write_dependency_reports(tmp_path)
    payload = build_product_maturity_radar(
        tmp_path,
        report_json=overrides,
        generated_at="2026-06-23T00:00:00Z",
    )

    assert payload["projection_status"] == "current"
    assert payload["dependency_status"]["fresh_dependency_count"] == len(
        radar_module.REPORT_DEPENDENCY_SPECS
    )
    assert payload["dependency_status"]["missing_dependency_count"] == 0
    assert payload["dependency_status"]["stale_dependency_count"] == 0
    assert payload["dependency_status"]["invalid_dependency_count"] == 0
    assert all(dependency["status"] == "fresh" for dependency in payload["report_dependencies"])


def test_product_maturity_radar_invalidates_stale_dependency(
    tmp_path: Path,
) -> None:
    _fixture_repo(tmp_path)
    overrides = _write_dependency_reports(
        tmp_path,
        stale_dependency="workflow_governance",
    )
    payload = build_product_maturity_radar(tmp_path, report_json=overrides)

    assert payload["projection_status"] == "invalid"
    assert payload["report_status"] == "invalid_dependency"
    workflow = next(
        dependency
        for dependency in payload["report_dependencies"]
        if dependency["id"] == "workflow_governance"
    )
    assert workflow["status"] == "stale"
    assert "dependency_head_mismatch" in workflow["reasons"]


def test_product_maturity_radar_freshness_detects_dependency_mutation(
    tmp_path: Path,
) -> None:
    _fixture_repo(tmp_path)
    overrides = _write_dependency_reports(tmp_path)
    out = tmp_path / "radar.json"

    write_product_maturity_radar(
        repo_root=tmp_path,
        out=out,
        report_json=overrides,
        generated_at="2026-06-23T00:00:00Z",
    )
    fresh = radar_module.check_product_maturity_radar_freshness(
        repo_root=tmp_path,
        report_path=out,
        report_json=overrides,
    )
    assert fresh["fresh"] is True
    assert fresh["projection_status"] == "current"

    dependency_path = tmp_path / str(
        radar_module.REPORT_DEPENDENCY_SPECS["automation_health"]["path"]
    )
    dependency = json.loads(dependency_path.read_text(encoding="utf-8"))
    dependency["mutation_probe"] = True
    dependency_path.write_text(json.dumps(dependency), encoding="utf-8")

    stale = radar_module.check_product_maturity_radar_freshness(
        repo_root=tmp_path,
        report_path=out,
        report_json=overrides,
    )
    assert stale["fresh"] is False
    assert "input_digest_mismatch" in stale["reasons"]


def test_product_maturity_radar_cli_freshness_and_report_overrides(
    tmp_path: Path,
    capsys,
) -> None:
    _fixture_repo(tmp_path)
    overrides = _write_dependency_reports(tmp_path)
    out = tmp_path / "radar.json"

    from sdetkit.cli import main as cli_main

    args = [
        "product-maturity-radar",
        "--root",
        str(tmp_path),
        "--out",
        str(out),
    ]
    for override in overrides:
        args.extend(["--report-json", override])

    assert cli_main([*args, "--format", "json"]) == 0
    generated = json.loads(capsys.readouterr().out)
    assert generated["projection_status"] == "current"

    original = out.read_text(encoding="utf-8")
    assert cli_main([*args, "--check-freshness", "--format", "text"]) == 0
    stdout = capsys.readouterr().out
    assert "freshness_status=fresh" in stdout
    assert "projection_status=current" in stdout
    assert out.read_text(encoding="utf-8") == original
