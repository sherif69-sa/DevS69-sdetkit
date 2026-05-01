from __future__ import annotations

import argparse
import ast
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

SCHEMA_VERSION = "sdetkit.index.v1"
IGNORED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "site",
    "htmlcov",
    ".mypy_cache",
    ".pytest_cache",
    "node_modules",
    "__pycache__",
    "build",
}
TEXT_EXTS = {".py", ".md", ".txt", ".rst", ".json", ".yml", ".yaml", ".toml", ".ini", ".cfg"}


@dataclass(frozen=True)
class ScanFile:
    path: str
    ext: str
    kind: str
    lines: int
    bytes: int


def _iter_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for base, dirs, files in __import__("os").walk(root):
        dirs[:] = sorted(d for d in dirs if d not in IGNORED_DIRS)
        pbase = Path(base)
        if any(part in IGNORED_DIRS for part in pbase.parts):
            continue
        for name in sorted(files):
            out.append(pbase / name)
    return out


def _kind_for(path: Path) -> str:
    rel = path.as_posix().lower()
    if "/tests/" in rel or path.name.startswith("test_"):
        return "test"
    if path.suffix.lower() in {".md", ".rst"}:
        return "docs"
    if ".github/workflows/" in rel:
        return "workflow"
    if path.suffix.lower() in {".toml", ".ini", ".cfg", ".yml", ".yaml", ".json"}:
        return "config"
    if path.suffix.lower() in {".py", ".js", ".ts", ".java", ".go", ".rs"}:
        return "source"
    return "other"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _extract_symbols(rel: str, path: Path, text: str) -> list[dict[str, object]]:
    symbols: list[dict[str, object]] = []
    if path.suffix.lower() == ".py":
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return symbols
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbols.append(
                    {"file": rel, "name": node.name, "type": "function", "line": node.lineno}
                )
            elif isinstance(node, ast.ClassDef):
                symbols.append(
                    {"file": rel, "name": node.name, "type": "class", "line": node.lineno}
                )
    elif path.suffix.lower() == ".md":
        for i, line in enumerate(text.splitlines(), start=1):
            if line.lstrip().startswith("#"):
                symbols.append(
                    {
                        "file": rel,
                        "name": line.strip().lstrip("#").strip(),
                        "type": "markdown_heading",
                        "line": i,
                    }
                )
    elif path.suffix.lower() == ".json":
        try:
            obj = json.loads(text)
        except json.JSONDecodeError:
            return symbols
        if isinstance(obj, dict):
            for key in sorted(obj.keys()):
                symbols.append({"file": rel, "name": str(key), "type": "json_key", "line": 1})
    return symbols


