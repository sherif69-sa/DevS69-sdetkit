from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

_REPORT_RE = re.compile(r"^impact-(\d+)-.*-report\.md$")
_PLAN_RE = re.compile(r"^(?:impact|day)(\d+)(?:-.*)?\.json$")
_CLOSEOUT_RE = re.compile(r"^(?P<lane>[a-z0-9_]+)_closeout_(?P<id>\d+)\.py$")


def _script_matches_closeout_lane(script: Path, lane: str) -> bool:
    lane_tokens = [tok for tok in lane.lower().split("_") if tok]
    if not lane_tokens:
        return False
    script_tokens = [tok for tok in script.stem.lower().split("_") if tok]
    return all(token in script_tokens for token in lane_tokens)


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


def _closeout_inventory(root: Path) -> dict[str, Any]:
    src_dir = root / "src" / "sdetkit"
    tests_dir = root / "tests"
    scripts_dir = root / "scripts"
    entries: list[dict[str, Any]] = []
    test_files = sorted(tests_dir.glob("test_*.py"))
    test_contents = {
        test_file: test_file.read_text(encoding="utf-8", errors="replace") for test_file in test_files
    }
    contract_candidates = sorted(scripts_dir.glob("check_*closeout_contract*.py"))
    for path in sorted(src_dir.glob("*_closeout_*.py")):
        m = _CLOSEOUT_RE.match(path.name)
        if not m:
            continue
        closeout_id = int(m.group("id"))
        lane = m.group("lane")
        module_stem = path.stem

        tests_refs = 0
        for test_file, text in test_contents.items():
            if module_stem in text:
                tests_refs += 1

        contract_scripts = sorted(scripts_dir.glob(f"check_*{closeout_id}*.py"))
        if not contract_scripts:
            for candidate in contract_candidates:
                if _script_matches_closeout_lane(candidate, lane):
                    contract_scripts.append(candidate)
            contract_scripts = sorted({script.resolve(): script for script in contract_scripts}.values())
        contract_refs = len(contract_scripts)

        day_refs = 0
        day_hint = f"day{closeout_id}"
        for repo_file in [path]:
            text = repo_file.read_text(encoding="utf-8", errors="replace")
            lowered = text.lower()
            if day_hint in lowered or f"day {closeout_id}" in lowered:
                day_refs += 1

        entries.append(
            {
                "id": closeout_id,
                "lane": lane,
                "module": f"sdetkit.{module_stem}",
                "module_path": path.relative_to(root).as_posix(),
                "tests_referencing_module": tests_refs,
                "contract_scripts": contract_refs,
                "contract_script_paths": [
                    script_path.relative_to(root).as_posix() for script_path in contract_scripts
                ],
                "legacy_day_refs_in_module": day_refs,
            }
        )

    covered = [
        item
        for item in entries
        if item["tests_referencing_module"] > 0 and item["contract_scripts"] > 0
    ]
    return {
        "count": len(entries),
        "fully_aligned_count": len(covered),
        "readiness_percent": round((len(covered) / len(entries) * 100), 2) if entries else 0.0,
        "entries": entries,
    }


def _next_closeout_calls(repo_root: Path | None = None, *, limit: int = 10) -> list[dict[str, Any]]:
    root = repo_root or _repo_root()
    inventory = _closeout_inventory(root).get("entries", [])
    if not isinstance(inventory, list):
        return []

    backlog: list[dict[str, Any]] = []
    for item in inventory:
        if not isinstance(item, dict):
            continue
        tests_refs = int(item.get("tests_referencing_module", 0))
        contract_refs = int(item.get("contract_scripts", 0))
        day_refs = int(item.get("legacy_day_refs_in_module", 0))
        if tests_refs > 0 and contract_refs > 0 and day_refs == 0:
            continue

        lane = str(item.get("lane", "unknown"))
        closeout_id = int(item.get("id", 0))
        module = str(item.get("module", "sdetkit.unknown"))
        script_paths = item.get("contract_script_paths", [])
        next_call = f"pytest -q -k {module.split('.')[-1]}"
        if isinstance(script_paths, list) and script_paths:
            next_call = f"python {script_paths[0]}"

        backlog.append(
            {
                "id": closeout_id,
                "lane": lane,
                "module": module,
                "tests_referencing_module": tests_refs,
                "contract_scripts": contract_refs,
                "legacy_day_refs_in_module": day_refs,
                "next_call": next_call,
            }
        )

    backlog.sort(
        key=lambda x: (
            int(x["contract_scripts"] > 0),
            int(x["tests_referencing_module"] > 0),
            -x["legacy_day_refs_in_module"],
            x["id"],
        )
    )
    return backlog[: max(1, limit)]


def build_manifest(repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root or _repo_root()
    docs_root = root / "docs" / "roadmap"
    reports_dir = docs_root / "reports"
    plans_dir = docs_root / "phase3" / "plans"

    items: dict[int, dict[str, Any]] = {}

    if reports_dir.exists():
        for p in sorted(reports_dir.glob("impact-*-*-report.md")):
            m = _REPORT_RE.match(p.name)
            if not m:
                continue
            impact = int(m.group(1))
            e = items.setdefault(impact, {"impact": impact})
            if "report_path" in e:
                raise ValueError(
                    f"duplicate report for impact {impact}: {e['report_path']} and {p}"
                )
            rel = p.relative_to(root).as_posix()
            report_title = _first_heading(p.read_text(encoding="utf-8")) or p.name
            e["report_path"] = rel
            e["report_title"] = report_title

    if plans_dir.exists():
        for p in sorted(plans_dir.glob("*.json")):
            m = _PLAN_RE.match(p.name)
            if not m:
                continue
            impact = int(m.group(1))
            e = items.setdefault(impact, {"impact": impact})
            if "plan_path" in e:
                raise ValueError(f"duplicate plan for impact {impact}: {e['plan_path']} and {p}")
            rel = p.relative_to(root).as_posix()
            data = _load_json(p)
            plan_title: str | None = None
            if isinstance(data, dict):
                for k in ("title", "name"):
                    v = data.get(k)
                    if isinstance(v, str) and v.strip():
                        plan_title = v.strip()
                        break
            e["plan_path"] = rel
            if plan_title:
                e["plan_title"] = plan_title

    phase_entries = [items[k] for k in sorted(items)]
    return {"phases": phase_entries, "closeout_alignment": _closeout_inventory(root)}


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
        print("usage: python -m sdetkit.roadmap_manifest {print|write|check|closeout-next [limit]}")
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
    if cmd == "closeout-next":
        limit = 10
        if len(args) > 1:
            try:
                limit = max(1, int(args[1]))
            except ValueError:
                print(f"invalid limit: {args[1]}", file=sys.stderr)
                return 2
        rows = _next_closeout_calls(limit=limit)
        payload = {"next_calls": rows, "count": len(rows)}
        sys.stdout.write(json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True) + "\n")
        return 0

    print("unknown command", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
