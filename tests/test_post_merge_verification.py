from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from sdetkit import _legacy_cli
from sdetkit.post_merge_verification import (
    DEFAULT_MARKDOWN_OUT,
    DEFAULT_OUT,
    SCHEMA_VERSION,
    build_post_merge_verification,
    check_post_merge_verification_freshness,
    main,
    write_post_merge_verification,
)

JsonObject = dict[str, Any]


def _run(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _commit(root: Path, message: str) -> str:
    _run(root, "add", ".")
    _run(root, "commit", "-q", "-m", message)
    return _run(root, "rev-parse", "HEAD")


def _seed_repo(
    tmp_path: Path,
    *,
    protected_change: bool = False,
) -> tuple[str, str]:
    _run(tmp_path, "init", "-q")
    _run(tmp_path, "config", "user.email", "tests@example.invalid")
    _run(tmp_path, "config", "user.name", "SDETKit Tests")

    (tmp_path / "README.md").write_text(
        "baseline\n",
        encoding="utf-8",
    )
    previous = _commit(tmp_path, "baseline")

    (tmp_path / "src").mkdir()
    (tmp_path / "src/example.py").write_text(
        "VALUE = 1\n",
        encoding="utf-8",
    )
    if protected_change:
        workflow = tmp_path / ".github/workflows/release.yml"
        workflow.parent.mkdir(parents=True)
        workflow.write_text("name: changed\n", encoding="utf-8")
    merge_commit = _commit(tmp_path, "merged change")
    return previous, merge_commit


def _thread(
    *,
    outdated: bool = False,
    resolved: bool = False,
) -> JsonObject:
    return {
        "id": "THREAD",
        "isResolved": resolved,
        "isOutdated": outdated,
        "path": "src/example.py",
        "line": 1,
        "originalLine": 1,
        "comments": {
            "nodes": [
                {
                    "body": "Evidence review signal",
                    "author": {"login": "review-bot"},
                }
            ]
        },
    }


def _write_evidence(
    root: Path,
    *,
    previous_main_sha: str,
    merge_commit_sha: str,
    pr_head_sha: str | None = None,
    pr_base_sha: str | None = None,
    ci_state: str = "success",
    threads: list[JsonObject] | None = None,
    findings: list[JsonObject] | None = None,
) -> Path:
    evidence = root / "evidence"
    evidence.mkdir()

    pr_payload = {
        "number": 42,
        "state": "closed",
        "merged": True,
        "head": {"sha": pr_head_sha or ("a" * 40)},
        "base": {"sha": pr_base_sha or previous_main_sha},
        "merge_commit_sha": merge_commit_sha,
    }
    status_payload = {
        "statuses": [
            {
                "context": "ci",
                "state": ci_state,
                "target_url": ("https://github.com/example/repo/actions/runs/123"),
            }
        ]
    }
    review_payload = {
        "data": {
            "repository": {
                "pullRequest": {
                    "reviewThreads": {
                        "nodes": threads or [],
                    }
                }
            }
        }
    }
    finding_rows = findings or []
    security_payload = {
        "counts": {
            "warn": len(finding_rows),
            "error": 0,
        },
        "findings": finding_rows,
    }

    for filename, payload in (
        ("pr.json", pr_payload),
        ("main-status.json", status_payload),
        ("review-threads.json", review_payload),
        ("security-check.json", security_payload),
    ):
        (evidence / filename).write_text(
            json.dumps(payload),
            encoding="utf-8",
        )
    return evidence


def test_exact_squash_merge_is_verified(tmp_path: Path) -> None:
    previous, merge_commit = _seed_repo(tmp_path)
    evidence = _write_evidence(
        tmp_path,
        previous_main_sha=previous,
        merge_commit_sha=merge_commit,
    )

    payload = build_post_merge_verification(
        tmp_path,
        evidence_dir=evidence,
        previous_main_sha=previous,
        current_head_sha=merge_commit,
        generated_at="2026-06-25T00:00:00Z",
    )

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["status"] == "verified"
    assert payload["report_status"] == "passed"
    assert payload["merge_relation"] == "exact_merge_commit"
    assert payload["merged"] is True
    assert payload["ci"]["state"] == "success"
    assert payload["ghas_review_threads"]["current_count"] == 0
    assert payload["local_security"]["finding_count"] == 0
    assert payload["protected_path_drift"] == []
    assert payload["merge_authorized"] is False


def test_merge_commit_ancestor_with_later_main_is_verified(
    tmp_path: Path,
) -> None:
    previous, merge_commit = _seed_repo(tmp_path)
    evidence = _write_evidence(
        tmp_path,
        previous_main_sha=previous,
        merge_commit_sha=merge_commit,
        pr_head_sha=merge_commit,
    )
    (tmp_path / "later.txt").write_text(
        "later\n",
        encoding="utf-8",
    )
    current = _commit(tmp_path, "later main work")

    payload = build_post_merge_verification(
        tmp_path,
        evidence_dir=evidence,
        previous_main_sha=previous,
        current_head_sha=current,
    )

    assert payload["status"] == "verified"
    assert payload["merge_relation"] == "merge_commit_ancestor"
    assert "later.txt" not in payload["changed_paths"]


def test_current_unresolved_ghas_thread_requires_review(
    tmp_path: Path,
) -> None:
    previous, merge_commit = _seed_repo(tmp_path)
    evidence = _write_evidence(
        tmp_path,
        previous_main_sha=previous,
        merge_commit_sha=merge_commit,
        threads=[_thread()],
    )

    payload = build_post_merge_verification(
        tmp_path,
        evidence_dir=evidence,
        previous_main_sha=previous,
        current_head_sha=merge_commit,
    )

    assert payload["status"] == "review_required"
    assert payload["ghas_review_threads"]["current_count"] == 1


def test_outdated_or_resolved_ghas_threads_are_non_blocking(
    tmp_path: Path,
) -> None:
    previous, merge_commit = _seed_repo(tmp_path)
    evidence = _write_evidence(
        tmp_path,
        previous_main_sha=previous,
        merge_commit_sha=merge_commit,
        threads=[
            _thread(outdated=True),
            _thread(resolved=True),
        ],
    )

    payload = build_post_merge_verification(
        tmp_path,
        evidence_dir=evidence,
        previous_main_sha=previous,
        current_head_sha=merge_commit,
    )

    assert payload["status"] == "verified"
    assert payload["ghas_review_threads"]["current_count"] == 0
    assert payload["ghas_review_threads"]["outdated_count"] == 1
    assert payload["ghas_review_threads"]["resolved_count"] == 1


@pytest.mark.parametrize("ci_state", ["pending", "failure"])
def test_non_success_ci_requires_review(
    tmp_path: Path,
    ci_state: str,
) -> None:
    previous, merge_commit = _seed_repo(tmp_path)
    evidence = _write_evidence(
        tmp_path,
        previous_main_sha=previous,
        merge_commit_sha=merge_commit,
        ci_state=ci_state,
    )

    payload = build_post_merge_verification(
        tmp_path,
        evidence_dir=evidence,
        previous_main_sha=previous,
        current_head_sha=merge_commit,
    )

    assert payload["status"] == "review_required"
    assert payload["ci"]["state"] == ci_state


def test_missing_or_malformed_evidence_is_unavailable(
    tmp_path: Path,
) -> None:
    previous, merge_commit = _seed_repo(tmp_path)
    evidence = _write_evidence(
        tmp_path,
        previous_main_sha=previous,
        merge_commit_sha=merge_commit,
    )
    (evidence / "review-threads.json").unlink()

    missing = build_post_merge_verification(
        tmp_path,
        evidence_dir=evidence,
        previous_main_sha=previous,
        current_head_sha=merge_commit,
    )
    assert missing["status"] == "unavailable"
    assert missing["input_artifacts"]["review_threads"]["collection_status"] == "missing"

    (evidence / "review-threads.json").write_text(
        "{",
        encoding="utf-8",
    )
    malformed = build_post_merge_verification(
        tmp_path,
        evidence_dir=evidence,
        previous_main_sha=previous,
        current_head_sha=merge_commit,
    )
    assert malformed["status"] == "unavailable"
    assert malformed["input_artifacts"]["review_threads"]["collection_status"] == "malformed"


def test_stale_pr_base_requires_review(tmp_path: Path) -> None:
    previous, merge_commit = _seed_repo(tmp_path)
    evidence = _write_evidence(
        tmp_path,
        previous_main_sha=previous,
        merge_commit_sha=merge_commit,
        pr_base_sha="b" * 40,
    )

    payload = build_post_merge_verification(
        tmp_path,
        evidence_dir=evidence,
        previous_main_sha=previous,
        current_head_sha=merge_commit,
    )

    assert payload["status"] == "review_required"
    assert payload["input_artifacts"]["pr"]["collection_status"] == "stale"


def test_protected_path_drift_requires_review(
    tmp_path: Path,
) -> None:
    previous, merge_commit = _seed_repo(
        tmp_path,
        protected_change=True,
    )
    evidence = _write_evidence(
        tmp_path,
        previous_main_sha=previous,
        merge_commit_sha=merge_commit,
    )

    payload = build_post_merge_verification(
        tmp_path,
        evidence_dir=evidence,
        previous_main_sha=previous,
        current_head_sha=merge_commit,
    )

    assert payload["status"] == "review_required"
    assert payload["protected_path_drift"] == [".github/workflows/release.yml"]


def test_local_security_finding_requires_review(
    tmp_path: Path,
) -> None:
    previous, merge_commit = _seed_repo(tmp_path)
    evidence = _write_evidence(
        tmp_path,
        previous_main_sha=previous,
        merge_commit_sha=merge_commit,
        findings=[
            {
                "rule_id": "TEST_RULE",
                "path": "src/example.py",
            }
        ],
    )

    payload = build_post_merge_verification(
        tmp_path,
        evidence_dir=evidence,
        previous_main_sha=previous,
        current_head_sha=merge_commit,
    )

    assert payload["status"] == "review_required"
    assert payload["local_security"]["finding_count"] == 1


def test_freshness_detects_evidence_drift(tmp_path: Path) -> None:
    previous, merge_commit = _seed_repo(tmp_path)
    evidence = _write_evidence(
        tmp_path,
        previous_main_sha=previous,
        merge_commit_sha=merge_commit,
    )
    out = tmp_path / "report.json"
    markdown = tmp_path / "report.md"

    write_post_merge_verification(
        tmp_path,
        evidence_dir=evidence,
        previous_main_sha=previous,
        out_json=out,
        out_md=markdown,
        current_head_sha=merge_commit,
        generated_at="2026-06-25T00:00:00Z",
    )

    fresh = check_post_merge_verification_freshness(
        repo_root=tmp_path,
        evidence_dir=evidence,
        previous_main_sha=previous,
        report_path=out,
        current_head_sha=merge_commit,
    )
    assert fresh["fresh"] is True

    status_path = evidence / "main-status.json"
    payload = json.loads(status_path.read_text(encoding="utf-8"))
    payload["statuses"][0]["state"] = "pending"
    status_path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    stale = check_post_merge_verification_freshness(
        repo_root=tmp_path,
        evidence_dir=evidence,
        previous_main_sha=previous,
        report_path=out,
        current_head_sha=merge_commit,
    )
    assert stale["fresh"] is False
    mismatch_reason = "_".join(("input", "digests", "mismatch"))
    assert mismatch_reason in stale["reasons"]


def test_module_and_root_cli_forwarding(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    previous, merge_commit = _seed_repo(tmp_path)
    evidence = _write_evidence(
        tmp_path,
        previous_main_sha=previous,
        merge_commit_sha=merge_commit,
    )

    module_json = tmp_path / "module.json"
    module_md = tmp_path / "module.md"
    rc = main(
        [
            "--root",
            str(tmp_path),
            "--evidence-dir",
            str(evidence),
            "--previous-main-sha",
            previous,
            "--out-json",
            str(module_json),
            "--out-md",
            str(module_md),
            "--format",
            "json",
        ]
    )
    assert rc == 0
    module_payload = json.loads(capsys.readouterr().out)
    assert module_payload["status"] == "verified"
    assert module_json.is_file()
    assert "# Post-merge verification" in module_md.read_text(encoding="utf-8")

    root_json = tmp_path / "root.json"
    root_md = tmp_path / "root.md"
    rc = _legacy_cli.main(
        [
            "post-merge-verification",
            "--root",
            str(tmp_path),
            "--evidence-dir",
            str(evidence),
            "--previous-main-sha",
            previous,
            "--out-json",
            str(root_json),
            "--out-md",
            str(root_md),
            "--format",
            "json",
        ]
    )
    assert rc == 0
    root_payload = json.loads(capsys.readouterr().out)
    assert root_payload["status"] == "verified"
    assert root_json.is_file()
    assert root_md.is_file()


def test_default_output_contract() -> None:
    assert DEFAULT_OUT == ("build/sdetkit/post-merge-verification/report.json")
    assert DEFAULT_MARKDOWN_OUT == ("build/sdetkit/post-merge-verification/report.md")
