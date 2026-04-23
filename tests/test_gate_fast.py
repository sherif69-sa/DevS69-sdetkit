from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from sdetkit import gate


def _run_sdetkit(repo_root: Path, cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root / "src")
    return subprocess.run(
        [sys.executable, "-m", "sdetkit", *args],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_gate_help_includes_fast() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    proc = _run_sdetkit(repo_root, repo_root, "gate", "--help")
    assert proc.returncode == 0
    assert "usage: gate" in proc.stdout
    assert "fast" in proc.stdout
    assert "release" in proc.stdout


def test_gate_fast_can_run_ci_templates_only(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]

    (tmp_path / "templates" / "ci" / "gitlab").mkdir(parents=True)
    (tmp_path / "templates" / "ci" / "jenkins").mkdir(parents=True)
    (tmp_path / "templates" / "ci" / "tekton").mkdir(parents=True)

    (tmp_path / "templates" / "ci" / "gitlab" / "gitlab-advanced-reference.yml").write_text(
        "bash scripts/bootstrap.sh\n. .venv/bin/activate\npython -m sdetkit\nCI_COMMIT_REF_SLUG\n",
        encoding="utf-8",
    )
    (
        tmp_path / "templates" / "ci" / "jenkins" / "jenkins-advanced-reference.Jenkinsfile"
    ).write_text(
        "bash scripts/bootstrap.sh\n. .venv/bin/activate\npytest -q\nsecurity.sh\nPYTHON_VERSION\n",
        encoding="utf-8",
    )
    (tmp_path / "templates" / "ci" / "tekton" / "tekton-self-hosted-reference.yaml").write_text(
        "bash scripts/bootstrap.sh\n. .venv/bin/activate\nbash ci.sh\nbash security.sh\n$(params.branch)\n",
        encoding="utf-8",
    )

    proc = _run_sdetkit(
        repo_root,
        tmp_path,
        "gate",
        "fast",
        "--root",
        str(tmp_path),
        "--format",
        "json",
        "--no-doctor",
        "--no-ruff",
        "--no-mypy",
        "--no-pytest",
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["ok"] is True
    assert [s["id"] for s in data["steps"]] == ["ci_templates"]


def test_gate_fast_fix_only_formats_files(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    (tmp_path / "a.py").write_text("x=1\n", encoding="utf-8")

    proc = _run_sdetkit(
        repo_root,
        tmp_path,
        "gate",
        "fast",
        "--root",
        str(tmp_path),
        "--format",
        "json",
        "--fix-only",
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert [s["id"] for s in data["steps"]] == ["ruff_fix", "ruff_format_apply"]
    assert (tmp_path / "a.py").read_text(encoding="utf-8") == "x = 1\n"


def test_gate_fast_fix_runs_before_ruff_checks(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    (tmp_path / "a.py").write_text("x=1\n", encoding="utf-8")

    proc = _run_sdetkit(
        repo_root,
        tmp_path,
        "gate",
        "fast",
        "--root",
        str(tmp_path),
        "--format",
        "json",
        "--fix",
        "--no-doctor",
        "--no-ci-templates",
        "--no-mypy",
        "--no-pytest",
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert [s["id"] for s in data["steps"]] == [
        "ruff_fix",
        "ruff_format_apply",
        "ruff",
        "ruff_format",
    ]
    assert (tmp_path / "a.py").read_text(encoding="utf-8") == "x = 1\n"


def test_gate_fast_list_steps() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    proc = _run_sdetkit(repo_root, repo_root, "gate", "fast", "--list-steps")
    assert proc.returncode == 0
    assert proc.stdout.splitlines() == [
        "ruff_fix",
        "ruff_format_apply",
        "doctor",
        "ci_templates",
        "ruff",
        "ruff_format",
        "mypy",
        "pytest",
    ]


def test_gate_fast_only_runs_selected_step(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]

    (tmp_path / "templates" / "ci" / "gitlab").mkdir(parents=True)
    (tmp_path / "templates" / "ci" / "jenkins").mkdir(parents=True)
    (tmp_path / "templates" / "ci" / "tekton").mkdir(parents=True)

    (tmp_path / "templates" / "ci" / "gitlab" / "gitlab-advanced-reference.yml").write_text(
        "bash scripts/bootstrap.sh\n. .venv/bin/activate\npython -m sdetkit\nCI_COMMIT_REF_SLUG\n",
        encoding="utf-8",
    )
    (
        tmp_path / "templates" / "ci" / "jenkins" / "jenkins-advanced-reference.Jenkinsfile"
    ).write_text(
        "bash scripts/bootstrap.sh\n. .venv/bin/activate\npytest -q\nsecurity.sh\nPYTHON_VERSION\n",
        encoding="utf-8",
    )
    (tmp_path / "templates" / "ci" / "tekton" / "tekton-self-hosted-reference.yaml").write_text(
        "bash scripts/bootstrap.sh\n. .venv/bin/activate\nbash ci.sh\nbash security.sh\n$(params.branch)\n",
        encoding="utf-8",
    )

    proc = _run_sdetkit(
        repo_root,
        tmp_path,
        "gate",
        "fast",
        "--root",
        str(tmp_path),
        "--format",
        "json",
        "--only",
        "ci_templates",
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert [s["id"] for s in data["steps"]] == ["ci_templates"]


def test_gate_fast_rejects_unknown_step() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    proc = _run_sdetkit(repo_root, repo_root, "gate", "fast", "--only", "wat")
    assert proc.returncode == 2
    assert "unknown step id" in proc.stderr


def test_gate_fast_default_pytest_scope_is_smoke_subset(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        calls.append(cmd)
        return {"cmd": cmd, "rc": 0, "ok": True, "duration_ms": 1, "stdout": "", "stderr": ""}

    monkeypatch.setattr(gate, "_run", fake_run)
    monkeypatch.chdir(tmp_path)

    rc = gate.main(
        ["fast", "--format", "json", "--no-doctor", "--no-ci-templates", "--no-ruff", "--no-mypy"]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert [s["id"] for s in payload["steps"]] == ["pytest"]
    assert calls[0][3:] == [
        "-q",
        "tests/test_gate_fast.py",
        "tests/test_gate_baseline.py",
        "tests/test_doctor_surgical.py",
        "tests/test_baseline_umbrella.py",
    ]


def test_gate_fast_full_pytest_uses_entire_suite(monkeypatch, tmp_path: Path, capsys) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        calls.append(cmd)
        return {"cmd": cmd, "rc": 0, "ok": True, "duration_ms": 1, "stdout": "", "stderr": ""}

    monkeypatch.setattr(gate, "_run", fake_run)
    monkeypatch.chdir(tmp_path)

    rc = gate.main(
        [
            "fast",
            "--format",
            "json",
            "--no-doctor",
            "--no-ci-templates",
            "--no-ruff",
            "--no-mypy",
            "--full-pytest",
        ]
    )
    assert rc == 0
    _ = json.loads(capsys.readouterr().out)
    assert calls[0][3:] == ["-q"]


def test_gate_fast_default_ruff_scope_targets_src_and_tests(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        calls.append(cmd)
        return {"cmd": cmd, "rc": 0, "ok": True, "duration_ms": 1, "stdout": "", "stderr": ""}

    monkeypatch.setattr(gate, "_run", fake_run)
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    monkeypatch.chdir(tmp_path)

    rc = gate.main(
        [
            "fast",
            "--format",
            "json",
            "--no-doctor",
            "--no-ci-templates",
            "--no-mypy",
            "--no-pytest",
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert [s["id"] for s in payload["steps"]] == ["ruff", "ruff_format"]
    assert calls[0][3:] == ["check", "src", "tests"]
    assert calls[1][3:] == ["format", "--check", "src", "tests"]


def test_gate_fast_ruff_scope_falls_back_to_repo_root_when_src_tests_absent(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        calls.append(cmd)
        return {"cmd": cmd, "rc": 0, "ok": True, "duration_ms": 1, "stdout": "", "stderr": ""}

    monkeypatch.setattr(gate, "_run", fake_run)
    monkeypatch.chdir(tmp_path)

    rc = gate.main(
        [
            "fast",
            "--format",
            "json",
            "--no-doctor",
            "--no-ci-templates",
            "--no-mypy",
            "--no-pytest",
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert [s["id"] for s in payload["steps"]] == ["ruff", "ruff_format"]
    assert calls[0][3:] == ["check", "."]
    assert calls[1][3:] == ["format", "--check", "."]


def test_gate_fast_adds_recommendation_for_missing_pytest(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        return {
            "cmd": cmd,
            "rc": 1,
            "ok": False,
            "duration_ms": 1,
            "stdout": "",
            "stderr": "/usr/bin/python: No module named 'pytest'",
        }

    monkeypatch.setattr(gate, "_run", fake_run)
    monkeypatch.chdir(tmp_path)

    rc = gate.main(
        ["fast", "--format", "json", "--no-doctor", "--no-ci-templates", "--no-ruff", "--no-mypy"]
    )
    assert rc == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["failed_steps"] == ["pytest"]
    assert payload["recommendations"] == [
        "Pytest is missing in this environment. Install test tooling: python -m pip install -e .[test]."
    ]


def test_gate_fast_fails_when_no_steps_are_enabled(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    proc = _run_sdetkit(
        repo_root,
        tmp_path,
        "gate",
        "fast",
        "--format",
        "json",
        "--only",
        "doctor",
        "--skip",
        "doctor",
    )
    assert proc.returncode == 2
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    assert payload["failed_steps"] == ["configuration"]
    assert payload["steps"] == []
    assert payload["recommendations"][0].startswith("No gate steps are enabled.")
