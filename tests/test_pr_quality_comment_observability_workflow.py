from __future__ import annotations

from pathlib import Path

WORKFLOW = Path(".github/workflows/pr-quality-comment.yml")


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_pr_quality_comment_workflow_has_queue_safe_concurrency_and_timeout() -> None:
    text = _workflow_text()

    assert "name: PR Quality Comment" in text
    assert "pull_request:" in text
    assert "concurrency:" in text
    assert "group: pr-quality-comment-${{ github.event.pull_request.number }}" in text
    assert "cancel-in-progress: true" in text
    assert "timeout-minutes: 20" in text


def test_pr_quality_comment_workflow_has_comment_permissions_without_repository_write() -> None:
    text = _workflow_text()
    permissions = text.split("jobs:", 1)[0]

    assert "contents: read" in permissions
    assert "contents: write" not in permissions
    assert "issues: write" in permissions
    assert "pull-requests: write" in permissions
    assert "checks: read" in permissions
    assert "actions: read" in permissions
    assert "security-events: read" in permissions


def test_pr_quality_comment_workflow_writes_comment_status_before_posting() -> None:
    text = _workflow_text()

    assert "Initialize PR comment status" in text
    assert "build/pr-quality/comment-status.json" in text
    assert '"status": "failed"' in text
    assert '"reason": "comment step did not complete"' in text


def test_pr_quality_comment_workflow_uploads_comment_artifacts() -> None:
    text = _workflow_text()

    assert "Upload PR quality comment artifacts" in text
    assert "build/pr-quality/pr-comment-body.md" in text
    assert "build/pr-quality/pr-comment-metadata.json" in text
    assert "build/pr-quality/pr-evidence-narrative.json" in text
    assert "build/pr-quality/changed-files.txt" in text
    assert "build/pr-quality/comment-status.json" in text
    assert "build/sdetkit/evidence-graph/" in text


def test_pr_quality_comment_workflow_updates_or_posts_comment_and_records_status() -> None:
    text = _workflow_text()
    publisher = text[
        text.index("- name: Comment on PR") : text.index(
            "- name: Verify PR Quality comment visibility"
        )
    ]

    assert "GH_TOKEN: ${{ github.token }}" in publisher
    assert "gh api" in publisher
    assert "--method PATCH" in publisher
    assert "--method POST" in publisher
    assert "issues/comments/${existing_id}" in publisher
    assert "issues/${PR_NUMBER}/comments" in publisher
    assert "actions/github-script@" not in publisher
    assert "comment_status=updated" in publisher
    assert "comment_status=posted" in publisher
    assert "posted SDET Quality Gate comment" in publisher
    assert "updated existing SDET Quality Gate comment" in publisher
    assert "readCommentMetadata" in publisher
    assert "action_report_status: metadata.status || 'unknown'" in publisher
    assert "comment_result_title: metadata.result_title || 'unknown'" in publisher
    assert "evidence_signal_kind: metadata.evidence_signal_kind || 'unknown'" in publisher
    assert "evidence_signal_present: Boolean(metadata.evidence_signal_present)" in publisher
    assert "evidence_review_required: Boolean(metadata.evidence_review_required)" in publisher


def test_pr_quality_comment_workflow_fails_loud_when_comment_not_visible() -> None:
    text = _workflow_text()

    assert "Verify PR Quality comment visibility" in text
    assert "if: always()" in text
    assert "comment_status=missing" in text
    assert 'status not in {"posted", "updated"}' in text
    assert "PR Quality comment was not posted or updated" in text


def test_pr_quality_comment_workflow_logs_final_comment_signal_state() -> None:
    text = _workflow_text()

    assert "action_report_status = str(payload.get(" in text
    assert "comment_result_title = str(payload.get(" in text
    assert "evidence_signal_kind = str(payload.get(" in text
    assert "evidence_signal_present = bool(payload.get(" in text
    assert "evidence_review_required = bool(payload.get(" in text
    assert 'print(f"action_report_status={action_report_status}")' in text
    assert 'print(f"comment_result_title={comment_result_title}")' in text
    assert 'print(f"evidence_signal_kind={evidence_signal_kind}")' in text
    assert 'print(f"evidence_signal_present={str(evidence_signal_present).lower()}")' in text
    assert 'print(f"evidence_review_required={str(evidence_review_required).lower()}")' in text


def test_pr_quality_comment_workflow_requires_final_comment_signal_metadata() -> None:
    text = _workflow_text()

    assert "PR Quality comment signal metadata missing: action_report_status=unknown" in text
    assert "PR Quality comment signal metadata missing: comment_result_title=unknown" in text
    assert 'evidence_signal_kind not in {"none", "proof", "review"}' in text
    assert "PR Quality comment signal metadata invalid: " in text


def test_pr_quality_comment_workflow_builds_check_intelligence_action_report() -> None:
    text = _workflow_text()

    assert "Build PR check intelligence action report" in text
    assert "check-runs?per_page=100" in text
    assert "build/pr-quality/checks/check-runs.json" in text
    assert "PR Quality local quality gate" in text
    assert "python -m sdetkit.check_intelligence" in text
    assert "--review-threads-json build/pr-quality/security-review/review-threads.json" in text
    assert "--out-dir build/pr-quality/check-intelligence" in text


def test_pr_quality_comment_workflow_renders_comment_from_action_report() -> None:
    text = _workflow_text()

    assert "python -m sdetkit.pr_quality_evidence_narrative" in text
    assert "--out build/pr-quality/pr-evidence-narrative.md" in text
    assert "--json-out build/pr-quality/pr-evidence-narrative.json" in text
    assert "python -m sdetkit.pr_quality_action_report" in text
    assert "--action-report build/pr-quality/check-intelligence/action-report.json" in text
    assert (
        "--check-intelligence build/pr-quality/check-intelligence/check-intelligence.json" in text
    )
    assert "--evidence-narrative build/pr-quality/pr-evidence-narrative.json" in text
    assert "--out build/pr-quality/pr-comment-body.md" in text
    assert "> build/pr-quality/pr-comment-metadata.json" in text


