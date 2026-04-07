from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPO_ROOT / "examples" / "adoption" / "real-repo"
BUILD_DIR = FIXTURE_ROOT / "build"
GOLDEN_DIR = REPO_ROOT / "artifacts" / "adoption" / "real-repo-golden"

CANONICAL_COMMANDS = (
    (
        [
            sys.executable,
            "-m",
            "sdetkit",
            "gate",
            "fast",
            "--format",
            "json",
            "--stable-json",
            "--out",
            "build/gate-fast.json",
        ],
        BUILD_DIR / "gate-fast.json",
        GOLDEN_DIR / "gate-fast.json",
    ),
    (
        [
            sys.executable,
            "-m",
            "sdetkit",
            "gate",
            "release",
            "--format",
            "json",
            "--out",
            "build/release-preflight.json",
        ],
        BUILD_DIR / "release-preflight.json",
        GOLDEN_DIR / "release-preflight.json",
    ),
    (
        [
            sys.executable,
            "-m",
            "sdetkit",
            "doctor",
            "--format",
            "json",
            "--out",
            "build/doctor.json",
        ],
        BUILD_DIR / "doctor.json",
        GOLDEN_DIR / "doctor.json",
    ),
)


def _run_command(cmd: list[str], expected_output: Path) -> None:
    proc = subprocess.run(cmd, cwd=FIXTURE_ROOT, text=True, capture_output=True, check=False)
    if not expected_output.is_file():
        raise RuntimeError(
            "expected output was not produced: "
            f"{expected_output}\n"
            f"command: {' '.join(cmd)}\n"
            f"returncode: {proc.returncode}\n"
            f"stdout:\n{proc.stdout}\n"
            f"stderr:\n{proc.stderr}"
        )

    if proc.returncode != 0:
        print(
            f"warning: command returned {proc.returncode} but produced {expected_output.name}",
            file=sys.stderr,
        )


def main() -> int:
    if not FIXTURE_ROOT.is_dir():
        raise FileNotFoundError(f"fixture directory not found: {FIXTURE_ROOT}")
    if not GOLDEN_DIR.is_dir():
        raise FileNotFoundError(f"golden directory not found: {GOLDEN_DIR}")

    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    for cmd, build_artifact, golden_artifact in CANONICAL_COMMANDS:
        _run_command(cmd, build_artifact)
        shutil.copyfile(build_artifact, golden_artifact)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
