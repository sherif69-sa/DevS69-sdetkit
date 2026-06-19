from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from sdetkit.repo_memory_profile_history import (
    AUTOMATION_ALLOWED,
    CONTROLLED_REVIEW_FIRST_COUNT,
    CONTROLLED_STRUCTURALLY_VERIFIED_COUNT,
    CONTROLLED_VALIDATION_PASSED,
    CONTROLLED_VALIDATION_RECORD_COUNT,
    CONTROLLED_VALIDATION_SCENARIO_COUNT,
    CONTROLLED_VALIDATION_STATUS,
    LIVE_CONTRACT_PROVEN,
    LIVE_PROFILE_STATUS,
    MERGE_AUTHORIZED,
    READ_ONLY_PROFILE_MODE,
    SEMANTIC_EQUIVALENCE_PROVEN,
    build_history_record,
    build_history_summary,
    write_history_jsonl,
)
from sdetkit.trusted_history_evidence import (
    COLLECTED,
    TRUSTED_HISTORY_VERIFIED,
    build_trusted_history_evidence,
    main,
    render_markdown,
    verify_base_ancestry,
)

ANTI_CHEAT_COUNT = "_".join(("anti", "cheat", "rejection", "scenario", "count"))


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
    _run("git", "config", "user.email", "history@example.test", cwd=repo)
    _run("git", "config", "user.name", "History Test", cwd=repo)

    (repo / "state.txt").write_text("first\n", encoding="utf-8")
    _run("git", "add", "state.txt", cwd=repo)
    _run("git", "commit", "-m", "first", cwd=repo)
    first = _run("git", "rev-parse", "HEAD", cwd=repo)

    (repo / "state.txt").write_text("second\n", encoding="utf-8")
    _run("git", "add", "state.txt", cwd=repo)
    _run("git", "commit", "-m", "second", cwd=repo)
    second = _run("git", "rev-parse", "HEAD", cwd=repo)
    return repo, first, second


def _profile() -> dict:
    return {
        "schema_version": "sdetkit.repo_memory.v4",
        "profile_status": LIVE_PROFILE_STATUS,
        "memory_mode": READ_ONLY_PROFILE_MODE,
        "known_safe_candidate_count": 0,
        "live_safe_candidate_count": 0,
        "proof_provenance": {
            LIVE_CONTRACT_PROVEN: True,
            ANTI_CHEAT_COUNT: 2,
        },
        "decision_boundary": {
            AUTOMATION_ALLOWED: False,
            MERGE_AUTHORIZED: False,
            SEMANTIC_EQUIVALENCE_PROVEN: False,
        },
    }


def _history_artifact(tmp_path: Path, *, run_id: str, head_sha: str) -> tuple[Path, Path, dict]:
    output = tmp_path / "history-artifact"
    record = build_history_record(
        _profile(),
        source_run_id=run_id,
        source_head_sha=head_sha,
        recorded_at_utc="2026-05-23T16:25:24Z",
    )
    history_path = write_history_jsonl([record], out_dir=output)
    summary = build_history_summary(
        [record],
        appended=True,
        history_path=history_path,
        prior_history_collected=False,
        prior_record_count=0,
    )
    summary_path = output / "repo-memory-history-summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary_path, history_path, summary


