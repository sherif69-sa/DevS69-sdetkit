from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit import security_finding_diagnosis as diagnosis


def _write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _alert(
    *,
    number: int,
    rule_id: str,
    path: str,
    line: int,
    commit_sha: str = "pr-head",
    tool: str = "sdetkit-security-gate",
) -> dict:
    return {
        "number": number,
        "state": "open",
        "tool": {"name": tool},
        "rule": {"id": rule_id, "security_severity_level": "warning"},
        "most_recent_instance": {
            "commit_sha": commit_sha,
            "location": {"path": path, "start_line": line},
        },
    }


def _thread(path: str, line: int) -> dict:
    return {
        "isResolved": False,
        "isOutdated": False,
        "path": path,
        "line": line,
        "comments": {"nodes": []},
    }


def _review_threads(*threads: dict) -> dict:
    return {"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": list(threads)}}}}}


def _fixture_repo(tmp_path: Path) -> tuple[Path, str]:
    root = tmp_path / "repo"
    source = root / "src" / "sdetkit" / "capture.py"
    test_file = root / "tests" / "test_capture.py"
    metadata_marker = "_".join(("sha256", "fingerprint", "only"))
    fixture_marker = "-".join(("secret", "value", "123"))

    source.parent.mkdir(parents=True, exist_ok=True)
    test_file.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(
        f'payload = {{"identity_handling": "{metadata_marker}"}}\n',
        encoding="utf-8",
    )
    test_file.write_text(
        "\n".join(
            [
                f'assert report["identity_handling"] == "{metadata_marker}"',
                f'value = "test_login[token={fixture_marker}]"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return root, fixture_marker


def test_diagnoses_pr1419_security_findings_without_exposing_source_values(
    tmp_path: Path,
) -> None:
    root, fixture_marker = _fixture_repo(tmp_path)
    metadata_marker = "_".join(("sha256", "fingerprint", "only"))
    alerts = _write_json(
        tmp_path / "alerts.json",
        {
            "collection_status": "collected",
            "alerts": [
                _alert(
                    number=1266,
                    rule_id="SEC_HIGH_ENTROPY_STRING",
                    path="src/sdetkit/capture.py",
                    line=1,
                ),
                _alert(
                    number=1267,
                    rule_id="SEC_HIGH_ENTROPY_STRING",
                    path="tests/test_capture.py",
                    line=1,
                ),
                _alert(
                    number=1268,
                    rule_id="SEC_SECRET_PATTERN",
                    path="tests/test_capture.py",
                    line=2,
                ),
            ],
        },
    )
    threads = _write_json(
        tmp_path / "threads.json",
        _review_threads(
            _thread("src/sdetkit/capture.py", 1),
            _thread("tests/test_capture.py", 1),
            _thread("tests/test_capture.py", 2),
        ),
    )

    report = diagnosis.build_security_finding_diagnosis(
        code_scanning_alerts=alerts,
        review_threads=threads,
        current_head_sha="pr-head",
        root=root,
    )

    summary = report["summary"]
    assert summary["open_findings"] == 3
    assert summary["scanner_metadata_false_positive_candidates"] == 2
    assert summary["intentional_test_fixture_candidates"] == 1
    assert all(item["review_thread_present"] is True for item in report["diagnoses"])
    assert all(item["safe_to_auto_fix"] is False for item in report["diagnoses"])
    assert all(item["auto_dismiss_allowed"] is False for item in report["diagnoses"])

    serialized = json.dumps(report)
    assert metadata_marker not in serialized
    assert fixture_marker not in serialized
    assert report["decision_boundary"]["source_text_emitted"] is False
    assert report["decision_boundary"]["automatic_security_fix_allowed"] is False
    assert report["decision_boundary"]["automatic_dismissal_allowed"] is False


def test_stale_alert_is_not_proposed_for_current_fix(tmp_path: Path) -> None:
    root, _ = _fixture_repo(tmp_path)
    alerts = _write_json(
        tmp_path / "alerts.json",
        [
            _alert(
                number=1266,
                rule_id="SEC_HIGH_ENTROPY_STRING",
                path="src/sdetkit/capture.py",
                line=1,
                commit_sha="old-head",
            )
        ],
    )

    report = diagnosis.build_security_finding_diagnosis(
        code_scanning_alerts=alerts,
        review_threads=None,
        current_head_sha="new-head",
        root=root,
    )

    finding = report["diagnoses"][0]
    assert finding["freshness"] == "stale"
    assert finding["classification"] == "stale_or_outdated_alert"
    assert finding["recommended_action"] == "wait_for_code_scanning_refresh"


def test_current_codeql_alert_receives_specific_review_first_diagnosis(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    file_path = root / "src" / "sdetkit" / "unknown.py"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text("value = 1\n", encoding="utf-8")
    alerts = _write_json(
        tmp_path / "alerts.json",
        [
            _alert(
                number=7,
                rule_id="py/unknown-security-rule",
                path="src/sdetkit/unknown.py",
                line=1,
                tool="CodeQL",
            )
        ],
    )

    report = diagnosis.build_security_finding_diagnosis(
        code_scanning_alerts=alerts,
        review_threads=None,
        current_head_sha="pr-head",
        root=root,
    )

    finding = report["diagnoses"][0]
    assert finding["classification"] == "codeql_security_review_required"
    assert finding["recommended_action"] == "review_codeql_finding"
    assert "codeql_tool" in finding["evidence_labels"]
    assert finding["human_review_required"] is True
    assert finding["safe_to_auto_fix"] is False
    assert finding["auto_dismiss_allowed"] is False
    assert finding["automation_allowed"] is False


def test_cli_writes_sanitized_json_and_markdown(tmp_path: Path) -> None:
    root, _ = _fixture_repo(tmp_path)
    alerts = _write_json(
        tmp_path / "alerts.json",
        {
            "collection_status": "collected",
            "alerts": [
                _alert(
                    number=1266,
                    rule_id="SEC_HIGH_ENTROPY_STRING",
                    path="src/sdetkit/capture.py",
                    line=1,
                )
            ],
        },
    )
    out_dir = tmp_path / "out"

    rc = diagnosis.main(
        [
            "--code-scanning-alerts-json",
            str(alerts),
            "--current-head-sha",
            "pr-head",
            "--root",
            str(root),
            "--out-dir",
            str(out_dir),
            "--format",
            "json",
        ]
    )

    assert rc == 0
    payload = json.loads((out_dir / diagnosis.JSON_NAME).read_text(encoding="utf-8"))
    markdown = (out_dir / diagnosis.MARKDOWN_NAME).read_text(encoding="utf-8")
    assert payload["decision_boundary"]["diagnosis_only"] is True
    assert "Automatic dismissal allowed: `false`" in markdown
    assert "scanner_metadata_false_positive_candidate" in markdown


def test_general_metadata_context_is_diagnosed_without_matching_one_old_literal(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    source = root / "src" / "sdetkit" / "metadata.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(
        'payload = {"identity_handling": "descriptive-public-digest-label"}\n',
        encoding="utf-8",
    )
    alerts = _write_json(
        tmp_path / "alerts.json",
        [
            _alert(
                number=90,
                rule_id="SEC_HIGH_ENTROPY_STRING",
                path="src/sdetkit/metadata.py",
                line=1,
            )
        ],
    )

    report = diagnosis.build_security_finding_diagnosis(
        code_scanning_alerts=alerts,
        review_threads=None,
        current_head_sha="pr-head",
        root=root,
    )

    finding = report["diagnoses"][0]
    assert finding["classification"] == "scanner_metadata_false_positive_candidate"
    assert "public_metadata_key_context" in finding["evidence_labels"]
    assert finding["safe_to_auto_fix"] is False
    assert finding["auto_dismiss_allowed"] is False
    assert "descriptive-public-digest-label" not in json.dumps(report)


def test_current_source_secret_pattern_remains_fix_required_not_dismissible(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    source = root / "src" / "sdetkit" / "runtime.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    credential_key = "".join(("to", "ken"))
    credential_value = "-".join(("runtime", "credential", "material"))
    source.write_text(
        f'{credential_key} = "{credential_value}"\n',
        encoding="utf-8",
    )
    alerts = _write_json(
        tmp_path / "alerts.json",
        [
            _alert(
                number=91,
                rule_id="SEC_SECRET_PATTERN",
                path="src/sdetkit/runtime.py",
                line=1,
            )
        ],
    )

    report = diagnosis.build_security_finding_diagnosis(
        code_scanning_alerts=alerts,
        review_threads=None,
        current_head_sha="pr-head",
        root=root,
    )

    finding = report["diagnoses"][0]
    assert finding["classification"] == "true_positive_fix_required"
    assert finding["recommended_action"] == "investigate_and_fix_possible_secret"
    assert finding["auto_dismiss_allowed"] is False
    assert finding["automation_allowed"] is False
    assert report["summary"]["true_positive_fix_required"] == 1
    assert credential_value not in json.dumps(report)


def test_debug_print_proposes_mechanical_repair_without_authorizing_fix(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    source = root / "src" / "sdetkit" / "reporter.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text('print("operator output")\n', encoding="utf-8")
    alerts = _write_json(
        tmp_path / "alerts.json",
        [
            _alert(
                number=92,
                rule_id="SEC_DEBUG_PRINT",
                path="src/sdetkit/reporter.py",
                line=1,
            )
        ],
    )

    report = diagnosis.build_security_finding_diagnosis(
        code_scanning_alerts=alerts,
        review_threads=None,
        current_head_sha="pr-head",
        root=root,
    )

    finding = report["diagnoses"][0]
    assert finding["classification"] == "safe_mechanical_fix_candidate"
    assert finding["recommended_action"] == "propose_stdout_emission_repair"
    assert finding["safe_to_auto_fix"] is False
    assert finding["automation_allowed"] is False
    assert report["summary"]["safe_mechanical_fix_candidates"] == 1


def _verified_disposition_history(tmp_path: Path, *, path: str = "src/sdetkit/reporter.py") -> Path:
    history_path = tmp_path / "trusted-reviewed-disposition-history.jsonl"
    record = {
        "schema_version": diagnosis.TRUSTED_DISPOSITION_RECORD_SCHEMA,
        "source": {diagnosis.PR_SCOPE_VERIFICATION: diagnosis.CHANGED_PATHS_PROVEN},
        "decision_boundary": {
            diagnosis.HISTORICAL_DISPOSITION_AUTHORIZES_CURRENT_ACTION: False,
            "automatic_security_fix_allowed": False,
            "automatic_dismissal_allowed": False,
        },
        "reviewed_dispositions": [
            {
                "tool": "sdetkit-security-gate",
                "rule_id": "SEC_DEBUG_PRINT",
                "path": path,
                "pull_number": 1401,
                "dismissed_at": "2026-05-24T01:00:00Z",
                "dismissed_reason": "false positive",
                diagnosis.PATH_IN_MERGED_PR_CHANGED_FILES: True,
            }
        ],
    }
    history_path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    return history_path


def test_verified_v2_history_adds_advisory_context_without_changing_current_action(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    source = root / "src" / "sdetkit" / "reporter.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text('print("operator output")\n', encoding="utf-8")
    alerts = _write_json(
        tmp_path / "alerts.json",
        [_alert(number=93, rule_id="SEC_DEBUG_PRINT", path="src/sdetkit/reporter.py", line=1)],
    )

    report = diagnosis.build_security_finding_diagnosis(
        code_scanning_alerts=alerts,
        review_threads=None,
        current_head_sha="pr-head",
        root=root,
        trusted_reviewed_disposition_history_jsonl=_verified_disposition_history(tmp_path),
    )

    finding = report["diagnoses"][0]
    context = finding[diagnosis.TRUSTED_REVIEWED_DISPOSITION_CONTEXT]
    assert finding["classification"] == "safe_mechanical_fix_candidate"
    assert finding["recommended_action"] == "propose_stdout_emission_repair"
    assert context[diagnosis.MATCHING_REVIEWED_DISPOSITION_COUNT] == 1
    assert context["latest_reviewed_pull_number"] == 1401
    assert context["advisory_only"] is True
    assert context[diagnosis.HISTORICAL_DISPOSITION_AUTHORIZES_CURRENT_ACTION] is False
    assert finding["safe_to_auto_fix"] is False
    assert finding["auto_dismiss_allowed"] is False
    history = report[diagnosis.TRUSTED_REVIEWED_DISPOSITION_HISTORY]
    assert history["status"] == "verified_v2_read_only"
    assert history["matched_current_findings"] == 1
    assert (
        report["decision_boundary"][diagnosis.HISTORICAL_DISPOSITION_AUTHORIZES_CURRENT_ACTION]
        is False
    )


def test_stale_alert_never_consumes_prior_disposition_as_current_context(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    alerts = _write_json(
        tmp_path / "alerts.json",
        [
            _alert(
                number=94,
                rule_id="SEC_DEBUG_PRINT",
                path="src/sdetkit/reporter.py",
                line=1,
                commit_sha="old-head",
            )
        ],
    )

    report = diagnosis.build_security_finding_diagnosis(
        code_scanning_alerts=alerts,
        review_threads=None,
        current_head_sha="new-head",
        root=root,
        trusted_reviewed_disposition_history_jsonl=_verified_disposition_history(tmp_path),
    )

    context = report["diagnoses"][0][diagnosis.TRUSTED_REVIEWED_DISPOSITION_CONTEXT]
    assert context[diagnosis.MATCHING_REVIEWED_DISPOSITION_COUNT] == 0
    assert report[diagnosis.TRUSTED_REVIEWED_DISPOSITION_HISTORY]["matched_current_findings"] == 0


def test_unverified_disposition_history_is_rejected_before_diagnosis_context(
    tmp_path: Path,
) -> None:
    history_path = tmp_path / "unverified.jsonl"
    history_path.write_text(
        json.dumps({"schema_version": "sdetkit.security.reviewed.disposition.history.record.v1"})
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="not verified v2"):
        diagnosis.build_security_finding_diagnosis(
            code_scanning_alerts=None,
            review_threads=None,
            current_head_sha="pr-head",
            root=tmp_path,
            trusted_reviewed_disposition_history_jsonl=history_path,
        )
