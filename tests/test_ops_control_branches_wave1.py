from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

import sdetkit.ops_control as oc
from sdetkit.ops_control import TaskDef


def test_load_config_missing_returns_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert oc._load_config() == {}


@dataclass(frozen=True)
class _Rec:
    factory: object


def test_task_catalog_accepts_taskdef_ignores_bad_and_exceptions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    def good() -> TaskDef:
        return TaskDef("plug", ("python3", "-c", "print('x')"))

    def bad() -> object:
        return {"no": "task"}

    def boom() -> object:
        raise RuntimeError("nope")

    monkeypatch.setattr(
        oc,
        "discover",
        lambda *_a, **_k: [_Rec(factory=good), _Rec(factory=bad), _Rec(factory=boom)],
    )

    tasks = oc._task_catalog()
    assert "plug" in tasks
    assert isinstance(tasks["plug"], TaskDef)


def test_task_order_ignores_deps_not_in_selected() -> None:
    tasks = {"a": TaskDef("a", ("echo", "a"), deps=("missing",))}
    assert oc._task_order(tasks, ("a",)) == ["a"]


def test_profile_tasks_falls_back_when_config_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        oc,
        "_load_config",
        lambda: {"profiles": {"default": ["quality", 1]}},
    )
    assert oc._profile_tasks("default") == oc.PROFILES["default"]


def test_inputs_hash_ignores_git_py_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    Path("a.py").write_text("print('a1')\n", encoding="utf-8")
    (tmp_path / ".git" / "inner").mkdir(parents=True)
    git_py = tmp_path / ".git" / "inner" / "x.py"
    git_py.write_text("print('git1')\n", encoding="utf-8")

    task = TaskDef("t", ("echo", "t"))

    h1 = oc._inputs_hash(task, "default", apply=False)

    git_py.write_text("print('git2')\n", encoding="utf-8")
    h2 = oc._inputs_hash(task, "default", apply=False)
    assert h2 == h1

    Path("a.py").write_text("print('a2')\n", encoding="utf-8")
    h3 = oc._inputs_hash(task, "default", apply=False)
    assert h3 != h1


def test_cache_status_invalid_json_returns_false(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    p = tmp_path / ".sdetkit" / "cache"
    p.mkdir(parents=True)
    (p / "quality.json").write_text("{", encoding="utf-8")

    assert oc._cache_status(oc.BUILTIN_TASKS["quality"], key="k") is False


def test_run_hits_cached_branch_and_security_fix_apply_cmd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)

    tasks = {
        "security-scan": TaskDef("security-scan", ("python3", "-c", "print('scan')")),
        "security-fix": TaskDef(
            "security-fix",
            ("python3", "-m", "sdetkit", "security", "fix", "--dry-run"),
            deps=("security-scan",),
        ),
    }

    monkeypatch.setattr(oc, "_task_catalog", lambda: tasks)
    monkeypatch.setattr(oc, "_profile_tasks", lambda _p: ("security-scan", "security-fix"))
    monkeypatch.setattr(oc, "_inputs_hash", lambda _t, _p, _a: "K")

    monkeypatch.setattr(oc, "_cache_status", lambda t, _k: t.name == "security-scan")

    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **_kwargs: object) -> SimpleNamespace:
        calls.append(list(cmd))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(oc.subprocess, "run", fake_run)

    rc = oc.run(
        profile="ci",
        jobs=1,
        apply=True,
        no_cache=False,
        fail_fast=False,
        keep_going=True,
    )
    assert rc == 0

    assert calls == [["python3", "-m", "sdetkit", "security", "fix", "--apply"]]

    out = capsys.readouterr().out
    assert "[CACHED] security-scan" in out
    assert "[PASS] security-fix" in out


def test_cli_run_computes_apply_and_failfast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(oc, "init_layout", lambda force=False: 0)

    seen: list[tuple[object, ...]] = []

    def fake_run(
        profile: str, jobs: int, apply: bool, no_cache: bool, fail_fast: bool, keep_going: bool
    ) -> int:
        seen.append((profile, jobs, apply, no_cache, fail_fast, keep_going))
        return 0

    monkeypatch.setattr(oc, "run", fake_run)

    rc1 = oc.cli(["run", "--profile", "ci", "--apply"])
    assert rc1 == 0
    assert seen[-1] == ("ci", 1, True, False, True, False)

    rc2 = oc.cli(["run", "--profile", "local", "--apply", "--dry-run"])
    assert rc2 == 0
    assert seen[-1] == ("local", 1, False, False, False, False)