def test_pr_quality_comment_workflow_uploads_check_intelligence_artifacts() -> None:
    text = _workflow_text()

    assert "build/pr-quality/checks/" in text
    assert "build/pr-quality/check-intelligence/" in text
    assert "build/pr-quality/pr-evidence-narrative.md" in text


def test_pr_quality_comment_workflow_marks_required_contexts_for_check_intelligence() -> None:
    text = _workflow_text()

    assert "required_status_checks/contexts" in text
    assert "combined-status-raw.json" in text
    assert "required-contexts.json" in text
    assert '"required": context in required_contexts' in text
    assert 'item["required"] = name in required_contexts' in text


def test_pr_quality_comment_workflow_persists_required_contexts_for_missing_status_detection() -> (
    None
):
    text = _workflow_text()

    assert '"required_contexts": sorted(required_contexts)' in text
    assert "required-contexts.json" in text
    assert "combined-status-raw.json" in text


def test_pr_quality_comment_workflow_feeds_action_report_into_evidence_graph() -> None:
    text = _workflow_text()

    check_intelligence_step = text.index("Build PR check intelligence action report")
    graph_step = text.index("Build PR evidence graph")
    narrative_step = text.index("python -m sdetkit.pr_quality_evidence_narrative")

    assert check_intelligence_step < graph_step < narrative_step
    assert "python -m sdetkit.evidence_graph" in text
    assert (
        "--pr-quality-action-report build/pr-quality/check-intelligence/action-report.json" in text
    )
    assert (
        "--sentinel-control-room build/sdetkit/sentinel/control-room-with-security-review.json"
        in text
    )
    assert "--failure-bundle build/pr-quality/failure-intelligence/failure-bundle.json" in text


def test_pr_quality_comment_workflow_passes_evidence_narrative_into_final_comment() -> None:
    text = _workflow_text()

    narrative_step = text.index("python -m sdetkit.pr_quality_evidence_narrative")
    narrative_json = text.index("--json-out build/pr-quality/pr-evidence-narrative.json")
    action_report_step = text.index("python -m sdetkit.pr_quality_action_report")
    evidence_arg = text.index(
        "--evidence-narrative build/pr-quality/pr-evidence-narrative.json",
        action_report_step,
    )
    comment_out = text.index("--out build/pr-quality/pr-comment-body.md", action_report_step)

    assert narrative_step < narrative_json < action_report_step
    assert action_report_step < evidence_arg < comment_out


def test_pr_quality_workflow_does_not_execute_unverified_safe_formatting() -> None:
    text = _workflow_text()

    assert "Commit approved safe formatting fixes" not in text
    assert "--commit-safe-fixes" not in text
    assert "--pr-quality-safe-bridge-only" not in text
    assert "build/pr-quality/safe-formatting-autopilot/" not in text
    assert "python -m sdetkit.check_intelligence" in text
    assert "python -m sdetkit.pr_quality_action_report" in text


def test_pr_quality_workflow_keeps_repository_contents_read_only() -> None:
    text = _workflow_text()
    permissions = text.split("jobs:", 1)[0]

    assert "permissions:" in permissions
    assert "contents: read" in permissions
    assert "contents: write" not in permissions


def test_pr_quality_workflow_preserves_reporting_without_safe_fix_execution_artifacts() -> None:
    text = _workflow_text()

    assert "build/pr-quality/safe-formatting-autopilot/" not in text
    assert "Commit approved safe formatting fixes" not in text
    assert "Build PR comment body" in text
    assert "python -m sdetkit.check_intelligence" in text
    assert "python -m sdetkit.pr_quality_action_report" in text


def test_pr_quality_comment_workflow_builds_and_passes_trajectory_artifact() -> None:
    text = _workflow_text()

    check_intelligence = text.index("python -m sdetkit.check_intelligence")
    evidence_narrative = text.index("python -m sdetkit.pr_quality_evidence_narrative")
    trajectory = text.index("python -m sdetkit.trajectory_store")
    comment_body = text.index("python -m sdetkit.pr_quality_action_report")

    assert check_intelligence < evidence_narrative < trajectory < comment_body
    assert (
        "--pr-quality-action-report build/pr-quality/check-intelligence/action-report.json" in text
    )
    assert (
        "--check-intelligence build/pr-quality/check-intelligence/check-intelligence.json" in text
    )
    assert "--evidence-narrative build/pr-quality/pr-evidence-narrative.json" in text
    assert "--out build/pr-quality/trajectory/trajectory.jsonl" in text
    assert "> build/pr-quality/trajectory/trajectory-metadata.json" in text
    assert "--trajectory-jsonl build/pr-quality/trajectory/trajectory.jsonl" in text
    assert "build/pr-quality/trajectory/" in text


def test_pr_quality_comment_workflow_exposes_trajectory_comment_metadata() -> None:
    text = _workflow_text()

    assert "trajectory_signal_present: Boolean(metadata.trajectory_signal_present)" in text
    assert "trajectory_record_count: Number(metadata.trajectory_record_count || 0)" in text
    assert (
        "trajectory_review_first_count: Number(metadata.trajectory_review_first_count || 0)" in text
    )
    assert (
        "trajectory_auto_fix_allowed_count: Number(metadata.trajectory_auto_fix_allowed_count || 0)"
        in text
    )
    assert 'print(f"trajectory_record_count={trajectory_record_count}")' in text
    assert 'print(f"trajectory_review_first_count={trajectory_review_first_count}")' in text
    assert 'print(f"trajectory_auto_fix_allowed_count={trajectory_auto_fix_allowed_count}")' in text


