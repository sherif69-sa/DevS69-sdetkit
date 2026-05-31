from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from sdetkit.diagnostic_signal_snapshot_history import (
    RATE_STATUS,
    build_history_record,
    build_history_summary,
    merge_history_records,
    write_history_jsonl,
)
from sdetkit.trusted_diagnostic_signal_snapshot_history import (
    COLLECTED,
    TRUSTED_HISTORY_VERIFIED,
    build_trusted_snapshot_history_evidence,
    main,
    render_markdown,
    verify_base_ancestry,
)


def _run(*args: str, cwd: Path) -> str:
    completed = subprocess.run(
        list(args),
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _git_repo(tmp_path: Path) -> tuple[Path, str, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _run("git", "init", cwd=repo)
    _run("git", "config", "user.email", "snapshot-history@example.test", cwd=repo)
    _run("git", "config", "user.name", "Snapshot History Test", cwd=repo)
    (repo / "state.txt").write_text("first\n", encoding="utf-8")
    _run("git", "add", "state.txt", cwd=repo)
    _run("git", "commit", "-m", "first", cwd=repo)
    first = _run("git", "rev-parse", "HEAD", cwd=repo)
    (repo / "state.txt").write_text("second\n", encoding="utf-8")
    _run("git", "add", "state.txt", cwd=repo)
    _run("git", "commit", "-m", "second", cwd=repo)
    second = _run("git", "rev-parse", "HEAD", cwd=repo)
    return repo, first, second


def _snapshot() -> dict:
    return {
        "schema_version": "sdetkit.diagnostic.signal.snapshot.v1",
        "status": "quiet_green_advisory_baseline",
        "snapshot_type": "current_pr_reporting_only",
        "quiet_green_advisory_baseline": True,
        "measurements": {
            "primary_signal_kind": "review_signal",
            "review_signal_present": True,
            "integration_proof_signal_present": False,
            "evidence_graph_node_count": 0,
            "diagnostic_worker_diagnosis_count": 0,
            "runtime_guard_violation_count": 0,
            "current_security_finding_count": 0,
        },
        "kpi_readiness": {
            "advisor_false_positive_rate_status": RATE_STATUS,
            "reviewed_false_positive_count": None,
            "reviewed_observation_count": None,
        },
        "decision_boundary": {
            "reporting_only": True,
            "current_pr_decision_input": False,
            "feeds_repo_memory": False,
            "proof_commands_executed": False,
            "patch_application_allowed": False,
            "automation_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        },
    }


def _artifact(tmp_path: Path, *, accepted_head: str) -> tuple[Path, Path, dict, dict]:
    record = build_history_record(
        _snapshot(),
        associated_pr_payload=[
            {
                "number": 1456,
                "merged_at": "2026-05-28T09:33:53Z",
                "merge_commit_sha": accepted_head,
                "head": {"sha": "pr-head-1"},
            }
        ],
        source_run_id="quality-run-1",
        source_run_conclusion="success",
        source_head_sha="pr-head-1",
        retention_run_id="retention-run-1",
        accepted_main_sha=accepted_head,
        recorded_at_utc="2026-05-28T10:00:00Z",
    )
    history_path = write_history_jsonl([record], out_dir=tmp_path)
    summary = build_history_summary(
        [record],
        appended=True,
        history_path=history_path,
        prior_history_collected=False,
        prior_record_count=0,
    )
    summary_path = tmp_path / "diagnostic-signal-snapshot-history-summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary_path, history_path, summary, record


def test_trusted_history_accepts_verified_ancestor_snapshot_history(tmp_path: Path) -> None:
    _repo, accepted_head, base_head = _git_repo(tmp_path)
    _summary_path, _history_path, summary, record = _artifact(
        tmp_path / "artifact",
        accepted_head=accepted_head,
    )

    evidence = build_trusted_snapshot_history_evidence(
        summary=summary,
        records=[record],
        selected_retention_run_id="retention-run-1",
        selected_head_sha=accepted_head,
        base_sha=base_head,
        base_ancestry_verified=True,
    )

    assert evidence["collection_status"] == COLLECTED
    assert evidence["status"] == TRUSTED_HISTORY_VERIFIED
    assert evidence["history"]["record_count"] == 1
    assert evidence["history"]["review_signal_record_count"] == 1
    assert evidence["history"]["advisor_false_positive_rate_status"] == RATE_STATUS
    assert evidence["decision_boundary"]["feeds_repo_memory"] is False
    assert evidence["decision_boundary"]["automation_allowed"] is False


def test_trusted_history_accepts_composite_retention_run_id_from_retention_artifact(
    tmp_path: Path,
) -> None:
    _repo, accepted_head, base_head = _git_repo(tmp_path)
    _summary_path, _history_path, summary, record = _artifact(
        tmp_path / "artifact",
        accepted_head=accepted_head,
    )
    composite_retention_run_id = f"retention-run-1:{accepted_head}"
    record["source"]["retention_run_id"] = composite_retention_run_id
    summary["latest_record"]["retention_run_id"] = composite_retention_run_id

    evidence = build_trusted_snapshot_history_evidence(
        summary=summary,
        records=[record],
        selected_retention_run_id="retention-run-1",
        selected_head_sha=accepted_head,
        base_sha=base_head,
        base_ancestry_verified=True,
    )

    assert evidence["status"] == TRUSTED_HISTORY_VERIFIED
    assert evidence["source"]["run_id"] == "retention-run-1"
    assert evidence["source"]["head_sha"] == accepted_head


def test_trusted_history_git_verifier_rejects_nonancestor_head(tmp_path: Path) -> None:
    repo, first, second = _git_repo(tmp_path)

    with pytest.raises(ValueError, match="not an ancestor"):
        verify_base_ancestry(repo_root=repo, selected_head_sha=second, base_sha=first)


def test_trusted_history_rejects_summary_totals_that_do_not_match_records(tmp_path: Path) -> None:
    _repo, accepted_head, base_head = _git_repo(tmp_path)
    _summary_path, _history_path, summary, record = _artifact(
        tmp_path / "artifact",
        accepted_head=accepted_head,
    )
    summary["review_signal_record_count"] = 99

    with pytest.raises(ValueError, match="signal totals do not match records"):
        build_trusted_snapshot_history_evidence(
            summary=summary,
            records=[record],
            selected_retention_run_id="retention-run-1",
            selected_head_sha=accepted_head,
            base_sha=base_head,
            base_ancestry_verified=True,
        )


def test_trusted_history_rejects_summary_that_expands_authority(tmp_path: Path) -> None:
    _repo, accepted_head, base_head = _git_repo(tmp_path)
    _summary_path, _history_path, summary, record = _artifact(
        tmp_path / "artifact",
        accepted_head=accepted_head,
    )
    summary["decision_boundary"]["feeds_repo_memory"] = True

    with pytest.raises(ValueError, match="no-authority boundary"):
        build_trusted_snapshot_history_evidence(
            summary=summary,
            records=[record],
            selected_retention_run_id="retention-run-1",
            selected_head_sha=accepted_head,
            base_sha=base_head,
            base_ancestry_verified=True,
        )


def test_trusted_history_cli_writes_reporting_only_evidence(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo, accepted_head, base_head = _git_repo(tmp_path)
    summary_path, history_path, _summary, _record = _artifact(
        tmp_path / "artifact",
        accepted_head=accepted_head,
    )
    out_dir = tmp_path / "out"

    rc = main(
        [
            "--history-summary",
            str(summary_path),
            "--history-jsonl",
            str(history_path),
            "--repo-root",
            str(repo),
            "--selected-retention-run-id",
            "retention-run-1",
            "--selected-head-sha",
            accepted_head,
            "--base-sha",
            base_head,
            "--out-dir",
            str(out_dir),
            "--format",
            "json",
        ]
    )

    assert rc == 0
    stdout = capsys.readouterr().out
    saved = json.loads(
        (out_dir / "trusted-diagnostic-signal-snapshot-history.json").read_text(encoding="utf-8")
    )
    markdown = (out_dir / "trusted-diagnostic-signal-snapshot-history.md").read_text(
        encoding="utf-8"
    )

    assert stdout == ""
    assert saved["collection_status"] == COLLECTED
    assert saved["status"] == TRUSTED_HISTORY_VERIFIED
    assert saved["decision_boundary"]["current_pr_decision_input"] is False
    assert saved["decision_boundary"]["feeds_repo_memory"] is False
    assert "Advisor false-positive rate status: `requires_reviewed_history`" in markdown
    assert "Historical snapshot authorizes current action: `false`" in markdown


def test_trusted_history_markdown_keeps_history_advisory(tmp_path: Path) -> None:
    _repo, accepted_head, base_head = _git_repo(tmp_path)
    _summary_path, _history_path, summary, record = _artifact(
        tmp_path / "artifact",
        accepted_head=accepted_head,
    )
    evidence = build_trusted_snapshot_history_evidence(
        summary=summary,
        records=[record],
        selected_retention_run_id="retention-run-1",
        selected_head_sha=accepted_head,
        base_sha=base_head,
        base_ancestry_verified=True,
    )

    markdown = render_markdown(evidence)

    assert (
        "Accepted-main snapshot history shows advisory signal availability only".lower()
        in markdown.lower()
    )
    assert "Current PR decision input: `false`" in markdown
    assert "Feeds RepoMemory: `false`" in markdown
    assert "Prior history is read-only input: `true`" in markdown
    assert "Proof commands executed: `false`" in markdown
    assert "Patch application allowed: `false`" in markdown
    assert "Automation allowed: `false`" in markdown
    assert "Merge authorized: `false`" in markdown
    assert "Semantic equivalence proven: `false`" in markdown


def test_trusted_history_accepts_artifact_republished_by_retention_rerun(tmp_path: Path) -> None:
    _repo, accepted_head, base_head = _git_repo(tmp_path)
    associated_pr = [
        {
            "number": 1456,
            "merged_at": "2026-05-28T09:33:53Z",
            "merge_commit_sha": accepted_head,
            "head": {"sha": "pr-head-1"},
        }
    ]
    first = build_history_record(
        _snapshot(),
        associated_pr_payload=associated_pr,
        source_run_id="quality-run-1",
        source_run_conclusion="success",
        source_head_sha="pr-head-1",
        retention_run_id="retention-run-1",
        accepted_main_sha=accepted_head,
    )
    rerun = build_history_record(
        _snapshot(),
        associated_pr_payload=associated_pr,
        source_run_id="quality-run-1",
        source_run_conclusion="success",
        source_head_sha="pr-head-1",
        retention_run_id="retention-run-rerun",
        accepted_main_sha=accepted_head,
    )
    records, appended = merge_history_records([first], rerun)
    history_path = write_history_jsonl(records, out_dir=tmp_path / "artifact-rerun")
    summary = build_history_summary(
        records,
        appended=appended,
        history_path=history_path,
        prior_history_collected=True,
        prior_record_count=1,
    )

    evidence = build_trusted_snapshot_history_evidence(
        summary=summary,
        records=records,
        selected_retention_run_id="retention-run-rerun",
        selected_head_sha=accepted_head,
        base_sha=base_head,
        base_ancestry_verified=True,
    )

    assert appended is False
    assert evidence["status"] == TRUSTED_HISTORY_VERIFIED
    assert evidence["history"]["record_count"] == 1
    assert evidence["source"]["run_id"] == "retention-run-rerun"
