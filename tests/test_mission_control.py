import json
from pathlib import Path

import pytest

from sdetkit import cli, mission_control


def _jsonl_records(path: Path):
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def test_mission_control_run_writes_json_markdown_and_ledger(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    out_dir = tmp_path / "out"

    rc = mission_control.main(["run", "--repo", str(repo), "--out-dir", str(out_dir)])

    assert rc == 0

    bundle_path = out_dir / "mission-control.json"
    brief_path = out_dir / "mission-control.md"
    ledger_path = repo / ".sdetkit" / "runs" / "mission-control-runs.jsonl"

    assert bundle_path.exists()
    assert brief_path.exists()
    assert ledger_path.exists()

    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    records = _jsonl_records(ledger_path)

    assert bundle["schema_version"] == "1"
    assert bundle["run_id"].startswith("mc-")
    assert bundle["ok"] is True
    assert bundle["mode"] == "plan"
    assert bundle["decision"] == "SHIP"
    assert bundle["risk_band"] == "low"
    assert bundle["repo"]["path"] == repo.resolve().as_posix()
    assert bundle["repo"]["branch"] == "unknown"
    assert bundle["repo"]["commit"] == "unknown"
    assert bundle["repo"]["dirty"] is False
    assert bundle["executed_step_count"] == 0
    assert [step["id"] for step in bundle["steps"]] == [
        "gate_fast",
        "gate_release",
        "doctor",
        "review",
        "readiness",
        "release_room",
    ]
    assert bundle["steps"][-1]["status"] == "planned"
    assert bundle["findings"] == []
    assert [artifact["kind"] for artifact in bundle["artifacts"]] == ["json", "markdown", "jsonl"]

    assert len(records) == 1
    assert records[0]["run_id"] == bundle["run_id"]
    assert records[0]["mode"] == "plan"
    assert records[0]["decision"] == "SHIP"
    assert records[0]["artifact_dir"] == out_dir.resolve().as_posix()

    brief = brief_path.read_text(encoding="utf-8")
    assert "# Mission Control" in brief
    assert f"Run ID: {bundle['run_id']}" in brief
    assert "Mode: plan" in brief
    assert "Decision: SHIP" in brief
    assert "gate_fast" in brief
    assert "release_room" in brief


def test_mission_control_no_ledger_suppresses_ledger_artifact(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    out_dir = tmp_path / "out"

    rc = mission_control.main(
        ["run", "--repo", str(repo), "--out-dir", str(out_dir), "--no-ledger"]
    )

    assert rc == 0

    bundle = json.loads((out_dir / "mission-control.json").read_text(encoding="utf-8"))

    assert not (repo / ".sdetkit").exists()
    assert [artifact["kind"] for artifact in bundle["artifacts"]] == ["json", "markdown"]


def test_mission_control_custom_ledger_path_appends_runs(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    out_dir_1 = tmp_path / "out1"
    out_dir_2 = tmp_path / "out2"
    ledger_path = tmp_path / "runs" / "mission-control.jsonl"

    assert (
        mission_control.main(
            [
                "run",
                "--repo",
                str(repo),
                "--out-dir",
                str(out_dir_1),
                "--ledger-path",
                str(ledger_path),
            ]
        )
        == 0
    )
    assert (
        mission_control.main(
            [
                "run",
                "--repo",
                str(repo),
                "--out-dir",
                str(out_dir_2),
                "--ledger-path",
                str(ledger_path),
            ]
        )
        == 0
    )

    records = _jsonl_records(ledger_path)

    assert len(records) == 2
    assert records[0]["run_id"] != records[1]["run_id"]
    assert records[0]["artifact_dir"] == out_dir_1.resolve().as_posix()
    assert records[1]["artifact_dir"] == out_dir_2.resolve().as_posix()


def test_mission_control_execute_writes_step_outputs(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    out_dir = tmp_path / "out"
    calls = []

    def fake_run_step_process(args, *, cwd, timeout_seconds):
        calls.append((list(args), cwd, timeout_seconds))
        return 0, "step stdout\n", "", 17

    monkeypatch.setattr(mission_control, "_run_step_process", fake_run_step_process)

    rc = mission_control.main(
        [
            "run",
            "--repo",
            str(repo),
            "--out-dir",
            str(out_dir),
            "--execute",
            "--no-ledger",
        ]
    )

    assert rc == 0

    bundle = json.loads((out_dir / "mission-control.json").read_text(encoding="utf-8"))
    executed = [step for step in bundle["steps"] if step["executed"] is True]

    assert bundle["mode"] == "execute"
    assert bundle["ok"] is True
    assert bundle["executed_step_count"] == 3
    assert bundle["passed_step_count"] == 3
    assert bundle["failed_step_count"] == 0
    assert [step["id"] for step in executed] == ["gate_fast", "doctor", "readiness"]
    assert all(step["status"] == "passed" for step in executed)
    assert all(step["rc"] == 0 for step in executed)
    assert len(calls) == 3

    for step in executed:
        stdout_path = Path(step["stdout_path"])
        stderr_path = Path(step["stderr_path"])
        assert stdout_path.read_text(encoding="utf-8") == "step stdout\n"
        assert stderr_path.read_text(encoding="utf-8") == ""


def test_mission_control_execute_include_release_adds_release_gate(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    out_dir = tmp_path / "out"

    def fake_run_step_process(args, *, cwd, timeout_seconds):
        return 0, "ok\n", "", 5

    monkeypatch.setattr(mission_control, "_run_step_process", fake_run_step_process)

    rc = mission_control.main(
        [
            "run",
            "--repo",
            str(repo),
            "--out-dir",
            str(out_dir),
            "--execute",
            "--include-release",
            "--no-ledger",
        ]
    )

    assert rc == 0

    bundle = json.loads((out_dir / "mission-control.json").read_text(encoding="utf-8"))
    executed_ids = [step["id"] for step in bundle["steps"] if step["executed"] is True]

    assert executed_ids == ["gate_fast", "gate_release", "doctor", "readiness"]
    assert bundle["executed_step_count"] == 4


def test_mission_control_execute_failed_step_sets_no_ship(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    out_dir = tmp_path / "out"

    def fake_run_step_process(args, *, cwd, timeout_seconds):
        if "doctor" in args:
            return 1, "", "doctor failed\n", 9
        return 0, "ok\n", "", 5

    monkeypatch.setattr(mission_control, "_run_step_process", fake_run_step_process)

    rc = mission_control.main(
        [
            "run",
            "--repo",
            str(repo),
            "--out-dir",
            str(out_dir),
            "--execute",
            "--no-ledger",
        ]
    )

    assert rc == 2

    bundle = json.loads((out_dir / "mission-control.json").read_text(encoding="utf-8"))

    assert bundle["ok"] is False
    assert bundle["decision"] == "NO_SHIP"
    assert bundle["risk_band"] == "high"
    assert bundle["failed_step_count"] == 1
    assert bundle["findings"][0]["code"] == "STEP_FAILED"


def test_mission_control_summarize_prints_stable_counts(tmp_path, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    out_dir = tmp_path / "out"

    assert (
        mission_control.main(["run", "--repo", str(repo), "--out-dir", str(out_dir), "--no-ledger"])
        == 0
    )

    capsys.readouterr()

    rc = mission_control.main(["summarize", "--bundle", str(out_dir / "mission-control.json")])

    assert rc == 0

    output = capsys.readouterr().out
    assert "run_id=mc-" in output
    assert "decision=SHIP" in output
    assert "risk_band=low" in output
    assert "mode=plan" in output
    assert "steps=6" in output
    assert "executed_steps=0" in output
    assert "failed_steps=0" in output
    assert "findings=0" in output


def test_mission_control_schema_lists_required_top_level_and_ledger_keys(capsys):
    rc = mission_control.main(["schema"])

    assert rc == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == "1"
    assert "run_id" in payload["required_top_level_keys"]
    assert "decision" in payload["required_top_level_keys"]
    assert "mode" in payload["required_top_level_keys"]
    assert "executed_step_count" in payload["required_top_level_keys"]
    assert "next_actions" in payload["required_top_level_keys"]
    assert "artifact_dir" in payload["ledger_record_keys"]
    assert "failure_rate" in payload["history_summary_keys"]
    assert "Executive summary" in payload["report_sections"]


def test_root_cli_dispatches_mission_control(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    out_dir = tmp_path / "out"

    rc = cli.main(
        [
            "mission-control",
            "run",
            "--repo",
            str(repo),
            "--out-dir",
            str(out_dir),
            "--no-ledger",
        ]
    )

    assert rc == 0
    assert (out_dir / "mission-control.json").exists()
    assert (out_dir / "mission-control.md").exists()


def test_root_cli_forwards_mission_control_help(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["mission-control", "--help"])

    assert exc.value.code == 0

    output = capsys.readouterr().out
    assert "sdetkit mission-control" in output
    assert "run" in output
    assert "summarize" in output
    assert "schema" in output
    assert "history" in output
    assert "report" in output


def test_mission_control_history_summarizes_text_ledger(tmp_path, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    ledger_path = tmp_path / "runs" / "mission-control.jsonl"

    assert (
        mission_control.main(
            [
                "run",
                "--repo",
                str(repo),
                "--out-dir",
                str(tmp_path / "one"),
                "--ledger-path",
                str(ledger_path),
            ]
        )
        == 0
    )
    assert (
        mission_control.main(
            [
                "run",
                "--repo",
                str(repo),
                "--out-dir",
                str(tmp_path / "two"),
                "--ledger-path",
                str(ledger_path),
            ]
        )
        == 0
    )

    capsys.readouterr()

    rc = mission_control.main(["history", "--ledger", str(ledger_path)])

    assert rc == 0

    output = capsys.readouterr().out
    assert "runs=2" in output
    assert "ship=2" in output
    assert "ship_with_findings=0" in output
    assert "no_ship=0" in output
    assert "latest_decision=SHIP" in output
    assert "latest_risk_band=low" in output
    assert "failure_rate=0.0" in output
    assert "most_common_failed_step=none" in output


def test_mission_control_history_json_reports_failed_step(tmp_path, monkeypatch, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    out_dir = tmp_path / "failed"
    ledger_path = tmp_path / "runs" / "mission-control.jsonl"

    def fake_run_step_process(args, *, cwd, timeout_seconds):
        if "doctor" in args:
            return 1, "", "doctor failed\n", 9
        return 0, "ok\n", "", 5

    monkeypatch.setattr(mission_control, "_run_step_process", fake_run_step_process)

    assert (
        mission_control.main(
            [
                "run",
                "--repo",
                str(repo),
                "--out-dir",
                str(out_dir),
                "--execute",
                "--ledger-path",
                str(ledger_path),
            ]
        )
        == 2
    )

    capsys.readouterr()

    rc = mission_control.main(["history", "--ledger", str(ledger_path), "--format", "json"])

    assert rc == 0

    summary = json.loads(capsys.readouterr().out)

    assert summary["runs"] == 1
    assert summary["no_ship"] == 1
    assert summary["failed_runs"] == 1
    assert summary["failure_rate"] == 1.0
    assert summary["latest_decision"] == "NO_SHIP"
    assert summary["most_common_failed_step"] == "doctor"


def test_mission_control_history_missing_ledger_is_empty(tmp_path, capsys):
    ledger_path = tmp_path / "missing.jsonl"

    rc = mission_control.main(["history", "--ledger", str(ledger_path)])

    assert rc == 0

    output = capsys.readouterr().out
    assert "runs=0" in output
    assert "latest_decision=none" in output
    assert "failure_rate=0.0" in output


def test_mission_control_report_writes_markdown_without_history(tmp_path, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    out_dir = tmp_path / "bundle"
    report_path = tmp_path / "report.md"

    assert (
        mission_control.main(["run", "--repo", str(repo), "--out-dir", str(out_dir), "--no-ledger"])
        == 0
    )

    capsys.readouterr()

    rc = mission_control.main(
        [
            "report",
            "--bundle",
            str(out_dir / "mission-control.json"),
            "--out",
            str(report_path),
        ]
    )

    assert rc == 0

    output = capsys.readouterr().out
    report = report_path.read_text(encoding="utf-8")

    assert "wrote " in output
    assert "decision=SHIP" in output
    assert "# Mission Control Report" in report
    assert "## Executive summary" in report
    assert "- Decision: SHIP" in report
    assert "- Risk band: low" in report
    assert "## History summary" in report
    assert "- not provided" in report
    assert "## Artifacts" in report


def test_mission_control_report_includes_history_summary(tmp_path, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    ledger_path = tmp_path / "runs" / "mission-control.jsonl"
    out_dir_1 = tmp_path / "one"
    out_dir_2 = tmp_path / "two"
    report_path = tmp_path / "report.md"

    assert (
        mission_control.main(
            [
                "run",
                "--repo",
                str(repo),
                "--out-dir",
                str(out_dir_1),
                "--ledger-path",
                str(ledger_path),
            ]
        )
        == 0
    )
    assert (
        mission_control.main(
            [
                "run",
                "--repo",
                str(repo),
                "--out-dir",
                str(out_dir_2),
                "--ledger-path",
                str(ledger_path),
            ]
        )
        == 0
    )

    capsys.readouterr()

    rc = mission_control.main(
        [
            "report",
            "--bundle",
            str(out_dir_2 / "mission-control.json"),
            "--history",
            str(ledger_path),
            "--out",
            str(report_path),
        ]
    )

    assert rc == 0

    output = capsys.readouterr().out
    report = report_path.read_text(encoding="utf-8")

    assert "history_runs=2" in output
    assert "- Runs: 2" in report
    assert "- Ship: 2" in report
    assert "- Latest decision: SHIP" in report
    assert "- Latest risk band: low" in report
    assert "- Failure rate: 0.0" in report
    assert "- Most common failed step: none" in report


def test_mission_control_bundle_output_redacts_sensitive_values(tmp_path):
    from sdetkit import mission_control

    bundle = {
        "run_id": "mc-test",
        "generated_at_utc": "2026-05-21T00:00:00Z",
        "decision": "review",
        "risk_band": "medium",
        "repo": {
            "path": "/repo",
            "branch": "main",
            "commit": "abc123",
            "dirty": False,
            ("tok" + "en"): "masked-value-alpha",
        },
        "mode": "plan",
        "steps": [],
        "executed_step_count": 0,
        "passed_step_count": 0,
        "failed_step_count": 0,
        "findings": [
            {
                "severity": "high",
                "code": "redaction-test",
                "message": ("tok" + "en") + "=masked-value-alpha",
            }
        ],
        "next_actions": [],
        "doctor_cortex": {
            "enabled": True,
            "ok": False,
            "diagnosis": {"diagnosis_count": 0},
            "prescriptions": {
                "prescription_count": 0,
                ("access" + "_" + "token"): "masked-value-beta",
            },
        },
    }

    mission_control.write_bundle(bundle, tmp_path)

    json_text = (tmp_path / "mission-control.json").read_text(encoding="utf-8")
    md_text = (tmp_path / "mission-control.md").read_text(encoding="utf-8")
    assert "masked-value-alpha" not in json_text
    assert "masked-value-alpha" not in md_text
    assert "masked-value-beta" not in json_text
    assert "masked-value-beta" not in md_text
    assert "tok" + "en" not in json_text
    assert "access" + "_" + "token" not in json_text
