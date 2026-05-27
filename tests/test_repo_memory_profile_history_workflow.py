from __future__ import annotations

from pathlib import Path

WORKFLOW = Path(".github/workflows/repo-memory-history.yml")


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_repo_memory_history_runs_only_from_trusted_main_pushes() -> None:
    text = _workflow_text()

    assert "name: RepoMemory Profile History" in text
    assert "push:" in text
    assert "branches: [main]" in text
    assert "pull_request:" not in text
    assert "workflow_run:" not in text
    assert "contents: read" in text
    assert "actions: read" in text
    assert "contents: write" not in text
    assert "pull-requests: write" not in text


def test_repo_memory_history_builds_fresh_live_profile_from_merged_code() -> None:
    text = _workflow_text()

    workspace = text.index("python -m sdetkit.pr_quality_live_benchmark_workspace")
    live_report = text.index("python -m sdetkit.replayable_benchmark_harness")
    producer = text.index("python -m sdetkit.trusted_flaky_test_registry_producer")
    profile = text.index("python -m sdetkit.repo_memory")
    history = text.index("python -m sdetkit.repo_memory_profile_history")

    assert workspace < live_report < producer < profile < history
    assert "${RUNNER_TEMP}/sdetkit-repo-memory-history-live-repositories" in text
    assert (
        "--live-benchmark-report build/repo-memory-history/live-report/benchmark-report.json"
        in text
    )
    assert 'assert profile["inputs"]["live_contract_proven"] is True' in text
    assert 'assert boundary["automation_allowed"] is False' in text
    assert 'assert boundary["merge_authorized"] is False' in text
    assert 'assert boundary["semantic_equivalence_proven"] is False' in text
    assert '--source-run-id "${GITHUB_RUN_ID}"' in text
    assert '--source-head-sha "${GITHUB_SHA}"' in text
    assert (
        "--flaky-test-registry-evidence build/repo-memory-history/flaky-test-registry/flaky-test-registry-evidence.json"
        in text
    )
    assert 'assert flaky["entry_count"] == 0' in text
    assert (
        'assert flaky["source"]["observation_status"] == "no_test_observations_available"' in text
    )
    assert 'assert flaky["source"]["observations_collected"] is False' in text


def test_repo_memory_history_imports_only_successful_ancestor_main_history() -> None:
    text = _workflow_text()

    assert "Select prior trusted main history artifact" in text
    assert (
        "actions/workflows/repo-memory-history.yml/runs?branch=main&event=push&status=completed"
        in text
    )
    assert 'select(.conclusion == "success")' in text
    assert 'git merge-base --is-ancestor "$candidate_head_sha" "$GITHUB_SHA"' in text
    assert 'gh run download "$prior_run_id"' in text
    assert "--prior-history-jsonl" in text
    assert "Prior trusted-main run was selected but supplied no history JSONL artifact." in text


def test_repo_memory_history_uploads_snapshot_without_repository_mutation() -> None:
    text = _workflow_text()

    assert "Upload trusted main RepoMemory history artifact" in text
    assert "name: repo-memory-profile-history" in text
    assert "build/repo-memory-history/output/" in text
    assert "build/repo-memory-history/flaky-test-registry/" in text
    assert "repo-memory-profile-history.jsonl" in text
    assert "git add " not in text
    assert "git commit " not in text
    assert "git push " not in text
    assert "create-pull-request" not in text


def test_repo_memory_history_verifies_no_authority_boundary() -> None:
    text = _workflow_text()

    assert 'assert summary["latest_record"]["live_contract_proven"] is True' in text
    assert 'assert boundary["automation_allowed"] is False' in text
    assert 'assert boundary["merge_authorized"] is False' in text
    assert 'assert boundary["semantic_equivalence_proven"] is False' in text
    assert 'assert boundary["prior_history_is_read_only_input"] is True' in text


def test_repo_memory_history_never_uses_example_flake_history_as_trusted_evidence() -> None:
    text = _workflow_text()

    assert "python -m sdetkit.trusted_flaky_test_registry_producer" in text
    assert "examples/kits/intelligence/flake-history.json" not in text
    assert "python -m sdetkit intelligence flake classify" not in text


