from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .adaptive_memory import _history_payload as adaptive_history_payload
from .adaptive_memory import explain_path, ingest_index, init_db
from .index import build_index

SCHEMA_VERSION = "sdetkit.boost.scan.v1"
SCHEMA_VERSION_V2 = "sdetkit.boost.scan.v2"
TEXT_SUFFIXES = {".md", ".py", ".toml", ".yml", ".yaml", ".json", ".txt", ".ini", ".cfg"}
IGNORED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "site",
    "htmlcov",
    ".mypy_cache",
    ".pytest_cache",
    "node_modules",
}


@dataclass(frozen=True)
class Risk:
    title: str
    severity: str
    file: str
    signal: str


@dataclass(frozen=True)
class Fix:
    title: str
    reason: str
    file: str
    priority: int


# ... keep helpers compact


def _rel(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _unique_dicts(values: list[dict[str, object]], key: str) -> list[dict[str, object]]:
    seen: set[object] = set()
    out: list[dict[str, object]] = []
    for item in values:
        m = item.get(key)
        if m in seen:
            continue
        seen.add(m)
        out.append(item)
    return out


def _limited_text_files(root: Path, limit: int) -> list[Path]:
    out: list[Path] = []
    for current, dirs, files in __import__("os").walk(root):
        dirs[:] = sorted(d for d in dirs if d not in IGNORED_DIRS)
        base = Path(current)
        if any(part in IGNORED_DIRS for part in base.parts):
            continue
        for name in sorted(files):
            if len(out) >= limit:
                return out
            p = base / name
            try:
                if p.suffix.lower() in TEXT_SUFFIXES and p.stat().st_size <= 500_000:
                    out.append(p)
            except OSError:
                continue
    return out


def _marker_counts(paths: list[Path]) -> dict[str, int]:
    counts = {"todo": 0, "fixme": 0, "operator_json": 0, "schema_version": 0, "strict_findings": 0}
    for p in paths:
        try:
            t = p.read_text(encoding="utf-8", errors="replace").lower()
        except OSError:
            continue
        counts["todo"] += t.count("todo")
        counts["fixme"] += t.count("fixme")
    return counts


def _workflow_surface(root: Path):
    w = root / ".github" / "workflows"
    ws = sorted(w.glob("*.y*ml")) if w.exists() else []
    risks = []
    fixes = []
    files = [_rel(root, p) for p in ws[:8]]
    sig = {"workflow_count": len(ws)}
    if not ws:
        risks.append(
            Risk("No CI workflows detected", "major", ".github/workflows", "workflow_count=0")
        )
        fixes.append(
            Fix(
                "Add deterministic CI workflow coverage",
                "No workflow files were found.",
                ".github/workflows",
                10,
            )
        )
    return risks, fixes, files, sig


def _test_surface(root: Path):
    td = root / "tests"
    tf = sorted(td.rglob("test*.py")) if td.exists() else []
    risks = []
    fixes = []
    sig = {"test_file_count": len(tf)}
    if len(tf) < 3:
        risks.append(Risk("Low test inventory", "moderate", "tests/", f"test_file_count={len(tf)}"))
        fixes.append(
            Fix(
                "Expand high-signal test inventory",
                "Fewer than three test files were found.",
                "tests/",
                7,
            )
        )
    return risks, fixes, [_rel(root, p) for p in tf[:8]], sig


def _docs_surface(root: Path):
    files = [n for n in ("README.md", "mkdocs.yml") if (root / n).exists()]
    return [], [], files, {"has_readme": (root / "README.md").exists()}


def _security_surface(root: Path):
    return [], [], [], {"security_marker_count": 0}


def _evidence_surface(root: Path):
    return [], [], [], {"evidence_file_count": 0}


def _source_surface(root: Path, limit: int):
    sf = sorted((root / "src").rglob("*.py")) if (root / "src").exists() else []
    m = _marker_counts(_limited_text_files(root, limit))
    risks = []
    fixes = []
    if m["fixme"]:
        risks.append(Risk("FIXME markers present", "minor", "repo", f"fixme={m['fixme']}"))
        fixes.append(
            Fix(
                "Triage FIXME markers", "FIXME markers were found in scanned text files.", "repo", 3
            )
        )
    return risks, fixes, [_rel(root, p) for p in sf[:8]], {"source_file_count": len(sf), **m}


def _package_surface(root: Path):
    return [], [], [], {"has_pyproject": (root / "pyproject.toml").exists()}


def _score(risks: list[Risk]) -> int:
    return max(
        0, 100 - sum({"major": 35, "moderate": 15, "minor": 5}.get(r.severity, 5) for r in risks)
    )


def _decision(score: int, risks: list[Risk]) -> str:
    return (
        "NO-SHIP"
        if any(r.severity == "major" for r in risks)
        else ("SHIP" if score >= 85 else "BOOST")
    )


def _next_prs(risks: list[Risk], fixes: list[Fix]) -> list[dict[str, object]]:
    return [
        {
            "title": "hotspot-cleanup",
            "reason": "Address recurring risk hotspots.",
            "files": sorted({r.file for r in risks})[:5],
            "priority": 8,
            "expected_validation": "python -m pytest -q",
        }
    ]


def _build_index_adaptive(root: Path, deep: bool, learn: bool, db: str, index_out: str):
    if not (deep or learn):
        return None, {}
    out = Path(index_out)
    idx = build_index(root.resolve(), out)
    am = {}
    if learn:
        dbp = Path(db)
        init_db(dbp)
        ingest_index(dbp, out / "index.json")
        hist = adaptive_history_payload(dbp)
        exp = explain_path(dbp, ".")
        am = {
            "db": dbp.as_posix(),
            "run_count": hist["run_count"],
            "latest_run": hist["latest_run"],
            "recurring_hotspots": exp["recurring_hotspots"],
            "top_risk_files": hist["top_risk_files"],
            "memory_recommendations": hist["recommendations"],
        }
    return idx, am


def build_scan(
    root: Path,
    minutes: int,
    max_lines: int,
    deep: bool = False,
    learn: bool = False,
    db: str = ".sdetkit/adaptive.db",
    index_out: str = "build/sdetkit-index",
    evidence_dir: str = "",
):
    resolved = root.resolve()
    scan_limit = max(100, min(1000, int(minutes) * 200))
    risks = []
    fixes = []
    high = []
    ev = []
    signals = {}
    for c in (
        _workflow_surface,
        _test_surface,
        _docs_surface,
        _security_surface,
        _evidence_surface,
        _package_surface,
    ):
        r, f, files, s = c(resolved)
        risks.extend(r)
        fixes.extend(f)
        high.extend(files)
        signals.update(s)
    r, f, files, s = _source_surface(resolved, scan_limit)
    risks.extend(r)
    fixes.extend(f)
    high.extend(files)
    signals.update(s)
    risks = sorted(
        risks,
        key=lambda x: ({"major": 0, "moderate": 1, "minor": 2}.get(x.severity, 3), x.title, x.file),
    )
    fixes = sorted(fixes, key=lambda x: (-x.priority, x.title, x.file))
    risk_dicts = _unique_dicts([asdict(x) for x in risks], "title")
    fix_dicts = _unique_dicts([asdict(x) for x in fixes], "title")
    idx, am = _build_index_adaptive(resolved, deep, learn, db, index_out)
    recurring = [
        {
            "title": f"Recurring {h['type']}",
            "severity": h["severity"],
            "file": h["file"],
            "signal": f"count={h['count']}",
        }
        for h in am.get("recurring_hotspots", [])
    ]
    candidates = _next_prs(risks, fixes)
    payload = {
        "schema_version": SCHEMA_VERSION_V2 if (deep or learn) else SCHEMA_VERSION,
        "tool": "sdetkit boost scan",
        "root": str(resolved),
        "decision": _decision(_score(risks), risks),
        "score": _score(risks),
        "confidence": round(_score(risks) / 100, 2),
        "budget": {
            "minutes": int(minutes),
            "max_lines": int(max_lines),
            "scan_file_limit": scan_limit,
        },
        "summary": f"{len(risk_dicts)} risk signal(s).",
        "trend": "stable",
        "top_risks": (recurring + risk_dicts)[:8],
        "new_risks": risk_dicts[:5],
        "recurring_risks": recurring[:8],
        "recommended_fixes": fix_dicts[:10],
        "patch_candidates": candidates,
        "next_pr_candidates": candidates,
        "high_signal_files": _unique(high)[:16],
        "evidence_files": ev,
        "adaptive_memory": am,
        "index_summary": {
            "counts": (idx or {}).get("counts", {}),
            "high_signal_files": (idx or {}).get("high_signal_files", []),
            "hotspots": (idx or {}).get("hotspots", [])[:8],
        },
        "signals": dict(sorted(signals.items())),
    }
    if evidence_dir:
        e = Path(evidence_dir)
        e.mkdir(parents=True, exist_ok=True)
        (e / "boost-scan.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (e / "boost-scan.txt").write_text(render_text(payload, max_lines) + "\n", encoding="utf-8")
        if idx:
            (e / "index.json").write_text(
                json.dumps(idx, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
        if learn:
            (e / "memory-history.json").write_text(
                json.dumps(adaptive_history_payload(Path(db)), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            (e / "memory-explain.json").write_text(
                json.dumps(explain_path(Path(db), "."), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
    return payload


def _render_section(lines: list[str], title: str, items: list[object], formatter):
    lines.append(f"{title}:")
    if not items:
        lines.append("- none")
        return
    for i in items:
        lines.append(formatter(i))


def render_text(payload: dict[str, object], max_lines: int) -> str:
    lines = [
        "Boost Scan Engine Report",
        f"decision: {payload['decision']}",
        f"score: {payload['score']}",
        f"confidence: {payload.get('confidence', 'n/a')}",
        f"summary: {payload['summary']}",
    ]
    _render_section(
        lines,
        "top risks",
        payload["top_risks"],
        lambda i: f"- {i['severity']}: {i['title']} ({i['file']})",
    )
    _render_section(
        lines,
        "recurring risks",
        payload.get("recurring_risks", []),
        lambda i: f"- {i['title']} ({i['file']})",
    )
    _render_section(
        lines,
        "recommended fixes",
        payload["recommended_fixes"],
        lambda i: f"- {i['title']} ({i['file']})",
    )
    _render_section(
        lines,
        "patch candidates",
        payload["patch_candidates"],
        lambda i: f"- {i['title']}: {i['reason']}",
    )
    _render_section(lines, "evidence files", payload["evidence_files"], lambda i: f"- {i}")
    return "\n".join(lines[: max(1, int(max_lines))])


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sdetkit boost")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan")
    s.add_argument("path")
    s.add_argument("--minutes", type=int, default=5)
    s.add_argument("--max-lines", type=int, default=100)
    s.add_argument("--format", choices=["text", "operator-json"], default="text")
    s.add_argument("--deep", action="store_true")
    s.add_argument("--learn", action="store_true")
    s.add_argument("--db", default=".sdetkit/adaptive.db")
    s.add_argument("--index-out", default="build/sdetkit-index")
    s.add_argument("--evidence-dir", default="")
    return p


def main(argv: list[str] | None = None) -> int:
    ns = _build_parser().parse_args(argv)
    payload = build_scan(
        Path(ns.path),
        int(ns.minutes),
        int(ns.max_lines),
        deep=bool(ns.deep),
        learn=bool(ns.learn),
        db=str(ns.db),
        index_out=str(ns.index_out),
        evidence_dir=str(ns.evidence_dir),
    )
    print(
        json.dumps(payload, indent=2, sort_keys=True)
        if ns.format == "operator-json"
        else render_text(payload, int(ns.max_lines))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
