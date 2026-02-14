from __future__ import annotations

import unicodedata as ud
from pathlib import Path

BIDI = {
    0x200E,
    0x200F,
    0x061C,
    0x202A,
    0x202B,
    0x202C,
    0x202D,
    0x202E,
    0x2066,
    0x2067,
    0x2068,
    0x2069,
}


def _is_bad(ch: str) -> bool:
    o = ord(ch)
    if o in BIDI:
        return True
    cat = ud.category(ch)
    if cat == "Cf" and ch not in ("\n", "\r", "\t"):
        return True
    return False


def test_repo_has_no_bidi_or_invisible_unicode_in_py_sources() -> None:
    targets: list[Path] = []
    for root in ("src", "tests", "tools"):
        p = Path(root)
        if p.exists():
            targets.extend(sorted(p.rglob("*.py")))

    bad: list[tuple[str, int, int, str, str]] = []
    for path in targets:
        s = path.read_text(encoding="utf-8", errors="strict")
        for i, ch in enumerate(s):
            if _is_bad(ch):
                line = s.count("\n", 0, i) + 1
                col = i - s.rfind("\n", 0, i)
                name = ud.name(ch, "UNKNOWN")
                bad.append((str(path), line, col, f"U+{ord(ch):04X}", name))

    if bad:
        msg = "\n".join(f"{p}:{ln}:{col} {cp} {name}" for p, ln, col, cp, name in bad[:200])
        raise AssertionError(msg)
