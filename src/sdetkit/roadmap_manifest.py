from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

_REPORT_RE = re.compile(r"^day-(\d+)-.*-report\.md$")
_PLAN_RE = re.compile(r"^day(\d+)-.*\.json$")


def _repo_root(start: Path | None = None) -> Path:
    here = (start or Path(__file__)).resolve()
    for p in [here] + list(here.parents):
        if (p / "pyproject.toml").exists():
            return p
    return Path.cwd()


def _first_heading(md: str) -> str | None:
    for ln in md.splitlines():
        s = ln.strip()
        if s.startswith("#"):
            title = s.lstrip("#").strip()
            if title:
                return title
    return None


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def build_manifest(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root or _repo_root()
    docs_root = root / "docs" / "roadmap"
    reports_dir = docs_root / "reports"
    plans_dir = docs_root / "phase3" / "plans"

    items: dict[int, dict[str, Any]] = {}

    if reports_dir.exists():
        for p in sorted(reports_dir.glob("day-*-*-report.md")):
            m = _REPORT_RE.match(p.name)
            if not m:
                continue
            day = int(m.group(1))
            e = items.setdefault(day, {"day": day})
            if "report_path" in e:
                raise ValueError(f"duplicate report for day {day}: {e['report_path']} and {p}")
            rel = p.relative_to(root).as_posix()
            title = _first_heading(p.read_text(encoding="utf-8")) or p.name
            e["report_path"] = rel
            e["report_title"] = title

    if plans_dir.exists():
        for p in sorted(plans_dir.glob("day*.json")):
            m = _PLAN_RE.match(p.name)
            if not m:
                continue
            day = int(m.group(1))
            e = items.setdefault(day, {"day": day})
            if "plan_path" in e:
                raise ValueError(f"duplicate plan for day {day}: {e['plan_path']} and {p}")
            rel = p.relative_to(root).as_posix()
            data = _load_json(p)
            title = None
            if isinstance(data, dict):
                for k in ("title", "name"):
                    v = data.get(k)
                    if isinstance(v, str) and v.strip():
                        title = v.strip()
                        break
            e["plan_path"] = rel
            if title:
                e["plan_title"] = title

    days = [items[k] for k in sorted(items)]
    return {"days": days}


def render_manifest_json(repo_root: Path | None = None) -> str:
    obj = build_manifest(repo_root=repo_root)
    return json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=True) + "\n"


def manifest_path(repo_root: Path | None = None) -> Path:
    root = repo_root or _repo_root()
    return root / "docs" / "roadmap" / "manifest.json"


def write_manifest(repo_root: Path | None = None) -> Path:
    root = repo_root or _repo_root()
    out_path = manifest_path(root)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_manifest_json(root), encoding="utf-8", newline="\n")
    return out_path


def check_manifest(repo_root: Path | None = None) -> bool:
    root = repo_root or _repo_root()
    out_path = manifest_path(root)
    if not out_path.exists():
        return False
    expected = out_path.read_text(encoding="utf-8")
    actual = render_manifest_json(root)
    return expected == actual


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if not args or args[0] in {"-h", "--help"}:
        print("usage: python -m sdetkit.roadmap_manifest {print|write|check}")
        return 0

    cmd = args[0]
    if cmd == "print":
        sys.stdout.write(render_manifest_json())
        return 0
    if cmd == "write":
        p = write_manifest()
        print(p.as_posix())
        return 0
    if cmd == "check":
        ok = check_manifest()
        if ok:
            return 0
        print(
            "roadmap manifest is stale; run: python -m sdetkit.roadmap_manifest write",
            file=sys.stderr,
        )
        return 1

    print("unknown command", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
