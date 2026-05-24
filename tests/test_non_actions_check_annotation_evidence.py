from __future__ import annotations

import json
from pathlib import Path

from sdetkit import check_intelligence, safe_remediation_eligibility
from sdetkit import failed_check_log_collection as collection


def _failed_security_check() -> dict:
    return {
        "name": "sdetkit-security-gate",
        "status": "completed",
        "conclusion": "failure",
        "head_sha": "pr-head",
        "current_pr_head_sha": "pr-head",
        "url": "https://api.github.com/repos/sherif69-sa/DevS69-sdetkit/check-runs/77563773066",
        "details_url": "https://github.com/sherif69-sa/DevS69-sdetkit/runs/77563773066",
        "required": False,
    }


def _write_checks(path: Path) -> Path:
    path.write_text(json.dumps({"check_runs": [_failed_security_check()]}), encoding="utf-8")
    return path


def test_manifest_routes_non_actions_failed_check_to_annotation_collection(tmp_path: Path) -> None:
    manifest = collection.build_failed_check_log_manifest(
        checks_json=_write_checks(tmp_path / "checks.json"),
        out_dir=tmp_path / "out",
    )

    item = manifest["logs"][0]
    assert item["run_id"] == ""
    assert item["check_run_id"] == "77563773066"
    assert item["download_supported"] is False
    assert item["annotation_collection_supported"] is True
    assert item["evidence_source"] == "github_check_run_annotations"

    script = collection.render_download_script(manifest)
    assert "check-runs/77563773066/annotations?per_page=100" in script
    assert "--sanitize-annotations-json" in script
    assert 'rm -f "$raw_annotations"' in script


def test_sanitizer_persists_only_safe_annotation_metadata_and_exact_line(tmp_path: Path) -> None:
    raw_path = tmp_path / "raw.json"
    log_path = tmp_path / "out" / "01-sdetkit-security-gate.log"
    evidence_path = tmp_path / "out" / "01-sdetkit-security-gate.annotations.json"
    raw_message = "Sensitive flagged source excerpt should never persist."
    raw_details = "Raw internal detail should never persist."
    raw_path.write_text(
        json.dumps(
            [
                {
                    "annotation_level": "failure",
                    "path": "tests/test_trusted_test_observation_capture.py",
                    "start_line": 203,
                    "end_line": 203,
                    "title": "Secret-like pattern",
                    "message": raw_message,
                    "raw_details": raw_details,
                }
            ]
        ),
        encoding="utf-8",
    )

    report = collection.sanitize_check_run_annotations(
        raw_annotations_json=raw_path,
        annotation_log_target=log_path,
        annotation_json_target=evidence_path,
    )

    serialized = evidence_path.read_text(encoding="utf-8")
    line = log_path.read_text(encoding="utf-8")
    assert report["annotation_count"] == 1
    assert report["raw_message_text_persisted"] is False
    assert report["raw_details_text_persisted"] is False
    assert raw_message not in serialized
    assert raw_details not in serialized
    assert raw_message not in line
    assert raw_details not in line
    assert (
        "GitHub check annotation failure: Secret-like pattern at "
        "tests/test_trusted_test_observation_capture.py:203"
    ) in line


def test_annotation_evidence_becomes_exact_security_diagnosis_but_never_safe_fix(
    tmp_path: Path,
) -> None:
    checks_path = _write_checks(tmp_path / "checks.json")
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    (logs_dir / "01-sdetkit-security-gate.log").write_text(
        "GitHub check annotation failure: Secret-like pattern at "
        "tests/test_trusted_test_observation_capture.py:203\n",
        encoding="utf-8",
    )
    (logs_dir / "01-sdetkit-security-gate.annotations.json").write_text(
        json.dumps(
            {
                "annotation_count": 1,
                "annotations": [{"annotation_level": "failure"}],
                "raw_message_text_persisted": False,
            }
        ),
        encoding="utf-8",
    )

    intelligence = check_intelligence.build_check_intelligence(
        checks_json=checks_path,
        logs_dir=logs_dir,
        current_head_sha="pr-head",
    )
    failure = intelligence["failed_checks"][0]
    first = failure["first_failure"]

    assert failure["log_collected"] is True
    assert first["tool"] == "github_checks"
    assert first["kind"] == "check_run_annotation"
    assert "tests/test_trusted_test_observation_capture.py:203" in first["line"]
    assert failure["diagnosis"]["code"] == "SECURITY_FINDING_REVIEW_REQUIRED"
    assert failure["surface"] == "security"
    assert failure["safe_to_auto_fix"] is False
    assert failure["safe_remediation"]["category"] == "review_first"


def test_formatting_like_check_annotation_remains_review_first() -> None:
    result = safe_remediation_eligibility.classify_check_failure(
        name="custom-check",
        first_failure={
            "kind": "check_run_annotation",
            "line": "GitHub check annotation failure: ruff format would reformat src/sdetkit/a.py:1",
        },
    )
    assert result["safe_to_auto_fix"] is False
    assert result["strategy"] == safe_remediation_eligibility.REVIEW_FIRST_STRATEGY
    assert "cannot authorize mutation" in result["reason"]
