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
    assert "Collect accepted-main observation recovery queue" in text
    assert "commits/$accepted_main_sha/pulls?per_page=10" in text
    assert "code-scanning/alerts?state=dismissed&pr=$source_pr_number&per_page=100" in text
    assert "python -m sdetkit.security_reviewed_disposition_history" in text
    assert '--associated-pr-json "$source_dir/associated-merged-pr.json"' in text
    assert (
        '--dismissed-alerts-json "$source_dir/security-reviewed-dispositions/dismissed-alerts.json"'
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
    assert "pulls/$source_pr_number/files?per_page=100" in text
    assert "changed-files.json" in text
    assert (
        '--changed-files-json "$source_dir/security-reviewed-dispositions/changed-files.json"'
        in text
    )
    assert (
        'assert summary["latest_record"]["pr_scope_verification"] == "changed_paths_proven"' in text
    )
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


def test_repo_memory_history_retains_diagnostic_snapshot_as_parallel_advisory_history() -> None:
    text = _workflow_text()

    source = text.index("Collect accepted-main observation recovery queue")
    producer = text.index("python -m sdetkit.diagnostic_signal_snapshot_history")
    security_history = text.index("python -m sdetkit.security_reviewed_disposition_history")
    repo_memory = text.index("python -m sdetkit.repo_memory")
    repo_memory_command = text[
        repo_memory : text.index("> build/repo-memory-history/profile-cli.json", repo_memory)
    ]

    assert source < producer < security_history
    assert (
        "actions/workflows/pr-quality-comment.yml/runs?event=pull_request&status=completed" in text
    )
    assert 'select(.conclusion == "success")' in text
    assert "--name pr-quality-comment" in text
    assert "diagnostic-signal-snapshot.json" in text
    assert "--prior-history-jsonl" in text
    assert "prior_diagnostic_signal_snapshot_jsonl" in text
    assert (
        'assert summary["advisor_false_positive_rate_status"] == "requires_reviewed_history"'
        in text
    )
    assert 'assert boundary["current_pr_decision_input"] is False' in text
    assert 'assert boundary["feeds_repo_memory"] is False' in text
    assert 'assert boundary["automation_allowed"] is False' in text
    assert 'assert boundary["merge_authorized"] is False' in text
    assert "build/repo-memory-history/diagnostic-signal-snapshots/" in text
    assert "diagnostic-signal-snapshot" not in repo_memory_command


def test_repo_memory_history_snapshot_retention_remains_read_only_and_non_mutating() -> None:
    text = _workflow_text()

    assert "python -m sdetkit.diagnostic_signal_snapshot_history" in text
    assert "--source-run-conclusion success" in text
    assert '--retention-run-id "${GITHUB_RUN_ID}:$accepted_main_sha"' in text
    assert '--accepted-main-sha "$accepted_main_sha"' in text
    assert 'assert boundary["patch_application_allowed"] is False' in text
    assert 'assert boundary["semantic_equivalence_proven"] is False' in text
    assert 'assert boundary["historical_snapshot_authorizes_current_action"] is False' in text
    assert "contents: write" not in text.split("jobs:", 1)[0]
    assert "git push " not in text


def test_repo_memory_history_binds_snapshot_source_run_to_verified_merge_head_with_safe_empty_metadata_fallback() -> (
    None
):
    text = _workflow_text()

    assert 'source_head_sha="$(' in text
    assert '(.pull_requests | map(.number | tostring) | join(","))' in text
    assert "bound_source_run_ids" in text
    assert "fallback_source_run_ids" in text
    assert "contradictory_pr_metadata_seen=false" in text
    assert "contradictory_pr_metadata_seen=true" in text
    assert "validate_candidate_artifact" in text
    assert "-name diagnostic-job.json" in text
    assert '"event_name": "pull_request"' in text
    assert '"pr_number": int(os.environ["SOURCE_PR_NUMBER"])' in text
    assert '"head_sha": os.environ["SOURCE_HEAD_SHA"]' in text
    assert '"repo": os.environ["REPOSITORY"]' in text
    assert "pr_number_metadata_and_artifact" in text
    assert "verified_merged_pr_exact_head_artifact_fallback" in text
    assert "No PR Quality artifact proved verified merged PR" in text
    assert 'if [ -z "$candidate_pr_numbers" ]; then' in text
    assert 'case ",${candidate_pr_numbers}," in' in text


def test_repo_memory_history_snapshot_retention_does_not_fail_non_pr_main_push() -> None:
    text = _workflow_text()

    assert 'source_match_count="$(' in text
    assert 'if [ "$source_match_count" -eq 0 ]; then' in text
    assert 'echo "source_available=false" >> "$GITHUB_OUTPUT"' in text
    assert (
        "No merged PR maps to accepted-main head; no diagnostic snapshot observation will be appended."
        in text
    )
    assert "if: steps.accepted-main-sources.outputs.source_available == 'true'" in text
    assert "sdetkit-prior-diagnostic-snapshot-history" in text
    assert "-name diagnostic-signal-snapshot-history.jsonl" in text


def test_repo_memory_history_recovers_snapshot_enabled_failed_ancestor_main_runs_before_current_head() -> (
    None
):
    text = _workflow_text()

    assert "failed-main-runs-oldest-first.tsv" in text
    assert 'select(.conclusion == "failure")' in text
    assert 'git merge-base --is-ancestor "$failed_head_sha" "${GITHUB_SHA}"' in text
    assert 'collect_source "$failed_head_sha" "recovered_failed_ancestor" "$failed_run_id"' in text
    assert 'collect_source "${GITHUB_SHA}" "current_head" "${GITHUB_RUN_ID}"' in text
    assert "expected_shas.issubset(retained_shas)" in text
    assert "if current_rows:" in text
    assert (
        'assert summary["latest_record"]["accepted_main_sha"] == os.environ["GITHUB_SHA"]' in text
    )


def test_repo_memory_history_recovers_reviewed_security_history_with_deterministic_accepted_main_identity() -> (
    None
):
    text = _workflow_text()

    assert '--source-run-id "accepted-main:$accepted_main_sha"' in text
    assert '--source-head-sha "$accepted_main_sha"' in text
    assert "expected_shas.issubset(retained_shas)" in text
    assert 'assert boundary["historical_disposition_authorizes_current_action"] is False' in text
    assert 'assert boundary["automatic_security_fix_allowed"] is False' in text
    assert 'assert boundary["automatic_dismissal_allowed"] is False' in text
    assert 'assert boundary["automation_allowed"] is False' in text
    assert 'assert boundary["merge_authorized"] is False' in text


def test_repo_memory_history_selects_exact_head_full_ci_observation_artifact() -> None:
    text = _workflow_text()

    selection = text.index("Select trusted-main test observation artifact")
    prior = text.index("Select prior trusted main history artifact")

    assert selection < prior
    assert "actions/workflows/ci.yml/runs?branch=main&event=push&status=completed" in text
    assert 'select(.conclusion == "success")' in text
    assert '[ "$candidate_head_sha" != "${GITHUB_SHA}" ]' in text
    assert '.name == "trusted-test-observations"' in text
    assert ".expired == false" in text
    assert 'if [ "$candidate_artifact_count" -gt 1 ]; then' in text
    assert "refusing ambiguous provenance" in text
    assert 'gh run download "$selected_run_id"' in text
    assert "--name trusted-test-observations" in text
    assert "-name trusted-test-observations.json" in text
    assert 'source["workflow"] == "CI"' in text
    assert 'source["job"] == "Full CI lane"' in text
    assert 'source["head_sha"] == os.environ["GITHUB_SHA"]' in text
    assert 'source["event_name"] == "push"' in text
    assert 'source["ref_name"] == "refs/heads/main"' in text
    assert 'source["trusted_main"] is True' in text
    assert 'source["input_read_only"] is True' in text
    assert 'source["commands_executed_by_reader"] is False' in text
    assert "for attempt in $(seq 1 20)" in text
    assert "sleep 15" in text


def test_repo_memory_history_recovers_optional_prior_test_observation_history() -> None:
    text = _workflow_text()

    assert 'echo "prior_test_observation_history_jsonl="' in text
    assert "-name trusted-test-observation-history.jsonl" in text
    assert (
        'echo "prior_test_observation_history_jsonl=$prior_test_observation_history_jsonl"' in text
    )
    assert "Prior trusted-main run was selected but supplied no history JSONL artifact." in text


def test_repo_memory_history_records_and_uploads_raw_observation_history() -> None:
    text = _workflow_text()

    selection = text.index("Select trusted-main test observation artifact")
    prior = text.index("Select prior trusted main history artifact")
    record = text.index("Record trusted main test observation history")
    upload = text.index("Upload trusted main RepoMemory history artifact")

    assert selection < prior < record < upload
    assert "OBSERVATION_REPORT: ${{ steps.test-observations.outputs.observation_report }}" in text
    assert "OBSERVATION_SOURCE_RUN_ID: ${{ steps.test-observations.outputs.source_run_id }}" in text
    assert (
        "PRIOR_TEST_OBSERVATION_HISTORY_JSONL: "
        "${{ steps.prior.outputs.prior_test_observation_history_jsonl }}" in text
    )
    assert "python -m sdetkit.trusted_test_observation_history" in text
    assert '--observation-report "$OBSERVATION_REPORT"' in text
    assert '--source-run-id "$OBSERVATION_SOURCE_RUN_ID"' in text
    assert '--source-head-sha "$OBSERVATION_SOURCE_HEAD_SHA"' in text
    assert '--prior-history-jsonl "$PRIOR_TEST_OBSERVATION_HISTORY_JSONL"' in text
    assert "build/repo-memory-history/test-observation-history/" in text
    assert 'summary["flaky_classification_performed"] is False' in text
    assert 'summary["current_pr_decision_input"] is False' in text
    assert 'boundary["automatic_quarantine_allowed"] is False' in text
    assert 'boundary["automatic_rerun_allowed"] is False' in text
    assert 'boundary["current_failure_suppression_allowed"] is False' in text
    assert 'boundary["automation_allowed"] is False' in text
    assert 'boundary["patch_application_allowed"] is False' in text
    assert 'boundary["merge_authorized"] is False' in text
    assert 'boundary["semantic_equivalence_proven"] is False' in text
    assert "python -m sdetkit intelligence flake classify" not in text
    assert "gh run rerun" not in text
    assert "rerun-failed-jobs" not in text
    assert "--quarantine" not in text.lower()
    assert "quarantine-test" not in text.lower()
    assert "pytest.mark.quarantine" not in text.lower()
