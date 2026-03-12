from __future__ import annotations

import json
from pathlib import Path

from sdetkit import policy


def test_policy_snapshot_deterministic(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    out = tmp_path / ".sdetkit" / "policies" / "baseline.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    assert policy.main(["snapshot", "--output", str(out)]) == 0
    first = out.read_text(encoding="utf-8")
    assert policy.main(["snapshot", "--output", str(out)]) == 0
    assert out.read_text(encoding="utf-8") == first


def test_policy_check_regression(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    base = tmp_path / "baseline.json"
    assert policy.main(["snapshot", "--output", str(base)]) == 0
    (tmp_path / "src" / "json.py").write_text("x=1\n", encoding="utf-8")
    assert policy.main(["check", "--baseline", str(base)]) == 1


def test_policy_diff_stable_json(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    base = tmp_path / "baseline.json"
    policy.main(["snapshot", "--output", str(base)])
    _ = capsys.readouterr()
    (tmp_path / "src" / "json.py").write_text("x=1\n", encoding="utf-8")
    assert policy.main(["diff", "--baseline", str(base), "--format", "json"]) == 0
    first = capsys.readouterr().out
    assert policy.main(["diff", "--baseline", str(base), "--format", "json"]) == 0
    second = capsys.readouterr().out
    assert json.loads(first) == json.loads(second)


def test_policy_check_json_with_waiver(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    base = tmp_path / "baseline.json"
    assert policy.main(["snapshot", "--output", str(base)]) == 0
    _ = capsys.readouterr()
    (tmp_path / "src" / "json.py").write_text("x=1\n", encoding="utf-8")
    waivers = tmp_path / "waivers.json"
    waivers.write_text(
        json.dumps(
            {
                "waivers": [
                    {
                        "type": "new_stdlib_shadowing",
                        "path": "src/json.py",
                        "owner": "release-engineering",
                        "justification": "temporary shim",
                        "expires_on": "2099-01-01",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    assert policy.main([
        "check",
        "--baseline",
        str(base),
        "--waivers",
        str(waivers),
        "--format",
        "json",
    ]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == "sdetkit.policy.v2"
    assert payload["ok"] is True
