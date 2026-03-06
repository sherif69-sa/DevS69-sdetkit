from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from sdetkit import gate


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

    rc = gate.main(
        [
            "fast",
            "--strict",
            "--only",
            "doctor",
        ]
    )

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

    rc_write = gate.main(
        ["baseline", "write", "--", "--no-doctor", "--no-ci-templates", "--no-mypy", "--no-pytest"]
    )
    assert rc_write == 0
    capsys.readouterr()

    snap = tmp_path / ".sdetkit" / "gate.fast.snapshot.json"
    snap.write_text("{}", encoding="utf-8")

    rc_check = gate.main(
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
