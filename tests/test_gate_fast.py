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
    (tmp_path / "pyproject.toml").write_text(
        "[tool.sdetkit.gate]\nci_templates = true\n", encoding="utf-8"
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
    (tmp_path / "ruff.toml").write_text("line-length = 100\n", encoding="utf-8")

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
        "tests",
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


def _fake_ok_run(calls: list[list[str]]):
    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        calls.append(cmd)
        return {"cmd": cmd, "rc": 0, "ok": True, "duration_ms": 1, "stdout": "", "stderr": ""}

    return fake_run


_ONLY_PYTEST = ["--no-doctor", "--no-ci-templates", "--no-ruff", "--no-mypy"]


def test_gate_fast_runs_repo_test_suite_when_tests_detected(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(gate, "_run", _fake_ok_run(calls))
    (tmp_path / "tests").mkdir()
    monkeypatch.chdir(tmp_path)

    rc = gate.main(["fast", "--format", "json", *_ONLY_PYTEST])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert [s["id"] for s in payload["steps"]] == ["pytest"]
    assert calls[0][3:] == ["-q"]


def test_gate_fast_pytest_args_come_from_pyproject(monkeypatch, tmp_path: Path, capsys) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(gate, "_run", _fake_ok_run(calls))
    (tmp_path / "pyproject.toml").write_text(
        '[tool.sdetkit.gate]\npytest_args = ["-q", "tests/test_smoke.py"]\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    rc = gate.main(["fast", "--format", "json", *_ONLY_PYTEST])
    assert rc == 0
    _ = json.loads(capsys.readouterr().out)
    assert calls[0][3:] == ["-q", "tests/test_smoke.py"]


def test_gate_fast_skips_pytest_when_repo_has_no_tests(monkeypatch, tmp_path: Path, capsys) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(gate, "_run", _fake_ok_run(calls))
    monkeypatch.chdir(tmp_path)

    rc = gate.main(["fast", "--format", "json", *_ONLY_PYTEST])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert calls == []
    assert payload["steps"] == []
    assert payload["skipped_steps"][0]["id"] == "pytest"


def test_gate_fast_only_pytest_forces_run_without_detected_tests(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(gate, "_run", _fake_ok_run(calls))
    monkeypatch.chdir(tmp_path)

    rc = gate.main(["fast", "--format", "json", "--only", "pytest"])
    assert rc == 0
    _ = json.loads(capsys.readouterr().out)
    assert calls[0][3:] == ["-q"]


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
    (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nline-length = 100\n", encoding="utf-8")
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
    (tmp_path / "ruff.toml").write_text("line-length = 100\n", encoding="utf-8")
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


def test_gate_fast_skips_ruff_and_mypy_when_repo_does_not_configure_them(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(gate, "_run", _fake_ok_run(calls))
    (tmp_path / "src").mkdir()
    monkeypatch.chdir(tmp_path)

    rc = gate.main(["fast", "--format", "json", "--no-doctor", "--no-ci-templates", "--no-pytest"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert calls == []
    assert [s["id"] for s in payload["skipped_steps"]] == ["ruff", "ruff_format", "mypy"]


def test_gate_fast_mypy_defers_to_configured_files(monkeypatch, tmp_path: Path, capsys) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(gate, "_run", _fake_ok_run(calls))
    (tmp_path / "mypy.ini").write_text("[mypy]\nfiles = pkg\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    rc = gate.main(["fast", "--format", "json", "--only", "mypy"])
    assert rc == 0
    _ = json.loads(capsys.readouterr().out)
    assert calls == [[sys.executable, "-m", "mypy"]]


def test_gate_fast_doctor_uses_portable_checks_by_default(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(gate, "_run", _fake_ok_run(calls))
    monkeypatch.chdir(tmp_path)

    rc = gate.main(["fast", "--format", "json", "--only", "doctor"])
    assert rc == 0
    _ = json.loads(capsys.readouterr().out)
    doctor_cmd = calls[0]
    assert "--repo" not in doctor_cmd
    assert "--ci" not in doctor_cmd
    assert doctor_cmd[3:7] == ["doctor", "--dev", "--deps", "--clean-tree"]


def test_gate_fast_doctor_args_come_from_pyproject(monkeypatch, tmp_path: Path, capsys) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(gate, "_run", _fake_ok_run(calls))
    (tmp_path / "pyproject.toml").write_text(
        '[tool.sdetkit.gate]\ndoctor_args = ["--dev", "--repo"]\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    rc = gate.main(["fast", "--format", "json", "--only", "doctor"])
    assert rc == 0
    _ = json.loads(capsys.readouterr().out)
    assert calls[0][3:6] == ["doctor", "--dev", "--repo"]


def test_gate_fast_rejects_invalid_gate_config(monkeypatch, tmp_path: Path, capsys) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[tool.sdetkit.gate]\npytest_args = "-q"\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    rc = gate.main(["fast", "--format", "json"])
    assert rc == 2
    assert "pytest_args must be a list of strings" in capsys.readouterr().err


def test_gate_fast_next_action_reuses_doctor_diagnosis(monkeypatch, tmp_path: Path, capsys) -> None:
    doctor_stdout = json.dumps(
        {
            "ok": False,
            "next_action": {
                "classification": "deps",
                "first_failure": "pip dependency graph is inconsistent",
                "affected_file": "pyproject.toml",
                "next_command": "python -m pip check",
            },
        }
    )

    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        return {
            "cmd": cmd,
            "rc": 2,
            "ok": False,
            "duration_ms": 1,
            "stdout": doctor_stdout,
            "stderr": "",
        }

    monkeypatch.setattr(gate, "_run", fake_run)
    monkeypatch.chdir(tmp_path)

    rc = gate.main(["fast", "--format", "json", "--only", "doctor"])
    assert rc == 2
    card = json.loads(capsys.readouterr().out)["next_action"]
    assert card["decision"] == "NO-SHIP"
    assert card["classification"] == "deps"
    assert card["first_failure"] == "pip dependency graph is inconsistent"
    assert card["affected_file"] == "pyproject.toml"
    assert card["next_command"] == "python -m pip check"


def test_gate_fast_reports_first_failing_test_in_an_unrelated_repo(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_math.py").write_text(
        "def test_add():\n    assert 1 + 2 == 4\n", encoding="utf-8"
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
    )
    assert proc.returncode == 2, proc.stderr
    data = json.loads(proc.stdout)
    assert data["failed_steps"] == ["pytest"]
    assert [s["id"] for s in data["skipped_steps"]] == [
        "ci_templates",
        "ruff",
        "ruff_format",
        "mypy",
    ]
    card = data["next_action"]
    assert card["decision"] == "NO-SHIP"
    assert "tests/test_math.py::test_add" in card["first_failure"]
    assert card["affected_file"] == "tests/test_math.py"


def test_gate_fast_reports_a_missing_pytest_as_not_run(monkeypatch, tmp_path: Path, capsys) -> None:
    # What `python -m pytest` prints when the interpreter has no pytest: no quotes.
    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        return {
            "cmd": cmd,
            "rc": 1,
            "ok": False,
            "duration_ms": 1,
            "stdout": "",
            "stderr": "/usr/bin/python: No module named pytest\n",
        }

    monkeypatch.setattr(gate, "_run", fake_run)
    (tmp_path / "tests").mkdir()
    monkeypatch.chdir(tmp_path)

    rc = gate.main(
        ["fast", "--format", "json", "--no-doctor", "--no-ci-templates", "--no-ruff", "--no-mypy"]
    )
    assert rc == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["failed_steps"] == ["pytest"]
    [step] = payload["steps"]
    assert step["environment_problem"].startswith("pytest is not installed in the interpreter")
    assert payload["verdict"]["decision"] == "NOT_RUN"
    assert payload["next_action"]["classification"] == "environment"
    assert payload["recommendations"] == ["python -m venv .venv && python -m sdetkit gate fast"]


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
