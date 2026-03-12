from __future__ import annotations

import json
from pathlib import Path

from sdetkit import policy


def test_policy_check_fail_on_security_ignores_non_security_regressions(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")

    base = tmp_path / "baseline.json"
    assert policy.main(["snapshot", "--output", str(base)]) == 0

    # trigger a non-security regression only (stdlib shadowing)
    (tmp_path / "src" / "json.py").write_text("x=1\n", encoding="utf-8")

    assert policy.main(["check", "--baseline", str(base), "--fail-on", "security"]) == 0


def test_policy_check_fail_on_security_fails_on_security_regression(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)

    base_payload = {
        "schema_version": "sdetkit.policy.v2",
        "version": 2,
        "security": {"rule_counts": {}},
        "repo": {"summary": {}},
        "hygiene": {"non_ascii_files": [], "stdlib_shadowing": []},
    }
    base = tmp_path / "baseline.json"
    base.write_text(json.dumps(base_payload), encoding="utf-8")

    monkeypatch.setattr(
        policy,
        "_snapshot",
        lambda _root: {
            "schema_version": "sdetkit.policy.v2",
        "version": 2,
            "security": {"rule_counts": {"SECRET_GENERIC": 1}},
            "repo": {"summary": {}},
            "hygiene": {"non_ascii_files": [], "stdlib_shadowing": []},
        },
    )

    assert policy.main(["check", "--baseline", str(base), "--fail-on", "security"]) == 1


def test_policy_diff_text_and_missing_baseline(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    missing = tmp_path / "missing.json"
    assert policy.main(["check", "--baseline", str(missing)]) == 2
    assert "baseline not found" in capsys.readouterr().out

    base = tmp_path / "baseline.json"
    base.write_text(
        '{"version":1,"security":{"rule_counts":{}},"repo":{"summary":{}},"hygiene":{"non_ascii_files":[],"stdlib_shadowing":[]}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        policy,
        "_snapshot",
        lambda _root: {
            "schema_version": "sdetkit.policy.v2",
        "version": 2,
            "security": {"rule_counts": {"SECRET_GENERIC": 2}},
            "repo": {"summary": {}},
            "hygiene": {"non_ascii_files": [], "stdlib_shadowing": []},
        },
    )

    assert policy.main(["diff", "--baseline", str(base), "--format", "text"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("RED-FLAG security_rule_increase")