def test_pr_quality_comment_workflow_collects_code_scanning_alert_visibility() -> None:
    text = _workflow_text()

    collection = text.index("Collect code scanning alert evidence")
    intelligence = text.index("Build PR check intelligence action report")

    assert collection < intelligence
    assert "security-events: read" in text.split("jobs:", 1)[0]
    assert "code-scanning/alerts?state=open&pr=$PR_NUMBER&per_page=100" in text
    assert '"collection_status": os.environ["COLLECTION_STATUS"]' in text
    assert "build/pr-quality/code-scanning/alerts.json" in text
    assert "--code-scanning-alerts-json build/pr-quality/code-scanning/alerts.json" in text
    assert '--current-head-sha "$HEAD_SHA"' in text
    assert "build/pr-quality/code-scanning/" in text


def test_pr_quality_comment_workflow_builds_current_pr_runtime_proof_artifact() -> None:
    text = _workflow_text()

    changed_files = text.index("> build/pr-quality/changed-files.txt")
    isolated_proof = text.index("python -m sdetkit.isolated_proof_runner")
    runtime_summary = text.index("python -m sdetkit.pr_quality_runtime_proof_artifacts")
    final_comment = text.index("python -m sdetkit.pr_quality_action_report")

    assert changed_files < isolated_proof < runtime_summary < final_comment
    assert "--inventory-mode base_head" in text
    assert '--base-ref "origin/${{ github.event.pull_request.base.ref }}"' in text
    assert "--profile ruff_src_tests" in text
    assert "--out-dir build/pr-quality/runtime-proof/isolated-proof" in text
    assert (
        "--isolated-proof build/pr-quality/runtime-proof/isolated-proof/verification-evidence.json"
        in text
    )
    assert "--out-dir build/pr-quality/runtime-proof/summary" in text
    assert (
        "--runtime-proof-artifacts build/pr-quality/runtime-proof/summary/runtime-proof-artifacts.json"
        in text
    )
    assert "build/pr-quality/runtime-proof/" in text


def test_pr_quality_comment_workflow_exposes_runtime_proof_metadata() -> None:
    text = _workflow_text()

    assert (
        "runtime_proof_artifacts_present: Boolean(metadata.runtime_proof_artifacts_present)" in text
    )
    assert (
        "runtime_proof_collection_status: metadata.runtime_proof_collection_status || 'not_collected'"
        in text
    )
    assert (
        "runtime_guard_violation_count: Number(metadata.runtime_guard_violation_count || 0)" in text
    )
    assert (
        'print(f"runtime_proof_artifacts_present={str(runtime_proof_artifacts_present).lower()}")'
        in text
    )
    assert 'print(f"runtime_proof_collection_status={runtime_proof_collection_status}")' in text
    assert 'print(f"runtime_guard_violation_count={runtime_guard_violation_count}")' in text


def test_pr_quality_comment_workflow_does_not_mask_quality_gate_failure_with_tee() -> None:
    text = _workflow_text()

    quality_step = text[
        text.index("- name: Run quality gate") : text.index(
            "- name: Build adaptive failure intelligence bundle"
        )
    ]

    quality_log = "/".join(("build", "pr-quality", "failure-intelligence", "quality.log"))

    assert "set -o pipefail" in quality_step
    assert f"bash quality.sh cov 2>&1 | tee {quality_log}" in quality_step
    assert "tee quality.log" not in quality_step


def test_pr_quality_comment_workflow_checks_out_history_for_runtime_proof_merge_base() -> None:
    text = _workflow_text()

    checkout = text[
        text.index("- uses: actions/checkout@") : text.index("- uses: actions/setup-python@")
    ]

    assert "fetch-depth: 0" in checkout
    assert "--inventory-mode base_head" in text
    assert '--base-ref "origin/${{ github.event.pull_request.base.ref }}"' in text


def test_pr_quality_comment_workflow_posts_runtime_diagnostic_before_failing_missing_collection() -> (
    None
):
    text = _workflow_text()

    build_comment = text[
        text.index("- name: Build PR comment body") : text.index(
            "- name: Build verified operator evidence loop"
        )
    ]
    verify_visibility = text[text.index("- name: Verify PR Quality comment visibility") :]

    assert "runtime_proof_rc=0" in build_comment
    assert "|| runtime_proof_rc=$?" in build_comment
    assert "isolated-proof-exit-code.txt" in build_comment
    assert (
        "test -s build/pr-quality/runtime-proof/isolated-proof/verification-evidence.json"
        not in build_comment
    )
    assert (
        "runtime proof artifact collection failed: isolated proof not collected"
        not in build_comment
    )

    assert "if not runtime_proof_artifacts_present:" in verify_visibility
    assert 'if runtime_proof_collection_status != "collected":' in verify_visibility
    assert "after diagnostic comment publication" in verify_visibility


def test_pr_quality_comment_workflow_builds_live_benchmark_and_repo_memory_artifacts() -> None:
    text = _workflow_text()

    workspace = text.index("python -m sdetkit.pr_quality_live_benchmark_workspace")
    live_benchmark = text.index("python -m sdetkit.replayable_benchmark_harness")
    trajectory = text.index("python -m sdetkit.trajectory_store")
    patterns = text.index("python -m sdetkit.trajectory_pattern_insights")
    memory = text.index("python -m sdetkit.repo_memory")
    runtime_summary = text.index("python -m sdetkit.pr_quality_runtime_proof_artifacts")
    action_report = text.index("python -m sdetkit.pr_quality_action_report")

    assert (
        workspace
        < live_benchmark
        < trajectory
        < patterns
        < memory
        < runtime_summary
        < action_report
    )
    assert "${RUNNER_TEMP}/sdetkit-pr-quality-live-benchmark-repositories" in text
    assert (
        "--live-benchmark-report build/pr-quality/live-benchmark/live-report/benchmark-report.json"
        in text
    )
    assert "--repo-memory-profile build/pr-quality/repo-memory/repo-memory-profile.json" in text
    assert "build/pr-quality/live-benchmark/" in text
    assert "build/pr-quality/repo-memory/" in text
    assert "build/pr-quality/trajectory-pattern-insights/" in text


