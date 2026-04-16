from __future__ import annotations

import json
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_module():
    module_path = Path("scripts/render_release_room_summary.py")
    spec = spec_from_file_location("render_release_room_summary", module_path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_release_room_summary_with_blockers_and_enterprise() -> None:
    mod = _load_module()
    ship = {
        "summary": {
            "decision": "no-go",
            "all_green": False,
            "gate_fast_ok": False,
            "gate_release_ok": False,
            "doctor_ok": True,
            "release_readiness_ok": True,
            "blockers": ["gate_fast"],
            "blocker_catalog": [
                {"id": "gate_fast", "error_kind": "command_failed", "attempts": 1, "return_code": 2}
            ],
        }
    }
    enterprise = {
        "summary": {"score": 88, "tier": "pilot-ready"},
        "upgrade_contract": {"risk_band": "medium", "gate_decision": "conditional-go"},
    }

    md = mod.build_release_room_summary(ship, enterprise)

    assert md.startswith("# Release room summary")
    assert "Blocker catalog" in md
    assert "Enterprise signal" in md
    assert "Resolve blocker catalog items" in md


def test_main_writes_markdown_output(tmp_path: Path) -> None:
    mod = _load_module()

    ship_path = tmp_path / "ship.json"
    ship_path.write_text(
        json.dumps(
            {
                "summary": {
                    "decision": "go",
                    "all_green": True,
                    "gate_fast_ok": True,
                    "gate_release_ok": True,
                    "doctor_ok": True,
                    "release_readiness_ok": True,
                    "blockers": [],
                    "blocker_catalog": [],
                }
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "summary.md"

    rc = mod.main(["--ship-summary", str(ship_path), "--out", str(out)])

    assert rc == 0
    text = out.read_text(encoding="utf-8")
    assert "Proceed to tagging" in text
