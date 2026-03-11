from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

BEGIN = "<!-- BEGIN:PUBLIC_SURFACE_CONTRACT_TABLE -->"
END = "<!-- END:PUBLIC_SURFACE_CONTRACT_TABLE -->"


def _yes_no(value: bool) -> str:
    return "Yes" if value else "No"


def render_table() -> str:
    lines = [
        "| Command family | Purpose | Stability tier | First-time adopter default? | Transition-era / legacy-oriented? |",
        "|---|---|---|---|---|",
    ]
    from sdetkit.public_surface_contract import PUBLIC_SURFACE_CONTRACT

    for family in PUBLIC_SURFACE_CONTRACT:
        lines.append(
            "| "
            f"`{family.name}`"
            f" | {family.role}"
            f" | {family.stability_tier}"
            f" | {_yes_no(family.first_time_recommended)}"
            f" | {_yes_no(family.transition_legacy_oriented)}"
            " |"
        )
    return "\n".join(lines)


def sync_doc(doc_path: Path) -> bool:
    content = doc_path.read_text(encoding="utf-8")
    if BEGIN not in content or END not in content:
        raise ValueError(f"Missing markers in {doc_path}")
    start = content.index(BEGIN) + len(BEGIN)
    end = content.index(END)
    rendered = "\n\n" + render_table() + "\n\n"
    updated = content[:start] + rendered + content[end:]
    changed = updated != content
    if changed:
        doc_path.write_text(updated, encoding="utf-8")
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render and sync the public surface contract command-family table."
    )
    parser.add_argument(
        "--doc",
        default="docs/command-surface.md",
        help="Markdown doc containing BEGIN/END markers for the contract table.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if the table is out of sync.",
    )
    args = parser.parse_args()

    changed = sync_doc(ROOT / args.doc)
    if args.check and changed:
        print(f"{args.doc} is out of sync with PUBLIC_SURFACE_CONTRACT.")
        return 1
    if changed:
        print(f"Updated {args.doc} from PUBLIC_SURFACE_CONTRACT.")
    else:
        print(f"{args.doc} already matches PUBLIC_SURFACE_CONTRACT.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
