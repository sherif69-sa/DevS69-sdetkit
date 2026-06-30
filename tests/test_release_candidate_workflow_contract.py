from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_candidate_replay_artifact_is_sha_bound() -> None:
    text = (ROOT / ".github/workflows/adoption-real-repo-canonical.yml").read_text()
    assert "adoption-real-repo-canonical-${{ github.sha }}" in text
    assert "permissions:\n  contents: read\n" in text


def test_release_matrix_covers_supported_python_versions() -> None:
    text = (ROOT / ".github/workflows/release.yml").read_text()
    assert 'python-version: ["3.10", "3.11", "3.12"]' in text
    assert "tests/contract/check_installed_wheel.py" in text
