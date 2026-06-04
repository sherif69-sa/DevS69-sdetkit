from __future__ import annotations

import json
from pathlib import Path

from scripts import baseline_blocker_register as reg


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_build_blocker_register_prioritizes_required() -> None:
    rows = reg.build_blocker_register(
        {"blocking_required_checks": ["doctor"], "missing_control_loop_stages": ["build"]},
        {"stages": []},
    )
    assert rows[0]["blocker"] == "doctor"


def test_main_writes_outputs(tmp_path: Path) -> None:
    followup_pass = tmp_path / "follow-up pass.json"
    loop = tmp_path / "control-loop.json"
    out_json = tmp_path / "out" / "register.json"
    out_csv = tmp_path / "out" / "register.csv"

    _write(
        followup_pass,
        {"blocking_required_checks": ["doctor"], "missing_control_loop_stages": ["build"]},
    )
    _write(loop, {"stages": []})

    rc = reg.main(
        [
            "--followup-pass",
            str(followup_pass),
            "--control-loop",
            str(loop),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--format",
            "json",
        ]
    )
    assert rc == 0
    assert out_json.exists()
    assert out_csv.exists()
