from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from pytest import MonkeyPatch

from sdetkit import adaptive_failure_bundle


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_failure_bundle_builds_full_operator_handoff_for_known_red(tmp_path: Path) -> None:
    log = _write(
        tmp_path / "coverage.log",
        "\n".join(
            [
                "[quality] running coverage :: Coverage lane",
                "[quality] coverage config: scope=core mode=standard fail-under=85",
                "Required test coverage of 85% not reached. Total coverage: 81.42%",
                "[quality] blocking failures: coverage gate failed",
                "[quality] merge/release recommendation: needs-fix",
            ]
        ),
    )

    bundle = adaptive_failure_bundle.build_failure_bundle(
        log_path=log,
        out_dir=tmp_path / "bundle",
        proof_failed=True,
    )

    assert bundle["schema_version"] == "sdetkit.adaptive.failure_bundle.v1"
    assert bundle["status"] == "needs_fix"
    assert bundle["primary_diagnosis_code"] == "COVERAGE_GATE_REGRESSION"
    assert bundle["review_first"] is False
    assert bundle["safe_to_auto_fix"] is False

    artifacts = bundle["artifacts"]
    for key in [
        "diagnosis_json",
        "pr_comment_markdown",
        "learning_db",
        "learning_summary_json",
        "safe_fix_plan_json",
        "patch_plan_json",
        "operator_brief_markdown",
        "artifact_manifest_json",
    ]:
        assert Path(artifacts[key]).exists(), key

    comment = Path(artifacts["pr_comment_markdown"]).read_text(encoding="utf-8")
    assert "### Adaptive Diagnosis" in comment
    assert "### Review-first Adaptive Diagnosis" not in comment

    learning = json.loads(Path(artifacts["learning_summary_json"]).read_text(encoding="utf-8"))
    assert learning["ok"] is True
    assert learning["diagnosis_records"] >= 1


def test_failure_bundle_keeps_unknown_failures_review_first(tmp_path: Path) -> None:
    log = _write(
        tmp_path / "unknown.log",
        "\n".join(
            [
                "Traceback (most recent call last):",
                '  File "scripts/custom_policy.py", line 10, in <module>',
                '    raise RuntimeError("unexpected integrity result")',
                "RuntimeError: unexpected integrity result",
            ]
        ),
    )

    bundle = adaptive_failure_bundle.build_failure_bundle(
        log_path=log,
        out_dir=tmp_path / "bundle",
        proof_failed=True,
    )

    assert bundle["status"] == "needs_fix"
    assert bundle["primary_diagnosis_code"] == "UNKNOWN_REVIEW_REQUIRED"
    assert bundle["review_first"] is True
    assert bundle["safe_to_auto_fix"] is False

    comment = Path(bundle["artifacts"]["pr_comment_markdown"]).read_text(encoding="utf-8")
    assert "### Review-first Adaptive Diagnosis" in comment
    assert "current evidence is not safe for automatic remediation" in comment

    safe_fix = json.loads(
        Path(bundle["artifacts"]["safe_fix_plan_json"]).read_text(encoding="utf-8")
    )
    assert safe_fix["safe_to_auto_fix"] is False
    assert safe_fix["fix_type"] == "review_required"


def test_failure_bundle_green_log_stays_quiet(tmp_path: Path) -> None:
    log = _write(
        tmp_path / "green.log",
        "\n".join(
            [
                "[quality] running coverage :: Coverage lane",
                "quality.sh cov passed",
                "✅ quality.sh cov passed",
            ]
        ),
    )

    bundle = adaptive_failure_bundle.build_failure_bundle(
        log_path=log,
        out_dir=tmp_path / "bundle",
    )

    assert bundle["status"] == "clear"
    assert bundle["diagnosis_count"] == 0
    assert bundle["primary_diagnosis_code"] == ""
    assert bundle["review_first"] is False
    assert bundle["safe_to_auto_fix"] is False

    comment = Path(bundle["artifacts"]["pr_comment_markdown"]).read_text(encoding="utf-8")
    assert "Adaptive Diagnosis" not in comment
    assert "Review-first Adaptive Diagnosis" not in comment


def test_sdetkit_adaptive_failure_bundle_subprocess(tmp_path: Path) -> None:
    log = _write(
        tmp_path / "pytest.log",
        "\n".join(
            [
                "FAILED tests/test_widget.py::test_widget_contract - AssertionError: expected stable evidence",
                "=========================== short test summary info ===========================",
                "FAILED tests/test_widget.py::test_widget_contract",
            ]
        ),
    )
    out_dir = tmp_path / "bundle"

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "sdetkit",
            "adaptive",
            "failure-bundle",
            "--log",
            str(log),
            "--out-dir",
            str(out_dir),
            "--proof-failed",
            "--format",
            "json",
        ],
        text=True,
        capture_output=True,
    )

    assert proc.returncode == 0, proc.stderr + proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["schema_version"] == "sdetkit.adaptive.failure_bundle.v1"
    assert payload["primary_diagnosis_code"] == "PYTEST_ASSERTION_FAILURE"
    assert Path(payload["bundle_path"]).exists()
    assert Path(payload["artifacts"]["operator_brief_markdown"]).exists()


