from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_distribution_manifest_records_exact_wheel_and_sdist(tmp_path: Path) -> None:
    module = _module(
        "build_release_distribution_manifest",
        ROOT / "scripts/build_release_distribution_manifest.py",
    )
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "sdetkit-1.1.0-py3-none-any.whl").write_bytes(b"wheel")
    (dist / "sdetkit-1.1.0.tar.gz").write_bytes(b"sdist")

    payload = module.build_manifest(
        dist_dir=dist,
        tag="v1.1.0",
        version="1.1.0",
        source_sha="a" * 40,
    )

    assert payload["schema_version"] == "sdetkit.release_distribution_manifest.v1"
    assert payload["tag"] == "v1.1.0"
    assert payload["source_sha"] == "a" * 40
    assert {item["name"] for item in payload["files"]} == {
        "sdetkit-1.1.0-py3-none-any.whl",
        "sdetkit-1.1.0.tar.gz",
    }
    assert all(len(item["sha256"]) == 64 for item in payload["files"])


@pytest.mark.parametrize(
    ("tag", "version", "source_sha", "message"),
    [
        ("1.1.0", "1.1.0", "a" * 40, "vX.Y.Z"),
        ("v1.1.0", "1.1.1", "a" * 40, "do not match"),
        ("v1.1.0", "1.1.0", "not-a-sha", "40-character"),
    ],
)
def test_distribution_manifest_rejects_invalid_identity(
    tmp_path: Path,
    tag: str,
    version: str,
    source_sha: str,
    message: str,
) -> None:
    module = _module(
        "build_release_distribution_manifest",
        ROOT / "scripts/build_release_distribution_manifest.py",
    )
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "sdetkit.whl").write_bytes(b"wheel")
    (dist / "sdetkit.tar.gz").write_bytes(b"sdist")

    with pytest.raises(ValueError, match=message):
        module.build_manifest(
            dist_dir=dist,
            tag=tag,
            version=version,
            source_sha=source_sha,
        )


def test_distribution_manifest_requires_both_distribution_types(tmp_path: Path) -> None:
    module = _module(
        "build_release_distribution_manifest",
        ROOT / "scripts/build_release_distribution_manifest.py",
    )
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "sdetkit-1.1.0-py3-none-any.whl").write_bytes(b"wheel")

    with pytest.raises(ValueError, match="sdist"):
        module.build_manifest(
            dist_dir=dist,
            tag="v1.1.0",
            version="1.1.0",
            source_sha="a" * 40,
        )


def test_pypi_verifier_accepts_exact_distribution_hashes() -> None:
    module = _module("verify_pypi_release", ROOT / "scripts/verify_pypi_release.py")
    manifest = {
        "files": [
            {"name": "sdetkit.whl", "sha256": "a" * 64},
            {"name": "sdetkit.tar.gz", "sha256": "b" * 64},
        ]
    }
    payload = {
        "urls": [
            {"filename": "sdetkit.whl", "digests": {"sha256": "a" * 64}},
            {"filename": "sdetkit.tar.gz", "digests": {"sha256": "b" * 64}},
        ]
    }

    result = module.compare_distribution_hashes(manifest, payload)

    assert result["ok"] is True
    assert result["missing"] == []
    assert result["unexpected"] == []
    assert result["digest_mismatches"] == []


def test_pypi_verifier_rejects_missing_unexpected_and_mismatched_files() -> None:
    module = _module("verify_pypi_release", ROOT / "scripts/verify_pypi_release.py")
    manifest = {
        "files": [
            {"name": "sdetkit.whl", "sha256": "a" * 64},
            {"name": "sdetkit.tar.gz", "sha256": "b" * 64},
        ]
    }
    payload = {
        "urls": [
            {"filename": "sdetkit.whl", "digests": {"sha256": "c" * 64}},
            {"filename": "unexpected.zip", "digests": {"sha256": "d" * 64}},
        ]
    }

    result = module.compare_distribution_hashes(manifest, payload)

    assert result["ok"] is False
    assert result["missing"] == ["sdetkit.tar.gz"]
    assert result["unexpected"] == ["unexpected.zip"]
    assert result["digest_mismatches"] == ["sdetkit.whl"]
