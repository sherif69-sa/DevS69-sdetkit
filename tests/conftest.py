from __future__ import annotations

import os
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


def pytest_sessionstart(session: pytest.Session) -> None:
    """Fail fast with actionable guidance when test bootstrap is invalid."""
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
