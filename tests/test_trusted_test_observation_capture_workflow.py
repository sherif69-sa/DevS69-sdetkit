from __future__ import annotations

from pathlib import Path

WORKFLOW = Path(".github/workflows/ci.yml")


def _full_ci_text() -> str:
    text = WORKFLOW.read_text(encoding="utf-8")
    return text.split("  full-ci:", 1)[1]


def test_full_ci_emits_junit_for_raw_observation_capture_without_extra_test_run() -> None:
    full_ci = _full_ci_text()
    coverage_block = full_ci.split("- name: Coverage gate", 1)[1].split(
        "- name: Normalize trusted-main test observations", 1
    )[0]

    assert 'PYTEST_ADDOPTS: "-n auto"' in full_ci
    assert "--junitxml=${{ runner.temp }}/sdetkit-trusted-test-input/junit.xml" in coverage_block
    assert "- name: Coverage gate" in full_ci
    assert "id: coverage" in full_ci
    assert full_ci.count("bash quality.sh cov") == 1
    assert "python -m sdetkit.trusted_test_observation_capture" in full_ci


def test_full_ci_does_not_use_runner_context_in_job_level_environment() -> None:
    full_ci = _full_ci_text()
    before_steps = full_ci.split("    steps:", 1)[0]

    assert 'PYTEST_ADDOPTS: "-n auto"' in before_steps
    assert "runner.temp" not in before_steps


def test_full_ci_captures_observations_only_from_trusted_main_push() -> None:
    full_ci = _full_ci_text()

    capture_guard = (
        "github.event_name == 'push' && github.ref == 'refs/heads/main' "
        "&& steps.coverage.outcome != 'skipped'"
    )
    upload_guard = (
        "github.event_name == 'push' && github.ref == 'refs/heads/main' "
        "&& steps.trusted_observations.outputs.artifact_written == 'true'"
    )
    assert full_ci.count(capture_guard) == 1
    assert full_ci.count(upload_guard) == 1
    assert "id: trusted_observations" in full_ci
    assert '--source-workflow "CI"' in full_ci
    assert '--source-job "Full CI lane"' in full_ci
    assert '--event-name "${GITHUB_EVENT_NAME}"' in full_ci
    assert '--ref-name "${GITHUB_REF}"' in full_ci


def test_full_ci_skips_observation_artifact_when_pytest_never_writes_junit() -> None:
    full_ci = _full_ci_text()

    assert 'if [[ ! -s "${RUNNER_TEMP}/sdetkit-trusted-test-input/junit.xml" ]]; then' in full_ci
    assert 'echo "trusted_test_observations=not_available_no_junit"' in full_ci
    assert 'echo "artifact_written=false" >> "${GITHUB_OUTPUT}"' in full_ci
    assert 'echo "artifact_written=true" >> "${GITHUB_OUTPUT}"' in full_ci
    assert "steps.trusted_observations.outputs.artifact_written == 'true'" in full_ci


def test_full_ci_uploads_normalized_observations_not_raw_junit_or_example_data() -> None:
    full_ci = _full_ci_text()
    upload = full_ci.split("- name: Upload trusted-main test observation artifact", 1)[1]

    assert "trusted-test-observations.json" in upload
    assert "trusted-test-observations.md" in upload
    assert "junit.xml" not in upload
    assert "examples/kits/intelligence/flake-history.json" not in full_ci
    assert "intelligence flake classify" not in full_ci