def test_repo_memory_history_collects_pr_scoped_reviewed_security_dispositions_read_only() -> None:
    text = _workflow_text()

    assert "pull-requests: read" in text
    assert "security-events: read" in text
    assert "Collect accepted-main reviewed security disposition inputs" in text
    assert "commits/${GITHUB_SHA}/pulls?per_page=10" in text
    assert "code-scanning/alerts?state=dismissed&pr=$pr_number&per_page=100" in text
    assert "python -m sdetkit.security_reviewed_disposition_history" in text
    assert (
        "--associated-pr-json build/repo-memory-history/security-reviewed-dispositions/associated-merged-pr.json"
        in text
    )
    assert (
        "--dismissed-alerts-json build/repo-memory-history/security-reviewed-dispositions/dismissed-alerts.json"
        in text
    )
    assert "--prior-history-jsonl" in text
    assert "security-reviewed-disposition-history.jsonl" in text
    assert "build/repo-memory-history/security-reviewed-dispositions/" in text


def test_repo_memory_history_disposition_lane_never_writes_security_actions() -> None:
    text = _workflow_text()

    assert 'assert boundary["historical_disposition_authorizes_current_action"] is False' in text
    assert 'assert boundary["automatic_security_fix_allowed"] is False' in text
    assert 'assert boundary["automatic_dismissal_allowed"] is False' in text
    assert "PATCH /repos/" not in text
    assert "updateAlert" not in text
    assert "dismissed_comment" not in text


def test_repo_memory_history_filters_dismissed_security_evidence_to_merged_pr_changed_paths() -> (
    None
):
    text = _workflow_text()
    assert "pulls/$pr_number/files?per_page=100" in text
    assert "changed-files.json" in text
    assert (
        "--changed-files-json build/repo-memory-history/security-reviewed-dispositions/changed-files.json"
        in text
    )
    assert (
        'assert summary["latest_record"]["pr_scope_verification"] == "changed_paths_proven"' in text
    )
    assert 'assert summary["latest_record"]["alerts_excluded_outside_changed_paths"] >= 0' in text
    assert "gh api --paginate" in text


def test_repo_memory_history_retains_controlled_candidate_validation_as_read_only_profile_evidence() -> (
    None
):
    text = _workflow_text()

    validation = text.index("python -m sdetkit.pr_quality_candidate_validation")
    profile = text.index("python -m sdetkit.repo_memory")

    assert validation < profile
    assert (
        "--scenario tests/fixtures/pr_quality_candidate_visibility/formatting_candidate_verified.json"
        in text
    )
    assert (
        "--scenario tests/fixtures/pr_quality_candidate_visibility/broader_diff_review_first.json"
        in text
    )
    assert (
        "--controlled-candidate-validation-evidence build/repo-memory-history/candidate-validation/candidate-validation.json"
        in text
    )
    assert 'assert controlled["status"] == "controlled_validation_passed"' in text
    assert 'assert controlled["current_pr_decision_input"] is False' in text
    assert 'assert controlled["decision_boundary"]["automation_allowed"] is False' in text
    assert 'assert controlled["decision_boundary"]["merge_authorized"] is False' in text
    assert "build/repo-memory-history/candidate-validation/" in text
    assert "contents: write" not in text.split("jobs:", 1)[0]
    assert "git push " not in text


def test_repo_memory_history_promotes_controlled_validation_as_advisory_counts_only() -> None:
    text = _workflow_text()

    assert 'assert summary["controlled_validation_record_count"] >= 1' in text
    assert 'assert summary["controlled_validation_scenario_count"] >= 2' in text
    assert 'assert summary["controlled_structurally_verified_count"] >= 1' in text
    assert 'assert summary["controlled_review_first_count"] >= 1' in text
    assert (
        'assert summary["latest_record"]["controlled_validation_status"] == "controlled_validation_passed"'
        in text
    )
    assert (
        'assert summary["latest_record"]["controlled_current_pr_decision_input"] is False' in text
    )
    assert 'assert boundary["controlled_validation_is_advisory_only"] is True' in text
    assert "contents: write" not in text.split("jobs:", 1)[0]
    assert "git push " not in text
