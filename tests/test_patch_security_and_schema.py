from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from sdetkit import patch


def _write_spec(tmp_path: Path, spec: dict) -> Path:
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    return spec_path


def test_patch_accepts_dict_file_form_and_sorted_output(tmp_path: Path, capsys):
    (tmp_path / "a.txt").write_text("A\n", encoding="utf-8")
    (tmp_path / "b.txt").write_text("B\n", encoding="utf-8")
    spec_path = _write_spec(
        tmp_path,
        {
            "spec_version": 1,
            "files": {
                "b.txt": [{"op": "insert_after", "pattern": r"^B$", "text": "X\\n"}],
                "a.txt": [{"op": "insert_after", "pattern": r"^A$", "text": "Y\\n"}],
            },
        },
    )

    old = Path.cwd()
    try:
        os.chdir(tmp_path)
        rc = patch.main([spec_path.name, "--check"])
    finally:
        os.chdir(old)

    out = capsys.readouterr().out
    assert rc == 1
    assert out.index("--- a.txt") < out.index("--- b.txt")


def test_patch_rejects_path_escape(tmp_path: Path):
    (tmp_path / "ok.txt").write_text("A\n", encoding="utf-8")
    spec_path = _write_spec(
        tmp_path,
        {
            "spec_version": 1,
            "files": [
                {
                    "path": "../oops.txt",
                    "ops": [{"op": "insert_after", "pattern": "A", "text": "X"}],
                }
            ],
        },
    )
    rc = patch.main([str(spec_path), "--root", str(tmp_path)])
    assert rc == 2


def test_patch_rejects_weird_path_separators_and_controls(tmp_path: Path):
    (tmp_path / "ok.txt").write_text("A\n", encoding="utf-8")
    for bad_path in ["sub\\file.txt", "sub//file.txt", "sub/\x01.txt", " "]:
        spec_path = _write_spec(
            tmp_path,
            {
                "spec_version": 1,
                "files": [
                    {
                        "path": bad_path,
                        "ops": [{"op": "insert_after", "pattern": "A", "text": "X"}],
                    }
                ],
            },
        )
        rc = patch.main([str(spec_path), "--root", str(tmp_path)])
        assert rc == 2


def test_patch_rejects_symlink_target_by_default(tmp_path: Path):
    (tmp_path / "real.txt").write_text("A\n", encoding="utf-8")
    (tmp_path / "link.txt").symlink_to(tmp_path / "real.txt")
    spec_path = _write_spec(
        tmp_path,
        {
            "spec_version": 1,
            "files": [
                {"path": "link.txt", "ops": [{"op": "insert_after", "pattern": "A", "text": "X"}]}
            ],
        },
    )
    rc = patch.main([str(spec_path), "--root", str(tmp_path)])
    assert rc == 2


def test_patch_rejects_symlink_parent_escape(tmp_path: Path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "victim.txt").write_text("A\n", encoding="utf-8")

    (tmp_path / "dir").symlink_to(outside, target_is_directory=True)
    spec_path = _write_spec(
        tmp_path,
        {
            "spec_version": 1,
            "files": [
                {
                    "path": "dir/victim.txt",
                    "ops": [{"op": "insert_after", "pattern": "A", "text": "X"}],
                }
            ],
        },
    )

    rc = patch.main([str(spec_path), "--root", str(tmp_path)])
    assert rc == 2
    assert (outside / "victim.txt").read_text(encoding="utf-8") == "A\n"


