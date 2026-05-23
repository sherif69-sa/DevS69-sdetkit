from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit.flaky_test_registry_evidence import (
    STATUS,
    build_flaky_test_registry_evidence,
    main,
    render_markdown,
)


def _classification_report() -> dict:
    return {
        "schema_version": "sdetkit.intelligence.flake.v1",
        "tests": [
            {
                "test_id": "tests/test_service.py::test_retry_path",
                "classification": "flaky",
                "signal": "nondeterministic-rerun",
                "next_step": "Quarantine test and capture deterministic evidence.",
                "runs": 3,
                "failures": 1,
                "passes": 2,
                "fingerprint": "abcd1234",
            },
            {
                "test_id": "tests/test_service.py::test_stable_failure",
                "classification": "stable-failing",
                "runs": 2,
                "failures": 2,
                "passes": 0,
                "fingerprint": "stable0001",
            },
        ],
        "summary": {
            "flaky": 1,
            "stable_failing": 1,
            "stable_passing": 0,
        },
    }


def test_flaky_test_registry_normalizes_flake_evidence_without_authority() -> None:
    evidence = build_flaky_test_registry_evidence(
        classification_report=_classification_report(),
        source_kind="operator_review_input",
        source_reference="local-proof",
    )

    assert evidence["status"] == STATUS
    assert evidence["summary"]["entry_count"] == 1
    entry = evidence["entries"][0]
    assert entry["test_id"] == "tests/test_service.py::test_retry_path"
    assert entry["decision"] == "instability_context_only"
    assert "next_step" not in entry
    assert entry["automatic_quarantine_allowed"] is False
    assert entry["current_failure_suppression_allowed"] is False

    boundary = evidence["decision_boundary"]
    assert boundary["automation_allowed"] is False
    assert boundary["merge_authorized"] is False
    assert boundary["semantic_equivalence_proven"] is False


def test_flaky_test_registry_rejects_unproven_flaky_entry() -> None:
    report = _classification_report()
    report["tests"][0]["passes"] = 0

    try:
        build_flaky_test_registry_evidence(
            classification_report=report,
            source_kind="operator_review_input",
            source_reference="local-proof",
        )
    except ValueError as exc:
        assert "mixed pass/fail observations" in str(exc)
    else:
        raise AssertionError("expected invalid flaky evidence to be rejected")


def test_flaky_test_registry_markdown_exposes_review_first_boundary() -> None:
    markdown = render_markdown(
        build_flaky_test_registry_evidence(
            classification_report=_classification_report(),
            source_kind="operator_review_input",
            source_reference="local-proof",
        )
    )

    assert "# Flaky-test registry evidence" in markdown
    assert "decision=`instability_context_only`" in markdown
    assert "Automatic quarantine allowed: `false`" in markdown
    assert "Current failure suppression allowed: `false`" in markdown
    assert "Merge authorized: `false`" in markdown


def test_flaky_test_registry_cli_writes_deterministic_artifacts(tmp_path: Path, capsys) -> None:
    input_path = tmp_path / "classification.json"
    out_dir = tmp_path / "registry"
    input_path.write_text(json.dumps(_classification_report()), encoding="utf-8")

    rc = main(
        [
            "--classification-report",
            str(input_path),
            "--source-kind",
            "operator_review_input",
            "--source-reference",
            "local-proof",
            "--out-dir",
            str(out_dir),
            "--format",
            "json",
        ]
    )

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    saved = json.loads((out_dir / "flaky-test-registry-evidence.json").read_text(encoding="utf-8"))
    markdown = (out_dir / "flaky-test-registry-evidence.md").read_text(encoding="utf-8")

    assert printed["status"] == "written"
    assert saved["status"] == STATUS
    assert saved["source"]["input_read_only"] is True
    assert "Automation allowed: `false`" in markdown



def test_flaky_test_registry_rejects_missing_source_reference_and_malformed_report() -> None:
    with pytest.raises(ValueError, match="source reference is required"):
        build_flaky_test_registry_evidence(
            classification_report=_classification_report(),
            source_kind="trusted_main_artifact",
            source_reference="",
        )

    malformed = {
        "schema_version": "sdetkit.intelligence.flake.v1",
        "tests": "not-a-list",
    }
    with pytest.raises(ValueError, match="tests array"):
        build_flaky_test_registry_evidence(
            classification_report=malformed,
            source_kind="operator_review_input",
            source_reference="local-proof",
        )


def test_flaky_test_registry_rejects_non_object_or_unknown_classification_entry() -> None:
    malformed = _classification_report()
    malformed["tests"] = ["not-an-object"]

    with pytest.raises(ValueError, match="non-object entry"):
        build_flaky_test_registry_evidence(
            classification_report=malformed,
            source_kind="operator_review_input",
            source_reference="local-proof",
        )

    unknown = _classification_report()
    unknown["tests"][0]["classification"] = "maybe-flaky"

    with pytest.raises(ValueError, match="unsupported flaky-test classification"):
        build_flaky_test_registry_evidence(
            classification_report=unknown,
            source_kind="operator_review_input",
            source_reference="local-proof",
        )
