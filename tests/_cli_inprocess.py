"""Run the ``sdetkit`` CLI in-process and return a ``CompletedProcess``-like result.

Tests that only need the CLI's exit code and output use this instead of a
subprocess so coverage measures the code they exercise.
"""

from __future__ import annotations

import io
import os
import subprocess
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from sdetkit import cli


def run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    out, err = io.StringIO(), io.StringIO()
    previous = Path.cwd()
    try:
        if cwd is not None:
            os.chdir(cwd)
        with redirect_stdout(out), redirect_stderr(err):
            try:
                rc = cli.main(list(args))
            except SystemExit as exc:
                rc = exc.code if isinstance(exc.code, int) else 1
    finally:
        os.chdir(previous)
    return subprocess.CompletedProcess(["sdetkit", *args], rc, out.getvalue(), err.getvalue())
