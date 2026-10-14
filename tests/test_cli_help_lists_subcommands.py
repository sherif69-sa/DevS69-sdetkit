from __future__ import annotations

import subprocess
import sys


def test_root_help_lists_every_command_and_nothing_removed() -> None:
    from sdetkit.cli import COMMANDS

    r = subprocess.run(
        [sys.executable, "-m", "sdetkit", "--help"],
        text=True,
        capture_output=True,
    )
    assert r.returncode == 0
    listed = {line.split()[0] for line in r.stdout.splitlines() if line.startswith("    ")}
    assert set(COMMANDS) <= listed
    for removed in ("playbooks", "legacy", "agent", "weekly-review", "kpi-audit"):
        assert removed not in listed


def test_unknown_command_is_a_usage_error() -> None:
    r = subprocess.run(
        [sys.executable, "-m", "sdetkit", "playbooks"],
        text=True,
        capture_output=True,
    )
    assert r.returncode == 2
    assert "invalid choice: 'playbooks'" in r.stderr
