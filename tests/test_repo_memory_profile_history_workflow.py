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
