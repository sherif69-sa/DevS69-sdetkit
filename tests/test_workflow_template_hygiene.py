from __future__ import annotations

import re
from pathlib import Path

CLOSEOUT_SOURCE_ROOTS = [
    Path("src/sdetkit"),
]

EMPTY_STRING_MEMBERSHIP = re.compile(
    r"""(?x)
    (?:
        ""\s+in\s+[A-Za-z_][A-Za-z0-9_]*
        |
        ''\s+in\s+[A-Za-z_][A-Za-z0-9_]*
    )
    """
)

BLANK_TEMPLATE_PATTERNS = [
    "## Why  matters",
    "## Required inputs ()",
    "##  command lane",
    "##  delivery board",
    "Re-run  ",
    "before  lock",
    "#  —",
    "#  -",
    "#  report",
    "#  delivery board",
    " +  strategy chain",
]


def _files() -> list[Path]:
    files: list[Path] = []
    for root in CLOSEOUT_SOURCE_ROOTS:
        files.extend(sorted(root.rglob("*closeout*.py")))
    return [path for path in files if "__pycache__" not in path.parts and path.is_file()]


def test_validators_do_not_use_empty_string_membership() -> None:
    offenders: list[str] = []

    for path in _files():
        text = path.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), 1):
            if EMPTY_STRING_MEMBERSHIP.search(line):
                offenders.append(f"{path}:{line_no}: {line.strip()}")

    assert not offenders, "\n".join(offenders)


def test_default_templates_do_not_contain_blank_lane_placeholders() -> None:
    offenders: list[str] = []

    for path in _files():
        text = path.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), 1):
            for pattern in BLANK_TEMPLATE_PATTERNS:
                if pattern in line:
                    offenders.append(f"{path}:{line_no}: {pattern}: {line.strip()}")

    assert not offenders, "\n".join(offenders)
