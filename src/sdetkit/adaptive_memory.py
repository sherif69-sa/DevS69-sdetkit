from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

SCHEMA_VERSION = "sdetkit.adaptive.memory.v1"
INDEX_SCHEMA_VERSION = "sdetkit.index.v1"


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                created_at_utc TEXT NOT NULL,
                root TEXT NOT NULL,
                source_schema TEXT NOT NULL,
                scanned_files INTEGER NOT NULL,
                scanned_lines INTEGER NOT NULL,
                source_index_path TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS files (
                run_id TEXT NOT NULL,
                path TEXT NOT NULL,
                kind TEXT NOT NULL,
                ext TEXT NOT NULL,
                lines INTEGER NOT NULL,
                bytes INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS symbols (
                run_id TEXT NOT NULL,
                file TEXT NOT NULL,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                line INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS hotspots (
                run_id TEXT NOT NULL,
                file TEXT NOT NULL,
                type TEXT NOT NULL,
                severity TEXT NOT NULL,
                signal TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS risk_events (
                run_id TEXT NOT NULL,
                risk_key TEXT NOT NULL,
                file TEXT NOT NULL,
                type TEXT NOT NULL,
                severity TEXT NOT NULL,
                occurrence_count INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS recommendations (
                run_id TEXT NOT NULL,
                title TEXT NOT NULL,
                reason TEXT NOT NULL,
                file TEXT NOT NULL,
                priority INTEGER NOT NULL
            );
            """
        )
        conn.execute(
            "INSERT INTO schema_meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            ("schema_version", SCHEMA_VERSION),
        )


def _run_id(payload: dict[str, object]) -> str:
    canon = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()[:16]


def ingest_index(db_path: Path, index_path: Path) -> str:
    init_db(db_path)
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != INDEX_SCHEMA_VERSION:
        raise SystemExit("invalid index schema")
    run_id = _run_id(payload)
    with _connect(db_path) as conn:
        exists = conn.execute("SELECT 1 FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        if exists:
            return run_id
        counts = payload.get("counts", {})
        conn.execute(
            "INSERT INTO runs(run_id, created_at_utc, root, source_schema, scanned_files, scanned_lines, source_index_path) VALUES(?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                str(payload.get("root", "")),
                str(payload.get("schema_version", "")),
                int(counts.get("scanned_files", 0)),
                int(counts.get("scanned_lines", 0)),
                index_path.as_posix(),
            ),
        )
        conn.executemany(
            "INSERT INTO files(run_id, path, kind, ext, lines, bytes) VALUES(?, ?, ?, ?, ?, ?)",
            [
                (
                    run_id,
                    str(r.get("path", "")),
                    str(r.get("kind", "other")),
                    str(r.get("ext", "<none>")),
                    int(r.get("lines", 0)),
                    int(r.get("bytes", 0)),
                )
                for r in payload.get("files", [])
            ],
        )
        conn.executemany(
            "INSERT INTO symbols(run_id, file, name, type, line) VALUES(?, ?, ?, ?, ?)",
            [
                (
                    run_id,
                    str(r.get("file", "")),
                    str(r.get("name", "")),
                    str(r.get("type", "unknown")),
                    int(r.get("line", 0)),
                )
                for r in payload.get("symbols", [])
            ],
        )
        hotspot_rows = [
            (
                run_id,
                str(r.get("file", "")),
                str(r.get("type", "unknown")),
                str(r.get("severity", "minor")),
                str(r.get("signal", "")),
            )
            for r in payload.get("hotspots", [])
        ]
        conn.executemany(
            "INSERT INTO hotspots(run_id, file, type, severity, signal) VALUES(?, ?, ?, ?, ?)",
            hotspot_rows,
        )

        risk_counts: dict[tuple[str, str, str], int] = {}
        for _, file, kind, severity, _ in hotspot_rows:
            key = (file, kind, severity)
            risk_counts[key] = risk_counts.get(key, 0) + 1
        conn.executemany(
            "INSERT INTO risk_events(run_id, risk_key, file, type, severity, occurrence_count) VALUES(?, ?, ?, ?, ?, ?)",
            [
                (run_id, f"{file}:{kind}:{severity}", file, kind, severity, count)
                for (file, kind, severity), count in sorted(risk_counts.items())
            ],
        )

        recs = []
        for (file, kind, severity), count in sorted(risk_counts.items()):
            priority = 1 if severity == "severe" else 2 if severity == "moderate" else 3
            if severity in {"severe", "moderate"} or count > 1:
                recs.append(
                    (
                        run_id,
                        f"Address {kind} hotspot",
                        f"{severity} hotspot seen {count} time(s)",
                        file,
                        priority,
                    )
                )
        conn.executemany(
            "INSERT INTO recommendations(run_id, title, reason, file, priority) VALUES(?, ?, ?, ?, ?)",
            recs,
        )
    return run_id


def _history_payload(db_path: Path) -> dict[str, object]:
    with _connect(db_path) as conn:
        run_count = int(conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0])
        latest = conn.execute(
            "SELECT run_id, created_at_utc, root FROM runs ORDER BY created_at_utc DESC, run_id DESC LIMIT 1"
        ).fetchone()
        totals = conn.execute(
            "SELECT COALESCE(SUM(scanned_files),0), (SELECT COUNT(*) FROM hotspots) FROM runs"
        ).fetchone()
        top_files = conn.execute(
            "SELECT file, COUNT(*) AS count FROM risk_events GROUP BY file ORDER BY count DESC, file ASC LIMIT 5"
        ).fetchall()
        recs = conn.execute(
            "SELECT title, reason, file, priority FROM recommendations ORDER BY priority ASC, file ASC, title ASC LIMIT 5"
        ).fetchall()
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": "sdetkit adaptive history",
        "db": db_path.as_posix(),
        "run_count": run_count,
        "latest_run": dict(latest) if latest else None,
        "totals": {"files_indexed": int(totals[0]), "hotspots": int(totals[1])},
        "top_risk_files": [{"file": r[0], "count": int(r[1])} for r in top_files],
        "recommendations": [dict(r) for r in recs],
    }


def explain_path(db_path: Path, path: str) -> dict[str, object]:
    history = _history_payload(db_path)
    with _connect(db_path) as conn:
        hot = conn.execute(
            "SELECT file, type, severity, COUNT(*) AS count FROM hotspots WHERE file LIKE ? GROUP BY file, type, severity ORDER BY count DESC, file ASC LIMIT 5",
            (f"%{path}%",),
        ).fetchall()
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": "sdetkit adaptive explain",
        "db": db_path.as_posix(),
        "path": path,
        "run_count": history["run_count"],
        "recurring_hotspots": [dict(r) for r in hot],
        "recommendations": history["recommendations"],
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="sdetkit adaptive")
    sub = p.add_subparsers(dest="cmd", required=True)
    ip = sub.add_parser("init")
    ip.add_argument("--db", default=".sdetkit/adaptive.db")
    ing = sub.add_parser("ingest")
    ing.add_argument("index_json")
    ing.add_argument("--db", default=".sdetkit/adaptive.db")
    hist = sub.add_parser("history")
    hist.add_argument("--db", default=".sdetkit/adaptive.db")
    hist.add_argument("--format", choices=["text", "operator-json"], default="text")
    exp = sub.add_parser("explain")
    exp.add_argument("path")
    exp.add_argument("--db", default=".sdetkit/adaptive.db")
    exp.add_argument("--format", choices=["text", "operator-json"], default="text")

    ns = p.parse_args(argv)
    db_path = Path(ns.db)
    if ns.cmd == "init":
        init_db(db_path)
        return 0
    if ns.cmd == "ingest":
        ingest_index(db_path, Path(ns.index_json))
        return 0
    if ns.cmd == "history":
        init_db(db_path)
        payload = _history_payload(db_path)
        if ns.format == "operator-json":
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            latest = payload["latest_run"]
            print(f"Runs: {payload['run_count']}")
            print(f"Latest: {latest['run_id']}" if latest else "Latest: none")
            print(
                f"Totals: files={payload['totals']['files_indexed']} hotspots={payload['totals']['hotspots']}"
            )
        return 0
    init_db(db_path)
    payload = explain_path(db_path, str(ns.path))
    if ns.format == "operator-json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"Path: {payload['path']}")
        print(f"Runs: {payload['run_count']}")
        print(f"Recurring hotspots: {len(payload['recurring_hotspots'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