def test_pr_quality_comment_workflow_requires_live_memory_visibility_after_posting() -> None:
    text = _workflow_text()
    verify_visibility = text[text.index("- name: Verify PR Quality comment visibility") :]

    assert "live_benchmark_collection_status" in verify_visibility
    assert 'if live_benchmark_collection_status != "collected":' in verify_visibility
    assert 'if live_benchmark_status != "passed":' in verify_visibility
    assert "live_benchmark_scenario_count != 6" in verify_visibility
    assert "anti_cheat_rejection_count != 2" in verify_visibility
    assert 'if repo_memory_collection_status != "collected":' in verify_visibility
    assert 'if repo_memory_status != "live_proof_supported_memory":' in verify_visibility
    assert "if not repo_memory_live_contract_proven:" in verify_visibility


def test_pr_quality_comment_workflow_exports_live_memory_metadata() -> None:
    text = _workflow_text()

    assert (
        "live_benchmark_collection_status: metadata.live_benchmark_collection_status || 'not_collected'"
        in text
    )
    assert "live_benchmark_status: metadata.live_benchmark_status || 'not_collected'" in text
    assert (
        "live_benchmark_scenario_count: Number(metadata.live_benchmark_scenario_count || 0)" in text
    )
    assert "anti_cheat_rejection_count: Number(metadata.anti_cheat_rejection_count || 0)" in text
    assert (
        "repo_memory_collection_status: metadata.repo_memory_collection_status || 'not_collected'"
        in text
    )
    assert "repo_memory_status: metadata.repo_memory_status || 'not_collected'" in text
    assert (
        "repo_memory_live_contract_proven: Boolean(metadata.repo_memory_live_contract_proven)"
        in text
    )


def test_pr_quality_comment_workflow_collects_trusted_main_history_from_accepted_base() -> None:
    text = _workflow_text()

    history_selection = text.index("actions/workflows/repo-memory-history.yml/runs")
    validator = text.index("python -m sdetkit.trusted_history_evidence")
    runtime_summary = text.index("python -m sdetkit.pr_quality_runtime_proof_artifacts")
    final_comment = text.index("python -m sdetkit.pr_quality_action_report")

    assert history_selection < validator < runtime_summary < final_comment
    assert "actions: read" in text.split("jobs:", 1)[0]
    assert "PR_BASE_SHA: ${{ github.event.pull_request.base.sha }}" in text
    assert "branch=main&event=push&status=completed" in text
    assert 'select(.conclusion == "success")' in text
    assert 'git merge-base --is-ancestor "$candidate_head_sha" "$PR_BASE_SHA"' in text
    assert 'gh run download "$trusted_history_run_id"' in text
    assert "--history-summary" in text
    assert "--history-jsonl" in text
    assert '--base-sha "$PR_BASE_SHA"' in text
    assert (
        "--trusted-history-evidence "
        "build/pr-quality/trusted-history/evidence/trusted-history-evidence.json" in text
    )
    assert "build/pr-quality/trusted-history/" in text


def test_pr_quality_comment_workflow_exports_trusted_history_visibility_metadata() -> None:
    text = _workflow_text()

    assert (
        "trusted_history_collection_status: "
        "metadata.trusted_history_collection_status || 'not_collected'" in text
    )
    assert "trusted_history_status: metadata.trusted_history_status || 'not_collected'" in text
    assert (
        "trusted_history_record_count: Number(metadata.trusted_history_record_count || 0)" in text
    )
    assert (
        "trusted_history_base_ancestry_verified: "
        "Boolean(metadata.trusted_history_base_ancestry_verified)" in text
    )
    assert (
        "trusted_history_prior_input_read_only: "
        "Boolean(metadata.trusted_history_prior_input_read_only)" in text
    )
    assert (
        "trusted_history_automation_allowed: Boolean(metadata.trusted_history_automation_allowed)"
        in text
    )
    assert (
        "trusted_history_merge_authorized: Boolean(metadata.trusted_history_merge_authorized)"
        in text
    )
    assert (
        "trusted_history_semantic_equivalence_proven: "
        "Boolean(metadata.trusted_history_semantic_equivalence_proven)" in text
    )


def test_pr_quality_comment_workflow_requires_trusted_history_visibility_after_posting() -> None:
    text = _workflow_text()
    verify_visibility = text[text.index("- name: Verify PR Quality comment visibility") :]

    assert 'if trusted_history_collection_status != "collected":' in verify_visibility
    assert 'if trusted_history_status != "trusted_history_verified":' in verify_visibility
    assert "if trusted_history_record_count < 1:" in verify_visibility
    assert "if not trusted_history_base_ancestry_verified:" in verify_visibility
    assert "if not trusted_history_prior_input_read_only:" in verify_visibility
    assert "if trusted_history_automation_allowed:" in verify_visibility
    assert "if trusted_history_merge_authorized:" in verify_visibility
    assert "if trusted_history_semantic_equivalence_proven:" in verify_visibility
    assert "after diagnostic comment publication" in verify_visibility


