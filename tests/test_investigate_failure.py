import json
from pathlib import Path

from sdetkit import investigate


def test_failure_investigation_wraps_adaptive_diagnosis_without_autofix(tmp_path):
    log = tmp_path / "failure.log"
    log.write_text(
        "AttributeError: SdetAsyncHttpClient object has no attribute "
        "get_json_list_paginated_envelope async parity",
        encoding="utf-8",
    )

    payload = investigate._payload_for_failure(log.read_text(encoding="utf-8"))

    assert payload["schema_version"] == "sdetkit.investigate.failure.v1"
    assert payload["diagnostic_only"] is True
    assert payload["automation_allowed"] is False
    assert payload["classification"] == "MISSING_PUBLIC_API_PARITY"
    assert payload["safe_to_auto_fix"] is False
    assert payload["requires_human_review"] is True
    assert payload["diagnosis"]["diagnoses"][0]["code"] == "MISSING_PUBLIC_API_PARITY"
    assert payload["summary"] == "Missing public API parity detected"
    assert payload["why_it_matters"]
    assert payload["next_actions"] == [
        "Add the missing public API parity and focused regression coverage for both surfaces."
    ]
    assert payload["proof_commands"]
    assert (
        payload["memory_lookup_key"]
        == "diagnosis:MISSING_PUBLIC_API_PARITY:missing-public-api-parity"
    )


def test_failure_investigation_json_cli_writes_output(tmp_path, capsys):
    log = tmp_path / "failure.log"
    out = tmp_path / "investigation.json"
    log.write_text("Exit: Missing test dependencies: hypothesis, yaml.", encoding="utf-8")

    rc = investigate.main(["failure", "--log", str(log), "--format", "json", "--out", str(out)])

    assert rc == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    printed = json.loads(capsys.readouterr().out)
    assert written["classification"] == "MISSING_TEST_DEPENDENCY"
    assert printed["classification"] == "MISSING_TEST_DEPENDENCY"
    assert written["automation_allowed"] is False


def test_failure_investigation_markdown_cli(tmp_path, capsys):
    log = tmp_path / "failure.log"
    log.write_text(
        "TypeError: Resp() takes no arguments because test double defines init_ instead of __init__",
        encoding="utf-8",
    )

    rc = investigate.main(["failure", "--log", str(log), "--format", "markdown"])

    assert rc == 0
    rendered = capsys.readouterr().out
    assert "# Failure investigation" in rendered
    assert "BROKEN_TEST_DOUBLE" in rendered
    assert "automation allowed: **False**" in rendered
    assert "requires human review: **True**" in rendered


def test_failure_investigation_missing_log_returns_2(tmp_path, capsys):
    missing = tmp_path / "missing.log"

    rc = investigate.main(["failure", "--log", str(missing), "--format", "json"])

    assert rc == 2
    assert "error=" in capsys.readouterr().err


def test_failure_markdown_includes_proof_commands():
    payload = {
        "classification": "MISSING_PUBLIC_API_PARITY",
        "confidence": "high",
        "diagnostic_only": True,
        "automation_allowed": False,
        "safe_to_auto_fix": False,
        "requires_human_review": True,
        "summary": "Missing public API parity detected.",
        "why_it_matters": "Users can hit runtime AttributeError.",
        "next_actions": ["Add parity coverage."],
        "proof_commands": ["python -m pytest -q tests/test_netclient_envelope_parity.py"],
        "memory_lookup_key": "diagnosis:MISSING_PUBLIC_API_PARITY:netclient",
    }

    rendered = investigate.render_failure_markdown(payload)

    assert "## Proof commands" in rendered
    assert "python -m pytest -q tests/test_netclient_envelope_parity.py" in rendered
    assert "diagnosis:MISSING_PUBLIC_API_PARITY:netclient" in rendered


def test_python_m_sdetkit_investigate_failure_outputs_json(tmp_path):
    import os
    import subprocess
    import sys

    log = tmp_path / "failure.log"
    log.write_text(
        "AttributeError: SdetAsyncHttpClient object has no attribute "
        "get_json_list_paginated_envelope async parity",
        encoding="utf-8",
    )

    env = dict(os.environ)
    env["PYTHONPATH"] = "src"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sdetkit",
            "investigate",
            "failure",
            "--log",
            str(log),
            "--format",
            "json",
        ],
        cwd=Path.cwd(),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["classification"] == "MISSING_PUBLIC_API_PARITY"
    assert payload["automation_allowed"] is False


def test_failure_investigation_can_emit_failure_bundle(tmp_path, capsys):
    log = tmp_path / "failure.log"
    out = tmp_path / "investigation.json"
    bundle_dir = tmp_path / "failure-intelligence"
    log.write_text(
        "\n".join(
            [
                "Traceback (most recent call last):",
                '  File "scripts/custom_policy.py", line 10, in <module>',
                '    raise RuntimeError("unexpected integrity result")',
                "RuntimeError: unexpected integrity result",
            ]
        ),
        encoding="utf-8",
    )

    rc = investigate.main(
        [
            "failure",
            "--log",
            str(log),
            "--format",
            "json",
            "--failure-bundle-out-dir",
            str(bundle_dir),
            "--out",
            str(out),
        ]
    )

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    written = json.loads(out.read_text(encoding="utf-8"))
    assert printed["failure_bundle"] == written["failure_bundle"]
    bundle = written["failure_bundle"]
    assert bundle["schema_version"] == "sdetkit.adaptive.failure_bundle.v1"
    assert bundle["primary_diagnosis_code"] == "UNKNOWN_REVIEW_REQUIRED"
    assert bundle["review_first"] is True
    assert bundle["safe_to_auto_fix"] is False
    assert Path(bundle["bundle_path"]).exists()
    assert Path(bundle["artifacts"]["operator_brief_markdown"]).exists()


def test_failure_investigation_bundle_markdown_handoff(tmp_path, capsys):
    log = tmp_path / "failure.log"
    bundle_dir = tmp_path / "failure-intelligence"
    log.write_text(
        "FAILED tests/test_widget.py::test_contract - AssertionError: expected stable evidence",
        encoding="utf-8",
    )

    rc = investigate.main(
        [
            "failure",
            "--log",
            str(log),
            "--format",
            "markdown",
            "--failure-bundle-out-dir",
            str(bundle_dir),
        ]
    )

    assert rc == 0
    rendered = capsys.readouterr().out
    assert "## Failure intelligence bundle" in rendered
    assert "PYTEST_ASSERTION_FAILURE" in rendered
    assert "operator-brief.md" in rendered


def test_failure_investigation_green_bundle_stays_clear(tmp_path, capsys):
    log = tmp_path / "green.log"
    bundle_dir = tmp_path / "failure-intelligence"
    log.write_text(
        "\n".join(
            [
                "[quality] running coverage :: Coverage lane",
                "quality.sh cov passed",
                "[quality] blocking failures: none",
                "[quality] merge/release recommendation: ready-for-merge-review",
            ]
        ),
        encoding="utf-8",
    )

    rc = investigate.main(
        [
            "failure",
            "--log",
            str(log),
            "--format",
            "json",
            "--failure-bundle-out-dir",
            str(bundle_dir),
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    bundle = payload["failure_bundle"]
    assert bundle["status"] == "clear"
    assert bundle["diagnosis_count"] == 0
    assert bundle["primary_diagnosis_code"] == ""
    assert bundle["review_first"] is False
