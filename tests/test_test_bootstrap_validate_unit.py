from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from sdetkit import test_bootstrap_validate as tbv


def test_render_text_includes_missing_and_unsupported_lines() -> None:
    report = {
        "python": {"current": "3.10", "required": "3.11", "supported": False},
        "dependencies": {"all_present": False, "missing_modules": ["pytest", "tomli"]},
        "remediation": "install deps",
    }
    out = tbv.render_text(report)
    assert "missing modules: pytest, tomli" in out
    assert "unsupported Python runtime detected" in out


def test_parse_args_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        sys, "argv", ["tbv", "--format", "json", "--strict", "--out", "build/x.json"]
    )
    ns = tbv.parse_args()
    assert ns.format == "json"
    assert ns.strict is True
    assert ns.out == "build/x.json"


def test_main_json_strict_writes_file_and_returns_2(
    tmp_path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    out = tmp_path / "out" / "report.json"
    monkeypatch.setattr(
        tbv,
        "parse_args",
        lambda: SimpleNamespace(format="json", strict=True, out=str(out)),
    )
    monkeypatch.setattr(
        tbv,
        "build_test_bootstrap_report",
        lambda: {
            "ok": False,
            "python": {"current": "3.10", "required": "3.11", "supported": False},
            "dependencies": {"all_present": False, "missing_modules": ["pytest"]},
            "remediation": "install",
        },
    )

    rc = tbv.main()
    assert rc == 2
    assert out.exists()
    assert '"ok": false' in out.read_text(encoding="utf-8")
    assert '"ok": false' in capsys.readouterr().out


def test_main_text_nonstrict_ok_path(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setattr(
        tbv,
        "parse_args",
        lambda: SimpleNamespace(format="text", strict=False, out=""),
    )
    monkeypatch.setattr(
        tbv,
        "build_test_bootstrap_report",
        lambda: {
            "ok": True,
            "python": {"current": "3.12", "required": "3.11", "supported": True},
            "dependencies": {"all_present": True, "missing_modules": []},
            "remediation": "",
        },
    )

    rc = tbv.main()
    assert rc == 0
    assert "dependencies present: True" in capsys.readouterr().out
