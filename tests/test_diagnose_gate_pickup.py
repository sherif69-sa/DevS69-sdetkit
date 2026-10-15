"""`diagnose run` with no --log picks up the failed steps of the latest gate run."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from sdetkit import gate, remediation_loop
from sdetkit.gates.latest_run import (
    LATEST_RUN_PATH,
    failed_step_outputs,
    load_latest_run,
    record_latest_run,
)

PYTEST_FAILURE = "FAILED tests/test_a.py::test_add - assert 3 == 4\n1 failed in 0.01s\n"


def _fast_payload(*, ok: bool) -> dict[str, Any]:
    steps = [{"id": "ruff", "ok": True, "rc": 0, "stdout": "All checks passed!", "stderr": ""}]
    if not ok:
        steps.append({"id": "pytest", "ok": False, "rc": 1, "stdout": PYTEST_FAILURE, "stderr": ""})
    return {"profile": "fast", "ok": ok, "steps": steps}


def test_gate_release_records_the_raw_output_of_its_steps(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def fake_run(cmd: list[str], cwd: Path) -> dict[str, object]:
        if cmd[3:5] == ["gate", "fast"]:
            fast = json.dumps(_fast_payload(ok=False))
            return {"cmd": cmd, "rc": 2, "ok": False, "stdout": fast, "stderr": "gate: problems"}
        return {"cmd": cmd, "rc": 0, "ok": True, "stdout": "{}", "stderr": ""}

    monkeypatch.setattr(gate, "_run", fake_run)
    monkeypatch.chdir(tmp_path)

    assert gate.main(["release", "--format", "json"]) == 2

    printed = json.loads(capsys.readouterr().out)
    assert all("stdout" not in step for step in printed["steps"])
    record = load_latest_run(tmp_path)
    assert record is not None and record["profile"] == "release" and record["ok"] is False
    assert failed_step_outputs(record) == [("gate_fast.pytest", PYTEST_FAILURE)]


def test_a_failed_step_without_nested_failures_uses_its_own_output() -> None:
    payload = {
        "steps": [
            {
                "id": "doctor_release",
                "ok": False,
                "rc": 2,
                "stdout": "{}",
                "stderr": "no CHANGELOG",
            },
            {"id": "gate_fast", "ok": False, "rc": 2, "stdout": "not json", "stderr": ""},
            {"id": "code_scanning", "ok": False, "rc": 1, "stdout": "", "stderr": ""},
        ]
    }

    assert failed_step_outputs(payload) == [
        ("doctor_release", "{}\nno CHANGELOG"),
        ("gate_fast", "not json"),
        ("code_scanning", "code_scanning failed with exit code 1"),
    ]


def test_no_recorded_gate_run_says_what_to_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = remediation_loop.main(["--repo-root", str(tmp_path), "--out-dir", str(tmp_path / "o")])

    assert rc == 2
    assert "run `python -m sdetkit gate fast` first" in capsys.readouterr().err


def test_a_passing_gate_run_has_nothing_to_diagnose(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    record_latest_run(tmp_path, _fast_payload(ok=True))

    rc = remediation_loop.main(
        ["--repo-root", str(tmp_path), "--out-dir", str(tmp_path / "o"), "--format", "json"]
    )

    assert rc == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True
    assert not (tmp_path / "o").exists()


def test_failed_steps_become_the_loops_logs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    record_latest_run(tmp_path, _fast_payload(ok=False))
    seen: dict[str, Any] = {}

    def fake_loop(**kwargs: Any) -> dict[str, Any]:
        seen.update(kwargs)
        return {"decision": "proof_not_run", "failure_count": 1, "artifacts": {}, "next_action": ""}

    monkeypatch.setattr(remediation_loop, "run_remediation_loop", fake_loop)

    assert (
        remediation_loop.main(["--repo-root", str(tmp_path), "--out-dir", str(tmp_path / "o")]) == 0
    )

    [log] = seen["log_paths"]
    assert Path(log) == tmp_path / "o/gate-logs/pytest/output.log"
    assert Path(log).read_text(encoding="utf-8") == PYTEST_FAILURE
    assert seen["rerun_args"] == ""
    assert (tmp_path / LATEST_RUN_PATH).is_file()


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
def test_a_gate_run_from_another_commit_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@example.com",
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "init",
        ],
        cwd=tmp_path,
        check=True,
    )
    record_latest_run(tmp_path, {**_fast_payload(ok=False), "provenance": {"head_sha": "0" * 40}})

    rc = remediation_loop.main(["--repo-root", str(tmp_path), "--out-dir", str(tmp_path / "o")])

    assert rc == 2
    assert "recorded on commit 000000000000" in capsys.readouterr().err


def test_the_next_action_for_a_gate_pickup_needs_no_log_flags() -> None:
    assert (
        remediation_loop._next_action(remediation_loop.DECISION_PROOF_NOT_RUN, [], "")
        == "python -m sdetkit diagnose run --prove"
    )
