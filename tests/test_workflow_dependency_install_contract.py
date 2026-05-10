from __future__ import annotations

import re
from pathlib import Path

WORKFLOW_DIR = Path(".github/workflows")

# These installs are intentionally outside the repo dependency resolver contract.
_ALLOWED_UNCONSTRAINED_PATTERNS = (
    "python -m pip install --upgrade pip",
    "python -m pip install -U pip",
    'python -m pip install "$WHEEL_PATH"',
    "python -m pip install --force-reinstall dist/*.whl",
    "python -m pip install pip-audit==",
    "python -m pip install cyclonedx-bom==",
    "python -m pip install mutmut",
)

# Reference/example workflows demonstrate third-party project behavior rather than
# this repository's active dependency contract.
_ALLOWED_WORKFLOW_PATH_PARTS = ("advanced-github-actions-reference",)


def _is_allowed_unconstrained_install(path: Path, line: str) -> bool:
    if any(part in path.name for part in _ALLOWED_WORKFLOW_PATH_PARTS):
        return True
    return any(pattern in line for pattern in _ALLOWED_UNCONSTRAINED_PATTERNS)


def test_active_workflow_repo_dependency_installs_use_constraints() -> None:
    offenders: list[str] = []

    for path in sorted(WORKFLOW_DIR.glob("*.yml")) + sorted(WORKFLOW_DIR.glob("*.yaml")):
        text = path.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if "pip install" not in stripped:
                continue
            if "constraints-ci.txt" in stripped:
                continue
            if _is_allowed_unconstrained_install(path, stripped):
                continue
            installs_repo_dependencies = any(
                marker in stripped
                for marker in (
                    "-e .",
                    "-e .[",
                    "-e '.[",
                    "-r requirements-test.txt",
                    "-r requirements-docs.txt",
                    "pre-commit==",
                )
            )
            if installs_repo_dependencies:
                offenders.append(f"{path}:{line_no}: {stripped}")

    assert not offenders, (
        "Active GitHub workflows must install repo-managed dependencies through "
        "constraints-ci.txt so CI, bot, docs, and local dependency behavior stay "
        "aligned. Offending install lines:\n" + "\n".join(offenders)
    )


def test_workflows_do_not_hard_code_repo_managed_precommit_versions() -> None:
    offenders: list[str] = []

    for path in sorted(WORKFLOW_DIR.glob("*.yml")) + sorted(WORKFLOW_DIR.glob("*.yaml")):
        text = path.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), 1):
            if re.search(r"pre-commit==\d", line):
                offenders.append(f"{path}:{line_no}: {line.strip()}")

    assert not offenders, (
        "GitHub workflows must not hard-code repo-managed pre-commit versions. "
        "Install pre-commit through constraints-ci.txt so workflow tooling stays "
        "aligned with pyproject.toml, requirements.txt, and constraints-ci.txt:\n"
        + "\n".join(offenders)
    )