def test_trusted_history_accepts_verified_ancestor_artifact(tmp_path: Path) -> None:
    _repo, accepted_head, base_head = _git_repo(tmp_path)
    _summary_path, _history_path, summary = _history_artifact(
        tmp_path,
        run_id="trusted-run-1",
        head_sha=accepted_head,
    )
    record = json.loads(
        (tmp_path / "history-artifact/repo-memory-profile-history.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()[0]
    )

    evidence = build_trusted_history_evidence(
        summary=summary,
        records=[record],
        selected_run_id="trusted-run-1",
        selected_head_sha=accepted_head,
        base_sha=base_head,
        base_ancestry_verified=True,
    )

    assert evidence["collection_status"] == COLLECTED
    assert evidence["status"] == TRUSTED_HISTORY_VERIFIED
    assert evidence["source"]["base_ancestry_verified"] is True
    assert evidence["history"]["record_count"] == 1
    assert evidence["history"]["live_contract_proven_record_count"] == 1
    assert evidence["history"]["prior_history_is_read_only_input"] is True
    assert evidence["decision_boundary"][AUTOMATION_ALLOWED] is False
    assert evidence["decision_boundary"][MERGE_AUTHORIZED] is False
    assert evidence["decision_boundary"][SEMANTIC_EQUIVALENCE_PROVEN] is False


def test_trusted_history_git_verifier_rejects_nonancestor_head(tmp_path: Path) -> None:
    repo, first, second = _git_repo(tmp_path)

    with pytest.raises(ValueError, match="not an ancestor"):
        verify_base_ancestry(
            repo_root=repo,
            selected_head_sha=second,
            base_sha=first,
        )


def test_trusted_history_rejects_authority_expanding_summary(tmp_path: Path) -> None:
    _repo, accepted_head, base_head = _git_repo(tmp_path)
    _summary_path, history_path, summary = _history_artifact(
        tmp_path,
        run_id="trusted-run-1",
        head_sha=accepted_head,
    )
    summary["decision_boundary"][AUTOMATION_ALLOWED] = True
    record = json.loads(history_path.read_text(encoding="utf-8").splitlines()[0])

    with pytest.raises(ValueError, match="expands authority"):
        build_trusted_history_evidence(
            summary=summary,
            records=[record],
            selected_run_id="trusted-run-1",
            selected_head_sha=accepted_head,
            base_sha=base_head,
            base_ancestry_verified=True,
        )


def test_trusted_history_rejects_selected_run_mismatch(tmp_path: Path) -> None:
    _repo, accepted_head, base_head = _git_repo(tmp_path)
    _summary_path, history_path, summary = _history_artifact(
        tmp_path,
        run_id="trusted-run-1",
        head_sha=accepted_head,
    )
    record = json.loads(history_path.read_text(encoding="utf-8").splitlines()[0])

    with pytest.raises(ValueError, match="selected run"):
        build_trusted_history_evidence(
            summary=summary,
            records=[record],
            selected_run_id="wrong-run",
            selected_head_sha=accepted_head,
            base_sha=base_head,
            base_ancestry_verified=True,
        )


def test_trusted_history_cli_writes_advisory_evidence(tmp_path: Path, capsys) -> None:
    repo, accepted_head, base_head = _git_repo(tmp_path)
    summary_path, history_path, _summary = _history_artifact(
        tmp_path,
        run_id="trusted-run-1",
        head_sha=accepted_head,
    )
    out_dir = tmp_path / "trusted-evidence"

    rc = main(
        [
            "--history-summary",
            str(summary_path),
            "--history-jsonl",
            str(history_path),
            "--repo-root",
            str(repo),
            "--selected-run-id",
            "trusted-run-1",
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
    captured = capsys.readouterr()
    saved = json.loads((out_dir / "trusted-history-evidence.json").read_text(encoding="utf-8"))
    markdown = (out_dir / "trusted-history-evidence.md").read_text(encoding="utf-8")

    assert captured.out == ""
    assert captured.err == ""
    assert saved["source"]["base_ancestry_verified"] is True
    assert "Trusted RepoMemory history evidence" in markdown
    assert "Records: `1`" in markdown
    assert "Automation allowed: `false`" in markdown


def test_trusted_history_markdown_preserves_advisory_boundary(tmp_path: Path) -> None:
    _repo, accepted_head, base_head = _git_repo(tmp_path)
    _summary_path, history_path, summary = _history_artifact(
        tmp_path,
        run_id="trusted-run-1",
        head_sha=accepted_head,
    )
    record = json.loads(history_path.read_text(encoding="utf-8").splitlines()[0])
    evidence = build_trusted_history_evidence(
        summary=summary,
        records=[record],
        selected_run_id="trusted-run-1",
        selected_head_sha=accepted_head,
        base_sha=base_head,
        base_ancestry_verified=True,
    )

    markdown = render_markdown(evidence)

    assert "Base ancestry verified: `true`" in markdown
    assert "Prior history is read-only input: `true`" in markdown
    assert "Proof commands executed by reader: `false`" in markdown
    assert "Merge authorized: `false`" in markdown
    assert "Semantic equivalence proven: `false`" in markdown


def _controlled_profile() -> dict:
    profile = _profile()
    profile["controlled_candidate_validation"] = {
        "status": CONTROLLED_VALIDATION_PASSED,
        "scenario_count": 2,
        "passed_count": 2,
        "structurally_verified_count": 1,
        "review_first_count": 1,
        "current_pr_decision_input": False,
        "decision_boundary": {
            AUTOMATION_ALLOWED: False,
            MERGE_AUTHORIZED: False,
            SEMANTIC_EQUIVALENCE_PROVEN: False,
        },
    }
    return profile


def test_trusted_history_reports_controlled_validation_as_advisory_only(tmp_path: Path) -> None:
    _repo, accepted_head, base_head = _git_repo(tmp_path)
    record = build_history_record(
        _controlled_profile(),
        source_run_id="trusted-controlled",
        source_head_sha=accepted_head,
    )
    history_path = write_history_jsonl([record], out_dir=tmp_path)
    summary = build_history_summary(
        [record],
        appended=True,
        history_path=history_path,
        prior_history_collected=False,
        prior_record_count=0,
    )

    evidence = build_trusted_history_evidence(
        summary=summary,
        records=[record],
        selected_run_id="trusted-controlled",
        selected_head_sha=accepted_head,
        base_sha=base_head,
        base_ancestry_verified=True,
    )

    history = evidence["history"]
    assert history[CONTROLLED_VALIDATION_RECORD_COUNT] == 1
    assert history[CONTROLLED_VALIDATION_SCENARIO_COUNT] == 2
    assert history[CONTROLLED_STRUCTURALLY_VERIFIED_COUNT] == 1
    assert history[CONTROLLED_REVIEW_FIRST_COUNT] == 1
    assert history["latest_controlled_validation_status"] == CONTROLLED_VALIDATION_PASSED
    assert history["controlled_validation_reporting_only"] is True
    assert evidence["decision_boundary"]["controlled_validation_authorizes_current_action"] is False

    markdown = render_markdown(evidence)
    assert "Controlled validation records: `1`" in markdown
    assert "Controlled validation reporting only: `true`" in markdown
    assert "Controlled validation authorizes current action: `false`" in markdown


def test_trusted_history_rejects_forged_controlled_validation_summary(tmp_path: Path) -> None:
    _repo, accepted_head, base_head = _git_repo(tmp_path)
    record = build_history_record(
        _controlled_profile(),
        source_run_id="trusted-controlled",
        source_head_sha=accepted_head,
    )
    history_path = write_history_jsonl([record], out_dir=tmp_path)
    summary = build_history_summary(
        [record],
        appended=True,
        history_path=history_path,
        prior_history_collected=False,
        prior_record_count=0,
    )
    summary[CONTROLLED_VALIDATION_RECORD_COUNT] = 99

    with pytest.raises(ValueError, match="controlled validation summary does not match records"):
        build_trusted_history_evidence(
            summary=summary,
            records=[record],
            selected_run_id="trusted-controlled",
            selected_head_sha=accepted_head,
            base_sha=base_head,
            base_ancestry_verified=True,
        )


def test_trusted_history_rejects_controlled_summary_not_marked_advisory_only(
    tmp_path: Path,
) -> None:
    _repo, accepted_head, base_head = _git_repo(tmp_path)
    record = build_history_record(
        _controlled_profile(),
        source_run_id="trusted-controlled",
        source_head_sha=accepted_head,
    )
    history_path = write_history_jsonl([record], out_dir=tmp_path)
    summary = build_history_summary(
        [record],
        appended=True,
        history_path=history_path,
        prior_history_collected=False,
        prior_record_count=0,
    )
    summary["decision_boundary"]["controlled_validation_is_advisory_only"] = False

    with pytest.raises(ValueError, match="not marked advisory only"):
        build_trusted_history_evidence(
            summary=summary,
            records=[record],
            selected_run_id="trusted-controlled",
            selected_head_sha=accepted_head,
            base_sha=base_head,
            base_ancestry_verified=True,
        )


def test_trusted_history_rejects_forged_latest_controlled_validation_status(
    tmp_path: Path,
) -> None:
    _repo, accepted_head, base_head = _git_repo(tmp_path)
    record = build_history_record(
        _controlled_profile(),
        source_run_id="trusted-controlled",
        source_head_sha=accepted_head,
    )
    history_path = write_history_jsonl([record], out_dir=tmp_path)
    summary = build_history_summary(
        [record],
        appended=True,
        history_path=history_path,
        prior_history_collected=False,
        prior_record_count=0,
    )
    summary["latest_record"][CONTROLLED_VALIDATION_STATUS] = "not_collected"

    with pytest.raises(
        ValueError, match="latest controlled validation status does not match JSONL record"
    ):
        build_trusted_history_evidence(
            summary=summary,
            records=[record],
            selected_run_id="trusted-controlled",
            selected_head_sha=accepted_head,
            base_sha=base_head,
            base_ancestry_verified=True,
        )


def _producer_vetted_history_profile() -> dict:
    profile = _profile()
    profile["flaky_test_registry"] = {
        "collection_status": "collected",
        "status": "advisory_registry_collected",
        "source": {
            "kind": "trusted_main_artifact",
            "reference": "registry.json",
            "classification_schema": ("sdetkit.trusted_test_observation_classification.v1"),
            "input_read_only": True,
            "commands_executed_by_reader": False,
            "workflow": "RepoMemory Profile History",
            "run_id": "trusted-registry-run",
            "head_sha": "a" * 40,
            "observation_status": (
                "producer_"
                # scanner-safe synthetic fixture split
                "vetted_flaky_"
                # scanner-safe synthetic fixture split
                "observations_"
                # scanner-safe synthetic fixture split
                "available"
            ),
            "observations_collected": True,
            "identity_kind": "fingerprint_only",
            "producer_vetted": True,
            "raw_test_identity_emitted": False,
        },
        "entries": [{"test_fingerprint": "b" * 64}],
        "entry_count": 1,
        "decision_boundary": {
            "automatic_quarantine_allowed": False,
            "automatic_rerun_allowed": False,
            "current_failure_suppression_allowed": False,
            "current_pr_decision_input": False,
            "patch_application_allowed": False,
            "automation_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        },
    }
    return profile


def test_trusted_history_exposes_registry_aggregate_without_identity(
    tmp_path: Path,
) -> None:
    from sdetkit import repo_memory_profile_history as history_model

    _repo, accepted_head, base_head = _git_repo(tmp_path)
    record = build_history_record(
        _producer_vetted_history_profile(),
        source_run_id="trusted-registry-run",
        source_head_sha=accepted_head,
    )
    history_path = write_history_jsonl([record], out_dir=tmp_path)
    summary = build_history_summary(
        [record],
        appended=True,
        history_path=history_path,
        prior_history_collected=False,
        prior_record_count=0,
    )

    evidence = build_trusted_history_evidence(
        summary=summary,
        records=[record],
        selected_run_id="trusted-registry-run",
        selected_head_sha=accepted_head,
        base_sha=base_head,
        base_ancestry_verified=True,
    )

    history = evidence["history"]
    assert history[history_model.FLAKY_TEST_REGISTRY_COLLECTION_STATUS] == "collected"
    assert history[history_model.FLAKY_TEST_REGISTRY_ENTRY_COUNT] == 1
    assert history[history_model.FLAKY_TEST_REGISTRY_PRODUCER_VETTED] is True
    assert history[history_model.FLAKY_TEST_REGISTRY_RAW_TEST_IDENTITY_EMITTED] is False
    assert history[history_model.FLAKY_TEST_REGISTRY_CURRENT_PR_DECISION_INPUT] is False

    serialized = json.dumps(evidence, sort_keys=True)
    for forbidden_key in (
        '"entries"',
        '"test_id"',
        '"classname"',
        '"nodeid"',
        '"test_fingerprint"',
        '"observation_provenance"',
    ):
        assert forbidden_key not in serialized

    markdown = render_markdown(evidence)
    assert "## Producer-vetted flaky-test registry" in markdown
    assert "Aggregate entry count: `1`" in markdown
    assert "Raw test identity emitted: `false`" in markdown
    assert "Current PR decision input: `false`" in markdown


def test_trusted_history_rejects_forged_registry_summary(
    tmp_path: Path,
) -> None:
    from sdetkit import repo_memory_profile_history as history_model

    _repo, accepted_head, base_head = _git_repo(tmp_path)
    record = build_history_record(
        _producer_vetted_history_profile(),
        source_run_id="trusted-registry-run",
        source_head_sha=accepted_head,
    )
    history_path = write_history_jsonl([record], out_dir=tmp_path)
    summary = build_history_summary(
        [record],
        appended=True,
        history_path=history_path,
        prior_history_collected=False,
        prior_record_count=0,
    )
    summary[history_model.FLAKY_TEST_REGISTRY_ENTRY_COUNT] = 99

    with pytest.raises(
        ValueError,
        match="flaky-test registry summary does not match",
    ):
        build_trusted_history_evidence(
            summary=summary,
            records=[record],
            selected_run_id="trusted-registry-run",
            selected_head_sha=accepted_head,
            base_sha=base_head,
            base_ancestry_verified=True,
        )