def build_index(root: Path, out_dir: Path) -> dict[str, object]:
    files: list[dict[str, object]] = []
    symbols: list[dict[str, object]] = []
    hotspots: list[dict[str, object]] = []
    counts = Counter()
    lang_counts = Counter()
    total_lines = 0

    for path in _iter_files(root):
        rel = path.relative_to(root).as_posix()
        ext = path.suffix.lower() or "<none>"
        kind = _kind_for(path)
        size = path.stat().st_size
        text = ""
        lines = 0
        if ext in TEXT_EXTS:
            text = _read_text(path)
            lines = text.count("\n") + (1 if text else 0)
        total_lines += lines
        lang_counts[ext] += 1
        counts[kind] += 1
        files.append({"path": rel, "ext": ext, "kind": kind, "lines": lines, "bytes": size})
        if size > 200_000 or lines > 1500:
            hotspots.append(
                {
                    "file": rel,
                    "type": "large_file",
                    "severity": "moderate",
                    "signal": f"lines={lines} bytes={size}",
                }
            )
        low = text.lower()
        todo_hits = low.count("todo") + low.count("fixme") + low.count("xxx")
        if todo_hits:
            hotspots.append(
                {
                    "file": rel,
                    "type": "todo_marker",
                    "severity": "minor",
                    "signal": f"marker_hits={todo_hits}",
                }
            )
        symbols.extend(_extract_symbols(rel, path, text) if text else [])

    hotspots = sorted(hotspots, key=lambda x: (str(x["file"]), str(x["type"])))
    symbols = sorted(
        symbols, key=lambda x: (str(x["file"]), str(x["type"]), str(x["name"]), int(x["line"]))
    )
    files = sorted(files, key=lambda x: str(x["path"]))

    high_signal = [f["path"] for f in files if f["kind"] in {"source", "test", "workflow"}][:10]
    index = {
        "schema_version": SCHEMA_VERSION,
        "tool": "sdetkit index",
        "root": root.resolve().as_posix(),
        "summary": "Deterministic local repository index for adaptive power engine wave 1.",
        "counts": {
            "scanned_files": len(files),
            "scanned_lines": total_lines,
            "source_files": counts["source"],
            "test_files": counts["test"],
            "docs_files": counts["docs"],
            "workflow_files": counts["workflow"],
            "config_files": counts["config"],
        },
        "languages": [
            {"ext": k, "files": v}
            for k, v in sorted(lang_counts.items(), key=lambda kv: (-kv[1], kv[0]))
        ],
        "files": files[:20],
        "symbols": symbols[:20],
        "hotspots": hotspots[:20],
        "high_signal_files": high_signal,
        "risk_markers": {
            "todo_hotspots": sum(1 for h in hotspots if h["type"] == "todo_marker"),
            "large_files": sum(1 for h in hotspots if h["type"] == "large_file"),
        },
        "evidence_files": {
            "index_json": (out_dir / "index.json").as_posix(),
            "files_jsonl": (out_dir / "files.jsonl").as_posix(),
            "symbols_jsonl": (out_dir / "symbols.jsonl").as_posix(),
            "hotspots_jsonl": (out_dir / "hotspots.jsonl").as_posix(),
        },
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.json").write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    for name, rows in (
        ("files.jsonl", files),
        ("symbols.jsonl", symbols),
        ("hotspots.jsonl", hotspots),
    ):
        with (out_dir / name).open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, sort_keys=True) + "\n")
    return index


def inspect_index(path: Path) -> dict[str, object]:
    resolved = path.resolve()
    candidate = resolved / "index.json"
    if candidate.exists():
        out_dir = resolved
    else:
        out_dir = resolved / "build" / "sdetkit-index"
        build_index(resolved, out_dir)

    idx = json.loads((out_dir / "index.json").read_text(encoding="utf-8"))
    if idx.get("schema_version") != SCHEMA_VERSION:
        raise SystemExit("invalid index schema")
    return idx


def _text_summary(payload: dict[str, object]) -> str:
    counts = payload["counts"]
    langs = payload["languages"][:5]
    hotspots = payload["hotspots"][:5]
    lines = [
        "Decision: index evidence ready for adaptive power engine wave 1.",
        f"Scanned files: {counts['scanned_files']}",
        f"Scanned lines: {counts['scanned_lines']}",
        "Top languages: " + ", ".join(f"{x['ext']}({x['files']})" for x in langs),
        "Top hotspots: " + ", ".join(f"{x['type']}:{x['file']}" for x in hotspots)
        if hotspots
        else "Top hotspots: none",
        "High-signal files: " + ", ".join(payload["high_signal_files"][:5]),
        "Evidence files: " + ", ".join(payload["evidence_files"].values()),
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="sdetkit index")
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="Build deterministic repo index evidence")
    b.add_argument("path")
    b.add_argument("--out", default="build/sdetkit-index")
    i = sub.add_parser("inspect", help="Inspect existing index evidence")
    i.add_argument("path")
    i.add_argument("--format", choices=["text", "operator-json"], default="text")

    ns = p.parse_args(argv)
    if ns.cmd == "build":
        build_index(Path(ns.path).resolve(), Path(ns.out))
        return 0
    payload = inspect_index(Path(ns.path))
    if ns.format == "operator-json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(_text_summary(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