def test_pr_quality_workflow_publishes_read_only_candidate_verification_visibility() -> None:
    text = _workflow_text()

    candidate_step = text.index("python -m sdetkit.pr_quality_candidate_visibility")
    report_step = text.index("python -m sdetkit.pr_quality_action_report")
    append_step = text.index("cat build/pr-quality/candidate-visibility/candidate-visibility.md")

    assert candidate_step < report_step < append_step
    assert (
        "--check-intelligence build/pr-quality/check-intelligence/check-intelligence.json" in text
    )
    assert "--evidence-graph build/sdetkit/evidence-graph/evidence-graph.json" in text
    assert "--changed-files build/pr-quality/changed-files.txt" in text
    assert (
        "--pattern-insights build/pr-quality/trajectory-pattern-insights/pattern-insights.json"
        in text
    )
    assert (
        "--verification-evidence build/pr-quality/runtime-proof/isolated-proof/verification-evidence.json"
        in text
    )
    assert "build/pr-quality/candidate-visibility/" in text
    assert "--commit-safe-fixes" not in text
    assert "--pr-quality-safe-bridge-only" not in text


def test_pr_quality_workflow_captures_required_pre_commit_candidate_proof() -> None:
    text = _workflow_text()

    assert "--profile ruff_src_tests" in text
    assert "--profile pre_commit_all" in text
    assert (
        "--verification-evidence build/pr-quality/runtime-proof/isolated-proof/verification-evidence.json"
        in text
    )
    assert "--commit-safe-fixes" not in text
    assert "--pr-quality-safe-bridge-only" not in text


def test_pr_quality_workflow_appends_controlled_candidate_validation_only_after_decision_render() -> (
    None
):
    text = _workflow_text()

    action_report = text.index("python -m sdetkit.pr_quality_action_report")
    validation = text.index("python -m sdetkit.pr_quality_candidate_validation")
    validation_append = text.index(
        "cat build/pr-quality/candidate-validation/candidate-validation.md"
    )
    action_report_command = text[
        action_report : text.index("> build/pr-quality/pr-comment-metadata.json", action_report)
    ]

    assert action_report < validation < validation_append
    assert "candidate-validation" not in action_report_command
    assert (
        "--scenario tests/fixtures/pr_quality_candidate_visibility/formatting_candidate_verified.json"
        in text
    )
    assert (
        "--scenario tests/fixtures/pr_quality_candidate_visibility/broader_diff_review_first.json"
        in text
    )
    assert "build/pr-quality/candidate-validation/" in text
    assert "--commit-safe-fixes" not in text
    assert "--pr-quality-safe-bridge-only" not in text


def test_pr_quality_workflow_runs_local_diagnostic_job_as_post_decision_read_only_evidence() -> (
    None
):
    text = _workflow_text()

    action_report = text.index("python -m sdetkit.pr_quality_action_report")
    job = text.index("python -m sdetkit.diagnostic_job")
    job_append = text.index("cat build/pr-quality/diagnostic-job/diagnostic-job.md")
    action_report_command = text[
        action_report : text.index("> build/pr-quality/pr-comment-metadata.json", action_report)
    ]

    assert action_report < job < job_append
    assert "diagnostic-job" not in action_report_command
    assert (
        "--check-intelligence build/pr-quality/check-intelligence/check-intelligence.json" in text
    )
    assert "--evidence-graph build/sdetkit/evidence-graph/evidence-graph.json" in text
    assert (
        "--pr-quality-action-report build/pr-quality/check-intelligence/action-report.json" in text
    )
    assert (
        "--security-review build/pr-quality/security-diagnosis/security-finding-diagnosis.json"
        in text
    )
    assert '--base-sha "$PR_BASE_SHA"' in text
    assert '--head-sha "$HEAD_SHA"' in text
    assert "build/pr-quality/diagnostic-job/" in text
    assert "--commit-safe-fixes" not in text
    assert "--pr-quality-safe-bridge-only" not in text


def test_pr_quality_workflow_keeps_failed_diagnostic_job_advisory_and_visible() -> None:
    text = _workflow_text()
    build_comment = text[
        text.index("- name: Build PR comment body") : text.index(
            "- name: Build verified operator evidence loop"
        )
    ]

    assert "diagnostic_job_rc=0" in build_comment
    assert "|| diagnostic_job_rc=$?" in build_comment
    assert "diagnostic-job-exit-code.txt" in build_comment
    assert 'if [ "$diagnostic_job_rc" -ne 0 ]' in build_comment
    assert "Status: `collection_failed`" in build_comment
    assert "Current PR decision input: `false`" in build_comment
    assert "Patch application allowed: `false`" in build_comment
    assert "Automation allowed: `false`" in build_comment
    assert "Merge authorized: `false`" in build_comment
    assert "base PR decision and report remain authoritative" in build_comment


def test_pr_quality_workflow_records_diagnostic_worker_trajectory_as_post_decision_advisory_only() -> (
    None
):
    text = _workflow_text()

    pattern_insights = text.index("python -m sdetkit.trajectory_pattern_insights")
    repo_memory = text.index("python -m sdetkit.repo_memory")
    action_report = text.index("python -m sdetkit.pr_quality_action_report")
    diagnostic_job = text.index("python -m sdetkit.diagnostic_job")
    trajectory = text.index("python -m sdetkit.diagnostic_worker_trajectory")
    trajectory_append = text.index(
        "cat build/pr-quality/diagnostic-job/trajectory/diagnostic-worker-trajectory.md"
    )
    action_report_command = text[
        action_report : text.index("> build/pr-quality/pr-comment-metadata.json", action_report)
    ]
    repo_memory_command = text[
        repo_memory : text.index("> build/pr-quality/repo-memory/repo-memory-cli.json", repo_memory)
    ]

    assert (
        pattern_insights
        < repo_memory
        < action_report
        < diagnostic_job
        < trajectory
        < trajectory_append
    )
    assert "diagnostic-worker-trajectory" not in action_report_command
    assert "diagnostic-worker-trajectory" not in repo_memory_command
    assert "--diagnostic-job build/pr-quality/diagnostic-job/diagnostic-job.json" in text
    assert (
        "--diagnostic-worker-result build/pr-quality/diagnostic-job/diagnostic-worker-result.json"
        in text
    )
    assert (
        "--diagnostic-vector build/pr-quality/diagnostic-job/vector/diagnostic-vector.json" in text
    )
    assert "build/pr-quality/diagnostic-job/trajectory/" in text
    assert "--commit-safe-fixes" not in text
    assert "--pr-quality-safe-bridge-only" not in text


