from __future__ import annotations

import json
from pathlib import Path

from sdetkit.maintenance import cli as mcli
from sdetkit.maintenance.types import CheckResult, MaintenanceContext


def test_build_report_handles_runner_crash(monkeypatch, tmp_path: Path) -> None:
    def _ok(ctx: MaintenanceContext) -> CheckResult:
        return CheckResult(ok=True, summary="ok", details={}, actions=[])

    def _boom(ctx: MaintenanceContext) -> CheckResult:
        raise RuntimeError("bad runner")

    monkeypatch.setattr(mcli, "checks_for_mode", lambda mode: [("a", _ok), ("b", _boom)])

    ctx = MaintenanceContext(
        repo_root=tmp_path,
        python_exe="python",
        mode="quick",
        fix=False,
        env={},
        logger=mcli.StderrLogger(),
    )
    report = mcli._build_report(ctx, deterministic=True)
    assert report["ok"] is False
    assert report["meta"]["had_crash"] is True
    assert "check crashed" in report["checks"]["b"]["summary"]


def test_main_json_output_and_write_file(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.chdir(tmp_path)

    def _ok(ctx: MaintenanceContext) -> CheckResult:
        return CheckResult(ok=True, summary="clean", details={"x": 1}, actions=[])

    monkeypatch.setattr(mcli, "checks_for_mode", lambda mode: [("only", _ok)])

    rc = mcli.main(["--format", "json", "--out", "reports/m.json", "--deterministic"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out.splitlines()[0])
    assert payload["ok"] is True
    assert (tmp_path / "reports/m.json").exists()


def test_main_handles_unknown_format_keyerror(monkeypatch) -> None:
    class _NS:
        format = "broken"
        out = None
        mode = "quick"
        fix = False
        deterministic = False
        quiet = False

    monkeypatch.setattr(mcli, "checks_for_mode", lambda mode: [])
    monkeypatch.setattr(
        mcli, "_build_parser", lambda: type("P", (), {"parse_args": lambda self, argv: _NS})()
    )

    rc = mcli.main([])
    assert rc == 2
