from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

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