def test_pr_quality_workflow_keeps_failed_diagnostic_worker_trajectory_visible_and_non_authorizing() -> (
    None
):
    text = _workflow_text()
    build_comment = text[
        text.index("- name: Build PR comment body") : text.index(
            "- name: Build verified operator evidence loop"
        )
    ]

    assert "diagnostic_worker_trajectory_rc=2" in build_comment
    assert "|| diagnostic_worker_trajectory_rc=$?" in build_comment
    assert "diagnostic-worker-trajectory-exit-code.txt" in build_comment
    assert "Local diagnostic worker trajectory handoff" in build_comment
    assert "post_decision_reporting_only_trajectory" in build_comment
    assert "Status: `collection_failed`" in build_comment
    assert "Reporting only: `true`" in build_comment
    assert "Current PR decision input: `false`" in build_comment
    assert "Patch application allowed: `false`" in build_comment
    assert "Automation allowed: `false`" in build_comment
    assert "Merge authorized: `false`" in build_comment
    assert "current-run candidate decisions and RepoMemory remain unchanged" in build_comment


def test_pr_quality_diagnostic_job_consumes_runtime_guard_summary_after_primary_decision_render() -> (
    None
):
    text = _workflow_text()

    action_report = text.index("python -m sdetkit.pr_quality_action_report")
    diagnostic_job = text.index("python -m sdetkit.diagnostic_job")
    diagnostic_job_command = text[
        diagnostic_job : text.index(
            "> build/pr-quality/diagnostic-job/diagnostic-job-cli.json", diagnostic_job
        )
    ]
    action_report_command = text[
        action_report : text.index("> build/pr-quality/pr-comment-metadata.json", action_report)
    ]

    assert action_report < diagnostic_job
    assert (
        "--runtime-proof-artifacts build/pr-quality/runtime-proof/summary/runtime-proof-artifacts.json"
        in diagnostic_job_command
    )
    assert (
        "--runtime-proof-artifacts build/pr-quality/runtime-proof/summary/runtime-proof-artifacts.json"
        in action_report_command
    )
    assert "--commit-safe-fixes" not in text
    assert "--pr-quality-safe-bridge-only" not in text


def test_pr_quality_workflow_runs_runtime_guard_worker_benchmark_as_non_decision_evidence() -> None:
    text = _workflow_text()
    scenario_marker = (
        "--diagnostic-worker-scenario tests/fixtures/remediation_benchmark/"
        "runtime_guard_worker_oracle.json"
    )
    marker_location = text.index(scenario_marker)
    step_start = text.rfind("\n      - name:", 0, marker_location) + 1
    step_end = text.find("\n      - name:", marker_location)
    if step_end < 0:
        step_end = len(text)
    benchmark_step = text[step_start:step_end]

    assert "- name: Build PR comment body diagnostic appendices" in benchmark_step
    assert benchmark_step.count(scenario_marker) == 1
    assert "runtime_guard_worker_nop.json" in benchmark_step
    assert "runtime_guard_worker_unsafe.json" in benchmark_step

    benchmark_command_start = benchmark_step.rfind(
        "python -m sdetkit.replayable_benchmark_harness",
        0,
        benchmark_step.index(scenario_marker),
    )
    assert benchmark_command_start >= 0

    repo_memory = text.index("python -m sdetkit.repo_memory")
    candidate_validation = step_start + benchmark_step.index(
        "python -m sdetkit.pr_quality_candidate_validation"
    )
    benchmark_command_start += step_start
    benchmark_append = step_start + benchmark_step.index(
        "cat build/pr-quality/runtime-guard-benchmark/benchmark-report.md"
    )

    assert repo_memory < candidate_validation < benchmark_command_start < benchmark_append


def test_pr_quality_workflow_runs_security_freshness_benchmark_as_non_decision_evidence() -> None:
    text = _workflow_text()
    marker = (
        "--security-freshness-scenario tests/fixtures/remediation_benchmark/"
        "security_freshness_stale_runtime_oracle.json"
    )
    marker_location = text.index(marker)
    step_start = text.rfind("\n      - name:", 0, marker_location) + 1
    step_end = text.find("\n      - name:", marker_location)
    if step_end < 0:
        step_end = len(text)
    benchmark_step = text[step_start:step_end]

    assert "- name: Build PR comment body diagnostic appendices" in benchmark_step
    assert "security_freshness_current_primary_oracle.json" in benchmark_step
    assert "security_freshness_authority_unsafe.json" in benchmark_step

    marker_in_step = benchmark_step.index(marker)
    security_command = benchmark_step.rfind(
        "python -m sdetkit.replayable_benchmark_harness",
        0,
        marker_in_step,
    )
    runtime_command = benchmark_step.rfind(
        "python -m sdetkit.replayable_benchmark_harness",
        0,
        security_command,
    )
    assert runtime_command >= 0
    assert security_command >= 0

    runtime_append = benchmark_step.index(
        "cat build/pr-quality/runtime-guard-benchmark/benchmark-report.md"
    )
    security_append = benchmark_step.index(
        "cat build/pr-quality/security-freshness-benchmark/benchmark-report.md"
    )

    assert runtime_command < security_command < runtime_append < security_append
    assert "python -m sdetkit.repo_memory" not in benchmark_step
    assert "python -m sdetkit.pr_quality_action_report" not in benchmark_step
    assert "--commit-safe-fixes" not in text
    assert "--pr-quality-safe-bridge-only" not in text


