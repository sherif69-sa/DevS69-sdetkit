from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli


def _run(args: list[str]) -> int:
    return cli.main(["security", *args])


def test_enforce_default_budgets_fail_on_info(tmp_path: Path, capsys) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "x.py").write_text("print('x')\n", encoding="utf-8")

    rc = _run(["enforce", "--root", str(tmp_path), "--format", "json"])
    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["counts"]["info"] == 1
    assert any(item["metric"] == "info" for item in payload["exceeded"])


def test_enforce_max_info_allows_current_info(tmp_path: Path, capsys) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "x.py").write_text("print('x')\n", encoding="utf-8")

    rc = _run(["enforce", "--root", str(tmp_path), "--format", "json", "--max-info", "1"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True


def test_enforce_max_rule_budget(tmp_path: Path, capsys) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "x.py").write_text("import os\nos.system('x')\n", encoding="utf-8")

    rc = _run(
        [
            "enforce",
            "--root",
            str(tmp_path),
            "--format",
            "json",
            "--max-info",
            "10",
            "--max-error",
            "10",
            "--max-rule",
            "SEC_OS_SYSTEM=0",
        ]
    )
    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["exceeded_rules"][0]["rule_id"] == "SEC_OS_SYSTEM"


def test_enforce_scan_json_input(tmp_path: Path, capsys) -> None:
    scan_json = tmp_path / "scan.json"
    scan_json.write_text(
        json.dumps(
            {
                "findings": [
                    {
                        "rule_id": "SEC_DEBUG_PRINT",
                        "severity": "info",
                        "path": "src/a.py",
                        "line": 1,
                        "column": 0,
                        "message": "print(...) found in src/.",
                        "suggestion": "",
                        "fingerprint": "abc",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    rc = _run(["enforce", "--root", str(tmp_path), "--scan-json", str(scan_json), "--format", "json"])
    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["counts"]["total"] == 1
