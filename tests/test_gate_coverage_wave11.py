from __future__ import annotations

import argparse
import json
from pathlib import Path

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
            "--no-mypy",
            "--pytest-args",
            "-q tests/test_gate_fast.py -k smoke",
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
