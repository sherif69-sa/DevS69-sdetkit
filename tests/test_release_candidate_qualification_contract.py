from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "release-candidate.yml"


def _workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_candidate_workflow_is_pre_tag_and_non_publishing() -> None:
    text = _workflow()

    assert "name: Release Candidate Qualification" in text
    assert "workflow_dispatch:" in text
    assert "pull_request:" in text
    assert "push:" in text
    assert "branches: [main]" in text
    assert "cancel-in-progress: ${{ github.event_name == 'pull_request' }}" in text
    assert "permissions:\n  contents: read" in text
    assert "id-token: write" not in text
    assert "contents: write" not in text
    assert "pypa/gh-action-pypi-publish" not in text
    assert "softprops/action-gh-release" not in text
    assert "publish_authorized" in text
    assert '"publication_attempted": False' in text
    assert '"tag_created": False' in text


def test_candidate_workflow_builds_once_and_qualifies_exact_wheel() -> None:
    text = _workflow()

    assert text.count("python -m build") == 1
    assert 'python-version: ["3.10", "3.11", "3.12"]' in text
    assert "name: release-candidate-distributions" in text
    assert "Install exact candidate wheel in clean-room venv" in text
    assert "path: ${{ runner.temp }}/release-candidate" in text
    assert 'wheel="$(find "$RUNNER_TEMP/release-candidate/dist"' in text
    assert 'python -m venv "$RUNNER_TEMP/release-candidate-venv"' in text
    assert '"$RUNNER_TEMP/release-candidate-venv/bin/python" -m pip install' in text
    assert '-c constraints-ci.txt --force-reinstall "$wheel"' in text
    assert "-c constraints-ci.txt -r requirements-test.txt" in text
    assert "Exercise installed-wheel product contracts" in text
    assert "tests/contract/check_installed_wheel.py" in text
    assert "Run exact-wheel repository gates" in text
    assert "-m sdetkit gate fast" in text
    assert "-m sdetkit gate release" in text
    assert "-m sdetkit doctor" in text
    assert "release-candidate-qualification-py${{ matrix.python-version }}" in text


def test_candidate_wheel_qualification_preserves_clean_checkout() -> None:
    text = _workflow()
    qualification = text[text.index("  qualify-wheel:") : text.index("  qualification-verdict:")]

    assert "path: release-candidate" not in qualification
    assert "python -m venv .venv-release-candidate" not in qualification
    assert "$RUNNER_TEMP/release-candidate" in qualification
    assert "$RUNNER_TEMP/release-candidate-venv" in qualification


def test_candidate_workflow_preserves_release_quality_contracts() -> None:
    text = _workflow()

    assert "scripts/release_preflight.py" in text
    assert "scripts/check_release_tag_version.py" in text
    assert "bash quality.sh cov" in text
    assert "python -m mkdocs build --strict" in text
    assert "python -m twine check dist/*" in text
    assert "python -m check_wheel_contents --ignore W009 dist/*.whl" in text
    assert "scripts/build_release_distribution_manifest.py" in text
    assert "if-no-files-found: error" in text


def test_candidate_evidence_keeps_external_authority_unverified() -> None:
    text = _workflow()

    assert '"external_settings_verified": False' in text
    assert '"publish_authorized": False' in text
    assert "GitHub environment pypi protection" in text
    assert "PyPI Trusted Publisher binding" in text
    assert "verify external publishing settings before creating v1.1.0" in text
    assert "Record qualification verdict" in text
