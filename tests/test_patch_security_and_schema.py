from __future__ import annotations

import json
import os
from pathlib import Path

from sdetkit import patch


def test_patch_accepts_dict_file_form_and_sorted_output(tmp_path: Path, capsys):
    (tmp_path / "a.txt").write_text("A\n", encoding="utf-8")
    (tmp_path / "b.txt").write_text("B\n", encoding="utf-8")
    spec = {
        "spec_version": 1,
        "files": {
            "b.txt": [{"op": "insert_after", "pattern": r"^B$", "text": "X\\n"}],
            "a.txt": [{"op": "insert_after", "pattern": r"^A$", "text": "Y\\n"}],
        },
    }
    (tmp_path / "spec.json").write_text(json.dumps(spec), encoding="utf-8")

    old = Path.cwd()
    try:
        os.chdir(tmp_path)
        rc = patch.main(["spec.json", "--check"])
    finally:
        os.chdir(old)

    out = capsys.readouterr().out
    assert rc == 1
    assert out.index("--- a.txt") < out.index("--- b.txt")


def test_patch_rejects_path_escape(tmp_path: Path):
    (tmp_path / "ok.txt").write_text("A\n", encoding="utf-8")
    spec = {
        "spec_version": 1,
        "files": [
            {"path": "../oops.txt", "ops": [{"op": "insert_after", "pattern": "A", "text": "X"}]}
        ],
    }
    (tmp_path / "spec.json").write_text(json.dumps(spec), encoding="utf-8")
    rc = patch.main([str(tmp_path / "spec.json"), "--root", str(tmp_path)])
    assert rc == 2


def test_patch_rejects_symlink_target_by_default(tmp_path: Path):
    (tmp_path / "real.txt").write_text("A\n", encoding="utf-8")
    (tmp_path / "link.txt").symlink_to(tmp_path / "real.txt")
    spec = {
        "spec_version": 1,
        "files": [
            {"path": "link.txt", "ops": [{"op": "insert_after", "pattern": "A", "text": "X"}]}
        ],
    }
    (tmp_path / "spec.json").write_text(json.dumps(spec), encoding="utf-8")
    rc = patch.main([str(tmp_path / "spec.json"), "--root", str(tmp_path)])
    assert rc == 2


def test_patch_report_json(tmp_path: Path):
    (tmp_path / "a.txt").write_text("A\n", encoding="utf-8")
    report = tmp_path / "report.json"
    spec = {
        "spec_version": 1,
        "files": [
            {"path": "a.txt", "ops": [{"op": "insert_after", "pattern": r"^A$", "text": "B\\n"}]}
        ],
    }
    (tmp_path / "spec.json").write_text(json.dumps(spec), encoding="utf-8")

    old = Path.cwd()
    try:
        os.chdir(tmp_path)
        rc = patch.main(["spec.json", "--report-json", str(report)])
    finally:
        os.chdir(old)

    assert rc == 0
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["status_code"] == 0
    assert data["files_touched"] == ["a.txt"]


def test_patch_invalid_spec_version_returns_2(tmp_path: Path):
    (tmp_path / "a.txt").write_text("A\n", encoding="utf-8")
    spec = {
        "files": [
            {"path": "a.txt", "ops": [{"op": "insert_after", "pattern": r"^A$", "text": "B\\n"}]}
        ],
    }
    (tmp_path / "spec.json").write_text(json.dumps(spec), encoding="utf-8")
    rc = patch.main([str(tmp_path / "spec.json")])
    assert rc == 2


def test_patch_limit_flags_must_be_positive(tmp_path: Path):
    (tmp_path / "a.txt").write_text("A\n", encoding="utf-8")
    spec = {
        "spec_version": 1,
        "files": [
            {"path": "a.txt", "ops": [{"op": "insert_after", "pattern": r"^A$", "text": "B\\n"}]}
        ],
    }
    (tmp_path / "spec.json").write_text(json.dumps(spec), encoding="utf-8")
    rc = patch.main([str(tmp_path / "spec.json"), "--max-files", "0"])
    assert rc == 2


def test_patch_check_is_deterministic_for_same_inputs(tmp_path: Path, capsys):
    (tmp_path / "a.txt").write_text("A\n", encoding="utf-8")
    spec = {
        "spec_version": 1,
        "files": [
            {"path": "a.txt", "ops": [{"op": "insert_after", "pattern": r"^A$", "text": "B\\n"}]}
        ],
    }
    (tmp_path / "spec.json").write_text(json.dumps(spec), encoding="utf-8")

    old = Path.cwd()
    try:
        os.chdir(tmp_path)
        rc1 = patch.main(["spec.json", "--check"])
        out1 = capsys.readouterr().out
        rc2 = patch.main(["spec.json", "--check"])
        out2 = capsys.readouterr().out
    finally:
        os.chdir(old)

    assert rc1 == rc2 == 1
    assert out1 == out2


def test_patch_missing_spec_version_defaults_to_v1(tmp_path: Path):
    (tmp_path / "a.txt").write_text("A\n", encoding="utf-8")
    spec = {
        "files": [
            {"path": "a.txt", "ops": [{"op": "insert_after", "pattern": r"^A$", "text": "B\\n"}]}
        ],
    }
    (tmp_path / "spec.json").write_text(json.dumps(spec), encoding="utf-8")

    old = Path.cwd()
    try:
        os.chdir(tmp_path)
        rc = patch.main(["spec.json", "--check"])
    finally:
        os.chdir(old)

    assert rc == 1


def test_patch_spec_size_limit(tmp_path: Path):
    (tmp_path / "a.txt").write_text("A\n", encoding="utf-8")
    spec = {
        "spec_version": 1,
        "files": [
            {"path": "a.txt", "ops": [{"op": "insert_after", "pattern": r"^A$", "text": "B\\n"}]}
        ],
    }
    payload = json.dumps(spec)
    (tmp_path / "spec.json").write_text(payload, encoding="utf-8")

    rc = patch.main([str(tmp_path / "spec.json"), "--max-spec-bytes", "8"])
    assert rc == 2
