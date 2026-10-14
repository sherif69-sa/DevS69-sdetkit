from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"

if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

_existing = os.environ.get("PYTHONPATH", "")
if _existing:
    if str(_SRC) not in _existing.split(os.pathsep):
        os.environ["PYTHONPATH"] = f"{_SRC}{os.pathsep}{_existing}"
else:
    os.environ["PYTHONPATH"] = str(_SRC)

from sdetkit.test_bootstrap import build_test_bootstrap_report  # noqa: E402

_TRACKED_STATE_KEY = pytest.StashKey[dict[str, str]]()


def _tracked_file_state() -> dict[str, str] | None:
    """Map each modified tracked file to its content hash, or None outside git."""

    try:
        changed = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
        if not changed:
            return {}
        hashes = subprocess.run(
            ["git", "hash-object", "--", *changed],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        ).stdout.split()
    except (OSError, subprocess.CalledProcessError):
        return None
    return dict(zip(changed, hashes, strict=False))


def _is_xdist_worker(config: pytest.Config) -> bool:
    return hasattr(config, "workerinput")


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Fail the run when tests modified tracked repository files."""

    if _is_xdist_worker(session.config) or _TRACKED_STATE_KEY not in session.config.stash:
        return
    after = _tracked_file_state()
    if after is None:
        return
    before = session.config.stash[_TRACKED_STATE_KEY]
    touched = sorted(path for path, digest in after.items() if before.get(path) != digest)
    if touched:
        sys.stderr.write(
            "\nTests modified tracked repository files (write to tmp_path instead):\n"
            + "".join(f"  - {path}\n" for path in touched)
        )
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_sessionstart(session: pytest.Session) -> None:
    """Fail fast with actionable guidance when test bootstrap is invalid."""
    if not _is_xdist_worker(session.config):
        state = _tracked_file_state()
        if state is not None:
            session.config.stash[_TRACKED_STATE_KEY] = state
    report = build_test_bootstrap_report()
    py = report["python"]
    deps = report["dependencies"]

    if not py["supported"]:
        pytest.exit(
            "sdetkit tests require Python >=3.10. "
            f"Detected {py['current']}. "
            "Use a 3.10+ interpreter before running pytest.",
            returncode=2,
        )

    missing = deps["missing_modules"]
    if missing:
        missing_csv = ", ".join(missing)
        pytest.exit(
            "Missing test dependencies: "
            f"{missing_csv}. "
            f"Install test requirements with: {report['remediation']}",
            returncode=2,
        )
