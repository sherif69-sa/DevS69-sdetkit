from __future__ import annotations

import importlib.util
import platform
import sys
from collections.abc import Sequence

REQUIRED_TEST_MODULES: tuple[str, ...] = ("httpx", "yaml", "hypothesis")
MIN_TEST_PYTHON: tuple[int, int] = (3, 11)
TEST_BOOTSTRAP_REMEDIATION = "python -m pip install -r requirements-test.txt"


def missing_modules(modules: Sequence[str] = REQUIRED_TEST_MODULES) -> list[str]:
    return sorted(name for name in modules if importlib.util.find_spec(name) is None)


def build_test_bootstrap_report() -> dict[str, object]:
    current = (sys.version_info.major, sys.version_info.minor)
    missing = missing_modules()
    return {
        "ok": current >= MIN_TEST_PYTHON and not missing,
        "python": {
            "current": platform.python_version(),
            "required": f"{MIN_TEST_PYTHON[0]}.{MIN_TEST_PYTHON[1]}+",
            "supported": current >= MIN_TEST_PYTHON,
        },
        "dependencies": {
            "required_modules": list(REQUIRED_TEST_MODULES),
            "missing_modules": missing,
            "all_present": not missing,
        },
        "remediation": TEST_BOOTSTRAP_REMEDIATION,
    }
