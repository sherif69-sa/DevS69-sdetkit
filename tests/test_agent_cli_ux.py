from __future__ import annotations

import json
import subprocess
import sys


def test_agent_help_lists_major_workflows() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "sdetkit", "agent", "--help"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0
    out = proc.stdout
    for phrase in ["init", "run", "templates", "serve", "history", "dashboard"]:
        assert phrase in out


def test_agent_run_help_shows_consistent_option_defaults() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "sdetkit", "agent", "run", "--help"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0
    out = proc.stdout
    assert "--config" in out
    assert ".sdetkit/agent/config.yaml" in out
    assert "--cache-dir" in out
    assert ".sdetkit/agent/cache" in out


def test_agent_user_error_is_single_line() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "sdetkit", "agent", "templates", "show", "missing-template"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 2
    assert "agent error:" in proc.stderr
    assert "Traceback" not in proc.stderr
    assert "\n" in proc.stderr
    assert len([x for x in proc.stderr.splitlines() if x.strip()]) == 1


def test_history_export_honors_history_dir_option(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    hist = tmp_path / "custom-history"
    hist.mkdir()
    record = {
        "captured_at": "2024-01-01T00:00:00Z",
        "hash": "abc",
        "status": "ok",
        "task": "demo",
        "actions": [],
    }
    (hist / "abc.json").write_text(json.dumps(record), encoding="utf-8")

    out_csv = tmp_path / "history.csv"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "sdetkit",
            "agent",
            "history",
            "export",
            "--history-dir",
            str(hist),
            "--output",
            str(out_csv),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0
    assert out_csv.exists()
