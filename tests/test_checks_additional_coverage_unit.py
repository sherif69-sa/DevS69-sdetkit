from __future__ import annotations

from pathlib import Path

from sdetkit.checks.base import CheckContext, CheckDefinition, CheckProfile, RegistrySnapshot
from sdetkit.checks.builtin import (
    _feature_registry_contract_command,
    _lint_command,
    _make_command_runner,
    _skip_missing_prereqs,
    _tests_full_command,
    _tests_smoke_command,
    _typing_command,
)
from sdetkit.checks.cache import CheckCache
from sdetkit.checks.planner import CheckPlan, PlannedCheck, SkippedCheck
from sdetkit.checks.results import CheckRecord
from sdetkit.checks.runner import CheckRunner


def test_builtin_command_helpers_and_skip_path_branches(tmp_path: Path) -> None:
    ctx = CheckContext(repo_root=tmp_path, out_dir=tmp_path / "out", python_executable="python")

    assert _lint_command(ctx) == ("python", "-m", "ruff", "check", ".")
    assert _typing_command(ctx) == (
        "python",
        "-m",
        "mypy",
        "--config-file",
        "pyproject.toml",
        "src",
    )
    assert _feature_registry_contract_command(ctx) == (
        "python",
        "scripts/check_feature_registry_contract.py",
    )

    tctx = ctx.for_check(
        check_id="tests_smoke", target_mode="targeted", selected_targets=("tests/test_demo.py",)
    )
    assert _tests_smoke_command(tctx)[2] == "pytest"
    assert _tests_smoke_command(ctx.for_check(check_id="tests_smoke", target_mode="full")) == (
        "python",
        "-m",
        "sdetkit",
        "gate",
        "fast",
    )
    assert _tests_full_command(ctx.for_check(check_id="tests_full", target_mode="full")) == (
        "python",
        "-m",
        "pytest",
        "-q",
        "-o",
        "addopts=",
    )

    check = CheckDefinition(
        id="repo_layout",
        title="Repo",
        category="repo",
        cost="cheap",
        truth_level="smoke",
        command=("python", "scripts/check_repo_layout.py"),
        required_paths=("scripts/check_repo_layout.py",),
    )
    skipped = _skip_missing_prereqs(check, ctx)
    assert skipped is not None and skipped.status == "skipped"
    assert "missing required path" in skipped.reason


def test_builtin_make_command_runner_returns_skipped_without_subprocess(tmp_path: Path) -> None:
    ctx = CheckContext(repo_root=tmp_path, out_dir=tmp_path / "out", python_executable="python")
    check = CheckDefinition(
        id="lint",
        title="Lint",
        category="lint",
        cost="cheap",
        truth_level="smoke",
        command=("ruff", "check", "."),
        required_tools=("tool-does-not-exist",),
    )
    runner = _make_command_runner(lambda _ctx: ("python", "-m", "pytest"))
    rec = runner(check, ctx)
    assert rec.status == "skipped"
    assert "missing required tool" in rec.reason


