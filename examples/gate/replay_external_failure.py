"""Prove a gate follow-up works from outside the checked repository.

Run with the Python environment that has SDETKit and pytest installed.
The deliberately failing test and its report live only in a temporary folder.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> None:
    if os.name != "posix":
        raise SystemExit("This example executes a POSIX shell follow-up command.")
    with tempfile.TemporaryDirectory(prefix="sdetkit-followup-") as directory:
        folder = Path(directory)
        repo = folder / "example repo"
        (repo / "tests").mkdir(parents=True)
        (repo / "tests/test_total.py").write_text("def test_total():\n    assert 2 + 3 == 6\n")
        report_path = folder / "gate.json"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "sdetkit",
                "gate",
                "fast",
                "--root",
                str(repo),
                "--only",
                "pytest",
                "--python",
                sys.executable,
                "--format",
                "json",
                "--out",
                str(report_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2, result.stdout + result.stderr
        report = json.loads(report_path.read_text())
        assert report["verdict"]["decision"] == "NO_SHIP"
        command = report["next_action"]["next_command"]
        replay = subprocess.run(
            ["sh", "-c", command], cwd=folder, check=False, capture_output=True, text=True
        )
        assert replay.returncode == 1, replay.stdout + replay.stderr
        assert "FAILED tests/test_total.py::test_total" in replay.stdout
        print("Gate: NO_SHIP for the deliberately failing test.")
        print("Follow-up: reproduced that same failure from outside the repository.")
        print(command)


if __name__ == "__main__":
    main()
