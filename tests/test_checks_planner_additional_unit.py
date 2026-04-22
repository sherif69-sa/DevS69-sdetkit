from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from sdetkit.checks.base import CheckDefinition, CheckProfile, PlannerHint, RegistrySnapshot
from sdetkit.checks.planner import CheckPlanner, classify_changed_files, discover_changed_files


def _snapshot() -> RegistrySnapshot:
    checks = {
        "lint": CheckDefinition(
            id="lint",
            title="Lint",
            category="lint",
            cost="cheap",
            truth_level="smoke",
            command=("ruff", "check", "."),
        ),
        "tests_smoke": CheckDefinition(
            id="tests_smoke",
            title="Smoke Tests",
            category="tests",
            cost="cheap",
            truth_level="smoke",
            command=("pytest", "-q"),
            required_tools=("pytest",),
        ),
        "tests_full": CheckDefinition(
            id="tests_full",
            title="Full Tests",
            category="tests",
            cost="expensive",
            truth_level="merge",
            command=("pytest",),
            required_tools=("pytest",),
            required_paths=("tests",),
        ),
    }
    profiles = {
        "quick": CheckProfile(
            name="quick",
            description="quick",
            default_truth_level="smoke",
            merge_truth=False,
            check_ids=("lint", "tests_smoke"),
            notes="quick lane",
        ),
        "standard": CheckProfile(
            name="standard",
            description="standard",
            default_truth_level="standard",
            merge_truth=False,
            check_ids=("lint", "tests_smoke"),
            notes="standard lane",
        ),
        "strict": CheckProfile(
            name="strict",
            description="strict",
            default_truth_level="merge",
            merge_truth=True,
            check_ids=("lint", "tests_full"),
            notes="strict lane",
        ),
        "adaptive": CheckProfile(
            name="adaptive",
            description="adaptive",
            default_truth_level="adaptive",
            merge_truth=False,
            check_ids=("lint", "tests_smoke"),
            planner_selected=True,
            notes="adaptive lane",
        ),
    }
    return RegistrySnapshot(profiles=profiles, checks=checks)


def test_discover_changed_files_handles_git_absent_and_status_fail(
    monkeypatch, tmp_path: Path
) -> None:
    assert discover_changed_files(tmp_path) == ()

    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(
        "sdetkit.checks.planner.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout=""),
    )
    assert discover_changed_files(tmp_path) == ()


def test_discover_changed_files_parses_rename_and_short_lines(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    stdout = "M  src/a.py\nR  old.py -> src/new.py\n?? docs/readme.md\nX\n"
    monkeypatch.setattr(
        "sdetkit.checks.planner.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=stdout),
    )

    changed = discover_changed_files(tmp_path)
    assert changed == ("docs/readme.md", "src/a.py", "src/new.py")


def test_classify_changed_files_covers_extra_branches() -> None:
    areas = classify_changed_files(
        (
            "tests/test_x.py",
            "src/sdetkit/mod.py",
            "docs/guide.md",
            "examples/demo.rst",
            "scripts/tool.sh",
            ".github/workflows/ci.yml",
            "README.md",
            "misc/file.py",
            "assets/logo.svg",
        )
    )
    assert areas == ("assets", "docs", "python", "source", "tests", "tooling")


def test_resolve_profile_branches(monkeypatch, tmp_path: Path) -> None:
    planner = CheckPlanner(_snapshot())

    monkeypatch.setattr("sdetkit.checks.planner.os.cpu_count", lambda: 8)
    monkeypatch.setattr("sdetkit.checks.planner.shutil.which", lambda _name: "/bin/tool")
    (tmp_path / "tests").mkdir()

    resolved, reason, _notes = planner._resolve_profile(
        "adaptive",
        repo_root=tmp_path,
        hint=PlannerHint(profile="adaptive", reasons=("CI build",)),
        changed_files=("src/sdetkit/mod.py",),
        changed_areas=("source",),
    )
    assert (resolved, reason) == ("strict", "CI-like environment requests merge/release truth")

    resolved, reason, _notes = planner._resolve_profile(
        "adaptive",
        repo_root=tmp_path,
        hint=None,
        changed_files=("docs/guide.md",),
        changed_areas=("docs",),
    )
    assert (resolved, reason) == ("quick", "docs/examples-only changes allow the honest smoke lane")

    monkeypatch.setattr("sdetkit.checks.planner.shutil.which", lambda _name: "/bin/tool")
    resolved, reason, _notes = planner._resolve_profile(
        "adaptive",
        repo_root=tmp_path,
        hint=None,
        changed_files=("src/sdetkit/mod.py",),
        changed_areas=("source",),
    )
    assert (resolved, reason) == (
        "standard",
        "small code change set keeps adaptive on standard validation",
    )

    monkeypatch.setattr("sdetkit.checks.planner.shutil.which", lambda _name: None)
    resolved, reason, _notes = planner._resolve_profile(
        "adaptive",
        repo_root=tmp_path,
        hint=None,
        changed_files=("src/sdetkit/mod.py",),
        changed_areas=("source",),
    )
    assert (resolved, reason) == (
        "quick",
        "repo/tooling signals are incomplete, so adaptive stays conservative",
    )


def test_targeting_for_hint_disabled_and_no_safe_targets(tmp_path: Path) -> None:
    planner = CheckPlanner(_snapshot())
    check = _snapshot().check("tests_smoke")

    mode, reason, targets = planner._targeting_for(
        check,
        profile="standard",
        requested_profile="standard",
        repo_root=tmp_path,
        hint=PlannerHint(profile="standard", targeted=False),
        changed_files=("src/sdetkit/mod.py",),
        changed_areas=("source",),
    )
    assert (mode, reason, targets) == ("smoke", "targeted execution disabled by planner hint", ())

    mode, reason, targets = planner._targeting_for(
        check,
        profile="standard",
        requested_profile="standard",
        repo_root=tmp_path,
        hint=None,
        changed_files=("src/sdetkit/unknown.py",),
        changed_areas=("source",),
    )
    assert (mode, reason, targets) == (
        "smoke",
        "no safe pytest targets were inferred from changed files",
        (),
    )


def test_infer_targets_handles_repo_none_and_missing_test_file(tmp_path: Path) -> None:
    planner = CheckPlanner(_snapshot())
    assert planner._infer_test_targets(None, ("tests/test_missing.py",)) == ()
    assert planner._infer_test_targets(tmp_path, ("tests/test_missing.py",)) == ()


def test_prereq_skip_reason_reports_missing_tools(monkeypatch) -> None:
    planner = CheckPlanner(_snapshot())
    check = _snapshot().check("tests_smoke")
    monkeypatch.setattr("sdetkit.checks.planner.shutil.which", lambda _name: None)
    assert planner._prereq_skip_reason(check, None) == "missing required tool(s): pytest"
