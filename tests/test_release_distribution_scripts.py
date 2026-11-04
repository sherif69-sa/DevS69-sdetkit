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


MANIFEST = {
    "files": [
        {"name": "sdetkit.whl", "sha256": "a" * 64},
        {"name": "sdetkit.tar.gz", "sha256": "b" * 64},
    ]
}
WHEEL = {"filename": "sdetkit.whl", "digests": {"sha256": "a" * 64}}
SDIST = {"filename": "sdetkit.tar.gz", "digests": {"sha256": "b" * 64}}


def test_pypi_verifier_waits_while_pypi_lists_only_some_files() -> None:
    module = _module("verify_pypi_release", ROOT / "scripts/verify_pypi_release.py")
    # Right after the upload: the wheel is listed, the sdist not yet.
    answers = iter([{"urls": [WHEEL]}, {"urls": [WHEEL]}, {"urls": [WHEEL, SDIST]}])
    sleeps: list[float] = []

    result = module.verify_release(MANIFEST, lambda: next(answers), sleep=sleeps.append)

    assert result["ok"] is True
    assert sleeps == [module.DELAY_SECONDS, module.DELAY_SECONDS]


def test_pypi_verifier_fails_at_once_on_a_wrong_file_and_gives_up_on_a_missing_one() -> None:
    module = _module("verify_pypi_release", ROOT / "scripts/verify_pypi_release.py")
    sleeps: list[float] = []
    wrong = {"urls": [{"filename": "sdetkit.whl", "digests": {"sha256": "c" * 64}}]}

    mismatch = module.verify_release(MANIFEST, lambda: wrong, sleep=sleeps.append)
    extra = module.verify_release(
        MANIFEST,
        lambda: {"urls": [WHEEL, SDIST, {"filename": "x.zip", "digests": {"sha256": "d"}}]},
        sleep=sleeps.append,
    )
    assert (mismatch["ok"], mismatch["digest_mismatches"]) == (False, ["sdetkit.whl"])
    assert (extra["ok"], extra["unexpected"]) == (False, ["x.zip"])
    # A wrong or extra file is no propagation delay: nothing waited for it.
    assert sleeps == []

    missing = module.verify_release(
        MANIFEST, lambda: {"urls": [WHEEL]}, attempts=3, sleep=sleeps.append
    )
    assert (missing["ok"], missing["missing"]) == (False, ["sdetkit.tar.gz"])
    assert len(sleeps) == 2


def test_pypi_lookup_retries_not_found_server_errors_and_the_network(monkeypatch) -> None:
    import io
    import json
    import urllib.error

    module = _module("verify_pypi_release", ROOT / "scripts/verify_pypi_release.py")
    url = "https://pypi.org/pypi/sdetkit/2.0.0/json"
    failures = [
        urllib.error.HTTPError(url, 404, "Not Found", {}, None),  # type: ignore[arg-type]
        urllib.error.HTTPError(url, 503, "Unavailable", {}, None),  # type: ignore[arg-type]
        urllib.error.URLError("timed out"),
    ]

    def urlopen(requested: str, timeout: float):
        assert requested == url
        if failures:
            raise failures.pop(0)
        return io.BytesIO(json.dumps({"urls": [WHEEL]}).encode())

    monkeypatch.setattr(module.urllib.request, "urlopen", urlopen)
    sleeps: list[float] = []

    assert module.fetch_sdetkit_release("2.0.0", sleep=sleeps.append) == {"urls": [WHEEL]}
    assert len(sleeps) == 3

    # A refusal is not a delay.
    def forbidden(requested: str, timeout: float):
        raise urllib.error.HTTPError(url, 403, "Forbidden", {}, None)  # type: ignore[arg-type]

    monkeypatch.setattr(module.urllib.request, "urlopen", forbidden)
    with pytest.raises(urllib.error.HTTPError):
        module.fetch_sdetkit_release("2.0.0", sleep=sleeps.append)
    assert len(sleeps) == 3


def test_the_install_from_pypi_waits_for_the_index() -> None:
    module = _module("verify_pypi_release", ROOT / "scripts/verify_pypi_release.py")
    calls: list[list[str]] = []
    codes = iter([1, 1, 0])

    def run(argv: list[str]) -> int:
        calls.append(argv)
        return next(codes)

    sleeps: list[float] = []
    assert module.install_from_index("2.0.0", run=run, sleep=sleeps.append) is True
    assert len(calls) == 3 and len(sleeps) == 2
    assert calls[0][-3:] == ["--index-url", "https://pypi.org/simple/", "sdetkit==2.0.0"]

    assert (
        module.install_from_index("2.0.0", attempts=2, run=lambda argv: 1, sleep=sleeps.append)
        is False
    )
