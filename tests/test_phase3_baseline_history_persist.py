from __future__ import annotations

import json
from pathlib import Path

from scripts import phase3_persist_baseline_history as persist


def _write_summary(path: Path, generated_at: str) -> None:
    payload = {
        "schema_version": "sdetkit.phase1_baseline.v1",
        "generated_at_utc": generated_at,
        "out_dir": "build/phase1-baseline",
        "ok": False,
        "checks": [{"id": "doctor", "ok": False, "rc": 1, "stdout_log": "a", "stderr_log": "b"}],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_persist_history_saves_new_entry(tmp_path: Path) -> None:
    summary = tmp_path / "phase1-baseline-summary.json"
    history = tmp_path / "history"
    _write_summary(summary, "2026-04-19T00:00:00Z")

    rc = persist.main(["--summary", str(summary), "--history-dir", str(history), "--format", "json"])

    assert rc == 0
    entries = sorted(history.glob("phase1-baseline-summary-*.json"))
    assert len(entries) == 1


def test_persist_history_dedupes_identical_payload(tmp_path: Path) -> None:
    summary = tmp_path / "phase1-baseline-summary.json"
    history = tmp_path / "history"
    _write_summary(summary, "2026-04-19T00:00:00Z")

    rc1 = persist.main(["--summary", str(summary), "--history-dir", str(history), "--format", "json"])
    rc2 = persist.main(["--summary", str(summary), "--history-dir", str(history), "--format", "json"])

    assert rc1 == 0
    assert rc2 == 0
    entries = sorted(history.glob("phase1-baseline-summary-*.json"))
    assert len(entries) == 1


def test_persist_history_prunes_old_entries(tmp_path: Path) -> None:
    summary = tmp_path / "phase1-baseline-summary.json"
    history = tmp_path / "history"

    _write_summary(summary, "2026-04-19T00:00:00Z")
    assert persist.main(["--summary", str(summary), "--history-dir", str(history), "--max-history", "2"]) == 0
    _write_summary(summary, "2026-04-20T00:00:00Z")
    assert persist.main(["--summary", str(summary), "--history-dir", str(history), "--max-history", "2"]) == 0
    _write_summary(summary, "2026-04-21T00:00:00Z")
    assert persist.main(["--summary", str(summary), "--history-dir", str(history), "--max-history", "2"]) == 0

    entries = sorted(history.glob("phase1-baseline-summary-*.json"))
    assert len(entries) == 2
