"""One failure engine, shared by investigate, the gate and the diagnose chain."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from sdetkit import check_intelligence, ci_failure_extractor, investigate
from sdetkit.diagnostic_vector_engine import build_diagnostic_vector
from sdetkit.evidence import evidence
from sdetkit.failure_vector_adapters import diagnosis_code, extract_ecosystem_failure_vector
from sdetkit.remediation_plan_engine import build_remediation_plan

ECOSYSTEM_LOGS = {
    "go": (
        "Run go test ./...\n--- FAIL: TestAdd (0.00s)\n"
        "    calc_test.go:12: expected 3, got 4\nFAIL\nProcess completed with exit code 1\n",
        "GO_TEST_FAILURE",
        "calc_test.go",
    ),
    "rust": (
        "Run cargo test\ntest tests::adds ... FAILED\nfailures:\n"
        "thread 'tests::adds' panicked at src/lib.rs:10:5:\nassertion failed\n"
        "Process completed with exit code 101\n",
        "RUST_TEST_FAILURE",
        "src/lib.rs",
    ),
    "java": (
        "Run mvn test\n[ERROR] Tests run: 3, Failures: 1\n"
        "[ERROR] src/test/java/CalcTest.java:[14,9] assertion\n"
        "Process completed with exit code 1\n",
        "JAVA_TEST_FAILURE",
        "src/test/java/CalcTest.java",
    ),
    "javascript_typescript": (
        "Run npx tsc --noEmit\n"
        "src/app.ts(3,7): error TS2322: Type 'string' is not assignable to type 'number'.\n"
        "Process completed with exit code 2\n",
        "JAVASCRIPT_TYPESCRIPT_TYPE_FAILURE",
        "src/app.ts",
    ),
    "dotnet": (
        "Run dotnet test\n  Failed CalcTests.Adds [12 ms]\n  Error Message:\n"
        "   Assert.Equal() Failure\n"
        "  at CalcTests.Adds() in src/Calc.Tests/CalcTests.cs:line 14\n"
        "Process completed with exit code 1\n",
        "DOTNET_TEST_FAILURE",
        "src/Calc.Tests/CalcTests.cs",
    ),
    "cpp": (
        "$ clang++ -c src/main.cpp\nsrc/main.cpp:3:1: error: expected expression\n"
        "Process completed with exit code 1\n",
        "CPP_COMPILE_FAILURE",
        "src/main.cpp",
    ),
}

FORMAT_LOG = (
    "Run python -m ruff format --check src\n"
    "Would reformat: src/app.py\n"
    "1 file would be reformatted\n"
    "Process completed with exit code 1\n"
)


@pytest.mark.parametrize("ecosystem", sorted(ECOSYSTEM_LOGS))
def test_investigate_classifies_every_supported_ecosystem(ecosystem: str) -> None:
    log, code, affected = ECOSYSTEM_LOGS[ecosystem]

    payload = investigate._payload_for_failure(log)

    assert payload["ecosystem"] == ecosystem
    assert payload["classification"] == code
    assert affected in payload["failure_vector"]["affected_files"]
    assert payload["requires_human_review"] is True
    assert payload["safe_to_auto_fix"] is False


def test_python_investigation_keeps_adaptive_diagnosis_and_adds_the_vector() -> None:
    payload = investigate._payload_for_failure(
        "Run python -m pytest -q\nFAILED tests/test_x.py::test_a - AssertionError: assert 1 == 2\n"
        "Process completed with exit code 1\n"
    )

    assert payload["classification"] == "PYTEST_ASSERTION_FAILURE"
    assert payload["ecosystem"] == "python"
    assert payload["failure_vector"]["failure_class"] == "test"


@pytest.mark.parametrize("ecosystem", sorted(ECOSYSTEM_LOGS))
def test_vector_json_carries_the_safety_gate_decision(ecosystem: str) -> None:
    log, code, _ = ECOSYSTEM_LOGS[ecosystem]

    result = extract_ecosystem_failure_vector(log)
    payload = result.to_dict()

    assert diagnosis_code(result) == code
    gate = payload["safety_gate"]
    assert gate["schema_version"] == "sdetkit.safety_gate.v1"
    assert gate["automation_allowed"] is False
    assert gate["merge_authorized"] is False
    assert gate["safe_fix_allowed"] is False
    assert gate["review_first"] is True


def test_extractor_uses_one_classifier_for_records_and_vectors(tmp_path: Path) -> None:
    log = tmp_path / "tests" / "ci_log.txt"
    log.parent.mkdir()
    log.write_text(
        "Run python -m pytest -q\n"
        "FAILED tests/test_widget.py::test_contract - AssertionError\n"
        "ruff format would reformat nothing\n"
        "Process completed with exit code 1\n",
        encoding="utf-8",
    )

    records = ci_failure_extractor.build_failed_check_logs([log])
    bundle = ci_failure_extractor.write_failure_vector_artifacts(
        [log], json_out=tmp_path / "vectors.json"
    )

    record = records["failed_checks"][0]
    vector = bundle["failure_vectors"][0]
    assert record["failure_class"] == vector["failure_class"] == "test"
    assert record["ecosystem"] == "python"
    assert record["safety_gate"]["schema_version"] == "sdetkit.safety_gate.v1"
    assert bundle["summary"]["by_ecosystem"] == {"python": 1}


def test_ci_log_output_feeds_checks_vector_and_remediation(tmp_path: Path) -> None:
    log = tmp_path / "lint" / "ci_log.txt"
    log.parent.mkdir()
    log.write_text(FORMAT_LOG, encoding="utf-8")
    failed_check_logs = tmp_path / "failed-check-logs.json"
    ci_failure_extractor.write_failed_check_logs([log], failed_check_logs)

    intelligence = check_intelligence.build_check_intelligence(
        checks_json=failed_check_logs, current_head_sha="abc123"
    )
    failed = intelligence["failed_checks"]
    assert len(failed) == 1
    assert failed[0]["code"] == "PRE_COMMIT_FORMAT_DRIFT"
    assert failed[0]["first_failure"]["tool"] == "ruff"
    assert failed[0]["safe_to_auto_fix"] is True
    assert failed[0]["current_pr_head_sha"] == "abc123"

    vector = build_diagnostic_vector(check_intelligence=intelligence)
    diagnosis = vector["diagnoses"][0]
    assert diagnosis["failure_surface"] == "formatting"
    assert diagnosis["safe_fix_candidate"] is True

    plan = build_remediation_plan(vector)
    assert plan["summary"]["executable_plan_count"] == 1
    assert plan["plans"][0]["allowed_strategy"] == "run_pre_commit"


def test_checks_engine_fallback_names_non_python_failures(tmp_path: Path) -> None:
    log, code, _ = ECOSYSTEM_LOGS["go"]
    checks = tmp_path / "checks.json"
    checks.write_text(
        json.dumps({"checks": [{"name": "go", "conclusion": "failure", "log": log}]}),
        encoding="utf-8",
    )

    intelligence = check_intelligence.build_check_intelligence(checks_json=checks)

    assert intelligence["failed_checks"][0]["code"] == code


def test_evidence_validate_rejects_a_zip_without_a_file_manifest(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pack = tmp_path / "evidence.zip"
    with zipfile.ZipFile(pack, "w") as zf:
        zf.writestr("manifest.json", json.dumps({"contents": ["verdict.json"]}))
        zf.writestr("verdict.json", "{}")

    rc = evidence._validate(pack, format="json")

    payload = json.loads(capsys.readouterr().out)
    assert rc != 0
    assert payload["ok"] is False
    assert payload["failures"][0]["code"] == "manifest_files_missing"


def test_core_exports_the_sqlite_scalar_helpers() -> None:
    import sdetkit.core as core

    assert callable(core.register_scalar_function)
    assert issubclass(core.ScalarFunctionRegistrationError, Exception)
