from __future__ import annotations

import json
from pathlib import Path

from sdetkit import gate


def test_gate_format_text_includes_failed_steps() -> None:
    payload = {
        "ok": False,
        "failed_steps": ["ruff"],
        "steps": [{"id": "ruff", "ok": False, "rc": 1, "duration_ms": 1}],
    }
    out = gate._format_text(payload)
    assert "gate fast: FAIL" in out
    assert "failed_steps:" in out
    assert "- ruff" in out


def test_gate_format_md_includes_sections() -> None:
    payload = {
        "ok": True,
        "root": "/abs/repo",
        "failed_steps": [],
        "steps": [{"id": "pytest", "ok": True, "rc": 0, "duration_ms": 1}],
    }
    out = gate._format_md(payload)
    assert "### SDET Gate Fast" in out
    assert "#### Steps" in out
    assert "`pytest`" in out


def test_gate_write_output_creates_parent_dirs(tmp_path: Path) -> None:
    out = tmp_path / "a" / "b" / "out.txt"
    gate._write_output("hello\n", str(out))
    assert out.read_text(encoding="utf-8") == "hello\n"


def test_gate_fast_list_steps_prints(capsys) -> None:
    rc = gate.main(["fast", "--list-steps"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "pytest" in out
    assert "ruff" in out


def test_gate_fast_unknown_only_step_returns_2(capsys) -> None:
    rc = gate.main(["fast", "--only", "nope"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "unknown step id" in err


def test_gate_normalize_payload_keeps_non_dict_step() -> None:
    payload = {
        "profile": "fast",
        "root": "/abs/repo",
        "ok": True,
        "failed_steps": [],
        "steps": ["x"],
    }
    norm = gate._normalize_gate_payload(payload)
    assert norm["root"] == "<repo>"
    assert norm["steps"] == ["x"]


def test_gate_normalize_payload_normalizes_python_under_repo() -> None:
    payload = {
        "profile": "fast",
        "root": "/abs/repo",
        "ok": True,
        "failed_steps": [],
        "steps": [
            {
                "id": "ruff",
                "cmd": ["/abs/repo/.venv/bin/python3.12", "-m", "ruff", "check", "."],
                "rc": 0,
                "ok": True,
                "duration_ms": 1,
                "stdout": "x",
                "stderr": "y",
            }
        ],
    }
    norm = gate._normalize_gate_payload(payload)
    step = norm["steps"][0]
    assert step["cmd"][0] == "python"
    assert "duration_ms" not in step
    assert "stdout" not in step
    assert "stderr" not in step


def test_gate_fast_stable_json_out_writes_normalized_file(tmp_path: Path, monkeypatch) -> None:
    def fake_run(cmd, cwd):
        return {
            "cmd": cmd,
            "rc": 0,
            "ok": True,
            "duration_ms": 1,
            "stdout": "x",
            "stderr": "y",
        }

    monkeypatch.setattr(gate, "_run", fake_run)

    out_path = tmp_path / "gate-fast.json"
    rc = gate.main(
        [
            "fast",
            "--only",
            "ruff",
            "--format",
            "json",
            "--stable-json",
            "--out",
            str(out_path),
        ]
    )
    assert rc == 0

    text = out_path.read_text(encoding="utf-8")
    assert text.endswith("\n")
    obj = json.loads(text)
    assert obj["root"] == "<repo>"
    assert obj["steps"][0]["cmd"][0] == "python"
    assert "stdout" not in obj["steps"][0]
    assert "stderr" not in obj["steps"][0]
    assert "duration_ms" not in obj["steps"][0]


def test_gate_release_dry_run_text_output(capsys) -> None:
    rc = gate.main(["release", "--dry-run", "--format", "text"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "gate release:" in out
    assert "[DRY]" in out


def test_gate_format_release_text_includes_failed_steps() -> None:
    payload = {
        "ok": False,
        "steps": [{"id": "gate_fast", "ok": False, "rc": 2}],
        "failed_steps": ["gate_fast"],
    }
    out = gate._format_release_text(payload)
    assert "gate release: FAIL" in out
    assert "failed_steps:" in out
    assert "- gate_fast" in out
