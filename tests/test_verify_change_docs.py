"""docs/verify-change.md documents every option of `sdetkit verify change`."""

from __future__ import annotations

from pathlib import Path

from sdetkit import change_verifier

DOC = Path(__file__).resolve().parents[1] / "docs" / "verify-change.md"


def test_every_option_is_in_the_options_table() -> None:
    table = DOC.read_text(encoding="utf-8").split("## Options", 1)[1].split("\n## ", 1)[0]
    options = [
        next(name for name in action.option_strings if name.startswith("--"))
        for action in change_verifier.build_parser()._actions
        if action.option_strings and "--help" not in action.option_strings
    ]

    missing = [option for option in options if f"| `{option}" not in table]

    assert not missing, (
        f"add these options to the Options table of docs/verify-change.md: {missing}"
    )
