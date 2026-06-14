from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import sdetkit.diagnostic_queue_runner_cli as cli
from sdetkit.diagnostic_queue_runner_cli import main


def _arguments(tmp_path: Path) -> list[str]:
    return [
        "--queue-path",
        str(tmp_path / "queue.json"),
        "--out-root",
        str(tmp_path / "worker"),
        "--input-root",
        str(tmp_path / "inputs"),
        "--max-jobs",
        "2",
        "--claimed-at",
        "2026-06-15T01:00:00Z",
        "--finished-at",
        "2026-06-15T02:00:00Z",
    ]


def test_cli_requires_explicit_arguments() -> None:
    with pytest.raises(SystemExit) as exc:
        main([])

    assert exc.value.code == 2


@pytest.mark.parametrize(
    "value",
    [
        "0",
        "-1",
        "not-an-integer",
    ],
)
def test_cli_rejects_invalid_max_jobs(
    tmp_path: Path,
    value: str,
) -> None:
    args = _arguments(tmp_path)
    index = args.index("--max-jobs") + 1
    args[index] = value

    with pytest.raises(SystemExit) as exc:
        main(args)

    assert exc.value.code == 2


def test_cli_runs_empty_queue_and_emits_json(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = main(_arguments(tmp_path))

    assert result == 0

    payload = json.loads(capsys.readouterr().out)

    assert payload["status"] == "completed"
    assert payload["stop_reason"] == "no_pending_jobs"
    assert payload["max_jobs"] == 2
    assert payload["jobs_attempted"] == 0
    assert payload["jobs_completed"] == 0
    assert payload["jobs_failed"] == 0

    assert payload["decision_boundary"]["automation_allowed"] is False
    assert payload["decision_boundary"]["merge_authorized"] is False
    assert payload["execution"]["automatic_retry"] is False


def test_cli_passes_explicit_arguments_to_runner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[str, Any] = {}

    def fake_runner(
        queue_path: Path,
        *,
        max_jobs: int,
        claimed_at: str,
        finished_at: str,
        out_root: Path,
        input_root: Path,
    ) -> dict[str, Any]:
        captured.update(
            {
                "queue_path": queue_path,
                "max_jobs": max_jobs,
                "claimed_at": claimed_at,
                "finished_at": finished_at,
                "out_root": out_root,
                "input_root": input_root,
            }
        )

        return {
            "schema_version": "runner.v1",
            "status": "completed",
            "stop_reason": "max_jobs_reached",
        }

    monkeypatch.setattr(
        cli,
        "run_bounded_diagnostic_queue",
        fake_runner,
    )

    result = main(_arguments(tmp_path))

    assert result == 0
    assert captured == {
        "queue_path": tmp_path / "queue.json",
        "max_jobs": 2,
        "claimed_at": "2026-06-15T01:00:00Z",
        "finished_at": "2026-06-15T02:00:00Z",
        "out_root": tmp_path / "worker",
        "input_root": tmp_path / "inputs",
    }

    payload = json.loads(capsys.readouterr().out)

    assert payload["status"] == "completed"


def test_cli_returns_one_for_runner_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fake_runner(
        *args: object,
        **kwargs: object,
    ) -> dict[str, Any]:
        return {
            "schema_version": "runner.v1",
            "status": "failed",
            "stop_reason": "job_failed",
            "jobs_attempted": 1,
            "jobs_completed": 0,
            "jobs_failed": 1,
        }

    monkeypatch.setattr(
        cli,
        "run_bounded_diagnostic_queue",
        fake_runner,
    )

    result = main(_arguments(tmp_path))

    assert result == 1

    payload = json.loads(capsys.readouterr().out)

    assert payload["status"] == "failed"
    assert payload["stop_reason"] == "job_failed"


def test_cli_emits_deterministic_error_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail_runner(
        *args: object,
        **kwargs: object,
    ) -> dict[str, Any]:
        raise ValueError("malformed local queue")

    monkeypatch.setattr(
        cli,
        "run_bounded_diagnostic_queue",
        fail_runner,
    )

    result = main(_arguments(tmp_path))

    assert result == 1

    payload = json.loads(capsys.readouterr().out)

    assert payload == {
        "schema_version": ("sdetkit.diagnostic_queue_runner_cli.v1"),
        "status": "error",
        "error": {
            "exception_type": "ValueError",
            "message": "malformed local queue",
        },
        "decision_boundary": {
            "automation_allowed": False,
            "automatic_retry": False,
            "proof_commands_executed": False,
            "patch_application_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        },
        "execution": {
            "automatic_retry": False,
            "proof_commands_executed": False,
            "patch_attempted": False,
            "merge_authorized": False,
        },
    }


def test_project_registers_queue_runner_script() -> None:
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")

    assert (
        'sdetkit-diagnostic-queue-runner = "sdetkit.diagnostic_queue_runner_cli:main"' in pyproject
    )
