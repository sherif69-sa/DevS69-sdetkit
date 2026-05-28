from __future__ import annotations

import json
from pathlib import Path

from sdetkit.diagnostic_vector_engine import (
    ACTUAL_FAILURE,
    AFFECTED_FILES,
    EVIDENCE_SOURCES,
    FAILURE_SURFACE,
    FIRST_FAILURE_LINE,
    HISTORY_CONTEXT,
    RECOMMENDED_NEXT_ACTION,
    REVIEW_FIRST,
    SAFE_FIX_CANDIDATE,
    build_diagnostic_vector,
    main,
)


def _write(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_diagnostic_vector_builds_review_first_type_contract_from_check_intelligence() -> None:
    check_intelligence = {
        "failed_checks": [
            {
                "name": "Fast CI lane (py3.12)",
                "diagnosis": {
                    "title": "Type contract failed",
                    "code": "MYPY_TYPE_CONTRACT",
                    "surface": "type_contract",
                    "confidence": "high",
                },
                "first_failure": {
                    "line": "src/sdetkit/example.py:10: error: Incompatible return value type",
                    "line_number": 42,
                    "tool": "mypy",
                    "kind": "type_contract",
                },
                "safe_to_auto_fix": False,
                "safe_remediation": {
                    "strategy": "review_first",
                    "reason": "type failures remain review-first",
                },
                "affected_files": ["src/sdetkit/example.py"],
            }
        ]
    }

    payload = build_diagnostic_vector(
        check_intelligence=check_intelligence,
        generated_at="2026-05-20T00:00:00Z",
    )

    diagnosis = payload["diagnoses"][0]
    assert payload["schema_version"] == "sdetkit.diagnostic_vector.v1"
    assert payload["summary"]["diagnosis_count"] == 1
    assert payload["summary"]["review_first_count"] == 1
    assert diagnosis[FAILURE_SURFACE] == "type_contract"
    assert (
        diagnosis[ACTUAL_FAILURE]
        == "src/sdetkit/example.py:10: error: Incompatible return value type"
    )
    assert (
        diagnosis[FIRST_FAILURE_LINE]
        == "src/sdetkit/example.py:10: error: Incompatible return value type"
    )
    assert diagnosis[REVIEW_FIRST] is True
    assert diagnosis[SAFE_FIX_CANDIDATE] is False
    assert diagnosis[AFFECTED_FILES] == ["src/sdetkit/example.py"]
    assert diagnosis[RECOMMENDED_NEXT_ACTION] == "review_first_type_contract"


def test_diagnostic_vector_uses_safe_fix_history_for_recurring_formatting_context() -> None:
    check_intelligence = {
        "failed_checks": [
            {
                "name": "autopilot",
                "diagnosis": {"title": "Formatter drift blocked pre-commit"},
                "first_failure": {
                    "line": "ruff format..............................Failed",
                    "line_number": 30,
                    "tool": "ruff",
                    "kind": "format_drift",
                },
                "safe_to_auto_fix": True,
                "safe_remediation": {
                    "safe_to_auto_fix": True,
                    "strategy": "run_pre_commit",
                },
                "affected_files": ["src/sdetkit/repeated.py"],
            }
        ]
    }
    safe_fix_history = {
        "metrics": {
            "safe_fix_attempts_total": 3,
            "recurring_format_drift_files": [{"file": "src/sdetkit/repeated.py", "count": 2}],
        }
    }

    payload = build_diagnostic_vector(
        check_intelligence=check_intelligence,
        safe_fix_history=safe_fix_history,
    )

    diagnosis = payload["diagnoses"][0]
    assert payload["summary"]["safe_fix_candidate_count"] == 1
    assert diagnosis[FAILURE_SURFACE] == "formatting"
    assert diagnosis[SAFE_FIX_CANDIDATE] is True
    assert diagnosis[REVIEW_FIRST] is False
    assert diagnosis[HISTORY_CONTEXT] == "recurring"
    assert diagnosis[RECOMMENDED_NEXT_ACTION] == "run_pre_commit"


def test_diagnostic_vector_preserves_evidence_graph_review_first_security_signal() -> None:
    evidence_graph = {
        "nodes": [
            {
                "summary": "Security-owned surface changed",
                "risk_surface": "security",
                "review_first": True,
                "safe_to_auto_fix": False,
                "owner_files": ["docs/security-posture.md"],
                "proof_commands": ["python -m sdetkit security check --root . --format json"],
                "source_artifacts": ["security-review.json"],
            }
        ]
    }

    payload = build_diagnostic_vector(evidence_graph=evidence_graph)

    diagnosis = payload["diagnoses"][0]
    assert diagnosis[FAILURE_SURFACE] == "security"
    assert diagnosis[REVIEW_FIRST] is True
    assert diagnosis[SAFE_FIX_CANDIDATE] is False
    assert diagnosis[AFFECTED_FILES] == ["docs/security-posture.md"]
    assert diagnosis[EVIDENCE_SOURCES] == ["evidence_graph", "security-review.json"]
    assert diagnosis[RECOMMENDED_NEXT_ACTION] == "review_first_security_review"


def test_diagnostic_vector_cli_writes_json_and_markdown(tmp_path: Path, capsys) -> None:
    check_path = _write(
        tmp_path / "check-intelligence.json",
        {
            "failed_checks": [
                {
                    "name": "Fast CI lane",
                    "first_failure_line": "FAILED tests/test_example.py::test_contract",
                    "safe_to_auto_fix": False,
                    "diagnosis": {"title": "Test contract failed", "surface": "test"},
                }
            ]
        },
    )
    out_dir = tmp_path / "diagnostics"

    rc = main(
        [
            "--check-intelligence",
            str(check_path),
            "--out-dir",
            str(out_dir),
            "--format",
            "json",
        ]
    )

    assert rc == 0
    stdout = capsys.readouterr().out
    payload = json.loads((out_dir / "diagnostic-vector.json").read_text(encoding="utf-8"))
    markdown = (out_dir / "diagnostic-vector.md").read_text(encoding="utf-8")
    assert payload["summary"]["diagnosis_count"] == 1
    assert "Diagnostic Vector" in markdown
    assert "diagnostic_vector_json" in stdout


def test_diagnostic_vector_embeds_canonical_failure_vector_contract() -> None:
    check_intelligence = {
        "failed_checks": [
            {
                "name": "Validate (ubuntu-latest / py3.12)",
                "command": "python -m pytest -q tests/test_widget.py -o addopts=",
                "exit_code": 1,
                "environment": "github_actions",
                "log_url": "https://github.example/actions/runs/1/job/2",
                "scope": "pr_owned_only",
                "review_first": True,
                "safe_to_auto_fix": False,
                "diagnosis": {
                    "title": "Pytest assertion failed",
                    "surface": "test",
                    "confidence": "high",
                },
                "first_failure": {
                    "line": "FAILED tests/test_widget.py::test_widget_contract - AssertionError: expected stable evidence",
                    "line_number": 88,
                    "tool": "pytest",
                    "kind": "test_failure",
                },
                "affected_files": ["tests/test_widget.py"],
            }
        ]
    }

    payload = build_diagnostic_vector(check_intelligence=check_intelligence)

    diagnosis = payload["diagnoses"][0]
    vector = diagnosis["failure_vector"]
    assert payload["summary"]["failure_vector_count"] == 1
    assert payload["failure_vectors"] == [vector]
    assert vector["schema_version"] == "sdetkit.failure_vector.v1"
    assert vector["check"] == "Validate (ubuntu-latest / py3.12)"
    assert vector["command"] == "python -m pytest -q tests/test_widget.py -o addopts="
    assert vector["exit_code"] == 1
    assert vector["headline_failure"] == "Pytest assertion failed"
    assert vector["actual_failure"].startswith("FAILED tests/test_widget.py::test_widget_contract")
    assert vector["first_failing_line"].startswith(
        "FAILED tests/test_widget.py::test_widget_contract"
    )
    assert vector["failing_file"] == "tests/test_widget.py"
    assert vector["failing_test"] == "tests/test_widget.py::test_widget_contract"
    assert vector["failure_class"] == "test"
    assert vector["risk"] == "medium"
    assert vector["risk_surface"] == "test"
    assert vector["scope"] == "pr_owned_only"
    assert vector["reproducible_locally"] == "not_run"
    assert vector["safe_fix_candidate"] is False
    assert vector["review_first"] is True
    assert vector["affected_files"] == ["tests/test_widget.py"]
    assert vector["owner_files"] == ["tests/test_widget.py"]
    assert vector["log_url"] == "https://github.example/actions/runs/1/job/2"
    assert vector["local_repro_command"] == "python -m pytest -q tests/test_widget.py -o addopts="
    assert vector["environment"] == "github_actions"


def test_diagnostic_vector_cli_writes_failure_vector_json(tmp_path: Path, capsys) -> None:
    check_path = _write(
        tmp_path / "check-intelligence.json",
        {
            "failed_checks": [
                {
                    "name": "pre-commit",
                    "command": "python -m pre_commit run -a",
                    "exit_code": 1,
                    "first_failure": {
                        "line": "ruff format..............................Failed",
                        "line_number": 30,
                        "tool": "ruff",
                        "kind": "format_drift",
                    },
                    "safe_to_auto_fix": True,
                    "safe_remediation": {
                        "safe_to_auto_fix": True,
                        "strategy": "run_pre_commit",
                    },
                    "affected_files": ["src/sdetkit/example.py"],
                }
            ]
        },
    )
    out_dir = tmp_path / "diagnostics"

    rc = main(
        [
            "--check-intelligence",
            str(check_path),
            "--out-dir",
            str(out_dir),
            "--format",
            "json",
        ]
    )

    assert rc == 0
    stdout = json.loads(capsys.readouterr().out)
    assert "failure_vector_json" in stdout["artifacts"]
    failure_vector_doc = json.loads((out_dir / "failure-vector.json").read_text(encoding="utf-8"))
    assert failure_vector_doc["schema_version"] == "sdetkit.failure_vector.v1"
    assert failure_vector_doc["summary"]["failure_vector_count"] == 1
    assert failure_vector_doc["failure_vectors"][0]["failure_class"] == "formatter_only"
    assert failure_vector_doc["failure_vectors"][0]["safe_fix_candidate"] is True


def test_diagnostic_vector_emits_review_first_runtime_guard_violation_from_runtime_proof_artifacts() -> (
    None
):
    payload = build_diagnostic_vector(
        runtime_proof_artifacts={
            "isolated_proof": {
                "collection_status": "collected",
                "runtime_guard_checked": True,
                "runtime_guard_passed": False,
                "runtime_guard_violation_count": 1,
            }
        }
    )

    diagnosis = payload["diagnoses"][0]
    vector = diagnosis["failure_vector"]
    assert payload["summary"]["diagnosis_count"] == 1
    assert payload["summary"]["review_first_count"] == 1
    assert payload["source_status"]["runtime_proof_artifacts"] is True
    assert diagnosis[FAILURE_SURFACE] == "runtime"
    assert (
        diagnosis[ACTUAL_FAILURE] == "runtime_guard_passed=false; runtime_guard_violation_count=1"
    )
    assert diagnosis[REVIEW_FIRST] is True
    assert diagnosis[SAFE_FIX_CANDIDATE] is False
    assert diagnosis[RECOMMENDED_NEXT_ACTION] == "review_first_runtime_debug"
    assert vector["source"] == "runtime_proof_artifacts"
    assert vector["failure_class"] == "runtime_guard"
    assert vector["scope"] == "proof_boundary"


def test_diagnostic_vector_does_not_emit_runtime_guard_diagnosis_when_guard_passes() -> None:
    payload = build_diagnostic_vector(
        runtime_proof_artifacts={
            "isolated_proof": {
                "collection_status": "collected",
                "runtime_guard_checked": True,
                "runtime_guard_passed": True,
                "runtime_guard_violation_count": 0,
            }
        }
    )

    assert payload["diagnoses"] == []
    assert payload["summary"]["diagnosis_count"] == 0
    assert payload["source_status"]["runtime_proof_artifacts"] is True
