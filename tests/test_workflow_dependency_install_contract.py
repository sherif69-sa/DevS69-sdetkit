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


def test_active_workflows_that_run_repo_code_install_repo_dependencies() -> None:
    reference_workflow_name_parts = ("advanced-github-actions-reference",)
    repo_code_markers = (
        "python -m sdetkit",
        "PYTHONPATH=src python -m sdetkit",
        "python scripts/",
        "python tools/",
        "bash quality.sh",
        "bash premium-gate.sh",
        "bash scripts/",
        "make ",
        "sdetkit ",
    )
    constrained_install_markers = (
        "pip install -c constraints-ci.txt -e .",
        "pip install -c constraints-ci.txt -e .[",
        "pip install -c constraints-ci.txt -e '.[",
        "pip install -c constraints-ci.txt -r requirements",
        "pip install -c constraints-ci.txt pre-commit",
    )
    stdlib_only_markers = (
        "Path('pyproject.toml')",
        'Path("pyproject.toml")',
        "grep -Eq",
        "version=$(python - <<'PY'",
    )
    offenders: list[str] = []

    for workflow_path in sorted(WORKFLOW_DIR.glob("*.yml")) + sorted(WORKFLOW_DIR.glob("*.yaml")):
        if any(part in workflow_path.name for part in reference_workflow_name_parts):
            continue

        text = workflow_path.read_text(encoding="utf-8")
        if "setup-python" not in text:
            continue
        if any(marker in text for marker in stdlib_only_markers):
            continue
        if not any(marker in text for marker in repo_code_markers):
            continue
        if any(marker in text for marker in constrained_install_markers):
            continue

        offenders.append(str(workflow_path))

    assert not offenders, (
        "Active workflows that run repo-owned Python, shell, Make, or CLI commands "
        "after setup-python must install repo dependencies through constraints-ci.txt:\n"
        + "\n".join(offenders)
    )
