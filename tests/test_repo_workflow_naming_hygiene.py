from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


_ALLOWED_CONTENT_CLOSEOUT_PATH_PARTS = (
    "src/sdetkit/legacy_adapters/",
    "src/sdetkit/legacy_commands.py",
    "src/sdetkit/legacy_namespace.py",
    "src/sdetkit/cli.py",
    "src/sdetkit/cli/playbooks_cli.py",
    "scripts/business_execution_",
    "scripts/phase1_",
    "tests/test_business_execution_",
    "tests/test_check_business_execution_",
    "tests/test_docs_qa.py",
    "tests/test_docs_nav_current_discoverability.py",
    "tests/test_legacy_commands.py",
    "tests/test_roadmap_manifest_edges_wave12.py",
)

_ALLOWED_FILENAME_PATH_PARTS = (
    # Business/history surfaces that are not part of the workflow-closeout cleanup.
    "scripts/business_execution_",
    "scripts/phase1_",
)


def _tracked_python_files() -> list[Path]:
    output = subprocess.check_output(
        ["git", "ls-files", "src", "tests", "scripts"],
        cwd=ROOT,
        text=True,
    )
    return [ROOT / line for line in output.splitlines() if line.endswith(".py")]


def _is_allowed_content_path(path: Path) -> bool:
    raw = path.relative_to(ROOT).as_posix()
    return any(part in raw for part in _ALLOWED_CONTENT_CLOSEOUT_PATH_PARTS)


def _is_allowed_filename_path(path: Path) -> bool:
    raw = path.relative_to(ROOT).as_posix()
    return any(part in raw for part in _ALLOWED_FILENAME_PATH_PARTS)


def test_canonical_workflow_python_files_do_not_use_numbered_closeout_names() -> None:
    bad: list[str] = []

    for path in _tracked_python_files():
        rel = path.relative_to(ROOT).as_posix()

        if _is_allowed_filename_path(path):
            continue

        if "closeout" in path.name:
            bad.append(f"{rel}: filename contains closeout")

        if re.search(r"_\d+\.py$", path.name):
            bad.append(f"{rel}: filename has numbered suffix")

        if re.search(r"(^|_)lane(_|$)", path.stem):
            bad.append(f"{rel}: filename contains lane workflow naming")

    assert not bad, "\\n".join(bad)


def test_workflow_tests_do_not_use_lane_number_function_names() -> None:
    bad: list[str] = []

    for path in _tracked_python_files():
        rel = path.relative_to(ROOT).as_posix()
        if not rel.startswith("tests/"):
            continue

        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"\btest_lane\d+|\blane\d+\b|\bLane\d+\b|_lane\d+", line):
                bad.append(f"{rel}:{number}: {line.strip()}")

    assert not bad, "\\n".join(bad)


def test_non_legacy_workflow_code_does_not_reference_numbered_closeout_modules() -> None:
    bad: list[str] = []

    for path in _tracked_python_files():
        rel = path.relative_to(ROOT).as_posix()

        if _is_allowed_content_path(path):
            continue

        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"\b\w+_closeout_\d+\b", line):
                bad.append(f"{rel}:{number}: numbered closeout module reference: {line.strip()}")

    assert not bad, "\\n".join(bad)
