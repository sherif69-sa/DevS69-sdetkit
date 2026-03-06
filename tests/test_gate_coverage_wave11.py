from __future__ import annotations

import argparse
import json
import runpy
import sys
from pathlib import Path

import pytest

from sdetkit import gate


def _ns(**kwargs: object) -> argparse.Namespace:
    base: dict[str, object] = dict(
from pathlib import Path

from sdetkit import gate


def _ns_fast(**kwargs):
    base = dict(
        root=".",
        only=None,
        skip=None,
        list_steps=False,
        fix=False,
        fix_only=False,
        no_doctor=False,
        no_ci_templates=False,
        no_ruff=False,
        no_mypy=False,
        no_pytest=False,
        strict=False,
        format="text",
        out=None,
        mypy_args=None,
        full_pytest=False,
        pytest_args=None,
        stable_json=False,
        no_doctor=True,
        no_ci_templates=True,
        no_ruff=True,
        no_mypy=True,
        no_pytest=True,
        strict=False,
        format="json",
        out=None,
        stable_json=False,
        mypy_args=None,
        full_pytest=False,
        pytest_args=None,
    )
    base.update(kwargs)
    return argparse.Namespace(**base)


def _ok(cmd: list[str], cwd: Path) -> dict[str, object]:
    return {"cmd": cmd, "rc": 0, "ok": True, "duration_ms": 1, "stdout": "", "stderr": ""}


def test_format_md_includes_failed_steps_block() -> None:
    payload = {
        "ok": False,
        "root": ".",
        "steps": [{"id": "ruff", "ok": True, "duration_ms": 1, "rc": 0}],
        "failed_steps": ["doctor", "mypy"],
    }
    out = gate._format_md(payload)
    assert "#### Failed steps" in out
    assert "- `doctor`" in out
    assert "- `mypy`" in out


def test_run_fast_hits_doctor_ci_mypy_and_pytest_args(monkeypatch, capsys) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        calls.append(cmd)
        return _ok(cmd, cwd)

    monkeypatch.setattr(gate, "_run", fake_run)
    rc = gate._run_fast(
        _ns(
            strict=True,
            no_ruff=True,
            mypy_args="src tests",
            pytest_args="-q tests/test_gate_fast.py",
            format="text",
        )
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "gate fast: OK" in out
    assert any(cmd[3] == "doctor" and "medium" in cmd for cmd in calls)
    assert any("validate-templates" in " ".join(cmd) for cmd in calls)
    assert any(cmd[1:3] == ["-m", "mypy"] and cmd[-2:] == ["src", "tests"] for cmd in calls)
    assert any(
        cmd[1:3] == ["-m", "pytest"] and cmd[-2:] == ["-q", "tests/test_gate_fast.py"]
        for cmd in calls
    )


def test_run_fast_md_branch_with_failures(monkeypatch, capsys) -> None:
    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        ok = "mypy" not in cmd
        return {
            "cmd": cmd,
            "rc": 0 if ok else 1,
            "ok": ok,
            "duration_ms": 2,
            "stdout": "",
            "stderr": "",
        }

    monkeypatch.setattr(gate, "_run", fake_run)
    rc = gate._run_fast(_ns(no_ruff=True, format="md"))
    out = capsys.readouterr().out
    assert rc == 2
    assert "#### Failed steps" in out


def test_playbooks_validate_args_aliases_branch() -> None:
    ns = argparse.Namespace(
        playbooks_all=False,
        playbooks_legacy=False,
        playbooks_aliases=True,
        playbook_name=[],
    )
    assert gate._playbooks_validate_args(ns) == ["--aliases", "--format", "json"]


def test_baseline_relative_path_is_resolved_under_cwd(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    rc = gate.main(
        [
            "baseline",
            "write",
            "--path",
            "snaps/custom.json",
            "--",
            "--no-doctor",
            "--no-ci-templates",
def test_format_md_failed_steps_section_is_rendered() -> None:
    payload = {
        "ok": False,
        "root": "/tmp/repo",
        "steps": [{"id": "pytest", "ok": False, "rc": 2, "duration_ms": 3}],
        "failed_steps": ["pytest"],
    }

    text = gate._format_md(payload)

    assert "#### Failed steps" in text
    assert "- `pytest`" in text


def test_run_fast_executes_ci_templates_mypy_and_pytest_args(monkeypatch, capsys) -> None:
    seen: list[list[str]] = []

    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        seen.append(cmd)
        return {"cmd": cmd, "rc": 0, "ok": True, "duration_ms": 1, "stdout": "", "stderr": ""}

    monkeypatch.setattr(gate, "_run", fake_run)

    rc = gate._run_fast(
        _ns_fast(
            only="ci_templates,mypy,pytest",
            no_ci_templates=False,
            no_mypy=False,
            no_pytest=False,
            mypy_args="src tests",
            pytest_args="tests/test_gate_fast.py -q",
            format="text",
        )
    )

    assert rc == 0
    assert any(
        cmd[:5]
        == [
            gate.sys.executable,
            "-m",
            "sdetkit",
            "ci",
            "validate-templates",
        ]
        for cmd in seen
    )
    assert any(
        cmd[:3] == [gate.sys.executable, "-m", "mypy"] and cmd[-2:] == ["src", "tests"]
        for cmd in seen
    )
    assert any(
        cmd[:3] == [gate.sys.executable, "-m", "pytest"]
        and cmd[-2:] == ["tests/test_gate_fast.py", "-q"]
        for cmd in seen
    )
    assert "gate fast: OK" in capsys.readouterr().out


def test_run_fast_strict_doctor_uses_medium_fail_on(monkeypatch) -> None:
    seen: list[list[str]] = []

    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        seen.append(cmd)
        return {"cmd": cmd, "rc": 0, "ok": True, "duration_ms": 1, "stdout": "", "stderr": ""}

    monkeypatch.setattr(gate, "_run", fake_run)

    rc = gate._run_fast(_ns_fast(only="doctor", no_doctor=False, strict=True))

    assert rc == 0
    doctor_cmd = seen[0]
    fail_idx = doctor_cmd.index("--fail-on")
    assert doctor_cmd[fail_idx + 1] == "medium"


def test_playbooks_validate_args_aliases_variant() -> None:
import pytest

from sdetkit import gate

# Wave 11 deliberately adds many narrow deterministic tests to exercise
# branch-only behavior in gate.py that existing subprocess-focused tests
# don't execute under coverage instrumentation.


def _ok_result(cmd: list[str]) -> dict[str, object]:
    return {
        "cmd": cmd,
        "rc": 0,
        "ok": True,
        "duration_ms": 1,
        "stdout": "",
        "stderr": "",
    }


def test_format_md_includes_failed_steps_section() -> None:
    payload = {
        "ok": False,
        "root": "/repo",
        "steps": [{"id": "ruff", "ok": False, "rc": 1, "duration_ms": 2}],
        "failed_steps": ["ruff", "pytest"],
def _fail_result(cmd: list[str]) -> dict[str, object]:
    return {
        "cmd": cmd,
        "rc": 2,
        "ok": False,
        "duration_ms": 1,
        "stdout": "",
        "stderr": "boom",
    }


def test_format_md_emits_failed_steps_block() -> None:
    payload = {
        "ok": False,
        "root": "/repo",
        "steps": [{"id": "doctor", "ok": False, "duration_ms": 4, "rc": 2}],
        "failed_steps": ["doctor", "ruff"],
    }

    rendered = gate._format_md(payload)

    assert "#### Failed steps" in rendered
    assert "- `ruff`" in rendered
    assert "- `pytest`" in rendered


def test_run_fast_uses_medium_fail_on_when_strict(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[list[str]] = []

    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        seen.append(cmd)
        return _ok_result(cmd)

    monkeypatch.setattr(gate, "_run", fake_run)
    assert "- `doctor`" in rendered
    assert "- `ruff`" in rendered


@pytest.mark.parametrize(
    ("strict", "expected_fail_on"),
    [
        (False, "high"),
        (True, "medium"),
    ],
)
def test_run_fast_doctor_uses_expected_fail_on(
    strict: bool,
    expected_fail_on: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        assert cwd == tmp_path
        calls.append(cmd)
        return _ok_result(cmd)

    monkeypatch.setattr(gate, "_run", fake_run)
    monkeypatch.chdir(tmp_path)

    rc = gate.main(
        [
            "fast",
            "--strict",
            "--only",
            "doctor",
            "--format",
            "json",
            "--strict" if strict else "--no-doctor",
            "--no-ci-templates",
            "--no-ruff",
            "--no-mypy",
            "--no-pytest",
        ]
        if strict
        else [
            "fast",
            "--format",
            "json",
            "--no-doctor",
            "--no-ci-templates",
            "--no-ruff",
            "--no-mypy",
            "--no-pytest",
        ]
    )
    assert rc == 0
    assert (tmp_path / "snaps" / "custom.json").exists()


def test_baseline_returns_fast_rc_when_profile_execution_fails(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(gate, "_run_fast", lambda ns: 7)
    rc = gate.main(["baseline", "check", "--", "--no-doctor"])
    assert rc == 7


def test_baseline_handles_non_json_exception_during_cur_obj_parse(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_run_fast(ns: argparse.Namespace) -> int:
        # baseline captures stdout from this recursive call
        sys.stdout.write('{"ok": true, "steps": []}\n')
        return 0

    monkeypatch.setattr(gate, "_run_fast", fake_run_fast)

    real_loads = gate.json.loads

    calls = {"n": 0}

    def boom(text: str, *args: object, **kwargs: object) -> object:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom")
        return real_loads(text, *args, **kwargs)

    monkeypatch.setattr(gate.json, "loads", boom)
    rc = gate.main(["baseline", "check"])
    out = capsys.readouterr().out
    # restore for assertion parsing
    monkeypatch.setattr(gate.json, "loads", real_loads)
    obj = json.loads(out)
    assert rc == 2
    assert obj["snapshot_diff_ok"] is False


def test_baseline_diff_jsondecodeerror_fallbacks_and_diff_newline(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    snap = tmp_path / ".sdetkit" / "gate.fast.snapshot.json"
    snap.parent.mkdir(parents=True, exist_ok=True)
    snap.write_text("{bad snapshot", encoding="utf-8")

    def fake_run_fast(ns: argparse.Namespace) -> int:
        sys.stdout.write('{"ok": false, "steps": []}')
        return 0

    monkeypatch.setattr(gate, "_run_fast", fake_run_fast)
    monkeypatch.setattr(gate.difflib, "unified_diff", lambda *a, **k: iter(["DIFF-NO-NL"]))

    real_loads = gate.json.loads
    calls = {"n": 0}

    def selective_loads(text: str, *args: object, **kwargs: object) -> object:
        calls["n"] += 1
        # Force the line-501 branch once in diff generation (parse current side).
        if calls["n"] == 3:
            raise json.JSONDecodeError("forced", text, 0)
        return real_loads(text, *args, **kwargs)

    monkeypatch.setattr(gate.json, "loads", selective_loads)

    rc = gate.main(["baseline", "check", "--diff"])
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert rc == 2
    assert payload["snapshot_diff"].endswith("\n")
    assert payload["snapshot_diff_ok"] is False


def test_baseline_parsed_is_none_when_cur_text_is_invalid_json(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_run_fast(ns: argparse.Namespace) -> int:
        sys.stdout.write("not-json")
        return 0

    monkeypatch.setattr(gate, "_run_fast", fake_run_fast)
    rc = gate.main(["baseline", "check"])
    out = capsys.readouterr().out
    assert rc == 2
    assert out == "not-json"


def test_main_unknown_command_fallback_branch(monkeypatch) -> None:
    class FakeParser:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def add_subparsers(self, *args: object, **kwargs: object) -> FakeParser:
            return self

        def add_parser(self, *args: object, **kwargs: object) -> FakeParser:
            return self

        def add_argument(self, *args: object, **kwargs: object) -> None:
            return None

        def add_mutually_exclusive_group(self) -> FakeParser:
            return self

        def parse_args(self, argv: list[str] | None = None) -> argparse.Namespace:
            return argparse.Namespace(cmd="mystery")

    monkeypatch.setattr(gate.argparse, "ArgumentParser", FakeParser)
    assert gate.main(["ignored"]) == 2


def test_module_main_invocation_executes_system_exit(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["sdetkit.gate", "fast", "--list-steps"])
    with pytest.raises(SystemExit) as ex:
        runpy.run_module("sdetkit.gate", run_name="__main__")
    assert ex.value.code == 0

    assert rc == 0
    doctor_cmd = seen[0]
    assert "--fail-on" in doctor_cmd
    assert doctor_cmd[doctor_cmd.index("--fail-on") + 1] == "medium"


def test_run_fast_uses_high_fail_on_when_not_strict(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[list[str]] = []

    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        seen.append(cmd)
        return _ok_result(cmd)

    monkeypatch.setattr(gate, "_run", fake_run)

    rc = gate.main(["fast", "--only", "doctor"])

    assert rc == 0
    doctor_cmd = seen[0]
    assert doctor_cmd[doctor_cmd.index("--fail-on") + 1] == "high"


def test_run_fast_executes_ci_templates_step(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[list[str]] = []

    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        seen.append(cmd)
        return _ok_result(cmd)

    monkeypatch.setattr(gate, "_run", fake_run)

    rc = gate.main(["fast", "--only", "ci_templates"])

    assert rc == 0
    assert len(seen) == 1
    assert seen[0][2:5] == ["sdetkit", "ci", "validate-templates"]


def test_run_fast_mypy_args_from_shlex(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[list[str]] = []

    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        seen.append(cmd)
        return _ok_result(cmd)

    monkeypatch.setattr(gate, "_run", fake_run)
    payload = json.loads(capsys.readouterr().out)
    if strict:
        assert [s[3] for s in calls] == ["doctor"]
        idx = calls[0].index("--fail-on")
        assert calls[0][idx + 1] == expected_fail_on
        assert payload["steps"][0]["id"] == "doctor"
    else:
        assert calls == []
        assert payload["steps"] == []


def test_run_fast_ci_templates_branch_is_covered(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
def test_format_md_includes_failed_steps_section() -> None:
    payload = {
        "ok": False,
        "root": "/repo",
        "steps": [{"id": "ruff", "ok": False, "rc": 1, "duration_ms": 2}],
        "failed_steps": ["ruff"],
    }

    out = gate._format_md(payload)

    assert "#### Failed steps" in out
    assert "- `ruff`" in out


def test_run_fast_strict_sets_doctor_fail_on_medium(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        calls.append(cmd)
        return _ok_result(cmd)

    monkeypatch.setattr(gate, "_run", fake_run)
    monkeypatch.chdir(tmp_path)

    rc = gate.main(
        [
            "fast",
            "--format",
            "json",
            "--only",
            "ci_templates",
            "--strict",
            "--format",
            "json",
            "--only",
            "doctor",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["steps"][0]["id"] == "ci_templates"
    assert calls[0][3:6] == ["ci", "validate-templates", "--root"]


def test_run_fast_accepts_custom_mypy_args(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert payload["ok"] is True
    assert calls[0][3:] == [
        "doctor",
        "--dev",
        "--ci",
        "--deps",
        "--clean-tree",
        "--repo",
        "--fail-on",
        "medium",
        "--format",
        "json",
    ]


def test_run_fast_runs_ci_templates_step(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        calls.append(cmd)
        return _ok_result(cmd)

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
            "--no-pytest",
            "--mypy-args",
            "src tests --strict",
            "--only",
            "ci_templates",
        ]
    )

    assert rc == 0
    _ = json.loads(capsys.readouterr().out)
    assert calls[0][:3] == [gate.sys.executable, "-m", "mypy"]
    assert calls[0][3:] == ["src", "tests", "--strict"]


def test_run_fast_accepts_custom_pytest_args(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = json.loads(capsys.readouterr().out)
    assert [s["id"] for s in payload["steps"]] == ["ci_templates"]
    assert calls[0][3:] == [
        "ci",
        "validate-templates",
        "--root",
        str(Path(".").resolve()),
        "--format",
        "json",
        "--strict",
    ]


def test_run_fast_uses_custom_mypy_and_pytest_args(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        calls.append(cmd)
        return _ok_result(cmd)

    monkeypatch.setattr(gate, "_run", fake_run)
    monkeypatch.chdir(tmp_path)

    rc = gate.main(
        [
            "fast",
            "--only",
            "mypy",
            "--mypy-args",
            "src tests",
        ]
    )

    assert rc == 0
    assert seen[0][-2:] == ["src", "tests"]


def test_run_fast_pytest_args_from_shlex(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[list[str]] = []

    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        seen.append(cmd)
        return _ok_result(cmd)

    monkeypatch.setattr(gate, "_run", fake_run)

    rc = gate.main(
        [
            "fast",
            "--only",
            "pytest",
            "--pytest-args",
            "-q tests/test_gate_fast.py",
        ]
    )

    assert rc == 0
    assert seen[0][-2:] == ["-q", "tests/test_gate_fast.py"]


def test_run_fast_text_format_path(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        return _ok_result(cmd)

    monkeypatch.setattr(gate, "_run", fake_run)

    rc = gate.main(["fast", "--only", "ruff", "--format", "text"])

    assert rc == 0
    out = capsys.readouterr().out
    assert out.startswith("gate fast: OK")


def test_playbooks_validate_args_aliases_branch() -> None:
    ns = argparse.Namespace(
        playbooks_all=False,
        playbooks_legacy=False,
        playbooks_aliases=True,
        playbook_name=[],
    )

    args = gate._playbooks_validate_args(ns)

    assert args == ["--aliases", "--format", "json"]


@pytest.mark.parametrize(
    "profile, expected, extra_args",
    [
        (
            "fast",
            ".sdetkit/gate.fast.snapshot.json",
            ["--no-doctor", "--no-ci-templates", "--no-mypy", "--no-pytest"],
        ),
        ("release", ".sdetkit/gate.release.snapshot.json", ["--dry-run"]),
    ],
)
def test_baseline_uses_relative_default_snapshot_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    profile: str,
    expected: str,
    extra_args: list[str],
) -> None:
    monkeypatch.chdir(tmp_path)

    rc = gate.main(["baseline", "write", "--profile", profile, "--", *extra_args])

    assert rc == 0
    assert (tmp_path / expected).exists()


def test_baseline_returns_fast_rc_when_profile_call_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    original_main = gate.main

    def fake_main(argv: list[str] | None = None) -> int:
        if argv and argv[0] in {"fast", "release"}:
            return 2
        return original_main(argv)

    monkeypatch.setattr(gate, "main", fake_main)

    rc = original_main(
        ["baseline", "check", "--", "--no-doctor", "--no-ci-templates", "--no-mypy", "--no-pytest"]
    )

    assert rc == 2


def test_baseline_json_loads_exception_sets_cur_obj_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    original_main = gate.main

    class Boom(Exception):
        pass

    def fake_loads(s: str) -> object:
        raise Boom("boom")

    def fake_main(argv: list[str] | None = None) -> int:
        if argv and argv[0] == "fast":
            print("{not-json")
            return 0
        return original_main(argv)

    monkeypatch.setattr(gate.json, "loads", fake_loads)
    monkeypatch.setattr(gate, "main", fake_main)

    rc = original_main(
        ["baseline", "write", "--", "--no-doctor", "--no-ci-templates", "--no-mypy", "--no-pytest"]
    )

    assert rc == 0
    snap = tmp_path / ".sdetkit" / "gate.fast.snapshot.json"
    assert snap.read_text(encoding="utf-8") == "{not-json\n"


def test_baseline_diff_fallback_when_snapshot_is_not_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)

    rc_write = gate.main(
        ["baseline", "write", "--", "--no-doctor", "--no-ci-templates", "--no-mypy", "--no-pytest"]
    )
    assert rc_write == 0

    snap = tmp_path / ".sdetkit" / "gate.fast.snapshot.json"
    snap.write_text("not-json", encoding="utf-8")

    rc_check = gate.main(
        [
            "baseline",
            "check",
            "--diff",
            "--format",
            "json",
            "--no-doctor",
            "--no-ci-templates",
            "--no-ruff",
            "--no-mypy",
            "--pytest-args",
            "-q tests/test_gate_fast.py -k smoke",
            "text",
            "--no-doctor",
            "--no-ci-templates",
            "--no-ruff",
            "--mypy-args",
            "src tests",
            "--pytest-args",
            "-q tests/test_gate_coverage_wave11.py",
        ]
    )

    assert rc == 0
    _ = json.loads(capsys.readouterr().out)
    assert calls[0][:3] == [gate.sys.executable, "-m", "pytest"]
    assert calls[0][3:] == ["-q", "tests/test_gate_fast.py", "-k", "smoke"]


def test_run_fast_text_format_branch_on_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        if cmd[2] == "ruff":
            return _fail_result(cmd)
        return _ok_result(cmd)

    monkeypatch.setattr(gate, "_run", fake_run)
    monkeypatch.chdir(tmp_path)

    rc = gate.main(["fast", "--no-doctor", "--no-ci-templates", "--no-mypy", "--no-pytest"])

    out = capsys.readouterr()
    assert rc == 2
    assert "gate fast: FAIL" in out.out
    assert "failed_steps:" in out.out
    assert "gate: problems found" in out.err


@pytest.mark.parametrize(
    "args",
    [
        ["--playbooks-aliases"],
        ["--playbooks-all"],
        ["--playbooks-legacy"],
        ["--playbook-name", "day28", "--playbook-name", "day29"],
        [],
    ],
)
def test_playbooks_validate_args_matrix(args: list[str]) -> None:
    ns = argparse.Namespace(
        playbooks_aliases=False,
        playbooks_all=False,
        playbooks_legacy=False,
        playbook_name=[],
    )

    i = 0
    while i < len(args):
        item = args[i]
        if item == "--playbooks-aliases":
            ns.playbooks_aliases = True
            i += 1
            continue
        if item == "--playbooks-all":
            ns.playbooks_all = True
            i += 1
            continue
        if item == "--playbooks-legacy":
            ns.playbooks_legacy = True
            i += 1
            continue
        if item == "--playbook-name":
            ns.playbook_name.append(args[i + 1])
            i += 2
            continue
        i += 1

    out = gate._playbooks_validate_args(ns)

    if ns.playbooks_aliases:
        assert out == ["--aliases", "--format", "json"]
    elif ns.playbooks_all:
        assert out == ["--all", "--format", "json"]
    elif ns.playbooks_legacy:
        assert out == ["--legacy", "--format", "json"]
    elif ns.playbook_name:
        assert out == [
            "--name",
            "day28",
            "--name",
            "day29",
            "--format",
            "json",
        ]
    else:
        assert out == ["--recommended", "--format", "json"]


def test_baseline_relative_path_gets_joined_to_repo_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)

    rc_write = gate.main(
        [
            "baseline",
            "write",
            "--path",
            "snapshots/local.json",
            "--",
            "--no-doctor",
            "--no-ci-templates",
            "--no-mypy",
            "--no-pytest",
        ]
    )

    assert rc_write == 0
    assert (tmp_path / "snapshots" / "local.json").exists()


@pytest.mark.parametrize("profile", ["fast", "release"])
def test_baseline_forwards_nonzero_subcommand_rc(
    profile: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)

    real_main = gate.main

    def fake_main(argv: list[str] | None = None) -> int:
        args = list(argv or [])
        if args and args[0] in {"fast", "release"}:
            return 2
        return real_main(argv)

    monkeypatch.setattr(gate, "main", fake_main)

    rc = fake_main(["baseline", "check", "--profile", profile])

    assert rc == 2


def test_baseline_check_handles_invalid_json_from_subcommand(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    snap = tmp_path / ".sdetkit" / "gate.fast.snapshot.json"
    snap.parent.mkdir(parents=True, exist_ok=True)
    snap.write_text("hello\n", encoding="utf-8")

    real_main = gate.main
    _ = capsys.readouterr().out
    assert calls[0][2:] == ["mypy", "src", "tests"]
    assert calls[1][2:] == ["pytest", "-q", "tests/test_gate_coverage_wave11.py"]


def test_playbooks_validate_args_aliases_path() -> None:
    ns = argparse.Namespace(
        playbooks_all=False,
        playbooks_legacy=False,
        playbooks_aliases=True,
        playbook_name=[],
    )

    assert gate._playbooks_validate_args(ns) == ["--aliases", "--format", "json"]


def test_baseline_check_returns_upstream_failure_without_snapshot_io(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)

    original_main = gate.main

    def fake_main(argv: list[str] | None = None) -> int:
        args = list(argv or [])
        if args and args[0] == "fast":
            return 2
        return original_main(args)

    monkeypatch.setattr(gate, "main", fake_main)

    rc = fake_main(["baseline", "check", "--", "--no-doctor", "--no-ci-templates", "--no-mypy"])

    assert rc == 2
    assert not (tmp_path / ".sdetkit" / "gate.fast.snapshot.json").exists()


def test_baseline_check_handles_invalid_current_json_and_invalid_snapshot_json(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    monkeypatch.chdir(tmp_path)

    snap = tmp_path / ".sdetkit" / "gate.fast.snapshot.json"
    snap.parent.mkdir(parents=True, exist_ok=True)
    snap.write_text("{broken\n", encoding="utf-8")

    original_main = gate.main

    def fake_main(argv: list[str] | None = None) -> int:
        args = list(argv or [])
        if args and args[0] == "fast":
            print("not-json")
            return 0
        return real_main(argv)

    monkeypatch.setattr(gate, "main", fake_main)

    rc = fake_main(["baseline", "check", "--profile", "fast"])

    out = capsys.readouterr().out
    assert rc == 2
    assert out == "not-json\n"


def test_baseline_diff_tolerates_invalid_snapshot_and_current_json(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    snap = tmp_path / ".sdetkit" / "gate.fast.snapshot.json"
    snap.parent.mkdir(parents=True, exist_ok=True)
    snap.write_text("snapshot<<<\n", encoding="utf-8")

    real_main = gate.main

    def fake_main(argv: list[str] | None = None) -> int:
        args = list(argv or [])
        if args and args[0] == "fast":
            print("current>>>")
            return 0
        return real_main(argv)

    monkeypatch.setattr(gate, "main", fake_main)

    rc = fake_main(["baseline", "check", "--profile", "fast", "--diff", "--diff-context", "0"])

    out = capsys.readouterr().out
    assert rc == 2
    assert "current>>>" in out


def test_baseline_diff_appends_newline_when_unified_diff_lacks_it(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    snap = tmp_path / ".sdetkit" / "gate.fast.snapshot.json"
    snap.parent.mkdir(parents=True, exist_ok=True)
    snap.write_text('{"k": 1}\n', encoding="utf-8")

    real_main = gate.main

    def fake_main(argv: list[str] | None = None) -> int:
        args = list(argv or [])
        if args and args[0] == "fast":
            print('{"k": 2}')
            return 0
        return real_main(argv)

    def fake_unified_diff(*_args: object, **_kwargs: object):
        yield "--- snapshot"
        yield "+++ current"
        yield "@@ -1 +1 @@"
        yield '-{"k": 1}'
        yield '+{"k": 2}'

    monkeypatch.setattr(gate, "main", fake_main)
    monkeypatch.setattr(gate.difflib, "unified_diff", fake_unified_diff)

    rc = fake_main(["baseline", "check", "--profile", "fast", "--diff"])

    payload = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert payload["snapshot_diff"].endswith("\n")


def test_baseline_check_json_parse_failure_for_output_object(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    snap = tmp_path / ".sdetkit" / "gate.fast.snapshot.json"
    snap.parent.mkdir(parents=True, exist_ok=True)
    snap.write_text("old\n", encoding="utf-8")

    real_main = gate.main

    def fake_main(argv: list[str] | None = None) -> int:
        args = list(argv or [])
        if args and args[0] == "fast":
            print("new")
            return 0
        return real_main(argv)

    monkeypatch.setattr(gate, "main", fake_main)

    rc = fake_main(["baseline", "check", "--profile", "fast", "--diff"])

    out = capsys.readouterr().out
    assert rc == 2
    assert out == "new\n"


def test_release_text_format_with_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    outcomes = {
        "doctor_release": True,
        "playbooks_validate": False,
        "gate_fast": True,
    }

    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        step = "doctor_release"
        if "playbooks" in cmd:
            step = "playbooks_validate"
        if "gate" in cmd and "fast" in cmd:
            step = "gate_fast"
        return _ok_result(cmd) if outcomes[step] else _fail_result(cmd)

    monkeypatch.setattr(gate, "_run", fake_run)
    monkeypatch.chdir(tmp_path)

    rc = gate.main(["release", "--format", "text"])

    out = capsys.readouterr()
    assert rc == 2
    assert "gate release: FAIL" in out.out
    assert "[FAIL] playbooks_validate rc=2" in out.out
    assert "gate: problems found" in out.err


def test_release_dry_run_marks_dry_status_in_text(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)

    rc = gate.main(["release", "--dry-run", "--format", "text"])

    out = capsys.readouterr().out
    assert rc == 0
    assert "[DRY] doctor_release rc=None" in out
    assert "[DRY] playbooks_validate rc=None" in out
    assert "[DRY] gate_fast rc=None" in out


def test_main_unknown_command_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    real_parse_args = argparse.ArgumentParser.parse_args

    def fake_parse_args(self: argparse.ArgumentParser, args: list[str] | None = None):
        class NS:
            cmd = "mystery"

        return NS()

    monkeypatch.setattr(argparse.ArgumentParser, "parse_args", fake_parse_args)

    try:
        assert gate.main(["ignored"]) == 2
    finally:
        monkeypatch.setattr(argparse.ArgumentParser, "parse_args", real_parse_args)


# Additional tiny helper-coverage tests to safely increase exercised branches.


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, set()),
        ("", set()),
        ("doctor", {"doctor"}),
        ("doctor,ruff", {"doctor", "ruff"}),
        (" doctor , , ruff ", {"doctor", "ruff"}),
    ],
)
def test_parse_step_filter_cases(raw: str | None, expected: set[str]) -> None:
    assert gate._parse_step_filter(raw) == expected


@pytest.mark.parametrize(
    "payload",
    [
        {"ok": True, "steps": []},
        {
            "ok": False,
            "steps": [{"id": "a", "ok": False, "rc": 1, "duration_ms": 0}],
            "failed_steps": ["a"],
        },
    ],
)
def test_format_text_is_stable(payload: dict[str, object]) -> None:
    text = gate._format_text(payload)
    assert text.endswith("\n")
    assert text.startswith("gate fast:")


@pytest.mark.parametrize(
    "profile",
    ["fast", "release"],
)
def test_baseline_snapshot_path(profile: str, tmp_path: Path) -> None:
    out = gate._baseline_snapshot_path(tmp_path, profile)
    assert out.parent == tmp_path / ".sdetkit"
    assert out.name.startswith("gate.")


@pytest.mark.parametrize(
    "cmd",
    [
        [gate.sys.executable, "-m", "x"],
        ["python", "-m", "x"],
        ["/tmp/repo", "/tmp/repo/path"],
    ],
)
def test_normalize_release_cmd_general(cmd: list[str], tmp_path: Path) -> None:
    root = Path("/tmp/repo")
    normalized = gate._normalize_release_cmd(cmd, root)
    assert len(normalized) == len(cmd)


@pytest.mark.parametrize(
    "with_failed",
    [False, True],
)
def test_format_release_text_with_and_without_failed(with_failed: bool) -> None:
    payload = {
        "ok": not with_failed,
        "steps": [
            {"id": "doctor_release", "ok": not with_failed, "rc": 0 if not with_failed else 1}
        ],
        "failed_steps": ["doctor_release"] if with_failed else [],
    }
    out = gate._format_release_text(payload)
    assert out.endswith("\n")
    if with_failed:
        assert "failed_steps:" in out


@pytest.mark.parametrize(
    "stable",
    [False, True],
)
def test_fast_json_and_stable_json_paths(
    stable: bool,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        return _ok_result(cmd)

    monkeypatch.setattr(gate, "_run", fake_run)
    monkeypatch.chdir(tmp_path)

    argv = [
        "fast",
        "--format",
        "json",
        "--no-doctor",
        "--no-ci-templates",
        "--no-ruff",
        "--no-mypy",
    ]
    if stable:
        argv.append("--stable-json")

    rc = gate.main(argv)

    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["profile"] == "fast"


@pytest.mark.parametrize(
    "with_output",
    [False, True],
)
def test_write_output_paths(
    with_output: bool, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = None
    if with_output:
        out = str(tmp_path / "dir" / "out.txt")

    gate._write_output("hello\n", out)

    if with_output:
        assert (tmp_path / "dir" / "out.txt").read_text(encoding="utf-8") == "hello\n"
    else:
        assert capsys.readouterr().out == "hello\n"


@pytest.mark.parametrize(
    "profile",
    ["fast", "release"],
)
def test_baseline_write_and_check_round_trip_profiles(
    profile: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    base_args = ["--profile", profile]
    passthrough = (
        ["--", "--dry-run"]
        if profile == "release"
        else [
            "--",
            "--no-doctor",
            "--no-ci-templates",
            "--no-mypy",
            "--no-pytest",
        ]
    )

    out = capsys.readouterr().out
    data = json.loads(out)
    assert rc_check == 2
    assert data["snapshot_diff_ok"] is False
    assert data["snapshot_diff"].startswith("--- snapshot")


def test_baseline_diff_fallback_when_current_is_not_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)

    original_main = gate.main

    def fake_main(argv: list[str] | None = None) -> int:
        if argv and argv[0] == "fast":
            print("this-is-not-json")
            return 0
        return original_main(argv)

    monkeypatch.setattr(gate, "main", fake_main)

    rc = original_main(
        [
            "baseline",
            "check",
            "--diff",
            "--",
            "--no-doctor",
            "--no-ci-templates",
            "--no-mypy",
            "--no-pytest",
        ]
    )

    out = capsys.readouterr().out
    assert rc == 2
    # Current output is invalid JSON in this scenario, so plain output is expected.
    assert "this-is-not-json" in out


def test_baseline_diff_payload_gets_trailing_newline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)

    rc_write = gate.main(["baseline", "write", *base_args, *passthrough])
    assert rc_write == 0
    capsys.readouterr()

    rc_check = gate.main(["baseline", "check", *base_args, *passthrough])
    payload = json.loads(capsys.readouterr().out)

    assert rc_check == 0
    assert payload["snapshot_diff_ok"] is True


@pytest.mark.parametrize(
    "mode",
    ["text", "json"],
)
def test_release_format_modes_pass(
    mode: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        return _ok_result(cmd)

    monkeypatch.setattr(gate, "_run", fake_run)
    monkeypatch.chdir(tmp_path)

    rc = gate.main(["release", "--format", mode])

    out = capsys.readouterr().out
    assert rc == 0
    if mode == "json":
        assert json.loads(out)["ok"] is True
    else:
        assert "gate release: OK" in out
            print("{not-json")
            return 0
        return original_main(args)

    monkeypatch.setattr(gate, "main", fake_main)

    rc = fake_main(["baseline", "check", "--diff"])

    out = capsys.readouterr().out
    assert rc == 2
    assert out.startswith("{not-json")


def test_baseline_check_diff_context_negative_is_clamped(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    rc_write = gate.main(
        ["baseline", "write", "--", "--no-doctor", "--no-ci-templates", "--no-mypy", "--no-pytest"]
    )
    assert rc_write == 0
    capsys.readouterr()

    snap = tmp_path / ".sdetkit" / "gate.fast.snapshot.json"
    snap.write_text("{}", encoding="utf-8")
    snap.write_text("{}\n", encoding="utf-8")

    rc_check = gate.main(
        [
            "baseline",
            "check",
            "--diff",
            "--diff-context",
            "-4",
            "--",
            "--no-doctor",
            "--no-ci-templates",
            "--no-mypy",
            "--no-pytest",
        ]
    )

    out = capsys.readouterr().out
    data = json.loads(out)
    assert rc_check == 2
    assert data["snapshot_diff"].endswith("\n")


def test_baseline_invalid_current_text_skips_output_object_enrichment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)

    original_main = gate.main

    def fake_main(argv: list[str] | None = None) -> int:
        if argv and argv[0] == "fast":
            print("[not-a-dict]")
            return 0
        return original_main(argv)

    monkeypatch.setattr(gate, "main", fake_main)

    rc = original_main(
        [
            "baseline",
            "check",
    payload = json.loads(capsys.readouterr().out)
    assert rc_check == 2
    assert payload["snapshot_diff_ok"] is False
    assert payload["snapshot_diff"].startswith("--- snapshot\n+++ current\n")


def test_baseline_check_with_relative_path_writes_under_repo(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    rc = gate.main(
        [
            "baseline",
            "write",
            "--path",
            "artifacts/snap.json",
            "--",
            "--no-doctor",
            "--no-ci-templates",
            "--no-mypy",
            "--no-pytest",
        ]
    )

    out = capsys.readouterr().out
    assert rc == 2
    assert out.strip() == "[not-a-dict]"


def test_main_unknown_command_branch(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class FakeParser:
        def add_subparsers(self, **kwargs):
            class FakeSub:
                def add_parser(self, *a, **k):
                    class P:
                        def add_argument(self, *aa, **kk):
                            return None

                        def add_mutually_exclusive_group(self):
                            class G:
                                def add_argument(self, *aaa, **kkk):
                                    return None

                            return G()

                    return P()

            return FakeSub()

        def parse_args(self, args):
            return argparse.Namespace(cmd="unexpected")

    monkeypatch.setattr(gate.argparse, "ArgumentParser", lambda *a, **k: FakeParser())

    rc = gate.main(["unexpected"])

    assert rc == 2
    assert "unknown gate command" in capsys.readouterr().err


@pytest.mark.parametrize(
    "args, expected_step_count",
    [
        (["fast", "--only", "ruff"], 1),
        (["fast", "--only", "ruff_format"], 1),
        (["fast", "--only", "mypy"], 1),
        (["fast", "--only", "pytest"], 1),
        (["fast", "--only", "doctor"], 1),
        (["fast", "--only", "ci_templates"], 1),
    ],
)
def test_fast_only_runs_targeted_step(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    args: list[str],
    expected_step_count: int,
) -> None:
    seen: list[list[str]] = []

    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        seen.append(cmd)
        return _ok_result(cmd)

    monkeypatch.setattr(gate, "_run", fake_run)

    rc = gate.main(args + ["--format", "json"])

    assert rc == 0
    assert len(seen) == expected_step_count
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["steps"]) == expected_step_count


@pytest.mark.parametrize(
    "skip_target",
    ["doctor", "ci_templates", "ruff", "ruff_format", "mypy", "pytest"],
)
def test_fast_skip_removes_individual_step(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    skip_target: str,
) -> None:
    seen: list[list[str]] = []

    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        seen.append(cmd)
        return _ok_result(cmd)

    monkeypatch.setattr(gate, "_run", fake_run)

    rc = gate.main(
        [
            "fast",
            "--skip",
            skip_target,
            "--no-doctor",
            "--no-ci-templates",
            "--no-ruff",
            "--no-mypy",
            "--no-pytest",
            "--format",
            "json",
    assert rc == 0
    assert (tmp_path / "artifacts" / "snap.json").exists()


def test_main_unknown_command_fallback(monkeypatch, capsys) -> None:
    class _FakeParser:
        def add_subparsers(self, *args, **kwargs):
            class _FakeSub:
                def add_parser(self, *a, **k):
                    class _P:
                        def add_argument(self, *a2, **k2):
                            return None

                        def add_mutually_exclusive_group(self):
                            class _G:
                                def add_argument(self, *a3, **k3):
                                    return None

                            return _G()

                    return _P()

            return _FakeSub()

        def parse_args(self, args=None):
            return argparse.Namespace(cmd="mystery")

    monkeypatch.setattr(gate.argparse, "ArgumentParser", lambda *a, **k: _FakeParser())

    rc = gate.main([])
    args = gate._playbooks_validate_args(ns)

    assert args == ["--aliases", "--format", "json"]


def test_baseline_uses_relative_snapshot_path_and_write(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)

    rc = gate.main(
        [
            "baseline",
            "write",
            "--path",
            "snapshots/gate.json",
            "--",
            "--no-doctor",
            "--no-ci-templates",
            "--no-mypy",
            "--no-pytest",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["steps"] == []
    assert seen == []


def test_release_json_output_includes_repo_root_placeholder(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        return _ok_result(cmd)

    monkeypatch.setattr(gate, "_run", fake_run)

    rc = gate.main(["release", "--format", "json"])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["root"] == "<repo>"


def test_release_returns_nonzero_and_writes_error_when_step_fails(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    call = {"n": 0}

    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        call["n"] += 1
        if call["n"] == 2:
            return {
                "cmd": cmd,
                "rc": 9,
                "ok": False,
                "duration_ms": 1,
                "stdout": "",
                "stderr": "",
            }
        return _ok_result(cmd)

    monkeypatch.setattr(gate, "_run", fake_run)

    rc = gate.main(["release", "--format", "text"])

    assert rc == 2
    err = capsys.readouterr().err
    assert "gate: problems found" in err


def test_baseline_release_profile_check_works_with_dry_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)

    rc1 = gate.main(["baseline", "write", "--profile", "release", "--", "--dry-run"])
    assert rc1 == 0
    capsys.readouterr()

    rc2 = gate.main(["baseline", "check", "--profile", "release", "--", "--dry-run"])

    out = capsys.readouterr().out
    data = json.loads(out)
    assert rc2 == 0
    assert data["snapshot_diff_ok"] is True
    assert (tmp_path / "snapshots" / "gate.json").exists()


def test_baseline_propagates_nonzero_fast_rc(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    rc = gate.main(["baseline", "check", "--", "--only", "nope"])

    assert rc == 2
    assert capsys.readouterr().out == ""


def test_baseline_handles_non_json_current_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_fast(ns: argparse.Namespace) -> int:
        print("not-json")
        return 0

    monkeypatch.setattr(gate, "_run_fast", fake_fast)

    rc = gate.main(["baseline", "check", "--diff", "--", "--no-doctor"])

    assert rc == 2
    assert capsys.readouterr().out == "not-json\n"


def test_baseline_diff_keeps_invalid_snapshot_and_current_text(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    snap = tmp_path / ".sdetkit" / "gate.fast.snapshot.json"
    snap.parent.mkdir(parents=True, exist_ok=True)
    snap.write_text("old-snapshot", encoding="utf-8")

    def fake_fast(ns: argparse.Namespace) -> int:
        print("new-current", end="")
        return 0

    monkeypatch.setattr(gate, "_run_fast", fake_fast)

    rc = gate.main(["baseline", "check", "--diff", "--", "--no-doctor"])

    assert rc == 2
    assert capsys.readouterr().out == "new-current"


def test_baseline_when_current_json_decode_fails_keeps_raw_text(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    snap = tmp_path / ".sdetkit" / "gate.fast.snapshot.json"
    snap.parent.mkdir(parents=True, exist_ok=True)
    snap.write_text("{}\n", encoding="utf-8")

    def fake_fast(ns: argparse.Namespace) -> int:
        print("still-not-json")
        return 0

    monkeypatch.setattr(gate, "_run_fast", fake_fast)

    rc = gate.main(["baseline", "check", "--", "--no-doctor"])

    assert rc == 2


def test_main_unknown_gate_command_branch(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    class FakeParser:
        def __init__(self, *args, **kwargs):
            pass

        def add_subparsers(self, **kwargs):
            class FakeSub:
                def add_parser(self, *a, **k):
                    class FakeCmd:
                        def add_argument(self, *args, **kwargs):
                            return None

                        def add_mutually_exclusive_group(self):
                            class FakeGroup:
                                def add_argument(self, *args, **kwargs):
                                    return None

                            return FakeGroup()

                    return FakeCmd()

            return FakeSub()

        def parse_args(self, *_args, **_kwargs):
            return argparse.Namespace(cmd="mystery")

    monkeypatch.setattr(gate.argparse, "ArgumentParser", FakeParser)

    rc = gate.main(["does-not-matter"])

    assert rc == 2
    assert "unknown gate command" in capsys.readouterr().err
