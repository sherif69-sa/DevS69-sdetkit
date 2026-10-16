"""The published docs keep clear of two kinds of damage found by a full read of the site.

A bulk find-and-replace once turned "demo" into "example" ("examplete" for "demote",
"examplenstrate" for "demonstrate"), "day" into "impact" ("30-impact", "impact-to-impact")
and "Phase 1" into "Baseline readiness" (so "Phase 10" read "Baseline readiness0"). And
the HUD cards showed a hard-coded "98.7% health score" and commands that do not exist.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DAMAGE = re.compile(
    r"exampl(?:ete|enstrat|etion)|readiness\d|\b30-impact\b|impact-to-impact|"
    r"operator guidanceal|on name one|report reports",
    re.IGNORECASE,
)
CARDS = sorted((DOCS / "assets").glob("devs69-card-*.svg"))
COMMAND = re.compile(r">(?:python -m )?sdetkit ([a-z][a-z -]*?)(?: --[^<]*)?<")


def test_published_docs_have_no_find_and_replace_damage() -> None:
    hits = [
        f"{path.relative_to(ROOT)}:{line_no}: {match.group(0)}"
        for path in sorted(DOCS.rglob("*.md"))
        if "artifacts" not in path.parts
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        for match in DAMAGE.finditer(line)
    ]

    assert hits == []


def test_hud_cards_show_no_invented_metrics() -> None:
    assert CARDS
    for card in CARDS:
        text = card.read_text(encoding="utf-8")
        assert not re.search(r">\s*\d+(\.\d+)?%\s*<", text), card.name  # a bare score
        assert "health score" not in text and "A+ security" not in text, card.name
        assert "src/sdkit" not in text, card.name


@pytest.mark.parametrize(
    "command",
    sorted({match[1].strip() for card in CARDS for match in COMMAND.finditer(card.read_text())}),
)
def test_every_command_on_a_hud_card_exists(command: str) -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "sdetkit", *command.split(), "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, f"sdetkit {command}: {proc.stderr[-300:]}"
