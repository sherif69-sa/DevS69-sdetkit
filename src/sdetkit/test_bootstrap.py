from __future__ import annotations

import importlib.util
import platform
import sys
from collections.abc import Sequence

REQUIRED_TEST_MODULES: tuple[str, ...] = ("httpx", "yaml", "hypothesis")
MIN_TEST_PYTHON: tuple[int, int] = (3, 10)
TEST_BOOTSTRAP_REMEDIATION = "python -m pip install -r requirements-test.txt"


def missing_modules(modules: Sequence[str] = REQUIRED_TEST_MODULES) -> list[str]:
    return sorted(name for name in modules if importlib.util.find_spec(name) is None)


def build_test_bootstrap_report() -> dict[str, object]:
    version = sys.version_info
    if hasattr(version, "major") and hasattr(version, "minor"):
        current = (int(version.major), int(version.minor))
    else:
        current = (int(version[0]), int(version[1]))
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
