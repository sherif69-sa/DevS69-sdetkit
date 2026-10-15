from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
# Pinned to a full commit SHA; Dependabot moves the SHA itself.
_SHA_PIN = r"@[0-9a-f]{40}\b"
PUBLISH_ACTION = re.compile(r"pypa/gh-action-pypi-publish" + _SHA_PIN)
PROVENANCE_ACTION = re.compile(r"actions/attest-build-provenance" + _SHA_PIN)
CHECKOUT_ACTION = re.compile(r"actions/checkout" + _SHA_PIN)


def _workflow() -> str:
    return RELEASE_WORKFLOW.read_text(encoding="utf-8")


def _pinned(action: re.Pattern[str], text: str) -> int:
    match = action.search(text)
    assert match, f"{action.pattern} not found"
    return match.start()


def _section(text: str, start: str, end: str) -> str:
    return text[text.index(start) : text.index(end)]


def test_release_workflow_uses_trusted_publishing_without_long_lived_token() -> None:
    text = _workflow()

    assert "PYPI_API_TOKEN" not in text
    assert "TWINE_PASSWORD" not in text
    assert "Publish with PyPI Trusted Publishing" in text
    _pinned(PUBLISH_ACTION, text)
    assert "# v1.14.2" in text
    assert "environment:\n      name: pypi" in text
    assert "permissions:\n      id-token: write" in text


def test_release_dispatch_input_is_validated_before_shell_use() -> None:
    text = _workflow()
    resolve_step = _section(
        text,
        "      - name: Resolve and validate tag",
        "      - name: Checkout requested tag",
    )

    assert "REQUESTED_TAG: ${{ inputs.tag }}" in resolve_step
    assert 'candidate="${REQUESTED_TAG:-}"' in resolve_step
    assert '[[ "$candidate" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]' in resolve_step
    assert "${{ inputs.tag }}" not in resolve_step.split("run: |", 1)[1]
    assert "Release tag must match vX.Y.Z" in resolve_step


def test_release_manifest_uses_validated_environment_values() -> None:
    text = _workflow()
    build_step = _section(
        text,
        "      - name: Build and validate distributions",
        "      - uses: actions/upload-artifact@",
    )

    assert "RELEASE_TAG: ${{ steps.tag.outputs.value }}" in build_step
    assert "RELEASE_VERSION: ${{ steps.meta.outputs.version }}" in build_step
    assert "SOURCE_SHA: ${{ steps.meta.outputs.source_sha }}" in build_step
    assert "scripts/build_release_distribution_manifest.py" in build_step
    assert '--tag "$RELEASE_TAG"' in build_step
    assert '--version "$RELEASE_VERSION"' in build_step
    assert '--source-sha "$SOURCE_SHA"' in build_step
    assert "${{ inputs.tag }}" not in build_step


def test_release_workflow_builds_once_and_qualifies_exact_wheel() -> None:
    text = _workflow()

    # The local-equivalent comment and the build step are both counted.
    assert text.count("python -m build") == 2
    assert 'python-version: ["3.10", "3.11", "3.12"]' in text
    assert "name: release-distributions" in text
    assert "Install exact release wheel in clean-room venv" in text
    assert "path: ${{ runner.temp }}/release-candidate" in text
    assert 'wheel="$(find "$RUNNER_TEMP/release-candidate/dist"' in text
    assert 'python -m venv "$RUNNER_TEMP/release-venv"' in text
    assert '"$RUNNER_TEMP/release-venv/bin/python" -m pip install' in text
    assert '-c constraints-ci.txt --force-reinstall "$wheel"' in text
    assert "-c constraints-ci.txt -r requirements-test.txt" in text
    assert "Exercise installed-wheel product contracts" in text
    assert "tests/contract/check_installed_wheel.py" in text
    assert "Run exact-wheel repository gates" in text
    assert "-m sdetkit gate fast" in text
    assert "-m sdetkit gate release" in text
    assert "-m sdetkit doctor" in text


def test_release_wheel_qualification_preserves_clean_checkout() -> None:
    text = _workflow()
    qualification = _section(text, "  qualify-wheel:", "  attest-github:")

    assert "path: release-candidate" not in qualification
    assert "python -m venv .venv-release" not in qualification
    assert "$RUNNER_TEMP/release-candidate" in qualification
    assert "$RUNNER_TEMP/release-venv" in qualification


def test_release_workflow_attests_publishes_and_verifies_in_order() -> None:
    text = _workflow()

    attest_index = text.index("  attest-github:")
    publish_index = text.index("  publish-pypi:")
    verify_index = text.index("  verify-pypi:")
    release_index = text.index("  github-release:")

    assert attest_index < publish_index < verify_index < release_index
    assert "needs: [build, qualify-wheel, attest-github]" in text
    assert "needs: [build, publish-pypi]" in text
    assert "needs: [build, verify-pypi]" in text
    _pinned(PROVENANCE_ACTION, text)
    assert "scripts/verify_pypi_release.py" in text
    assert "Create GitHub Release after PyPI verification" in text


def test_release_verification_checks_out_exact_tag_before_repository_script() -> None:
    verification = _section(_workflow(), "  verify-pypi:", "  github-release:")

    checkout = _pinned(CHECKOUT_ACTION, verification)
    assert "ref: ${{ needs.build.outputs.tag }}" in verification
    assert "persist-credentials: false" in verification
    assert checkout < verification.index("actions/setup-python@")
    assert checkout < verification.index("scripts/verify_pypi_release.py")


def test_release_workflow_fails_closed_with_narrow_permissions_and_budget() -> None:
    text = _workflow()

    assert "PyPI publish skipped" not in text
    assert "exit 0" not in _section(text, "  publish-pypi:", "  verify-pypi:")
    assert "if-no-files-found: error" in text
    assert "permissions:\n  contents: read\n" in text
    assert text.count("      contents: write") == 1
    assert "      attestations: write" in text
    assert len(text.splitlines()) < 285
