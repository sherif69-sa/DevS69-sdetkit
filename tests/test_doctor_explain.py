from __future__ import annotations

import json

from sdetkit import doctor


def test_doctor_explain_json_emits_prioritized_steps(capsys) -> None:
    rc = doctor.main(["--only", "clean_tree", "--format", "json", "--explain"])
    assert rc in (0, 2)
    payload = json.loads(capsys.readouterr().out)
    explain = payload.get("explain", {})
    assert explain.get("mode") == "doctor-explain"
    assert isinstance(explain.get("steps"), list)
    if explain["steps"]:
        step = explain["steps"][0]
        assert "confidence" in step
        assert "recommended_fix" in step


def test_doctor_explain_text_includes_explain_block(capsys) -> None:
    rc = doctor.main(["--only", "clean_tree", "--explain"])
    assert rc in (0, 2)
    out = capsys.readouterr().out
    assert "explain:" in out
