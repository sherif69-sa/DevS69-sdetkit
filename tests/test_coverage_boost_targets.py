from __future__ import annotations

import runpy
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from sdetkit import gate, netclient
from sdetkit.maintenance import registry
from sdetkit.maintenance.checks import lint_check
from sdetkit.maintenance.types import MaintenanceContext


def test_maintenance_main_module_executes_main(monkeypatch: pytest.MonkeyPatch) -> None:
    import sdetkit.maintenance.cli as mcli

    monkeypatch.setattr(mcli, "main", lambda: 7)
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("sdetkit.maintenance.main", run_name="main_")
    assert exc.value.code == 7


def test_registry_discover_and_mode_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        registry.pkgutil,
        "iter_modules",
        lambda _path: [SimpleNamespace(name="_private"), SimpleNamespace(name="alpha")],
    )

    mod = SimpleNamespace(CHECK_NAME="alpha", run=lambda _ctx: None, CHECK_MODES="bad")
    monkeypatch.setattr(registry.importlib, "import_module", lambda _name: mod)

    found = registry.discover_checks()
    assert found and found[0][0] == "alpha"
    assert found[0][2] == {"quick", "full"}
    assert registry.checks_for_mode("quick")[0][0] == "alpha"


def test_lint_check_fix_mode_and_failure_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    ctx = MaintenanceContext(
        repo_root=tmp_path,
        python_exe="python",
        mode="quick",
        fix=True,
        env={},
        logger=object(),
    )
    monkeypatch.setattr(
        lint_check.shutil,
        "which",
        lambda tool: "/usr/bin/x" if tool in {"ruff", "pre-commit"} else None,
    )

    calls: list[list[str]] = []

    def _run(cmd: list[str], *, cwd: Path):
        calls.append(cmd)
        if cmd[-2:] == ["--check", "."]:
            return SimpleNamespace(returncode=1, stdout="fmt", stderr="")
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(lint_check, "run_cmd", _run)
    result = lint_check.run(ctx)
    assert result.ok is False
    assert any(a.id == "precommit-hygiene" for a in result.actions)
    assert any(cmd[:4] == ["python", "-m", "pre_commit", "run"] for cmd in calls)


def test_gate_helpers_cover_normalization_and_output(tmp_path: Path, capsys) -> None:
    payload = {
        "root": str(tmp_path),
        "steps": [
            {
                "id": "x",
                "cmd": ["/usr/bin/python3", str(tmp_path / "a")],
                "duration_ms": 11,
                "stdout": "a",
                "stderr": "b",
            }
        ],
    }
    normalized = gate._normalize_gate_payload(payload)
    assert normalized["root"] == "<repo>"
    assert normalized["steps"][0]["cmd"][0] == "python"
    assert normalized["steps"][0]["cmd"][1] == "<repo>/a"
    assert gate._parse_step_filter("ruff,,doctor") == {"ruff", "doctor"}

    gate._write_output("ok", None)
    assert capsys.readouterr().out == "ok"


def test_netclient_helper_branches() -> None:
    assert netclient._retry_after_seconds({"Retry-After": "abc"}) is None
    hdrs, rid = netclient._merge_headers({"A": "B"}, None, "rid")
    assert hdrs == {"A": "B"}
    assert rid == "rid"

    req = httpx.Request("GET", "https://example.test/a")
    resp = httpx.Response(200, request=req, headers={"Link": "<b>; rel=next"})
    assert netclient._link_next_url(resp) == "https://example.test/b"
