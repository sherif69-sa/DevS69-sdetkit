from __future__ import annotations

import json
from pathlib import Path

from scripts import phase1_next_pass_card as card


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_build_next_pass_card() -> None:
    out = card.build_next_pass_card(
        {
            "status": "near_finish",
            "completion_percent": 80,
            "blocking_required_checks": ["doctor"],
            "next_step": "make x",
        },
        {"next_actions": ["fix doctor"]},
        {"stages": [{"stage": "build", "ok": False}]},
    )
    assert out["status"] == "near_finish"
    assert out["missing_control_loop_stages"] == ["build"]


def test_main_missing_inputs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    rc = card.main(["--format", "json"])
    assert rc == 1


def test_main_writes_outputs(tmp_path: Path) -> None:
    finish = tmp_path / "finish.json"
    nxt = tmp_path / "next.json"
    loop = tmp_path / "loop.json"
    out_json = tmp_path / "out" / "card.json"
    out_md = tmp_path / "out" / "card.md"

    _write(
        finish,
        {
            "status": "early",
            "completion_percent": 0,
            "blocking_required_checks": [],
            "next_step": "make phase1-next",
        },
    )
    _write(nxt, {"next_actions": ["make phase1-next"]})
    _write(loop, {"stages": [{"stage": "build", "ok": False}]})

    rc = card.main(
        [
            "--finish-signal",
            str(finish),
            "--next-actions",
            str(nxt),
            "--control-loop",
            str(loop),
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
