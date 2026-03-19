from __future__ import annotations

import json
from pathlib import Path

from sdetkit.maintenance import cli as mcli
from sdetkit.maintenance.types import CheckAction, CheckResult, MaintenanceContext


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


def test_build_report_filters_checks_and_aggregates_actions(monkeypatch, tmp_path: Path) -> None:
    def _fail(_ctx: MaintenanceContext) -> CheckResult:
        return CheckResult(
            ok=False,
            summary="needs work",
            details={},
            actions=[CheckAction(id="lint", title="Run lint", applied=False)],
        )

    def _ok(_ctx: MaintenanceContext) -> CheckResult:
        return CheckResult(ok=True, summary="ok", details={}, actions=[])

    monkeypatch.setattr(
        mcli,
        "checks_for_mode",
        lambda mode: [("lint_check", _fail), ("tests_check", _ok), ("doctor_check", _ok)],
    )

    ctx = MaintenanceContext(
        repo_root=tmp_path,
        python_exe="python",
        mode="quick",
        fix=False,
        env={},
        logger=mcli.StderrLogger(),
    )
    report = mcli._build_report(
        ctx,
        deterministic=True,
        include_checks=["lint_check", "tests_check"],
        exclude_checks=["tests_check"],
        jobs=4,
    )

    assert set(report["checks"]) == {"lint_check"}
    assert report["meta"]["selected_checks"] == ["lint_check"]
    assert report["meta"]["excluded_checks"] == ["tests_check"]
    assert report["meta"]["jobs"] == 4
    assert "Suggested next actions: Run lint." in report["recommendations"]


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


def test_renderers_include_quality_signals_and_hints(tmp_path: Path) -> None:
    report = {
        "ok": False,
        "score": 50,
        "checks": {
            "doctor_check": {
                "ok": False,
                "summary": "doctor score 82% (1 failed, 1 hint(s))",
                "details": {
                    "quality": {
                        "passed_checks": 2,
                        "failed_checks": 1,
                        "skipped_checks": 0,
                        "pass_rate": 67,
                    },
                    "hint_samples": ["impact quality-tooling: 1 actionable package(s)"],
                },
                "actions": [],
            }
        },
        "recommendations": [
            "Doctor hint spotlight: impact quality-tooling: 1 actionable package(s)"
        ],
        "meta": {"mode": "quick"},
    }

    text = mcli._render_text(report)
    md = mcli._render_markdown(report)

    assert "quality: 2 passed / 1 failed / 0 skipped" in text
    assert "hint: impact quality-tooling: 1 actionable package(s)" in text
    assert "### Quality signals" in md
    assert "### Hint samples" in md


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
