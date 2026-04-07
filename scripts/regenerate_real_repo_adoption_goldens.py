from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from real_repo_adoption_projection import project_contract_for_artifact

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


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _regenerate_goldens() -> int:
    for cmd, build_artifact, golden_artifact in CANONICAL_COMMANDS:
        _run_command(cmd, build_artifact)
        shutil.copyfile(build_artifact, golden_artifact)
    return 0


def _check_goldens() -> int:
    mismatches: list[str] = []
    for cmd, build_artifact, golden_artifact in CANONICAL_COMMANDS:
        _run_command(cmd, build_artifact)
        generated = project_contract_for_artifact(build_artifact.name, _load_json(build_artifact), fixture_root=FIXTURE_ROOT, repo_root=REPO_ROOT)
        golden = project_contract_for_artifact(golden_artifact.name, _load_json(golden_artifact), fixture_root=FIXTURE_ROOT, repo_root=REPO_ROOT)
        if generated != golden:
            mismatches.append(golden_artifact.name)

    if mismatches:
        print("real-repo adoption golden drift detected:", file=sys.stderr)
        for artifact in mismatches:
            print(f"  - mismatch: {artifact}", file=sys.stderr)
        print(
            "run `python scripts/regenerate_real_repo_adoption_goldens.py` to intentionally refresh checked-in goldens.",
            file=sys.stderr,
        )
        return 1

    print("real-repo adoption goldens are up to date.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Regenerate or verify canonical real-repo adoption golden artifacts.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify generated outputs match checked-in goldens without rewriting files.",
    )
    args = parser.parse_args(argv)

    if not FIXTURE_ROOT.is_dir():
        raise FileNotFoundError(f"fixture directory not found: {FIXTURE_ROOT}")
    if not GOLDEN_DIR.is_dir():
        raise FileNotFoundError(f"golden directory not found: {GOLDEN_DIR}")

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    if args.check:
        return _check_goldens()
    return _regenerate_goldens()


if __name__ == "__main__":
    raise SystemExit(main())
