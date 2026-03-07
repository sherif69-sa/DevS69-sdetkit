from __future__ import annotations

import argparse
import difflib
import json
from pathlib import Path

import pytest

from sdetkit import gate


def _ns(**kwargs: object) -> argparse.Namespace:
    base: dict[str, object] = {
        "root": ".",
        "only": None,
        "skip": None,
        "list_steps": False,
        "fix": False,
        "fix_only": False,
        "no_doctor": True,
        "no_ci_templates": True,
        "no_ruff": True,
        "no_mypy": True,
        "no_pytest": True,
        "strict": False,
        "format": "json",
        "out": None,
        "mypy_args": None,
        "full_pytest": False,
        "pytest_args": None,
        "stable_json": False,
        "dry_run": False,
        "release_full": False,
        "playbooks_all": False,
        "playbooks_legacy": False,
        "playbooks_aliases": False,
        "playbook_name": [],
    }
    base.update(kwargs)
    return argparse.Namespace(**base)


def test_run_fast_md_output_uses_markdown_formatter(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        gate,
        "_run",
        lambda cmd, cwd: {
            "cmd": cmd,
            "rc": 0,
            "ok": True,
            "duration_ms": 1,
            "stdout": "",
            "stderr": "",
        },
    )
    rc = gate._run_fast(
        _ns(
            format="md",
            no_doctor=True,
            no_ci_templates=True,
            no_mypy=True,
            no_pytest=True,
            no_ruff=False,
        )
    )
    assert rc == 0
    assert "### SDET Gate Fast" in capsys.readouterr().out


def test_baseline_check_handles_non_json_fast_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_fast(ns: argparse.Namespace) -> int:
        print("not-json-fast-output", end="")
        return 0

    monkeypatch.setattr(gate, "_run_fast", fake_fast)
    snap = tmp_path / ".sdetkit" / "baseline.txt"
    snap.parent.mkdir(parents=True, exist_ok=True)
    snap.write_text("{invalid-json", encoding="utf-8")

    monkeypatch.setattr(
        difflib,
        "unified_diff",
        lambda *args, **kwargs: iter(["--- snapshot\n", "+++ current\n", "@@\n", "-a\n", "+b"]),
    )

    rc = gate.main(["baseline", "check", "--path", str(snap), "--diff"])
    assert rc == 2
    assert "not-json-fast-output" in capsys.readouterr().out


def test_baseline_check_diff_payload_gets_trailing_newline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_fast(ns: argparse.Namespace) -> int:
        print('{"profile":"fast","ok":true,"steps":[],"failed_steps":[],"root":"."}')
        return 0

    monkeypatch.setattr(gate, "_run_fast", fake_fast)
    snap = tmp_path / ".sdetkit" / "baseline.json"
    snap.parent.mkdir(parents=True, exist_ok=True)
    snap.write_text("{}\n", encoding="utf-8")

    monkeypatch.setattr(
        difflib,
        "unified_diff",
        lambda *args, **kwargs: iter(["--- snapshot\n", "+++ current\n", "@@\n", "-a\n", "+b"]),
    )

    rc = gate.main(["baseline", "check", "--path", str(snap), "--diff"])
    assert rc == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["snapshot_diff"].endswith("\n")


def test_main_unknown_command_branch(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        argparse.ArgumentParser,
        "parse_args",
        lambda self, *args, **kwargs: argparse.Namespace(cmd="mystery"),
    )
    rc = gate.main(["whatever"])
    assert rc == 2
    assert "unknown gate command" in capsys.readouterr().err


def test_playbooks_validate_args_aliases_branch() -> None:
    ns = argparse.Namespace(playbooks_aliases=True, playbooks_all=False, playbooks_legacy=False)
    assert gate._playbooks_validate_args(ns) == ["--aliases", "--format", "json"]