def test_cache_internal_path_logic_and_disabled_roundtrip(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.py").write_text("print('a')\n", encoding="utf-8")
    (repo / "pkg").mkdir()
    (repo / "pkg" / "b.py").write_text("print('b')\n", encoding="utf-8")
    (repo / ".git").mkdir()
    (repo / ".git" / "ignored.txt").write_text("x", encoding="utf-8")
    (repo / ".sdetkit" / "out").mkdir(parents=True)
    (repo / ".sdetkit" / "out" / "tmp.txt").write_text("x", encoding="utf-8")

    cache = CheckCache(tmp_path / "cache")
    assert cache.base_dir == tmp_path / "cache"
    assert cache._is_ignored_path(repo, Path("/tmp/elsewhere")) is True
    assert cache._is_ignored_path(repo, repo / ".git" / "ignored.txt") is True
    assert cache._is_ignored_path(repo, repo / "a.py") is False

    discovered = list(cache._iter_paths(repo, ("a.py", "pkg", ".git")))
    rel = [p.relative_to(repo).as_posix() for p in discovered]
    assert rel == ["a.py", "pkg/b.py"]

    all_paths = [p.relative_to(repo).as_posix() for p in cache._iter_paths(repo, ())]
    assert ".git/ignored.txt" not in all_paths
    assert ".sdetkit/out/tmp.txt" not in all_paths

    disabled = CheckCache(tmp_path / "cache-disabled", enabled=False)
    rec = CheckRecord(id="lint", title="Lint", status="passed")
    disabled.save("abc", rec)
    assert disabled.load("abc") is None


def _mk_snapshot(*, parallel_safe: bool = True, run=None) -> RegistrySnapshot:
    profile = CheckProfile(
        name="quick",
        description="",
        default_truth_level="smoke",
        merge_truth=False,
        check_ids=("a",),
    )
    check = CheckDefinition(
        id="a",
        title="A",
        category="repo",
        cost="cheap",
        truth_level="smoke",
        parallel_safe=parallel_safe,
        command=("echo", "a"),
        cacheable=False,
        run=run,
    )
    return RegistrySnapshot(profiles={"quick": profile}, checks={"a": check})


def test_runner_handles_unwired_check_and_loop_break_edges(tmp_path: Path) -> None:
    snapshot = _mk_snapshot(run=None)
    runner = CheckRunner(snapshot)

    # Hit line 252 branch: definition.run is None -> skipped record.
    plan = CheckPlan(
        profile="quick",
        requested_profile="quick",
        selected_checks=(PlannedCheck("a", "A", True, (), "echo a", "repo", "smoke", True),),
        skipped_checks=(),
    )
    report = runner.run(
        plan,
        repo_root=tmp_path,
        out_dir=tmp_path / "out1",
        env={},
        python_executable="python",
        use_cache=False,
    )
    assert report.records[0].status == "skipped"
    assert "no execution wiring" in report.records[0].reason

    # Hit lines 117 + 169: selected id already in completed via skipped_checks.
    plan_precompleted = CheckPlan(
        profile="quick",
        requested_profile="quick",
        selected_checks=(PlannedCheck("a", "A", True, (), "echo a", "repo", "smoke", True),),
        skipped_checks=(SkippedCheck("a", "A", "pre-skipped", True),),
    )
    report2 = runner.run(
        plan_precompleted,
        repo_root=tmp_path,
        out_dir=tmp_path / "out2",
        env={},
        python_executable="python",
        use_cache=False,
    )
    assert report2.records and report2.records[0].status == "skipped"

    # Hit lines 119 + 169: unresolved dependency leaves item pending and loop exits.
    plan_unresolved = CheckPlan(
        profile="quick",
        requested_profile="quick",
        selected_checks=(
            PlannedCheck("a", "A", True, ("ghost",), "echo a", "repo", "smoke", True),
        ),
        skipped_checks=(),
    )
    report3 = runner.run(
        plan_unresolved,
        repo_root=tmp_path,
        out_dir=tmp_path / "out3",
        env={},
        python_executable="python",
        use_cache=False,
    )
    assert report3.records == ()


def test_runner_scheduling_guards_for_parallel_safe_and_non_parallel(tmp_path: Path) -> None:
    calls = {"n": 0}

    def delayed(_ctx):
        calls["n"] += 1
        return CheckRecord(id="a", title="A", status="passed")

    # workers=1 and already a future -> hit line 150 continue
    profile = CheckProfile("quick", "", "smoke", False, ("a", "b"))
    checks = {
        "a": CheckDefinition(
            "a", "A", "repo", "cheap", "smoke", command=("echo", "a"), run=delayed
        ),
        "b": CheckDefinition(
            "b", "B", "repo", "cheap", "smoke", command=("echo", "b"), run=delayed
        ),
    }
    snapshot = RegistrySnapshot(profiles={"quick": profile}, checks=checks)
    plan = CheckPlan(
        profile="quick",
        requested_profile="quick",
        selected_checks=(
            PlannedCheck("a", "A", True, (), "echo a", "repo", "smoke", True),
            PlannedCheck("b", "B", True, (), "echo b", "repo", "smoke", True),
        ),
        skipped_checks=(),
    )
    report = CheckRunner(snapshot).run(
        plan,
        repo_root=tmp_path,
        out_dir=tmp_path / "out4",
        env={},
        python_executable="python",
        use_cache=False,
        max_workers=1,
    )
    assert len(report.records) == 2

    # non-parallel item submitted should break scheduling pass (line 163)
    checks2 = {
        "a": CheckDefinition(
            "a",
            "A",
            "repo",
            "cheap",
            "smoke",
            parallel_safe=False,
            command=("echo", "a"),
            run=delayed,
        )
    }
    snapshot2 = RegistrySnapshot(
        profiles={"quick": CheckProfile("quick", "", "smoke", False, ("a",))}, checks=checks2
    )
    plan2 = CheckPlan(
        profile="quick",
        requested_profile="quick",
        selected_checks=(PlannedCheck("a", "A", True, (), "echo a", "repo", "smoke", False),),
        skipped_checks=(),
    )
    report2 = CheckRunner(snapshot2).run(
        plan2,
        repo_root=tmp_path,
        out_dir=tmp_path / "out5",
        env={},
        python_executable="python",
        use_cache=False,
        max_workers=2,
    )
    assert report2.records[0].status == "passed"


def test_checks_module_getattr_and_registry_profile_definitions() -> None:
    import sdetkit.checks as checks_pkg
    from sdetkit.checks.registry import profile_definitions

    assert checks_pkg.main_.__name__.endswith("checks.main")
    profiles = profile_definitions()
    assert any(profile.name == "quick" for profile in profiles)


def test_run_subprocess_failed_status_for_single_attempt(tmp_path: Path, monkeypatch) -> None:
    from sdetkit.checks.builtin import _run_subprocess

    ctx = CheckContext(repo_root=tmp_path, out_dir=tmp_path / "out", python_executable="python")
    check = CheckDefinition(
        id="lint",
        title="Lint",
        category="lint",
        cost="cheap",
        truth_level="smoke",
        command=("python", "-m", "ruff", "check", "."),
    )

    monkeypatch.setattr(
        "sdetkit.checks.builtin.subprocess.run",
        lambda *_a, **_k: type("R", (), {"returncode": 2, "stdout": "", "stderr": "boom"})(),
    )
    record = _run_subprocess(check, ctx, check.command)
    assert record.status == "failed"
    assert "rc=2" in record.reason


def test_cache_iter_tree_files_and_iter_paths_skip_branches(monkeypatch, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    cache = CheckCache(tmp_path / "cache")

    assert cache._is_ignored_path(repo, repo / ".sdetkit" / "out" / "result.json") is True

    fake_walk_rows = [
        (str(repo), [".git", ".sdetkit", "ok"], ["root.txt"]),
        (str(repo / ".git"), ["inner"], ["ignored.txt"]),
        (str(repo / ".sdetkit" / "out"), ["nested"], ["ignored2.txt"]),
        (str(repo / "ok"), [], ["keep.txt"]),
    ]
    monkeypatch.setattr("sdetkit.checks.cache.os.walk", lambda _root: iter(fake_walk_rows))
    files = list(cache._iter_tree_files(repo))
    rel = [p.relative_to(repo).as_posix() for p in files]
    assert rel == ["root.txt", "ok/keep.txt"]

    (repo / "src").mkdir()
    normal = repo / "normal.py"
    ignored = repo / ".git" / "ignored.py"

    monkeypatch.setattr(cache, "_iter_tree_files", lambda _root: iter((normal, ignored)))
    monkeypatch.setattr(
        cache,
        "_is_ignored_path",
        lambda _repo, p: (
            p.as_posix().endswith(".git/ignored.py") or p.as_posix().endswith("/ignored.py")
        ),
    )
    out = list(cache._iter_paths(repo, ("src",)))
    assert out == [normal]

    out2 = list(cache._iter_paths(repo, ()))
    assert out2 == [normal]


def test_runner_hits_non_parallel_guard_with_existing_futures(tmp_path: Path) -> None:
    def rec_a(_ctx):
        return CheckRecord(id="a", title="A", status="passed")

    def rec_b(_ctx):
        return CheckRecord(id="b", title="B", status="passed")

    profile = CheckProfile("quick", "", "smoke", False, ("a", "b"))
    checks = {
        "a": CheckDefinition("a", "A", "repo", "cheap", "smoke", command=("echo", "a"), run=rec_a),
        "b": CheckDefinition(
            "b",
            "B",
            "repo",
            "cheap",
            "smoke",
            parallel_safe=False,
            command=("echo", "b"),
            run=rec_b,
        ),
    }
    snapshot = RegistrySnapshot(profiles={"quick": profile}, checks=checks)
    plan = CheckPlan(
        profile="quick",
        requested_profile="quick",
        selected_checks=(
            PlannedCheck("a", "A", True, (), "echo a", "repo", "smoke", True),
            PlannedCheck("b", "B", True, (), "echo b", "repo", "smoke", False),
        ),
        skipped_checks=(),
    )
    report = CheckRunner(snapshot).run(
        plan,
        repo_root=tmp_path,
        out_dir=tmp_path / "out6",
        env={},
        python_executable="python",
        use_cache=False,
        max_workers=2,
    )
    assert [r.id for r in report.records] == ["a", "b"]


def test_checks_module_getattr_unknown_attribute_raises() -> None:
    import pytest

    import sdetkit.checks as checks_pkg

    with pytest.raises(AttributeError):
        _ = checks_pkg.not_real  # type: ignore[attr-defined]
