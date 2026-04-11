from __future__ import annotations

import json
from pathlib import Path

from sdetkit import doctor


def test_doctor_ci_missing_files(tmp_path: Path, monkeypatch, capsys):
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.chdir(root)

    rc = doctor.main(["--ci", "--json"])
    data = json.loads(capsys.readouterr().out)

    assert rc == 2
    assert data["checks"]["ci_workflows"]["ok"] is False
    assert data["judgment"]["schema_version"] == "sdetkit.judgment.v1"
    assert {"ci", "quality", "security"}.issubset(set(data["ci_missing"]))


def test_doctor_security_files_pass_when_present(tmp_path: Path, monkeypatch, capsys):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "SECURITY.md").write_text("sec\n", encoding="utf-8")
    (root / "CONTRIBUTING.md").write_text("contrib\n", encoding="utf-8")
    (root / "CODE_OF_CONDUCT.md").write_text("coc\n", encoding="utf-8")
    (root / "LICENSE").write_text("license\n", encoding="utf-8")
    monkeypatch.chdir(root)

    rc = doctor.main(["--ci", "--fail-on", "high", "--json"])
    data = json.loads(capsys.readouterr().out)

    assert rc == 2
    assert data["checks"]["security_files"]["ok"] is True


def test_doctor_pre_commit_and_deps_and_clean_tree(tmp_path: Path, monkeypatch, capsys):
    root = tmp_path / "repo"
    root.mkdir()
    (root / ".pre-commit-config.yaml").write_text("repos: []\n", encoding="utf-8")

    def fake_run(cmd, *, cwd=None):
        s = " ".join(cmd)
        if s.endswith("-m pre_commit --version"):
            return 0, "pre-commit 9.9.9\\n", ""
        if "validate-config" in s:
            return 0, "", ""
        if s.endswith("-m pip check"):
            return 0, "", ""
        if s == "git status --porcelain":
            return 0, "", ""
        return 0, "", ""

    monkeypatch.setattr(doctor, "_run", fake_run)
    monkeypatch.chdir(root)

    rc = doctor.main(["--pre-commit", "--deps", "--clean-tree", "--json"])
    data = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert data["pre_commit_ok"] is True
    assert data["deps_ok"] is True
    assert data["clean_tree_ok"] is True


def test_doctor_evidence_writes_json_and_markdown(tmp_path: Path, monkeypatch, capsys):
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.chdir(root)

    evidence_dir = root / "build" / "doctor-evidence"
    rc = doctor.main(["--ci", "--json", "--evidence-dir", str(evidence_dir)])
    data = json.loads(capsys.readouterr().out)

    assert rc == 2
    assert data["ok"] is False
    assert (evidence_dir / "doctor-evidence.json").exists()
    assert (evidence_dir / "doctor-evidence.md").exists()
    assert (evidence_dir / "doctor-evidence-manifest.json").exists()
    evidence = json.loads((evidence_dir / "doctor-evidence.json").read_text(encoding="utf-8"))
    manifest = json.loads(
        (evidence_dir / "doctor-evidence-manifest.json").read_text(encoding="utf-8")
    )
    assert evidence["schema_version"] == "sdetkit.doctor.evidence.v2"
    assert evidence["profile"] == "full"
    assert evidence["include"] == "all"
    assert manifest["schema_version"] == "sdetkit.doctor.evidence.manifest.v1"
    assert manifest["profile"] == "full"
    assert manifest["include"] == "all"
    assert evidence["failed_checks"]
    assert evidence["diagnostics_rows"]
    assert isinstance(evidence["structured_recommendations"], list)
    assert "surface_consistency" in evidence
    forbidden = {
        "root_cause",
        "correct_fix",
        "wrong_fix",
        "target",
        "false_positive",
        "control_label",
        "hint",
        "answer",
    }
    assert forbidden.isdisjoint(set(evidence))


def test_doctor_evidence_profile_and_include_filter(tmp_path: Path, monkeypatch, capsys):
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.chdir(root)

    evidence_dir = root / "build" / "doctor-evidence"
    rc = doctor.main(
        [
            "--ci",
            "--json",
            "--evidence-dir",
            str(evidence_dir),
            "--evidence-profile",
            "ci",
            "--evidence-include",
            "failed",
        ]
    )
    _ = json.loads(capsys.readouterr().out)

    assert rc == 2
    evidence = json.loads((evidence_dir / "doctor-evidence.json").read_text(encoding="utf-8"))
    assert evidence["profile"] == "ci"
    assert evidence["include"] == "failed"
    assert evidence["passing_controls"] == []
    assert evidence["structured_recommendations"] == []
    assert all(row["id"] in {"ci_workflows", "security_files"} for row in evidence["failed_checks"])


def test_doctor_evidence_fails_for_non_actionable_check_selection(
    tmp_path: Path, monkeypatch, capsys
):
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.chdir(root)

    skip_all = ",".join(doctor.CHECK_ORDER)
    rc = doctor.main(["--json", "--skip", skip_all, "--evidence-dir", "build/doctor-evidence"])
    data = json.loads(capsys.readouterr().out)

    assert rc == 2
    assert data["error"]["code"] == "doctor_evidence_empty"
