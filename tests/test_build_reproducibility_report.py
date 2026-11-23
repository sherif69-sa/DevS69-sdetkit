from __future__ import annotations

import importlib.util
import io
import tarfile
import zipfile
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/check_build_reproducibility.py"
spec = importlib.util.spec_from_file_location("build_repro", SCRIPT)
assert spec is not None and spec.loader is not None
repro = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repro)


def wheel(directory, payload=b"same", year=2020):
    directory.mkdir(exist_ok=True)
    path = directory / "sample-1-py3-none-any.whl"
    with zipfile.ZipFile(path, "w") as archive:
        item = zipfile.ZipInfo("sample.py", date_time=(year, 1, 1, 0, 0, 0))
        archive.writestr(item, payload)
    return path


def sdist(directory, payload=b"same", timestamp=1):
    directory.mkdir(exist_ok=True)
    path = directory / "sample-1.tar.gz"
    with tarfile.open(path, "w:gz") as archive:
        item = tarfile.TarInfo("sample-1/sample.py")
        item.size, item.mtime = len(payload), timestamp
        archive.addfile(item, io.BytesIO(payload))
    return path


@pytest.mark.parametrize("builder", [wheel, sdist])
def test_identical_bytes_are_reproducible(tmp_path, builder):
    a, b = tmp_path / "a", tmp_path / "b"
    original = builder(a)
    b.mkdir()
    (b / original.name).write_bytes(original.read_bytes())
    report = repro.compare(a, b)
    assert report["status"] == "completed"
    assert report["reproducible"] is True
    assert report["artifacts"][0]["member_content_identical"] is True


@pytest.mark.parametrize("builder,kwargs", [(wheel, {"year": 2021}), (sdist, {"timestamp": 2})])
def test_metadata_difference_is_not_called_reproducible(tmp_path, builder, kwargs):
    a, b = tmp_path / "a", tmp_path / "b"
    builder(a)
    builder(b, **kwargs)
    report = repro.compare(a, b)
    assert report["reproducible"] is False
    artifact = report["artifacts"][0]
    assert artifact["member_content_identical"] is True
    assert artifact["changed_members"] == []


@pytest.mark.parametrize("builder", [wheel, sdist])
def test_changed_content_is_identified(tmp_path, builder):
    a, b = tmp_path / "a", tmp_path / "b"
    builder(a)
    builder(b, payload=b"changed")
    report = repro.compare(a, b)
    assert report["reproducible"] is False
    assert report["artifacts"][0]["member_content_identical"] is False
    assert len(report["artifacts"][0]["changed_members"]) == 1


def test_missing_artifact_cannot_pass(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    wheel(a)
    sdist(a)
    wheel(b)
    report = repro.compare(a, b)
    assert report["reproducible"] is False
    assert (
        next(x for x in report["artifacts"] if x["name"].endswith("tar.gz"))["status"] == "missing"
    )


def test_empty_or_missing_inputs_are_errors(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ValueError, match="no distributions"):
        repro.compare(empty, empty)
    with pytest.raises(ValueError, match="does not exist"):
        repro.compare(empty, tmp_path / "missing")


def test_broken_archive_is_not_a_comparison(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    path = wheel(a)
    b.mkdir()
    (b / path.name).write_bytes(b"broken archive")
    with pytest.raises(zipfile.BadZipFile):
        repro.compare(a, b)


def test_archive_paths_are_never_extracted(tmp_path):
    path = tmp_path / "input.tar.gz"
    with tarfile.open(path, "w:gz") as archive:
        item = tarfile.TarInfo("../outside.txt")
        item.size = 3
        archive.addfile(item, io.BytesIO(b"one"))
    assert repro.members(path) == {"../outside.txt": repro.digest(b"one")}
    assert not (tmp_path.parent / "outside.txt").exists()


def test_duplicate_zip_members_are_rejected(tmp_path):
    path = tmp_path / "input.whl"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("same.py", b"one")
        with pytest.warns(UserWarning, match="Duplicate name"):
            archive.writestr("same.py", b"two")
    with pytest.raises(ValueError, match="duplicate archive member"):
        repro.members(path)


def test_link_members_are_rejected_without_following_them(tmp_path):
    path = tmp_path / "input.tar.gz"
    with tarfile.open(path, "w:gz") as archive:
        item = tarfile.TarInfo("link")
        item.type = tarfile.SYMTYPE
        item.linkname = "elsewhere"
        archive.addfile(item)
    with pytest.raises(ValueError, match="unsupported archive member"):
        repro.members(path)


def test_cli_writes_tool_error_instead_of_success_for_missing_input(tmp_path, monkeypatch):
    out = tmp_path / "report.json"
    monkeypatch.setattr(
        "sys.argv",
        [
            str(SCRIPT),
            "--left",
            str(tmp_path / "missing"),
            "--right",
            str(tmp_path),
            "--out",
            str(out),
        ],
    )
    assert repro.main() == 1
    import json

    report = json.loads(out.read_text())
    assert report["status"] == "tool_error"
    assert report["reproducible"] is None
