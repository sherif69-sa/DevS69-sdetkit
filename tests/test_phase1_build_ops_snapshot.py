from __future__ import annotations

import json
from pathlib import Path

from scripts import phase1_build_ops_snapshot as snap


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_build_ops_snapshot_ranks_debt() -> None:
    summary = {
        "checks": [
            {"id": "ruff", "ok": False},
            {"id": "doctor", "ok": False},
            {"id": "pytest", "ok": True},
        ]
    }
    status = {"accomplished": ["a", "b"], "not_yet": ["c"], "hard_blockers": ["c"]}
    next_actions = {"next_actions": ["fix doctor"]}

    out = snap.build_ops_snapshot(summary, status, next_actions)
    assert out["progress_percent"] == 66.7
    assert out["quality_debt_register"][0]["check_id"] == "doctor"


def test_main_writes_outputs(tmp_path: Path) -> None:
    summary = tmp_path / "summary.json"
    status = tmp_path / "status.json"
    next_actions = tmp_path / "next.json"
    out_json = tmp_path / "out" / "snapshot.json"
    out_md = tmp_path / "out" / "snapshot.md"

    _write(summary, {"checks": [{"id": "doctor", "ok": True}]})
    _write(status, {"accomplished": ["x"], "not_yet": [], "hard_blockers": []})
    _write(next_actions, {"next_actions": ["none"]})

    rc = snap.main(
        [
            "--summary",
            str(summary),
            "--status",
            str(status),
            "--next-actions",
            str(next_actions),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
            "--format",
            "json",
        ]
    )
    assert rc == 0
    assert out_json.exists()
    assert out_md.exists()
