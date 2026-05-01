from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-m", "sdetkit", *args], text=True, capture_output=True)


def _build_index(tmp_path: Path) -> Path:
    proc = _run("index", "inspect", str(tmp_path), "--format", "operator-json")
    assert proc.returncode == 0
    out = tmp_path / "index.json"
    out.write_text(proc.stdout, encoding="utf-8")
    return out


def test_adaptive_init_creates_schema_and_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / ".sdetkit" / "adaptive.db"
    p1 = _run("adaptive", "init", "--db", str(db))
    p2 = _run("adaptive", "init", "--db", str(db))
    assert p1.returncode == 0
    assert p2.returncode == 0
    with sqlite3.connect(db) as conn:
        got = conn.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()
    assert got and got[0] == "sdetkit.adaptive.memory.v1"


def test_adaptive_ingest_store_and_schema_reject(tmp_path: Path) -> None:
    db = tmp_path / "adaptive.db"
    good = _build_index(tmp_path)
    init = _run("adaptive", "init", "--db", str(db))
    assert init.returncode == 0
    ing = _run("adaptive", "ingest", str(good), "--db", str(db))
    assert ing.returncode == 0
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM files").fetchone()[0] >= 0
        assert conn.execute("SELECT COUNT(*) FROM symbols").fetchone()[0] >= 0
        assert conn.execute("SELECT COUNT(*) FROM hotspots").fetchone()[0] >= 0

    bad = tmp_path / "bad.json"
    payload = json.loads(good.read_text(encoding="utf-8"))
    payload["schema_version"] = "wrong"
    bad.write_text(json.dumps(payload), encoding="utf-8")
    bad_proc = _run("adaptive", "ingest", str(bad), "--db", str(db))
    assert bad_proc.returncode != 0


def test_adaptive_history_and_explain_contracts(tmp_path: Path) -> None:
    db = tmp_path / "adaptive.db"
    _run("adaptive", "init", "--db", str(db))

    empty = _run("adaptive", "explain", ".", "--db", str(db), "--format", "text")
    assert empty.returncode == 0
    assert "Runs: 0" in empty.stdout

    good = _build_index(tmp_path)
    _run("adaptive", "ingest", str(good), "--db", str(db))

    htxt = _run("adaptive", "history", "--db", str(db), "--format", "text")
    assert htxt.returncode == 0
    assert "Runs:" in htxt.stdout

    hjson = _run("adaptive", "history", "--db", str(db), "--format", "operator-json")
    payload = json.loads(hjson.stdout)
    assert payload["schema_version"] == "sdetkit.adaptive.memory.v1"

    ejson = _run("adaptive", "explain", ".", "--db", str(db), "--format", "operator-json")
    ep = json.loads(ejson.stdout)
    assert "recurring_hotspots" in ep
    assert "recommendations" in ep


def test_adaptive_cli_help_discoverability() -> None:
    proc = _run("adaptive", "--help")
    assert proc.returncode == 0
    assert "init" in proc.stdout
    assert "ingest" in proc.stdout
    assert "history" in proc.stdout
    assert "explain" in proc.stdout

    assert _run("adaptive", "init", "--help").returncode == 0
    assert _run("adaptive", "ingest", "--help").returncode == 0
    assert _run("adaptive", "history", "--help").returncode == 0
    assert _run("adaptive", "explain", "--help").returncode == 0
