"""One repository model shared by gate, doctor, init and fit."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from sdetkit import doctor, fit, repo_adoption, repo_model
from sdetkit.adoption_surface import core as surface_core
from sdetkit.gates import gate, gate_config

FIXTURES = Path(__file__).parent / "fixtures" / "adoption_repos"


def _write(root: Path, rel: str, text: str = "") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_one_walk_matches_what_rglob_found(tmp_path: Path) -> None:
    for rel in (
        "pkg/a.py",
        "pkg/sub/b.py",
        "node_modules/dep/c.py",
        ".git/hooks/d.py",
        "tests/fixtures/sample/e.py",
        "build/lib/f.py",
        "Makefile",
    ):
        _write(tmp_path, rel)

    assert surface_core.walk_matching(tmp_path, "*.py") == ["pkg/a.py", "pkg/sub/b.py"]
    assert surface_core.walk_matching(tmp_path, "sub/*.py") == ["pkg/sub/b.py"]
    assert surface_core.walk_matching(tmp_path, "Makefile") == ["Makefile"]


def test_a_discovery_pass_walks_each_root_once(tmp_path: Path) -> None:
    _write(tmp_path, "a.py")
    with surface_core.shared_walk():
        first = surface_core.walk_files(tmp_path)
        _write(tmp_path, "b.py")
        assert surface_core.walk_files(tmp_path) == first
    assert surface_core.walk_files(tmp_path) == ("a.py", "b.py")


def test_the_model_reads_each_ecosystem_and_its_test_chain() -> None:
    go = repo_model.build_repo_model(FIXTURES / "go_module")
    cpp = repo_model.build_repo_model(FIXTURES / "cpp_operator_proof")
    nested = repo_model.build_repo_model(FIXTURES / "mixed_nested_go_workspaces")
    jenkins = repo_model.build_repo_model(FIXTURES / "jenkins_java")

    assert go.languages == ("go",)
    assert go.has_python is False
    assert [suite.step_id for suite in go.test_suites] == ["tests:go"]
    # A C++ suite configures and builds before it tests.
    assert cpp.test_suites[0].commands == (
        "cmake --preset ci",
        "cmake --build --preset ci",
        "ctest --preset ci",
    )
    assert [suite.working_directory for suite in nested.test_suites] == [
        "services/api",
        "services/worker",
    ]
    # Commands read out of a CI file are evidence, not a second suite.
    assert [suite.step_id for suite in jenkins.test_suites] == ["tests:java"]
    assert jenkins.ci_systems == ("jenkins",)


def test_test_fixtures_are_not_the_repository() -> None:
    model = repo_model.build_repo_model(Path(__file__).parents[1])

    assert model.languages == ("python",)
    assert [suite.step_id for suite in model.test_suites] == ["tests:python"]


def test_a_suite_never_runs_outside_the_repository() -> None:
    commands = [
        {
            "surface": "go",
            "purpose": "test",
            "confidence": "high",
            "command": "go test ./...",
            "source": {"working_directory": directory},
        }
        for directory in ("../elsewhere", "/abs", "svc")
    ]

    suites = repo_model._test_suites(commands, ("go",))

    assert [suite.working_directory for suite in suites] == ["svc"]


def _go_repo(tmp_path: Path) -> Path:
    _write(tmp_path, "go.mod", "module example.com/x\n\ngo 1.21\n")
    _write(tmp_path, "x.go", "package x\n")
    # A test/ directory used to make the gate run pytest in a Go repository.
    _write(tmp_path, "test/data.txt", "fixture\n")
    return tmp_path


def _gate_fast(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    root: Path,
    *args: str,
    rc: int = 0,
    installed: bool = True,
) -> tuple[int, dict[str, Any], list[list[str]]]:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], cwd: Path) -> dict[str, Any]:
        calls.append(cmd)
        return {"cmd": cmd, "rc": rc, "ok": rc == 0, "stdout": "", "stderr": ""}

    monkeypatch.setattr(gate, "_run", fake_run)
    monkeypatch.setattr(
        gate_config.shutil, "which", lambda name: f"/usr/bin/{name}" if installed else None
    )
    code = gate.main(["fast", "--root", str(root), "--no-doctor", "--format", "json", *args])
    return code, json.loads(capsys.readouterr().out), calls


def test_gate_runs_a_go_repository_s_own_tests_not_pytest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code, payload, calls = _gate_fast(monkeypatch, capsys, _go_repo(tmp_path))

    assert code == 0
    assert calls == [["go", "test", "./..."]]
    skipped = {item["id"]: item["reason"] for item in payload["skipped_steps"]}
    assert skipped["pytest"] == "no Python detected (repository languages: go)"
    assert payload["repo"] == {
        "languages": ["go"],
        "ci_systems": [],
        "test_suites": ["tests:go"],
    }
    assert payload["verdict"]["decision"] == "SHIP"


def test_a_failing_suite_blocks_and_names_its_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code, payload, _ = _gate_fast(monkeypatch, capsys, _go_repo(tmp_path), rc=1)

    assert code == 2
    assert payload["failed_steps"] == ["tests:go"]
    assert payload["next_action"]["next_command"] == "go test ./..."
    assert payload["verdict"]["decision"] == "NO_SHIP"


def test_a_suite_that_cannot_run_here_is_not_a_ship(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code, payload, calls = _gate_fast(monkeypatch, capsys, _go_repo(tmp_path), installed=False)

    assert code == 0
    assert calls == []
    assert payload["verdict"]["decision"] == "NOT_RUN"
    assert payload["verdict"]["reasons"] == ["tests:go did not run: go is not installed"]


@pytest.mark.parametrize("flags", [("--no-tests",), ("--skip", "tests"), ("--profile", "adoption")])
def test_suites_can_be_left_out(
    flags: tuple[str, ...],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _, payload, calls = _gate_fast(monkeypatch, capsys, _go_repo(tmp_path), *flags)

    assert not any(cmd[:1] == ["go"] for cmd in calls)
    assert payload["verdict"]["decision"] != "NOT_RUN"


def test_gate_release_keeps_a_fast_gate_that_proved_nothing_from_shipping(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    not_run = gate.build_verdict(source="gate fast", decision="NOT_RUN", reasons=["x"])

    def fake_run(cmd: list[str], cwd: Path) -> dict[str, Any]:
        stdout = json.dumps({"verdict": not_run}) if "gate" in cmd else ""
        return {"cmd": cmd, "rc": 0, "ok": True, "stdout": stdout, "stderr": ""}

    monkeypatch.setattr(gate, "_run", fake_run)

    assert gate.main(["release", "--root", str(tmp_path), "--format", "json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["verdict"]["decision"] == "NOT_RUN"
    assert "gate fast: NOT_RUN" in payload["verdict"]["reasons"]


def test_a_failing_chain_stops_and_keeps_the_failing_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_run(cmd: list[str], cwd: Path) -> dict[str, Any]:
        ok = cmd[0] != "make"
        return {"cmd": cmd, "rc": 0 if ok else 2, "ok": ok, "stdout": cmd[0], "stderr": ""}

    monkeypatch.setattr(gate, "_run", fake_run)

    result = gate._run_chain([["cmake", "."], ["make"], ["ctest"]], cwd=tmp_path)

    assert result["ok"] is False
    assert [step["cmd"][0] for step in result["chain"]] == ["cmake", "make"]
    assert result["stdout"] == "make"


def test_doctor_accepts_ci_on_any_system(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(tmp_path, "pyproject.toml", "[project]\nname = 'x'\n")
    _write(
        tmp_path,
        ".gitlab-ci.yml",
        "lint:\n  script:\n    - ruff check .\n"
        "audit:\n  script:\n    - pip-audit -r requirements.txt\n"
        "tests:\n  script:\n    - pytest -q\n",
    )
    monkeypatch.chdir(tmp_path)

    doctor.main(["--ci", "--only", "ci_workflows", "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["ci_missing"] == []
    assert data["checks"]["ci_workflows"]["ok"] is True


def test_doctor_still_names_what_ci_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(
        tmp_path, "Jenkinsfile", "pipeline { stages { stage('t') { steps { sh 'mvn test' } } } }\n"
    )
    monkeypatch.chdir(tmp_path)

    doctor.main(["--ci", "--only", "ci_workflows", "--format", "json"])

    data = json.loads(capsys.readouterr().out)
    assert data["ci_missing"] == ["quality", "security"]
    messages = [item["message"] for item in data["checks"]["ci_workflows"]["evidence"]]
    assert "linter or formatter" in messages[0]


def test_init_reports_the_repository_it_scaffolds(tmp_path: Path) -> None:
    payload = repo_adoption.build_init_payload(_go_repo(tmp_path), preset="enterprise_python")

    assert payload["repo_model"]["languages"] == ["go"]
    assert "Python CI" in payload["warnings"][0]
    assert payload["detected"]["has_test_command"] is True
    assert all("quality.sh" not in step for step in payload["next_commands"])
    assert payload["next_commands"][0].startswith("python -m sdetkit gate fast")
    rendered = repo_adoption.render_init_payload(payload, fmt="text")
    assert "test suite tests:go: go test ./..." in rendered


def test_init_has_no_warning_for_a_python_repository(tmp_path: Path) -> None:
    _write(tmp_path, "pyproject.toml", "[project]\nname = 'x'\n")

    assert repo_adoption.build_init_payload(tmp_path, preset="enterprise_python")["warnings"] == []


def test_fit_reads_the_repository(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert fit.main(["--root", str(_go_repo(tmp_path)), "--format", "json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["inputs"]["repo_size"] == "small"
    assert payload["repo"]["test_suites"] == ["tests:go"]
    assert payload["next_steps"][0].startswith("No CI system was detected")
    assert not any("gate-decision-summary" in step for step in payload["next_steps"])
