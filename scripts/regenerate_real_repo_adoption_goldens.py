from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from real_repo_adoption_projection import (
    CANONICAL_LANE_SPEC,
    build_lane_proof_summary,
    project_contract_for_artifact,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPO_ROOT / "examples" / "adoption" / "real-repo"
BUILD_DIR = FIXTURE_ROOT / "build"
GOLDEN_DIR = REPO_ROOT / "artifacts" / "adoption" / "real-repo-golden"
SUMMARY_FILE = "adoption-proof-summary.json"

CANONICAL_COMMANDS = tuple(
    (
        [sys.executable, "-m", "sdetkit", *spec["args"]],
        BUILD_DIR / spec["artifact"],
        BUILD_DIR / spec["rc_file"],
        GOLDEN_DIR / spec["artifact"],
        GOLDEN_DIR / spec["rc_file"],
    )
    for spec in CANONICAL_LANE_SPEC
)


def _reset_fixture_workspace() -> None:
    workspace_dir = FIXTURE_ROOT / ".sdetkit"
    if workspace_dir.exists():
        shutil.rmtree(workspace_dir)


def _run_command(cmd: list[str], expected_output: Path, rc_output: Path) -> None:
    _reset_fixture_workspace()
    proc = subprocess.run(cmd, cwd=FIXTURE_ROOT, text=True, capture_output=True, check=False)
    rc_output.write_text(f"{proc.returncode}\n", encoding="utf-8")

    if not expected_output.is_file():
        raise RuntimeError(
            "expected output was not produced: "
            f"{expected_output}\n"
            f"command: {' '.join(cmd)}\n"
            f"returncode: {proc.returncode}\n"
            f"stdout:\n{proc.stdout}\n"
            f"stderr:\n{proc.stderr}"
        )


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_summary(build_dir: Path, golden_dir: Path | None = None) -> None:
    summary = build_lane_proof_summary(
        fixture_root=FIXTURE_ROOT, repo_root=REPO_ROOT, build_dir=build_dir
    )
    summary_path = build_dir / SUMMARY_FILE
    summary_path.write_text(json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    if golden_dir is not None:
        shutil.copyfile(summary_path, golden_dir / SUMMARY_FILE)


def _regenerate_goldens() -> int:
    for cmd, build_artifact, build_rc, golden_artifact, golden_rc in CANONICAL_COMMANDS:
        _run_command(cmd, build_artifact, build_rc)
        shutil.copyfile(build_artifact, golden_artifact)
        shutil.copyfile(build_rc, golden_rc)
    _write_summary(BUILD_DIR, GOLDEN_DIR)
    _reset_fixture_workspace()
    return 0


def _check_goldens() -> int:
    mismatches: list[str] = []
    for cmd, build_artifact, build_rc, golden_artifact, golden_rc in CANONICAL_COMMANDS:
        _run_command(cmd, build_artifact, build_rc)
        generated = project_contract_for_artifact(
            build_artifact.name,
            _load_json(build_artifact),
            fixture_root=FIXTURE_ROOT,
            repo_root=REPO_ROOT,
        )
        golden = project_contract_for_artifact(
            golden_artifact.name,
            _load_json(golden_artifact),
            fixture_root=FIXTURE_ROOT,
            repo_root=REPO_ROOT,
        )
        if generated != golden:
            mismatches.append(golden_artifact.name)
        if (
            build_rc.read_text(encoding="utf-8").strip()
            != golden_rc.read_text(encoding="utf-8").strip()
        ):
            mismatches.append(golden_rc.name)

    _write_summary(BUILD_DIR)
    generated_summary = _load_json(BUILD_DIR / SUMMARY_FILE)
    golden_summary = _load_json(GOLDEN_DIR / SUMMARY_FILE)
    if generated_summary != golden_summary:
        mismatches.append(SUMMARY_FILE)

    if mismatches:
        print("real-repo adoption golden drift detected:", file=sys.stderr)
        for artifact in sorted(set(mismatches)):
            print(f"  - mismatch: {artifact}", file=sys.stderr)
        print(
            "run `python scripts/regenerate_real_repo_adoption_goldens.py` to intentionally refresh checked-in goldens.",
            file=sys.stderr,
        )
        _reset_fixture_workspace()
        return 1

    print("real-repo adoption goldens are up to date.")
    _reset_fixture_workspace()
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
