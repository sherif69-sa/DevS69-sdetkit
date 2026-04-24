from __future__ import annotations

import importlib.util
import json
from pathlib import Path


_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "phase2_hotspot_delta.py"
_SPEC = importlib.util.spec_from_file_location("phase2_hotspot_delta_script", _SCRIPT_PATH)
assert _SPEC is not None and _SPEC.loader is not None
phase2_delta = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(phase2_delta)


def test_build_delta_computes_module_differences() -> None:
    baseline = {
        "generated_at_utc": "2026-04-24T00:00:00Z",
        "modules": [{"path": "a.py", "lines_of_code": 10, "function_count": 3, "class_count": 1}],
    }
    current = {
        "generated_at_utc": "2026-04-24T01:00:00Z",
        "modules": [{"path": "a.py", "lines_of_code": 8, "function_count": 2, "class_count": 1}],
    }
    delta = phase2_delta.build_delta(baseline=baseline, current=current)
    assert delta["summary"]["total_lines_of_code_delta"] == -2
    assert delta["summary"]["total_function_count_delta"] == -1
    assert delta["summary"]["total_class_count_delta"] == 0


def test_main_writes_json_and_markdown(tmp_path: Path) -> None:
    baseline = tmp_path / "base.json"
    current = tmp_path / "curr.json"
    out_json = tmp_path / "delta.json"
    out_md = tmp_path / "delta.md"
    baseline.write_text(
        json.dumps({"generated_at_utc": "x", "modules": [{"path": "m.py", "lines_of_code": 1}]}),
        encoding="utf-8",
    )
    current.write_text(
        json.dumps({"generated_at_utc": "y", "modules": [{"path": "m.py", "lines_of_code": 2}]}),
        encoding="utf-8",
    )
    rc = phase2_delta.main(
        [
            "--baseline",
            str(baseline),
            "--current",
            str(current),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ]
    )
    assert rc == 0
    assert "total LOC delta" in out_md.read_text(encoding="utf-8")
