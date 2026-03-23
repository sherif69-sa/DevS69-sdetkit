from __future__ import annotations

from pathlib import Path

from sdetkit.checks import CheckPlanner, CheckRunner, build_final_verdict, default_registry
from sdetkit.checks.base import CheckDefinition, CheckProfile, PlannerHint, RegistrySnapshot
from sdetkit.checks.results import CheckRecord


def test_registry_exposes_initial_real_checks_and_profiles() -> None:
    registry = default_registry()

    assert registry.profile_names() == ("quick", "standard", "strict", "adaptive")
    assert {
        "format_check",
        "lint",
        "typing",
        "tests_smoke",
        "tests_full",
        "doctor_core",
        "security_source_scan",
    }.issubset(set(registry.check_ids()))
    assert registry.profile_check_ids("quick") == (
        "repo_layout",
        "format_check",
        "lint",
        "typing",
        "tests_smoke",
    )
    assert registry.profile_check_ids("strict")[-2:] == ("tests_full", "security_source_scan")

    planner = registry.planner_seed()
    assert planner["profile"] == "adaptive"
    assert planner["planner_selected"] is True
    assert "doctor" in planner["categories"]


def test_planner_selects_expected_checks_by_profile() -> None:
    planner = CheckPlanner(default_registry().snapshot())
    repo_root = Path.cwd()

    quick = planner.plan("quick", repo_root=repo_root)
    standard = planner.plan("standard", repo_root=repo_root)
    strict = planner.plan("strict", repo_root=repo_root)

    assert quick.selected_ids == (
        "repo_layout",
        "format_check",
        "lint",
        "typing",
        "tests_smoke",
    )
    assert standard.selected_ids == (
        "repo_layout",
        "doctor_core",
        "format_check",
        "lint",
        "typing",
        "tests_smoke",
        "security_source_scan",
    )
    assert strict.selected_ids == (
        "repo_layout",
        "doctor_core",
        "format_check",
        "lint",
        "typing",
        "tests_full",
        "security_source_scan",
    )
    assert "tests_smoke" not in strict.selected_ids


def test_adaptive_profile_returns_valid_conservative_plan(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    planner = CheckPlanner(default_registry().snapshot())

    standard_like = planner.plan("adaptive", repo_root=tmp_path)
    quick_like = planner.plan(
        "adaptive",
        repo_root=tmp_path,
        hint=PlannerHint(profile="adaptive", changed_paths=("docs/guide.md",)),
    )

    assert standard_like.profile == "standard"
    assert standard_like.planner_selected is True
    assert standard_like.selected_ids
    assert quick_like.profile == "quick"
    assert quick_like.selected_ids[-1] == "tests_smoke"


def test_planner_respects_dependencies() -> None:
    snapshot = RegistrySnapshot(
        profiles={
            "quick": CheckProfile(
                name="quick",
                description="",
                default_truth_level="smoke",
                merge_truth=False,
                check_ids=("child",),
            )
        },
        checks={
            "dep": CheckDefinition(
                id="dep",
                title="Dependency",
                category="repo",
                cost="cheap",
                truth_level="smoke",
            ),
            "child": CheckDefinition(
                id="child",
                title="Child",
                category="tests",
                cost="cheap",
                truth_level="smoke",
                dependencies=("dep",),
            ),
        },
    )

    plan = CheckPlanner(snapshot).plan("quick")

    assert plan.selected_ids == ("dep", "child")


def test_skipped_checks_keep_explicit_reasons(tmp_path: Path) -> None:
    plan = CheckPlanner(default_registry().snapshot()).plan("quick", repo_root=tmp_path)
    skipped = {item.id: item.reason for item in plan.skipped_checks}

    assert (
        skipped["tests_full"]
        == "quick profile favors faster validation; run strict for merge truth"
    )
    assert skipped["doctor_core"] == "not selected in quick profile"


def test_runner_marks_dependency_blocked_checks_as_skipped(tmp_path: Path) -> None:
    def fail(_ctx: object) -> CheckRecord:
        return CheckRecord(id="dep", title="Dependency", status="failed")

    def child(_ctx: object) -> CheckRecord:
        return CheckRecord(id="child", title="Child", status="passed")

    snapshot = RegistrySnapshot(
        profiles={
            "quick": CheckProfile(
                name="quick",
                description="",
                default_truth_level="smoke",
                merge_truth=False,
                check_ids=("child",),
            )
        },
        checks={
            "dep": CheckDefinition(
                id="dep",
                title="Dependency",
                category="repo",
                cost="cheap",
                truth_level="smoke",
                run=fail,
            ),
            "child": CheckDefinition(
                id="child",
                title="Child",
                category="tests",
                cost="cheap",
                truth_level="smoke",
                dependencies=("dep",),
                run=child,
            ),
        },
    )

    plan = CheckPlanner(snapshot).plan("quick", repo_root=tmp_path)
    report = CheckRunner(snapshot).run(
        plan,
        repo_root=tmp_path,
        out_dir=tmp_path / ".sdetkit" / "out",
        env={},
        python_executable="python",
    )
    records = {record.id: record for record in report.records}

    assert records["dep"].status == "failed"
    assert records["child"].status == "skipped"
    assert records["child"].reason == "dependency not satisfied: dep"
    assert report.verdict.ok is False


def test_final_verdict_contract_separates_run_skipped_and_failures() -> None:
    verdict = build_final_verdict(
        profile="quick",
        profile_notes="Smoke only.",
        checks=[
            CheckRecord(id="format_check", title="Ruff format check", status="passed"),
            CheckRecord(id="tests_smoke", title="Fast/smoke tests", status="failed"),
            CheckRecord(
                id="tests_full",
                title="Full pytest suite",
                status="skipped",
                reason="quick profile favors faster validation; run strict for merge truth",
            ),
        ],
    )

    payload = verdict.as_dict()

    assert payload["verdict_contract"] == "sdetkit.final-verdict.v1"
    assert payload["profile"] == "quick"
    assert payload["confidence_level"] == "low (smoke-only)"
    assert payload["blocking_failures"] == ["tests_smoke: Fast/smoke tests"]
    assert payload["checks_skipped"][0]["reason"] == (
        "quick profile favors faster validation; run strict for merge truth"
    )
    assert payload["recommendation"] == "do-not-merge"
