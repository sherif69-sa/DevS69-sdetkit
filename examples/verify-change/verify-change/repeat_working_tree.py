"""Run with the Python environment that has sdetkit, pytest and coverage installed.

Creates a disposable calculator repository, verifies a fix twice, and checks that
only the fix, never the verifier's old evidence, enters the verified patch.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="sdetkit-repeat-example-") as directory:
        repo = Path(directory)

        def git(*args: str) -> None:
            subprocess.run(
                ["git", "-c", "user.name=Example", "-c", "user.email=example@invalid.local", *args],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            )

        (repo / "calc.py").write_text("def add(a, b):\n    return a - b\n")
        (repo / "test_calc.py").write_text(
            "from calc import add\n\ndef test_add():\n    assert add(2, 3) == 5\n"
        )
        git("init", "-q")
        git("add", ".")
        git("commit", "-qm", "calculator before the fix")
        (repo / "calc.py").write_text("def add(a, b):\n    return a + b\n")
        command = [
            sys.executable,
            "-m",
            "sdetkit",
            "verify",
            "change",
            "--working-tree",
            "--repo-root",
            str(repo),
            "--out-dir",
            str(repo / "reports"),
            "--python",
            sys.executable,
            "--format",
            "json",
        ]
        reports = []
        for number in (1, 2):
            result = subprocess.run(command, check=True, capture_output=True, text=True)
            report = json.loads(result.stdout)
            paths = [entry["path"] for entry in report["change"]["changed"]]
            assert report["status"] == "VERIFIED", report["reasons"]
            assert paths == ["calc.py"], paths
            reports.append(report)
            print(f"Run {number}: VERIFIED, changed paths: {paths}")
        assert reports[0]["change"]["patch_sha256"] == reports[1]["change"]["patch_sha256"]
        git("checkout", "--", "calc.py")
        clean = subprocess.run(command, check=False, capture_output=True, text=True)
        assert clean.returncode == 2 and "no uncommitted change" in clean.stderr, clean
        print("After reverting the fix: no uncommitted change, old reports are not a change.")


if __name__ == "__main__":
    main()