def test_pr_quality_workflow_renders_diagnostic_signal_snapshot_after_worker_as_reporting_only() -> (
    None
):
    text = _workflow_text()
    build_comment = text[
        text.index("- name: Build PR comment body") : text.index(
            "- name: Build verified operator evidence loop"
        )
    ]

    repo_memory = build_comment.index("python -m sdetkit.repo_memory")
    action_report = build_comment.index("python -m sdetkit.pr_quality_action_report")
    diagnostic_job = build_comment.index("python -m sdetkit.diagnostic_job")
    trajectory = build_comment.index("python -m sdetkit.diagnostic_worker_trajectory")
    snapshot = build_comment.index("python -m sdetkit.diagnostic_signal_snapshot")
    candidate_validation = build_comment.index("python -m sdetkit.pr_quality_candidate_validation")
    snapshot_append = build_comment.index(
        "cat build/pr-quality/diagnostic-signal-snapshot/diagnostic-signal-snapshot.md"
    )
    repo_memory_command = build_comment[
        repo_memory : build_comment.index(
            "> build/pr-quality/repo-memory/repo-memory-cli.json", repo_memory
        )
    ]
    action_report_command = build_comment[
        action_report : build_comment.index(
            "> build/pr-quality/pr-comment-metadata.json", action_report
        )
    ]

    assert (
        repo_memory < action_report < diagnostic_job < trajectory < snapshot < candidate_validation
    )
    assert snapshot < snapshot_append
    assert "diagnostic-signal-snapshot" not in repo_memory_command
    assert "diagnostic-signal-snapshot" not in action_report_command
    assert (
        "--diagnostic-worker-result build/pr-quality/diagnostic-job/diagnostic-worker-result.json"
        in build_comment
    )
    assert "Diagnostic signal KPI snapshot" in build_comment
    assert "current_pr_reporting_only_snapshot" in build_comment
    assert "Current PR decision input: `false`" in build_comment
    assert "Feeds RepoMemory: `false`" in build_comment
    assert "Automation allowed: `false`" in build_comment
    assert "Merge authorized: `false`" in build_comment
    assert "--commit-safe-fixes" not in text
    assert "--pr-quality-safe-bridge-only" not in text


def test_pr_quality_workflow_appends_trusted_diagnostic_snapshot_history_post_decision_only() -> (
    None
):
    text = _workflow_text()
    comment_builder = text[
        text.index("- name: Build PR comment body") : text.index(
            "- name: Build trusted diagnostic signal snapshot history visibility"
        )
    ]
    trusted_visibility = text[
        text.index(
            "- name: Build trusted diagnostic signal snapshot history visibility"
        ) : text.index("- name: Build verified operator evidence loop")
    ]

    repo_memory = comment_builder.index("python -m sdetkit.repo_memory")
    action_report = comment_builder.index("python -m sdetkit.pr_quality_action_report")
    current_snapshot = comment_builder.index("python -m sdetkit.diagnostic_signal_snapshot")
    candidate_validation = comment_builder.index(
        "python -m sdetkit.pr_quality_candidate_validation"
    )
    repo_memory_command = comment_builder[
        repo_memory : comment_builder.index(
            "> build/pr-quality/repo-memory/repo-memory-cli.json", repo_memory
        )
    ]
    action_report_command = comment_builder[
        action_report : comment_builder.index(
            "> build/pr-quality/pr-comment-metadata.json", action_report
        )
    ]

    assert action_report < current_snapshot < candidate_validation
    assert "python -m sdetkit.trusted_diagnostic_signal_snapshot_history" in trusted_visibility
    assert "trusted-diagnostic-signal-snapshot-history" not in repo_memory_command
    assert "trusted-diagnostic-signal-snapshot-history" not in action_report_command
    assert '--selected-retention-run-id "$trusted_snapshot_history_run_id"' in trusted_visibility
    assert '--selected-head-sha "$trusted_snapshot_history_head_sha"' in trusted_visibility
    assert 'body = body.replace(snapshot, f"{snapshot}\\n\\n{history}", 1)' in trusted_visibility
    assert "Advisor false-positive rate status: `requires_reviewed_history`" in trusted_visibility
    assert "Current PR decision input: `false`" in trusted_visibility
    assert "Feeds RepoMemory: `false`" in trusted_visibility
    assert "Historical snapshot authorizes current action: `false`" in trusted_visibility


def test_pr_quality_workflow_uploads_trusted_diagnostic_snapshot_history_artifact() -> None:
    text = _workflow_text()

    assert "build/pr-quality/trusted-diagnostic-signal-snapshot-history/" in text
    assert "python -m sdetkit.trusted_diagnostic_signal_snapshot_history" in text
    assert "--commit-safe-fixes" not in text
    assert "--pr-quality-safe-bridge-only" not in text