def test_failure_bundle_exposes_complete_diagnosis_set_for_graph_consumers(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    diagnoses = [
        {
            "code": "PACKAGE_INSTALL_FAILURE",
            "title": "Dependency resolver failed",
            "diagnosis": "pip could not resolve constraints before tests could prove behavior.",
            "severity": "high",
            "confidence": "high",
            "affected_files": ["constraints-ci.txt", "requirements-test.txt"],
            "recommended_fix": ["Align the smallest dependency surface."],
            "proof_commands": [
                "python -m pip install -c constraints-ci.txt -r requirements-test.txt -e ."
            ],
        },
        {
            "code": "SECURITY_FINDING_REVIEW_REQUIRED",
            "title": "Security finding requires review",
            "diagnosis": "A protected security surface emitted a review-first finding.",
            "severity": "high",
            "confidence": "high",
            "affected_files": ["docs/security-posture.md"],
            "recommended_fix": ["Inspect the security finding and affected surface."],
            "proof_commands": ["python -m pre_commit run -a"],
        },
    ]

    diagnosis = {
        "schema_version": "sdetkit.adaptive.diagnosis.v1",
        "ok": False,
        "status": "needs_fix",
        "risk_score": 100,
        "confidence": "high",
        "summary": "Primary issue: Dependency resolver failed. Fix this before release signoff.",
        "diagnosis_count": len(diagnoses),
        "diagnoses": diagnoses,
        "fix_plan": [],
        "scenario_database": {},
        "scenario_codes": [],
    }

    def fake_analyze_evidence(*, log_text: str) -> dict[str, object]:
        assert "synthetic multi-domain failure" in log_text
        return diagnosis

    monkeypatch.setattr(
        adaptive_failure_bundle.adaptive_diagnosis,
        "analyze_evidence",
        fake_analyze_evidence,
    )

    log = _write(tmp_path / "failure.log", "synthetic multi-domain failure\n")
    bundle = adaptive_failure_bundle.build_failure_bundle(
        log_path=log,
        out_dir=tmp_path / "bundle",
        proof_failed=True,
    )

    assert bundle["primary_diagnosis_code"] == "PACKAGE_INSTALL_FAILURE"
    assert bundle["primary_diagnosis_title"] == "Dependency resolver failed"
    assert bundle["diagnosis_count"] == 2
    assert bundle["diagnosis_codes"] == [
        "PACKAGE_INSTALL_FAILURE",
        "SECURITY_FINDING_REVIEW_REQUIRED",
    ]
    assert bundle["diagnoses"] == diagnoses
    assert bundle["diagnosis"]["diagnoses"] == diagnoses

    manifest = json.loads(
        Path(bundle["artifacts"]["artifact_manifest_json"]).read_text(encoding="utf-8")
    )
    assert manifest["diagnosis_codes"] == bundle["diagnosis_codes"]

    from sdetkit.evidence_graph import build_evidence_graph

    graph = build_evidence_graph(failure_bundle=Path(str(bundle["bundle_path"])))
    assert graph["source_summary"][-1]["source"] == "failure_bundle"
    assert graph["source_summary"][-1]["findings_seen"] == 2
    assert graph["source_summary"][-1]["findings_emitted"] == 2

    nodes = {node["title"]: node for node in graph["nodes"]}
    assert nodes["Dependency resolver failed"]["risk_surface"] == "dependency"
    assert nodes["Dependency resolver failed"]["review_first"] is True
    assert nodes["Security finding requires review"]["risk_surface"] == "security"
    assert nodes["Security finding requires review"]["review_first"] is True


def test_failure_bundle_successful_proof_does_not_promote_failure_shaped_fixture_text(
    tmp_path: Path,
) -> None:
    log = _write(
        tmp_path / "green-with-failure-shaped-fixture-text.log",
        "\n".join(
            [
                "[quality] running coverage :: Coverage lane",
                "tests/test_fixture_contract.py::test_rendered_message_contains coverage failure wording PASSED",
                "Required test coverage of 95% reached. Total coverage: 96.69%",
                "[quality] final verdict contract: sdetkit.final-verdict.v2",
                "[quality] blocking failures: none",
                "[quality] merge/release recommendation: ready-for-merge-review",
            ]
        ),
    )

    bundle = adaptive_failure_bundle.build_failure_bundle(
        log_path=log,
        out_dir=tmp_path / "passed-bundle",
        proof_passed=True,
    )

    assert bundle["status"] == "clear"
    assert bundle["diagnosis_count"] == 0
    assert bundle["primary_diagnosis_code"] == ""
    assert bundle["review_first"] is False
    assert bundle["safe_to_auto_fix"] is False
    assert bundle["proof_outcome"] == "passed"
    assert bundle["raw_log_promoted"] is False
    assert bundle["diagnosis"]["evidence"]["raw_log_promoted"] is False

    manifest = json.loads(
        Path(bundle["artifacts"]["artifact_manifest_json"]).read_text(encoding="utf-8")
    )
    assert manifest["proof_outcome"] == "passed"
    assert manifest["raw_log_promoted"] is False


def test_failure_bundle_failed_proof_still_promotes_failure_shaped_log_for_review(
    tmp_path: Path,
) -> None:
    log = _write(
        tmp_path / "failed-with-failure-shaped-text.log",
        "custom check emitted coverage failure wording without a recognized repair route\n",
    )

    bundle = adaptive_failure_bundle.build_failure_bundle(
        log_path=log,
        out_dir=tmp_path / "failed-bundle",
        proof_failed=True,
    )

    assert bundle["status"] == "needs_fix"
    assert bundle["primary_diagnosis_code"] == "UNKNOWN_REVIEW_REQUIRED"
    assert bundle["review_first"] is True
    assert bundle["proof_outcome"] == "failed"
    assert bundle["raw_log_promoted"] is True
