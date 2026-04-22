from __future__ import annotations

from pathlib import Path

from sdetkit.checks.base import CheckDefinition, CheckProfile, RegistrySnapshot
from sdetkit.checks.cache import CheckCache
from sdetkit.checks.planner import CheckPlan, PlannedCheck, SkippedCheck
from sdetkit.checks.registry import (
    CheckRegistry,
    check_ids_for_profile,
    planner_seed,
    registry_snapshot,
)
from sdetkit.checks.results import CheckRecord
from sdetkit.checks.runner import CheckRunner


def test_check_cache_roundtrip_and_iter_paths(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "a.py").write_text("print('a')\n", encoding="utf-8")
    (repo / ".sdetkit" / "out").mkdir(parents=True)
    (repo / ".sdetkit" / "out" / "skip.txt").write_text("x", encoding="utf-8")
    (repo / "__pycache__").mkdir()
    (repo / "__pycache__" / "skip.pyc").write_bytes(b"x")

    cache = CheckCache(tmp_path / "cache")
    fp = cache.compute_repo_fingerprint(repo, ())
    assert fp
    key = cache.key_for(
        repo_root=repo,
        check_id="lint",
        profile="quick",
        target_mode="full",
        command="ruff check .",
        changed_paths=(),
        selected_targets=(),
    )
    rec = CheckRecord(id="lint", title="Lint", status="passed", metadata={"x": 1})
    cache.save(key, rec)
    loaded = cache.load(key)
    assert loaded is not None
    assert loaded.metadata["cache"]["status"] == "hit"


def test_check_runner_executes_and_blocks_dependencies(tmp_path: Path) -> None:
    check_a = CheckDefinition(
        id="a",
        title="A",
        category="repo",
        cost="cheap",
        truth_level="smoke",
        command=("echo", "a"),
        run=lambda _ctx: CheckRecord(id="a", title="A", status="failed", reason="bad"),
    )
    check_b = CheckDefinition(
        id="b",
        title="B",
        category="repo",
        cost="cheap",
        truth_level="smoke",
        dependencies=("a",),
        command=("echo", "b"),
        run=lambda _ctx: CheckRecord(id="b", title="B", status="passed"),
    )
    profile = CheckProfile(
        name="quick",
        description="q",
        default_truth_level="smoke",
        merge_truth=False,
        check_ids=("a", "b"),
    )
    snapshot = RegistrySnapshot(profiles={"quick": profile}, checks={"a": check_a, "b": check_b})
    plan = CheckPlan(
        profile="quick",
        requested_profile="quick",
        selected_checks=(
            PlannedCheck("a", "A", True, (), "echo a", "repo", "smoke", True),
            PlannedCheck("b", "B", True, ("a",), "echo b", "repo", "smoke", True),
        ),
        skipped_checks=(SkippedCheck("c", "C", "manual", True),),
        notes=(),
    )
    report = CheckRunner(snapshot).run(
        plan,
        repo_root=tmp_path,
        out_dir=tmp_path / "out",
        env={},
        python_executable="python",
        use_cache=False,
        max_workers=1,
    )
    payload = report.as_dict()
    assert payload["plan"]["profile"] == "quick"
    assert any(r.id == "a" and r.status == "failed" for r in report.records)
    assert any(r.id == "b" and r.status == "skipped" for r in report.records)


def test_registry_helpers() -> None:
    reg = CheckRegistry()
    assert "quick" in reg.profile_names()
    assert reg.profile_check_ids("quick")
    assert reg.check_ids()
    assert planner_seed("adaptive")["profile"] == "adaptive"
    assert registry_snapshot().checks
    assert check_ids_for_profile("quick")