def test_pr_quality_snapshot_history_allows_bootstrap_absence_but_fails_invalid_present_history() -> (
    None
):
    text = _workflow_text()
    trusted_visibility = text[
        text.index(
            "- name: Build trusted diagnostic signal snapshot history visibility"
        ) : text.index("- name: Build verified operator evidence loop")
    ]
    verify_visibility = text[text.index("- name: Verify PR Quality comment visibility") :]

    history_file_count = "_".join(("trusted", "snapshot", "history", "file", "count"))
    assert f"{history_file_count}=0" in trusted_visibility
    assert f'if [ "${history_file_count}" -eq 0 ]; then' in trusted_visibility
    assert f'elif [ "${history_file_count}" -ne 2 ]' in trusted_visibility
    history_rc = "_".join(("trusted", "diagnostic", "signal", "snapshot", "history", "rc"))
    assert f"|| {history_rc}=3" in trusted_visibility
    assert "Collection status: `not_collected`" in trusted_visibility
    assert "Collection status: `collection_failed`" in trusted_visibility
    assert "failed validation or is incomplete" in trusted_visibility
    guard_name = "_".join(("trusted", "snapshot", "history", "exit", "code"))
    assert f'{guard_name} not in {{"0", "2"}}' in verify_visibility
    assert "validation failed after " in verify_visibility
    assert "diagnostic comment publication" in verify_visibility


def test_pr_quality_snapshot_history_falls_back_to_latest_ancestor_artifact_with_stream() -> None:
    text = _workflow_text()
    trusted_visibility = text[
        text.index(
            "- name: Build trusted diagnostic signal snapshot history visibility"
        ) : text.index("- name: Build verified operator evidence loop")
    ]

    assert "sdetkit-trusted-diagnostic-snapshot-history" in trusted_visibility
    assert "build/pr-quality/trusted-history/successful-main-runs.tsv" in trusted_visibility
    assert 'if [ "$candidate_file_count" -eq 0 ]; then' in trusted_visibility
    assert 'trusted_snapshot_history_run_id="$candidate_run_id"' in trusted_visibility
    assert '--selected-retention-run-id "$trusted_snapshot_history_run_id"' in trusted_visibility
    assert '--selected-head-sha "$trusted_snapshot_history_head_sha"' in trusted_visibility


def test_pr_quality_builds_trusted_snapshot_history_for_runtime_and_visibility() -> None:
    text = _workflow_text()
    comment_builder = text[
        text.index("- name: Build PR comment body") : text.index(
            "- name: Build trusted diagnostic signal snapshot history visibility"
        )
    ]
    trusted_visibility = text[
        text.index(
            "- name: Build trusted diagnostic signal snapshot history visibility"
        ) : text.index("- name: Build verified operator evidence loop")
    ]

    assert "python -m sdetkit.diagnostic_signal_snapshot" in comment_builder
    assert "python -m sdetkit.pr_quality_candidate_validation" in comment_builder
    assert "runtime_guard_worker_oracle.json" in comment_builder
    assert "security_freshness_stale_runtime_oracle.json" in comment_builder

    runtime_summary = comment_builder.index("python -m sdetkit.pr_quality_runtime_proof_artifacts")
    early_trusted_history = comment_builder.index(
        "python -m sdetkit.trusted_diagnostic_signal_snapshot_history"
    )
    runtime_command = comment_builder[
        runtime_summary : comment_builder.index(
            "> build/pr-quality/runtime-proof/summary-metadata.json", runtime_summary
        )
    ]

    assert early_trusted_history < runtime_summary
    assert "--trusted-diagnostic-signal-snapshot-history" in runtime_command
    assert (
        "build/pr-quality/trusted-diagnostic-signal-snapshot-history/"
        "trusted-diagnostic-signal-snapshot-history.json"
    ) in runtime_command
    assert "python -m sdetkit.trusted_diagnostic_signal_snapshot_history" in trusted_visibility
    assert "trusted-diagnostic-signal-snapshot-history.md" in trusted_visibility
    assert 'body = body.replace(snapshot, f"{snapshot}\\n\\n{history}", 1)' in trusted_visibility


def test_pr_quality_comment_avoids_untrusted_head_ref_expression_in_run_blocks() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    lines = text.splitlines()
    direct_expression = "${{ github.event.pull_request.head.ref }}"
    offending_run_lines: list[int] = []

    for index, line in enumerate(lines):
        if line.strip() != "run: |":
            continue

        run_indent = len(line) - len(line.lstrip())
        block: list[str] = []
        for block_line in lines[index + 1 :]:
            stripped = block_line.strip()
            block_indent = len(block_line) - len(block_line.lstrip())
            if stripped and block_indent <= run_indent:
                break
            block.append(block_line)

        if direct_expression in "\n".join(block):
            offending_run_lines.append(index + 1)

    assert not offending_run_lines, (
        "PR Quality Comment must pass untrusted pull_request.head.ref through "
        f"an environment variable before inline scripts: {offending_run_lines}"
    )


def test_pr_quality_comment_workflow_run_blocks_stay_below_registration_limit() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    lines = text.splitlines()
    max_chars = 24_000
    oversized: list[tuple[int, int]] = []

    for index, line in enumerate(lines):
        if line.strip() != "run: |":
            continue

        run_indent = len(line) - len(line.lstrip())
        block: list[str] = []
        for block_line in lines[index + 1 :]:
            stripped = block_line.strip()
            block_indent = len(block_line) - len(block_line.lstrip())
            if stripped and block_indent <= run_indent:
                break
            block.append(block_line)

        size = len("\n".join(block))
        if size > max_chars:
            oversized.append((index + 1, size))

    assert not oversized, (
        "PR Quality Comment run blocks must stay small enough for GitHub "
        f"workflow registration: {oversized}"
    )


def test_pr_quality_prefers_final_trusted_diagnostic_snapshot_history_output_files() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert (
        "-path '*/diagnostic-signal-snapshots/output/"
        "diagnostic-signal-snapshot-history-summary.json'"
    ) in text
    assert (
        "-path '*/diagnostic-signal-snapshots/output/diagnostic-signal-snapshot-history.jsonl'"
    ) in text
    assert text.count("diagnostic-signal-snapshots/output/") >= 4
    assert text.count("-name diagnostic-signal-snapshot-history-summary.json") >= 2
    assert text.count("-name diagnostic-signal-snapshot-history.jsonl") >= 2
