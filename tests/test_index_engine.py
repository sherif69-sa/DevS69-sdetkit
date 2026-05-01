from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-m", "sdetkit", *args], text=True, capture_output=True)


def test_index_build_creates_evidence_files(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "src.py").write_text("def alpha():\n    return 1\n", encoding="utf-8")
    out = tmp_path / "build" / "sdetkit-index"
    proc = _run("index", "build", str(repo), "--out", str(out))
    assert proc.returncode == 0
    for name in ("index.json", "files.jsonl", "symbols.jsonl", "hotspots.jsonl"):
        assert (out / name).exists()


def test_index_inspect_operator_json_schema(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.py").write_text("class A:\n    pass\n", encoding="utf-8")
    out = tmp_path / "idx"
    assert _run("index", "build", str(repo), "--out", str(out)).returncode == 0
    proc = _run("index", "inspect", str(out), "--format", "operator-json")
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["schema_version"] == "sdetkit.index.v1"


def test_python_ast_symbol_extraction(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pkg.py").write_text(
        "class Engine:\n    pass\n\ndef run():\n    return 7\n", encoding="utf-8"
    )
    out = tmp_path / "idx"
    _run("index", "build", str(repo), "--out", str(out))
    rows = [
        (json.loads(line))
        for line in (out / "symbols.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    names = {r["name"] for r in rows}
    assert "Engine" in names
    assert "run" in names


def test_markdown_heading_extraction(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Title\n## Scope\n", encoding="utf-8")
    out = tmp_path / "idx"
    _run("index", "build", str(repo), "--out", str(out))
    rows = [
        json.loads(line)
        for line in (out / "symbols.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    headings = [r["name"] for r in rows if r["type"] == "markdown_heading"]
    assert "Title" in headings
    assert "Scope" in headings


def test_todo_fixme_hotspot_detection(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.py").write_text("# TODO: repair\n# FIXME: later\n", encoding="utf-8")
    out = tmp_path / "idx"
    _run("index", "build", str(repo), "--out", str(out))
    rows = [
        json.loads(line)
        for line in (out / "hotspots.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert any(r["type"] == "todo_marker" for r in rows)


def test_ignored_directories_are_skipped(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (repo / ".git" / "hidden.py").write_text("def nope():\n    pass\n", encoding="utf-8")
    (repo / "node_modules").mkdir()
    (repo / "node_modules" / "pkg.js").write_text("console.log('x')\n", encoding="utf-8")
    (repo / "ok.py").write_text("def yes():\n    return 1\n", encoding="utf-8")
    out = tmp_path / "idx"
    _run("index", "build", str(repo), "--out", str(out))
    files = [
        json.loads(line)["path"]
        for line in (out / "files.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert "ok.py" in files
    assert ".git/hidden.py" not in files
    assert "node_modules/pkg.js" not in files


def test_index_inspect_accepts_repo_root_operator_json(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.py").write_text("def run():\n    return 1\n", encoding="utf-8")

    proc = _run("index", "inspect", str(repo), "--format", "operator-json")
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["schema_version"] == "sdetkit.index.v1"


def test_index_inspect_accepts_evidence_directory(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    out = tmp_path / "idx"
    assert _run("index", "build", str(repo), "--out", str(out)).returncode == 0

    proc = _run("index", "inspect", str(out), "--format", "text")
    assert proc.returncode == 0
    assert "Scanned files:" in proc.stdout


def test_index_inspect_repo_root_text_includes_scanned_and_evidence(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.py").write_text("def run():\n    return 1\n", encoding="utf-8")

    proc = _run("index", "inspect", str(repo), "--format", "text")
    assert proc.returncode == 0
    assert "Scanned files:" in proc.stdout
    assert "Evidence files:" in proc.stdout
