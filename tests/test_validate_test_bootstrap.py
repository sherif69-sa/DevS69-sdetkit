import json
from types import SimpleNamespace

from sdetkit import test_bootstrap
from sdetkit import test_bootstrap_validate as bootstrap


def test_build_report_ok(monkeypatch):
    monkeypatch.setattr(test_bootstrap.sys, "version_info", (3, 11, 0, "final", 0))
    monkeypatch.setattr(test_bootstrap.importlib.util, "find_spec", lambda name: object())

    report = test_bootstrap.build_test_bootstrap_report()

    assert report["ok"] is True
    assert report["dependencies"]["missing_modules"] == []
    assert report["python"]["supported"] is True


def test_build_report_detects_missing(monkeypatch):
    monkeypatch.setattr(test_bootstrap.sys, "version_info", (3, 9, 0, "final", 0))
    monkeypatch.setattr(
        test_bootstrap.importlib.util,
        "find_spec",
        lambda name: None if name == "yaml" else object(),
    )

    report = test_bootstrap.build_test_bootstrap_report()

    assert report["ok"] is False
    assert report["dependencies"]["missing_modules"] == ["yaml"]
    assert report["python"]["supported"] is False


def test_render_json_output(monkeypatch, capsys):
    monkeypatch.setattr(
        bootstrap,
        "parse_args",
        lambda: SimpleNamespace(format="json", strict=False, out=""),
    )
    monkeypatch.setattr(
        bootstrap,
        "build_test_bootstrap_report",
        lambda: {
            "ok": True,
            "python": {"current": "3.12.2", "required": "3.10+", "supported": True},
            "dependencies": {
                "required_modules": ["httpx", "yaml", "hypothesis"],
                "missing_modules": [],
                "all_present": True,
            },
            "remediation": "python -m pip install -r requirements-test.txt",
        },
    )

    rc = bootstrap.main()
    captured = capsys.readouterr().out

    assert rc == 0
    payload = json.loads(captured)
    assert payload["ok"] is True


def test_main_writes_output_file(monkeypatch, tmp_path):
    out_file = tmp_path / "bootstrap.json"
    monkeypatch.setattr(
        bootstrap,
        "parse_args",
        lambda: SimpleNamespace(format="json", strict=False, out=str(out_file)),
    )
    monkeypatch.setattr(
        bootstrap,
        "build_test_bootstrap_report",
        lambda: {
            "ok": True,
            "python": {"current": "3.12.2", "required": "3.10+", "supported": True},
            "dependencies": {
                "required_modules": ["httpx", "yaml", "hypothesis"],
                "missing_modules": [],
                "all_present": True,
            },
            "remediation": "python -m pip install -r requirements-test.txt",
        },
    )

    rc = bootstrap.main()

    assert rc == 0
    assert out_file.exists()
    assert json.loads(out_file.read_text(encoding="utf-8"))["ok"] is True