def test_patch_default_root_uses_git_repo_root(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    init = subprocess.run(
        ["git", "-C", str(root), "init"], check=False, capture_output=True, text=True
    )
    assert init.returncode == 0

    nested = root / "nested"
    nested.mkdir()
    target = root / "a.txt"
    target.write_text("A\n", encoding="utf-8")
    _write_spec(
        nested,
        {
            "files": [
                {
                    "path": "a.txt",
                    "ops": [{"op": "insert_after", "pattern": r"^A$", "text": "B\\n"}],
                }
            ],
        },
    )

    old = Path.cwd()
    try:
        os.chdir(nested)
        rc = patch.main(["spec.json"])
    finally:
        os.chdir(old)

    assert rc == 0
    assert target.read_text(encoding="utf-8") == "A\nB\n"


def test_patch_default_root_falls_back_to_cwd(tmp_path: Path):
    target = tmp_path / "a.txt"
    target.write_text("A\n", encoding="utf-8")
    _write_spec(
        tmp_path,
        {
            "spec_version": 1,
            "files": [
                {
                    "path": "a.txt",
                    "ops": [{"op": "insert_after", "pattern": r"^A$", "text": "B\\n"}],
                }
            ],
        },
    )

    old = Path.cwd()
    try:
        os.chdir(tmp_path)
        rc = patch.main(["spec.json"])
    finally:
        os.chdir(old)

    assert rc == 0
    assert target.read_text(encoding="utf-8") == "A\nB\n"


def test_patch_report_json(tmp_path: Path):
    (tmp_path / "a.txt").write_text("A\n", encoding="utf-8")
    report = tmp_path / "report.json"
    spec_path = _write_spec(
        tmp_path,
        {
            "spec_version": 1,
            "files": [
                {
                    "path": "a.txt",
                    "ops": [{"op": "insert_after", "pattern": r"^A$", "text": "B\\n"}],
                }
            ],
        },
    )

    old = Path.cwd()
    try:
        os.chdir(tmp_path)
        rc = patch.main([spec_path.name, "--report-json", str(report)])
    finally:
        os.chdir(old)

    assert rc == 0
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["status_code"] == 0
    assert data["files_touched"] == ["a.txt"]


def test_patch_invalid_spec_version_returns_2(tmp_path: Path):
    (tmp_path / "a.txt").write_text("A\n", encoding="utf-8")
    spec_path = _write_spec(
        tmp_path,
        {
            "spec_version": 2,
            "files": [
                {
                    "path": "a.txt",
                    "ops": [{"op": "insert_after", "pattern": r"^A$", "text": "B\\n"}],
                }
            ],
        },
    )
    rc = patch.main([str(spec_path)])
    assert rc == 2


def test_patch_limit_flags_must_be_positive(tmp_path: Path):
    (tmp_path / "a.txt").write_text("A\n", encoding="utf-8")
    spec_path = _write_spec(
        tmp_path,
        {
            "spec_version": 1,
            "files": [
                {
                    "path": "a.txt",
                    "ops": [{"op": "insert_after", "pattern": r"^A$", "text": "B\\n"}],
                }
            ],
        },
    )
    rc = patch.main([str(spec_path), "--max-files", "0"])
    assert rc == 2


def test_patch_enforces_resource_limits(tmp_path: Path):
    (tmp_path / "a.txt").write_text("A\n", encoding="utf-8")
    spec_path = _write_spec(
        tmp_path,
        {
            "spec_version": 1,
            "files": [
                {
                    "path": "a.txt",
                    "ops": [{"op": "insert_after", "pattern": r"^A$", "text": "B\\n"}],
                }
            ],
        },
    )

    assert patch.main([str(spec_path), "--root", str(tmp_path), "--max-files", "1"]) == 0
    assert patch.main([str(spec_path), "--root", str(tmp_path), "--max-op-count", "0"]) == 2
    assert patch.main([str(spec_path), "--root", str(tmp_path), "--max-bytes-per-file", "1"]) == 2


def test_patch_check_is_deterministic_for_same_inputs(tmp_path: Path, capsys):
    (tmp_path / "a.txt").write_text("A\n", encoding="utf-8")
    spec_path = _write_spec(
        tmp_path,
        {
            "spec_version": 1,
            "files": [
                {
                    "path": "a.txt",
                    "ops": [{"op": "insert_after", "pattern": r"^A$", "text": "B\\n"}],
                }
            ],
        },
    )

    old = Path.cwd()
    try:
        os.chdir(tmp_path)
        rc1 = patch.main([spec_path.name, "--check"])
        out1 = capsys.readouterr().out
        rc2 = patch.main([spec_path.name, "--check"])
        out2 = capsys.readouterr().out
    finally:
        os.chdir(old)

    assert rc1 == rc2 == 1
    assert out1 == out2


def test_patch_missing_spec_version_defaults_to_v1(tmp_path: Path):
    (tmp_path / "a.txt").write_text("A\n", encoding="utf-8")
    spec_path = _write_spec(
        tmp_path,
        {
            "files": [
                {
                    "path": "a.txt",
                    "ops": [{"op": "insert_after", "pattern": r"^A$", "text": "B\\n"}],
                }
            ],
        },
    )

    old = Path.cwd()
    try:
        os.chdir(tmp_path)
        rc = patch.main([spec_path.name, "--check"])
    finally:
        os.chdir(old)

    assert rc == 1


def test_patch_spec_size_limit(tmp_path: Path):
    (tmp_path / "a.txt").write_text("A\n", encoding="utf-8")
    spec_path = _write_spec(
        tmp_path,
        {
            "spec_version": 1,
            "files": [
                {
                    "path": "a.txt",
                    "ops": [{"op": "insert_after", "pattern": r"^A$", "text": "B\\n"}],
                }
            ],
        },
    )

    rc = patch.main([str(spec_path), "--max-spec-bytes", "8"])
    assert rc == 2


def test_patch_atomic_write_does_not_partial_on_replace_failure(tmp_path: Path, monkeypatch):
    target = tmp_path / "a.txt"
    target.write_text("A\n", encoding="utf-8")

    def fail_replace(_src: Path, _dst: Path) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(patch.os, "replace", fail_replace)

    with pytest.raises(OSError):
        patch._write_atomic(target, "B\n")

    assert target.read_text(encoding="utf-8") == "A\n"
    temp_files = list(tmp_path.glob(".a.txt.*.tmp"))
    assert temp_files == []
