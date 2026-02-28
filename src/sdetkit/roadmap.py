from __future__ import annotations

import json
import os
import sys
import webbrowser
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RoadmapEntry:
    day: int
    report_file: str | None
    plan_file: str | None
    report_path: str | None
    plan_path: str | None


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for p in [here] + list(here.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _first_existing(root: Path, rel_candidates: list[str]) -> str | None:
    for rel in rel_candidates:
        p = root / rel
        if p.exists():
            return rel.replace("\\", "/")
    return None


def load_manifest() -> list[RoadmapEntry]:
    root = _repo_root()
    manifest_path = root / "docs" / "roadmap" / "manifest.json"
    if not manifest_path.exists():
        return []

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    out: list[RoadmapEntry] = []

    for row in data.get("days", []):
        day = int(row.get("day"))
        report_file = row.get("report_file")
        plan_file = row.get("plan_file")

        report_path = None
        if report_file:
            report_path = _first_existing(
                root,
                [
                    f"docs/roadmap/reports/{report_file}",
                    f"docs/{report_file}",
                ],
            )

        plan_path = None
        if plan_file:
            candidates: list[str] = []
            if plan_file.startswith("."):
                candidates.append(plan_file)
                candidates.append(f"docs/roadmap/phase3/plans/{plan_file.lstrip('.')}")
                candidates.append(f"docs/roadmap/phase3/plans/{plan_file}")
            else:
                candidates.append(f"docs/roadmap/phase3/plans/{plan_file}")
                candidates.append(f".{plan_file}")
                candidates.append(plan_file)
            plan_path = _first_existing(root, candidates)

        out.append(
            RoadmapEntry(
                day=day,
                report_file=report_file,
                plan_file=plan_file,
                report_path=report_path,
                plan_path=plan_path,
            )
        )

    out.sort(key=lambda e: e.day)
    return out


def get_entry(day: int) -> RoadmapEntry | None:
    for e in load_manifest():
        if e.day == day:
            return e
    return None


def main(argv: list[str]) -> int:
    if not argv or argv[0] in {"-h", "--help"}:
        print("usage: sdetkit roadmap {list|show|open} [day] [report|plan]")
        return 0

    cmd = argv[0]
    rest = argv[1:]

    if cmd == "list":
        entries = load_manifest()
        for e in entries:
            r = "R" if e.report_path else "-"
            p = "P" if e.plan_path else "-"
            print(f"{e.day:02d} {r} {p}")
        return 0

    if cmd in {"show", "open"}:
        if not rest:
            print("roadmap: missing day", file=sys.stderr)
            return 2
        try:
            day = int(rest[0])
        except ValueError:
            print("roadmap: invalid day", file=sys.stderr)
            return 2

        e = get_entry(day)
        if e is None:
            print("roadmap: unknown day", file=sys.stderr)
            return 2

        if cmd == "show":
            payload = {
                "day": e.day,
                "report_path": e.report_path,
                "plan_path": e.plan_path,
            }
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0

        which = rest[1] if len(rest) > 1 else "report"
        rel = e.report_path if which != "plan" else e.plan_path
        if not rel:
            print("roadmap: file not found", file=sys.stderr)
            return 2

        abs_path = (_repo_root() / rel).resolve()
        print(str(abs_path))
        if os.environ.get("SDETKIT_ROADMAP_LAUNCH") == "1":
            webbrowser.open(abs_path.as_uri())
        return 0

    print("roadmap: unknown command", file=sys.stderr)
    return 2
