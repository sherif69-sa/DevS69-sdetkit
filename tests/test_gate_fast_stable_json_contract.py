from __future__ import annotations

import json

from sdetkit import gate as gate_mod


def test_gate_fast_stable_json_is_normalized() -> None:
    payload = {
        "profile": "fast",
        "root": "/abs/repo",
        "ok": True,
        "failed_steps": [],
        "steps": [
            {
                "id": "ruff",
                "cmd": ["/abs/repo/.venv/bin/python", "-m", "ruff", "check", "."],
                "rc": 0,
                "ok": True,
                "duration_ms": 123,
                "stdout": "x",
                "stderr": "y",
            }
        ],
    }

    normalized = gate_mod._normalize_gate_payload(payload)
    out = gate_mod._stable_json(normalized)

    assert out.endswith("\n")
    obj = json.loads(out)
    assert obj["root"] == "<repo>"
    step = obj["steps"][0]
    assert "duration_ms" not in step
    assert "stdout" not in step
    assert "stderr" not in step
    assert step["cmd"][0] == "python"
