from __future__ import annotations

import json
from pathlib import Path

from sdetkit import doctor


def test_doctor_json_schema_version_and_plan_error(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\nversion='0.1.0'\n", encoding="utf-8")

    assert doctor.main(["--format", "json", "--only", "pyproject"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == "sdetkit.doctor.v2"

    assert doctor.main(["--apply-plan", "bad", "--format", "json"]) == 2
    bad = json.loads(capsys.readouterr().out)
    assert bad["error"]["code"] == "plan_id_mismatch"
