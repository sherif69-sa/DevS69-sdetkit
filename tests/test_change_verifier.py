"""`sdetkit verify change`: run a change's tests in a clone and catch weakened tests."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import site
import subprocess
import sys
from pathlib import Path

import pytest

from sdetkit import change_verifier
from tests._cli_inprocess import run_cli

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="needs git")

BUGGY = "def add(a, b):\n    return a - b\n"
FIXED = "def add(a, b):\n    return a + b\n"
TEST = (
    "from calc import add\n\n\n"
    "def test_add():\n    assert add(2, 3) == 5\n\n\n"
    "def test_zero():\n    assert add(0, 0) == 0\n"
)


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _repo(tmp_path: Path, source: str = BUGGY, test: str = TEST) -> Path:
    repo = tmp_path / "repo"
    (repo / "src" / "calc").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "src" / "calc" / "__init__.py").write_text(source, encoding="utf-8")
    (repo / "tests" / "test_calc.py").write_text(test, encoding="utf-8")
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "calc"\nversion = "0"\n\n[tool.coverage.report]\nfail_under = 90\n',
        encoding="utf-8",
    )
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    return repo


def _patch(repo: Path, files: dict[str, str]) -> str:
    """The diff a contributor would send: edit, diff, then put the tree back."""

    for path, text in files.items():
        (repo / path).write_text(text, encoding="utf-8")
    diff = _git(repo, "diff")
    _git(repo, "checkout", "--", ".")
    return diff


def _verify(repo: Path, tmp_path: Path, **kwargs: object) -> dict[str, object]:
    return change_verifier.verify_change(
        repo_root=repo,
        out_dir=tmp_path / "out",
        python=sys.executable,
        timeout_seconds=120,
        **kwargs,  # type: ignore[arg-type]
    )


def test_a_real_fix_is_verified_and_attested(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    report = _verify(
        repo,
        tmp_path,
        patch_text=_patch(repo, {"src/calc/__init__.py": FIXED}),
        base_mode="full",
    )

    assert report["status"] == change_verifier.VERIFIED, report["reasons"]
    comparison = report["tests"]["comparison"]  # type: ignore[index]
    # Only a full base run knows which tests failed before and pass now.
    assert comparison["fixed"] == ["tests.test_calc::test_add"]
    assert comparison["regressions"] == []
    out = tmp_path / "out"
    patch_bytes = (out / "change.patch").read_bytes()
    statement = json.loads((out / "change-verification.intoto.json").read_text(encoding="utf-8"))
    assert statement["_type"] == "https://in-toto.io/Statement/v1"
    assert statement["subject"][0]["digest"]["sha256"] == hashlib.sha256(patch_bytes).hexdigest()
    assert statement["predicate"]["status"] == "VERIFIED"
    report_digest = hashlib.sha256((out / "change-verification.json").read_bytes()).hexdigest()
    assert statement["predicate"]["evidence"]["change-verification.json"] == report_digest
    # The caller's tree is untouched.
    assert (repo / "src" / "calc" / "__init__.py").read_text(encoding="utf-8") == BUGGY
    assert _git(repo, "status", "--porcelain") == ""


def test_deleting_the_failing_test_is_not_verified(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    weakened = "from calc import add\n\n\ndef test_zero():\n    assert add(0, 0) == 0\n"

    report = _verify(repo, tmp_path, patch_text=_patch(repo, {"tests/test_calc.py": weakened}))

    assert report["status"] == change_verifier.REVIEW
    codes = [finding["code"] for finding in report["findings"]]  # type: ignore[attr-defined]
    assert "tests_removed" in codes
    assert report["tests"]["comparison"]["missing"] == ["tests.test_calc::test_add"]  # type: ignore[index]


def test_an_assertion_swapped_for_assert_true_is_caught(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    emptied = TEST.replace("assert add(2, 3) == 5", "assert True")

    report = _verify(repo, tmp_path, patch_text=_patch(repo, {"tests/test_calc.py": emptied}))

    assert report["status"] == change_verifier.REVIEW
    [finding] = [f for f in report["findings"] if f["code"] == "assertions_removed"]  # type: ignore[attr-defined]
    assert finding["items"] == ["tests/test_calc.py::test_add (1 -> 0)"]


def test_a_new_skip_marker_is_caught(tmp_path: Path) -> None:
    repo = _repo(tmp_path, source=FIXED)
    skipped = "import pytest\n" + TEST.replace(
        "def test_add", '@pytest.mark.skip(reason="flaky")\ndef test_add'
    )

    report = _verify(repo, tmp_path, patch_text=_patch(repo, {"tests/test_calc.py": skipped}))

    assert report["status"] == change_verifier.REVIEW
    codes = [finding["code"] for finding in report["findings"]]  # type: ignore[attr-defined]
    assert "skip_added" in codes
    assert report["tests"]["comparison"]["now_skipped"] == ["tests.test_calc::test_add"]  # type: ignore[index]


def test_a_change_that_breaks_a_passing_test_fails(tmp_path: Path) -> None:
    repo = _repo(tmp_path, source=FIXED)
    broken = "def add(a, b):\n    return a + b + 1\n"

    report = _verify(repo, tmp_path, patch_text=_patch(repo, {"src/calc/__init__.py": broken}))

    assert report["status"] == change_verifier.FAILED
    assert set(report["tests"]["comparison"]["regressions"]) == {  # type: ignore[index]
        "tests.test_calc::test_add",
        "tests.test_calc::test_zero",
    }
    # Why each one fails, in the report, its Markdown and the job summary.
    failures = report["tests"]["failures"]  # type: ignore[index]
    assert set(failures) == {"tests.test_calc::test_add", "tests.test_calc::test_zero"}
    assert "assert 6 == 5" in failures["tests.test_calc::test_add"]
    markdown = (tmp_path / "out" / "change-verification.md").read_text(encoding="utf-8")
    assert "## Why they fail" in markdown and "assert 6 == 5" in markdown
    summary = change_verifier.render_summary(report)
    assert "Why they fail (2)" in summary and "assert 6 == 5" in summary


def test_failure_messages_keep_their_end_and_stay_few() -> None:
    long = "start " + "x" * 5000 + " AssertionError: the end"
    failures = {f"t::{n}": long for n in range(30)}

    kept = change_verifier.keep_failures(failures, sorted(failures))

    assert len(kept) == change_verifier.MAX_FAILURES
    assert all(why.startswith("...") and why.endswith("the end") for why in kept.values())
    assert all(len(why) == change_verifier.FAILURE_CHARS + 3 for why in kept.values())
    assert change_verifier.keep_failures({"t::a": "  "}, ["t::a", "t::b"]) == {}


def test_failure_messages_lose_runner_frames_and_clone_paths(tmp_path: Path) -> None:
    clone = tmp_path / "clone"
    text = (
        "Error: expect(received).toBe(expected)\n"
        f"    at Object.toBe ({clone.as_posix()}/test/calc.test.js:4:23)\n"
        "    at callAsyncCircusFn (/x/node_modules/jest-circus/build/a.js:1:2)\n"
        "    at new Promise (<anonymous>)\n"
        "    at process.processTicksAndRejections (node:internal/process/task_queues:95:5)\n"
        f"    at file://{clone.as_posix()}/src/a.mjs:2:3\n"
    )

    assert change_verifier.clean_failure(text, clone) == (
        "Error: expect(received).toBe(expected)\n"
        "    at Object.toBe (test/calc.test.js:4:23)\n"
        "    at src/a.mjs:2:3"
    )


def test_a_failure_message_cannot_close_its_code_block() -> None:
    fenced = change_verifier._fenced("before\n```\nafter")

    assert fenced.startswith("````text\n") and fenced.endswith("\n````")


def test_lowering_the_coverage_threshold_is_caught(tmp_path: Path) -> None:
    repo = _repo(tmp_path, source=FIXED)
    pyproject = (repo / "pyproject.toml").read_text(encoding="utf-8").replace("90", "50")

    report = _verify(repo, tmp_path, patch_text=_patch(repo, {"pyproject.toml": pyproject}))

    assert report["status"] == change_verifier.REVIEW
    [finding] = [f for f in report["findings"] if f["code"] == "coverage_threshold_lowered"]  # type: ignore[attr-defined]
    assert finding["items"] == ["pyproject.toml (90 -> 50)"]


def test_a_head_commit_is_verified_without_a_patch_file(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    base = _git(repo, "rev-parse", "HEAD").strip()
    (repo / "src" / "calc" / "__init__.py").write_text(FIXED, encoding="utf-8")
    _git(repo, "commit", "-qam", "fix")
    head = _git(repo, "rev-parse", "HEAD").strip()

    report = _verify(repo, tmp_path, base=base, head=head)

    assert report["status"] == change_verifier.VERIFIED, report["reasons"]
    statement = json.loads(
        (tmp_path / "out" / "change-verification.intoto.json").read_text(encoding="utf-8")
    )
    assert {"name": "head", "digest": {"gitCommit": head}} in statement["subject"]


def test_cli_reports_a_patch_that_does_not_apply(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    bad = tmp_path / "bad.patch"
    bad.write_text(
        "--- a/src/calc/missing.py\n+++ b/src/calc/missing.py\n@@ -1 +1 @@\n-x\n+y\n",
        encoding="utf-8",
    )

    result = run_cli(
        "verify",
        "change",
        "--repo-root",
        str(repo),
        "--patch",
        str(bad),
        "--out-dir",
        str(tmp_path / "o"),
    )

    assert result.returncode == 2
    assert "does not apply" in result.stderr


def test_cli_exit_code_follows_the_status(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    patch = tmp_path / "fix.patch"
    patch.write_text(_patch(repo, {"src/calc/__init__.py": FIXED}), encoding="utf-8")

    result = run_cli(
        "verify",
        "change",
        "--repo-root",
        str(repo),
        "--patch",
        str(patch),
        "--python",
        sys.executable,
        "--out-dir",
        str(tmp_path / "o"),
        "--format",
        "json",
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "VERIFIED"


def test_a_fix_with_its_test_proves_itself(tmp_path: Path) -> None:
    # The test the change adds fails on the code before it and passes with it.
    repo = _repo(
        tmp_path, test="from calc import add\n\n\ndef test_zero():\n    assert add(0, 0) == 0\n"
    )
    with_test = (
        "from calc import add\n\n\ndef test_zero():\n    assert add(0, 0) == 0\n\n\n"
        "def test_add():\n    assert add(2, 3) == 5\n"
    )

    report = _verify(
        repo,
        tmp_path,
        patch_text=_patch(repo, {"src/calc/__init__.py": FIXED, "tests/test_calc.py": with_test}),
    )

    assert report["status"] == change_verifier.VERIFIED, report["reasons"]
    proof = report["tests"]["proof"]  # type: ignore[index]
    assert proof["files"] == ["tests/test_calc.py"]
    assert proof["proving"] == ["tests.test_calc::test_add"]
    assert proof["not_proving"] == ["tests.test_calc::test_zero"]
    summary = change_verifier.render_summary(report)
    assert (
        "**Proof:** 1 of the 2 passing test(s) in the changed test files fail on the code before"
        in summary
    )
    assert (tmp_path / "out" / "tests-proof.xml").is_file()
    statement = json.loads(
        (tmp_path / "out" / "change-verification.intoto.json").read_text(encoding="utf-8")
    )
    assert statement["predicate"]["tests"]["proving"] == 1


def test_a_test_for_a_new_function_proves_it_even_though_it_cannot_import_before(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path, source=FIXED)
    feature = FIXED + "\n\ndef double(x):\n    return 2 * x\n"
    (repo / "tests" / "test_double.py").write_text(
        "from calc import double\n\n\ndef test_double():\n    assert double(4) == 8\n",
        encoding="utf-8",
    )
    _git(repo, "add", "tests/test_double.py")
    patch = _patch(repo, {"src/calc/__init__.py": feature}) + _git(repo, "diff", "--cached")
    _git(repo, "reset", "-q", "--hard")

    report = _verify(repo, tmp_path, patch_text=patch)

    assert report["status"] == change_verifier.VERIFIED, report["reasons"]
    assert report["tests"]["proof"]["proving"] == ["tests.test_double::test_double"]  # type: ignore[index]


def test_tests_that_pass_either_way_are_noted_not_blocked(tmp_path: Path) -> None:
    # A refactor: the new test passes before and after, which is right for a refactor.
    repo = _repo(tmp_path, source=FIXED)
    refactor = "def add(a, b):\n    total = a + b\n    return total\n"
    more = TEST + "\n\ndef test_negative():\n    assert add(-1, -1) == -2\n"

    report = _verify(
        repo,
        tmp_path,
        patch_text=_patch(repo, {"src/calc/__init__.py": refactor, "tests/test_calc.py": more}),
    )

    assert report["status"] == change_verifier.VERIFIED, report["reasons"]
    [note] = [f for f in report["findings"] if f["code"] == "tests_do_not_prove_the_change"]  # type: ignore[attr-defined]
    assert note["blocking"] is False
    assert "tests.test_calc::test_negative" in note["items"]
    assert (
        "none of the 3 passing test(s) in the changed test files"
        in change_verifier.render_summary(report)
    )


def test_assertions_moved_into_a_helper_still_count() -> None:
    # #2420 moved each review test's checks into `_review()`; that is not a weaker test.
    before = "def test_a():\n    run = go()\n    assert run.ok\n    assert run.out\n"
    after = (
        "def _checked():\n    run = go()\n    assert run.ok\n    assert run.out\n    return run\n\n"
        "def _loop():\n    return _loop()\n\n"
        "def test_a():\n    _checked()\n    _loop()\n"
    )

    assert change_verifier.test_facts(before)["test_a"]["assertions"] == 2
    assert change_verifier.test_facts(after)["test_a"]["assertions"] == 2


def test_test_facts_counts_assertions_and_skips() -> None:
    source = (
        "import pytest\n"
        "pytestmark = pytest.mark.xfail\n"
        "def test_a():\n    assert 1 == 1\n    assert True\n"
        "class TestB:\n"
        "    @pytest.mark.skipif(True, reason='x')\n"
        "    def test_c(self):\n        self.assertEqual(1, 1)\n        pytest.skip('no')\n"
        "def helper():\n    assert False\n"
    )

    facts = change_verifier.test_facts(source)

    assert facts == {
        "test_a": {"assertions": 1, "skips": 1},
        "TestB.test_c": {"assertions": 1, "skips": 3},
    }


def test_a_pytest_config_change_needs_review(tmp_path: Path) -> None:
    repo = _repo(tmp_path, source=FIXED)
    pyproject = (repo / "pyproject.toml").read_text(encoding="utf-8")
    pyproject += '\n[tool.pytest.ini_options]\naddopts = "-k zero"\n'

    report = _verify(repo, tmp_path, patch_text=_patch(repo, {"pyproject.toml": pyproject}))

    assert report["status"] == change_verifier.REVIEW
    codes = [finding["code"] for finding in report["findings"]]  # type: ignore[attr-defined]
    assert "test_config_changed" in codes
    # `-k zero` stops test_add from running: the comparison sees that too.
    assert report["tests"]["comparison"]["missing"] == ["tests.test_calc::test_add"]  # type: ignore[index]


def test_junit_id_matches_the_ids_pytest_reports() -> None:
    assert change_verifier.junit_id("tests/test_x.py::test_a") == "tests.test_x::test_a"
    assert (
        change_verifier.junit_id("tests/test_x.py::TestA::test_b") == "tests.test_x.TestA::test_b"
    )
    # Parameters keep their own `::` and dots.
    assert (
        change_verifier.junit_id("tests/sub/test_x.py::test_c[a::b-1.5]")
        == "tests.sub.test_x::test_c[a::b-1.5]"
    )


def test_collection_errors_are_read_from_pytest_s_summary() -> None:
    output = (
        "tests/test_ok.py::test_ok\n\n"
        "=========================== short test summary info ============================\n"
        "ERROR tests/sub/test_b.py\n"
        "ERROR tests/test_a.py - ModuleNotFoundError: No module named 'ruamel'\n"
        "ERROR tests/test_ok.py::test_ok - RuntimeError: a test's error, not a module's\n"
        "!!!!!!!!!!!!!!!!!!! Interrupted: 2 errors during collection !!!!!!!!!!!!!!!!!!!!\n"
    )

    assert change_verifier.collection_errors(output) == ["tests/sub/test_b.py", "tests/test_a.py"]
    # The id pytest's JUnit report gives a module it could not collect.
    assert change_verifier.junit_id("tests/sub/test_b.py") == "::tests.sub.test_b"


def test_missing_modules_are_named_from_the_failures() -> None:
    failures = {
        "::tests.test_a": "ModuleNotFoundError: No module named 'ruamel.yaml'",
        "t::b": "ModuleNotFoundError: No module named 'msgpack'",
        "t::c": "assert 1 == 2",
    }

    assert change_verifier.missing_modules(failures, ["::tests.test_a", "t::c"]) == ["ruamel"]
    assert change_verifier.missing_modules(failures, ["t::c", "t::unknown"]) == []


def test_a_test_module_that_never_imports_stops_no_other_test(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    # An optional dependency this machine lacks, before the change and after it.
    (repo / "tests" / "test_extra.py").write_text(
        "import a_dependency_not_installed\n\n\ndef test_it():\n    pass\n", encoding="utf-8"
    )
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "an optional dependency")
    diff = _patch(repo, {"src/calc/__init__.py": FIXED})

    report = _verify(repo, tmp_path, patch_text=diff)

    # The other module's tests ran, so the fix is seen working; the module that never imports
    # failed before too, so the change is not blamed for it.
    assert report["tests"]["head"]["counts"] == {"passed": 2, "failed": 1, "skipped": 0}  # type: ignore[index]
    assert report["tests"]["comparison"]["still_failing"] == ["::tests.test_extra"]  # type: ignore[index]
    assert report["status"] == "REVIEW"
    assert report["reasons"] == [
        "1 test(s) failed before and still fail"
        " (a_dependency_not_installed not installed where they ran)"
    ]


def test_helper_pythons_import_nothing_from_the_clone(tmp_path: Path) -> None:
    # A module of the project's named like the tool, in the folder the command runs in.
    (tmp_path / "coverage.py").write_text("raise SystemExit('the clone, not coverage')\n")
    (tmp_path / "json.py").write_text("raise SystemExit('the clone, not json')\n")

    module = subprocess.run(
        change_verifier._python_module(sys.executable, "coverage", "--version"),
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    code = subprocess.run(
        change_verifier._python_code(sys.executable, "import json; print(sys.argv[1:])", "a"),
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    if change_verifier._importable(sys.executable, "coverage"):
        assert module.returncode == 0 and "Coverage.py" in module.stdout, module.stderr
    assert (code.returncode, code.stdout.strip()) == (0, "['a']"), code.stderr


@pytest.mark.skipif(
    sys.platform == "win32" or not site.ENABLE_USER_SITE,
    reason="needs an interpreter that uses a user site under HOME",
)
def test_packages_installed_with_pip_install_user_are_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    user_site = subprocess.run(
        [sys.executable, "-c", "import site; print(site.getusersitepackages())"],
        env={**os.environ, "HOME": str(home)},
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    Path(user_site).mkdir(parents=True)
    (Path(user_site) / "installed_for_the_user.py").write_text("", encoding="utf-8")

    assert "PYTHONNOUSERSITE" not in change_verifier._execution_environment()
    assert change_verifier._importable(sys.executable, "installed_for_the_user")


def test_a_targeted_base_run_agrees_with_a_full_one(tmp_path: Path) -> None:
    # One test breaks, one is deleted, one becomes skipped, one was already failing.
    test = (
        "import pytest\nfrom calc import add\n\n\n"
        "def test_add():\n    assert add(2, 3) == 5\n\n\n"
        "def test_zero():\n    assert add(0, 0) == 0\n\n\n"
        "def test_gone():\n    assert add(1, 0) == 1\n\n\n"
        "def test_flaky():\n    assert add(1, 1) == 2\n\n\n"
        "def test_broken():\n    assert False\n"
    )
    repo = _repo(tmp_path, source=FIXED, test=test)
    changed = test.replace("def test_gone():\n    assert add(1, 0) == 1\n\n\n", "").replace(
        "def test_flaky", '@pytest.mark.skip(reason="later")\ndef test_flaky'
    )
    patch = _patch(
        repo,
        {
            "src/calc/__init__.py": "def add(a, b):\n    return a + b + (a == 2)\n",
            "tests/test_calc.py": changed,
        },
    )

    reports = {}
    for mode in ("full", "targeted"):
        reports[mode] = change_verifier.verify_change(
            repo_root=repo,
            out_dir=tmp_path / mode,
            python=sys.executable,
            timeout_seconds=120,
            patch_text=patch,
            base_mode=mode,
        )

    for key in ("regressions", "new_failures", "still_failing", "now_skipped", "missing"):
        assert (
            reports["targeted"]["tests"]["comparison"][key]  # type: ignore[index]
            == reports["full"]["tests"]["comparison"][key]  # type: ignore[index]
        ), key
    comparison = reports["targeted"]["tests"]["comparison"]  # type: ignore[index]
    assert comparison["regressions"] == ["tests.test_calc::test_add"]
    assert comparison["missing"] == ["tests.test_calc::test_gone"]
    assert comparison["now_skipped"] == ["tests.test_calc::test_flaky"]
    assert comparison["still_failing"] == ["tests.test_calc::test_broken"]
    assert reports["targeted"]["status"] == reports["full"]["status"] == change_verifier.FAILED
    base = reports["targeted"]["tests"]["base"]  # type: ignore[index]
    # The base ran only what failed or was skipped on the change, after collecting all five.
    assert (base["mode"], base["collected"], base["rerun"]) == ("targeted", 5, 3)
    assert "5 collected, 3 re-run" in change_verifier.render_summary(reports["targeted"])


def test_a_renamed_test_is_not_a_removed_one(tmp_path: Path) -> None:
    repo = _repo(tmp_path, source=FIXED)
    renamed = TEST.replace("def test_add():", "def test_adds_two_numbers():")

    report = _verify(repo, tmp_path, patch_text=_patch(repo, {"tests/test_calc.py": renamed}))

    assert report["status"] == change_verifier.VERIFIED, report["reasons"]
    [note] = [f for f in report["findings"] if f["code"] == "tests_renamed"]  # type: ignore[attr-defined]
    assert note["blocking"] is False
    assert note["items"] == [
        "tests/test_calc.py::test_add -> tests/test_calc.py::test_adds_two_numbers"
    ]
    assert report["tests"]["comparison"]["missing"] == []  # type: ignore[index]


def test_a_rename_that_also_weakens_the_test_is_still_caught(tmp_path: Path) -> None:
    repo = _repo(tmp_path, source=FIXED)
    weakened = TEST.replace(
        "def test_add():\n    assert add(2, 3) == 5", "def test_adds():\n    assert add(2, 3)"
    )

    report = _verify(repo, tmp_path, patch_text=_patch(repo, {"tests/test_calc.py": weakened}))

    assert report["status"] == change_verifier.REVIEW
    codes = [f["code"] for f in report["findings"]]  # type: ignore[attr-defined]
    assert "tests_removed" in codes and "tests_renamed" not in codes
    assert report["tests"]["comparison"]["missing"] == ["tests.test_calc::test_add"]  # type: ignore[index]


def test_a_test_moved_to_another_file_counts_as_renamed(tmp_path: Path) -> None:
    repo = _repo(tmp_path, source=FIXED)
    kept = TEST.split("\n\n\ndef test_zero")[0] + "\n"
    (repo / "tests" / "test_zero.py").write_text(
        "from calc import add\n\n\ndef test_zero():\n    assert add(0, 0) == 0\n", encoding="utf-8"
    )
    _git(repo, "add", "tests/test_zero.py")
    patch = _patch(repo, {"tests/test_calc.py": kept}) + _git(repo, "diff", "--cached")
    _git(repo, "reset", "-q", "--hard")

    report = _verify(repo, tmp_path, patch_text=patch)

    assert report["status"] == change_verifier.VERIFIED, report["reasons"]
    [note] = [f for f in report["findings"] if f["code"] == "tests_renamed"]  # type: ignore[attr-defined]
    assert note["items"] == ["tests/test_calc.py::test_zero -> tests/test_zero.py::test_zero"]


def test_fingerprints_ignore_line_numbers_but_not_decorators() -> None:
    plain = "def test_a():\n    assert f() == 1\n"
    shifted = "\n\n\ndef test_b():\n    assert f() == 1\n"
    skipped = "import pytest\n@pytest.mark.skip\ndef test_c():\n    assert f() == 1\n"

    a = change_verifier.test_fingerprints(plain)["test_a"]
    assert change_verifier.test_fingerprints(shifted)["test_b"] == a
    assert change_verifier.test_fingerprints(skipped)["test_c"] != a


def test_a_pull_request_is_verified_from_where_it_left_the_default_branch(
    tmp_path: Path,
) -> None:
    # A remote with main and a pull request branched before main moved on.
    origin = tmp_path / "origin"
    seed = _repo(tmp_path / "seed", source=FIXED)
    _git(tmp_path, "clone", "-q", "--bare", str(seed), str(origin))
    work = tmp_path / "work"
    _git(tmp_path, "clone", "-q", str(origin), str(work))
    branch_point = _git(work, "rev-parse", "HEAD").strip()
    (work / "tests" / "test_calc.py").write_text(
        TEST + "\n\ndef test_two():\n    assert add(1, 1) == 2\n"
    )
    _git(work, "commit", "-qam", "pr")
    pr_head = _git(work, "rev-parse", "HEAD").strip()
    _git(work, "push", "-q", "origin", f"{pr_head}:refs/pull/7/head")
    _git(work, "checkout", "-q", branch_point)
    (work / "NOTES.md").write_text("main moved on\n")
    _git(work, "add", "-A")
    _git(work, "commit", "-qm", "main moves on")
    _git(work, "push", "-q", "origin", "HEAD:refs/heads/main")
    # A reviewer's clone, from before both.
    reviewer = tmp_path / "reviewer"
    _git(tmp_path, "clone", "-q", str(origin), str(reviewer))
    _git(reviewer, "reset", "-q", "--hard", branch_point)

    base, head = change_verifier.pull_request_change(reviewer, 7)

    assert (base, head) == (branch_point, pr_head)
    assert _git(reviewer, "rev-parse", "refs/sdetkit/pull/7").strip() == pr_head
    # The reviewer's checkout is as it was.
    assert _git(reviewer, "rev-parse", "HEAD").strip() == branch_point
    assert not _git(reviewer, "status", "--porcelain")

    out = tmp_path / "out"
    code = change_verifier.main(
        [
            "--pr",
            "7",
            "--repo-root",
            str(reviewer),
            "--out-dir",
            str(out),
            "--python",
            sys.executable,
        ]
    )
    report = json.loads((out / "change-verification.json").read_text(encoding="utf-8"))
    assert code == 0, report["reasons"]
    # Only the pull request's own change: not main's NOTES.md.
    assert [item["path"] for item in report["change"]["changed"]] == ["tests/test_calc.py"]
    with pytest.raises(change_verifier.ChangeError, match="pull request number"):
        change_verifier.pull_request_change(reviewer, 0)


def test_pull_request_numbers_default_branches_and_a_given_base(tmp_path: Path) -> None:
    # A remote whose default branch has a slash in its name, and pull request #1.
    seed = _repo(tmp_path / "seed", source=FIXED)
    _git(seed, "branch", "-m", "team/main")
    origin = tmp_path / "origin"
    _git(tmp_path, "clone", "-q", "--bare", str(seed), str(origin))
    work = tmp_path / "work"
    _git(tmp_path, "clone", "-q", str(origin), str(work))
    branch_point = _git(work, "rev-parse", "HEAD").strip()
    (work / "tests" / "test_calc.py").write_text(
        TEST + "\n\ndef test_two():\n    assert add(1, 1) == 2\n"
    )
    _git(work, "commit", "-qam", "pr")
    pr_head = _git(work, "rev-parse", "HEAD").strip()
    _git(work, "push", "-q", "origin", f"{pr_head}:refs/pull/1/head")
    reviewer = tmp_path / "reviewer"
    _git(tmp_path, "clone", "-q", str(origin), str(reviewer))
    assert _git(reviewer, "symbolic-ref", "--short", "refs/remotes/origin/HEAD").strip() == (
        "origin/team/main"
    )

    # The whole branch name, slash included, and number 1.
    assert change_verifier.pull_request_change(reviewer, 1) == (branch_point, pr_head)

    # A clone without origin/HEAD falls back to origin/main, which this remote lacks.
    _git(reviewer, "remote", "set-head", "origin", "-d")
    with pytest.raises(change_verifier.ChangeError, match="main"):
        change_verifier.pull_request_change(reviewer, 1)

    # A --base given with --pr is used as it is.
    _git(reviewer, "remote", "set-head", "origin", "team/main")
    out = tmp_path / "out"
    change_verifier.main(
        [
            "--pr",
            "1",
            "--base",
            pr_head,
            "--repo-root",
            str(reviewer),
            "--out-dir",
            str(out),
            "--python",
            sys.executable,
            "--base-run",
            "none",
        ]
    )
    report = json.loads((out / "change-verification.json").read_text(encoding="utf-8"))
    assert report["change"]["base_sha"] == pr_head
    assert report["change"]["changed"] == []


@pytest.mark.parametrize(
    ("name", "text"),
    [
        ("setup.py", "from setuptools import setup\nsetup(package_dir={'': 'lib'})\n"),
        ("setup.cfg", "[options]\npackage_dir =\n    =lib\n"),
        ("pyproject.toml", '[tool.setuptools.package-dir]\n"" = "lib"\n'),
    ],
)
def test_source_roots_follow_setuptools_package_dir(tmp_path: Path, name: str, text: str) -> None:
    (tmp_path / "lib").mkdir()
    (tmp_path / "src").mkdir()
    (tmp_path / name).write_text(text, encoding="utf-8")

    # The declared root wins over a src/ folder that is something else.
    assert change_verifier.source_roots(tmp_path) == [tmp_path / "lib"]


def test_source_roots_fall_back_to_src_then_nothing(tmp_path: Path) -> None:
    assert change_verifier.source_roots(tmp_path) == []
    (tmp_path / "src").mkdir()
    # A declared root that does not exist is not one, so src/ still is.
    (tmp_path / "setup.py").write_text("setup(package_dir={'': 'lib'})\n", encoding="utf-8")
    assert change_verifier.source_roots(tmp_path) == [tmp_path / "src"]
    # Packages declared at the repository root leave src/ alone; the root is on the path anyway.
    (tmp_path / "setup.cfg").write_text("[options]\npackage_dir =\n    =.\n", encoding="utf-8")
    assert change_verifier.source_roots(tmp_path) == []


def test_a_package_under_lib_is_tested_from_the_clone(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "lib" / "calc").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "lib" / "calc" / "__init__.py").write_text(BUGGY, encoding="utf-8")
    (repo / "tests" / "test_calc.py").write_text(TEST, encoding="utf-8")
    (repo / "setup.py").write_text(
        "from setuptools import setup\nsetup(name='calc', package_dir={'': 'lib'}, packages=['calc'])\n",
        encoding="utf-8",
    )
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")

    report = _verify(
        repo, tmp_path, patch_text=_patch(repo, {"lib/calc/__init__.py": FIXED}), base_mode="full"
    )

    assert report["status"] == change_verifier.VERIFIED, report["reasons"]
    assert report["tests"]["comparison"]["fixed"] == ["tests.test_calc::test_add"]  # type: ignore[index]
    assert report["changed_coverage"]["percent"] == 100.0  # type: ignore[index]


def test_a_lib_package_imported_from_elsewhere_is_flagged(tmp_path: Path) -> None:
    (tmp_path / "setup.py").write_text("setup(package_dir={'': 'lib'})\n", encoding="utf-8")
    (tmp_path / "lib" / "json").mkdir(parents=True)
    (tmp_path / "lib" / "calc").mkdir()
    (tmp_path / "lib" / "calc" / "__init__.py").write_text("", encoding="utf-8")
    change = {"changed": [{"path": "lib/json/decoder.py"}, {"path": "lib/calc/__init__.py"}]}

    # lib/json has no __init__.py, so the interpreter's own json wins; lib/calc is the clone's.
    elsewhere = change_verifier._imports_the_clone(tmp_path, sys.executable, change)

    assert [entry.split(" -> ")[0] for entry in elsewhere] == ["json"]


# --- several projects in one repository ---------------------------------------------------

SLUG = 'export function slug(s) {\n  return s.trim().toLowerCase().replace(/ +/g, "-");\n}\n'
SLUG_TEST = (
    'import test from "node:test";\nimport assert from "node:assert/strict";\n'
    'import { slug } from "../slug.js";\n\n'
    'test("slug", () => {\n  assert.equal(slug(" Hello World "), "hello-world");\n});\n'
)


def _two_projects(tmp_path: Path) -> Path:
    """A Python package at the root and a web app with its own tests in web/."""

    repo = _repo(tmp_path, FIXED)
    (repo / "web" / "test").mkdir(parents=True)
    (repo / "web" / "package.json").write_text(
        '{"name": "web", "private": true, "type": "module", "scripts": {"test": "node --test"}}\n',
        encoding="utf-8",
    )
    (repo / "web" / "slug.js").write_text(SLUG, encoding="utf-8")
    (repo / "web" / "test" / "slug.test.js").write_text(SLUG_TEST, encoding="utf-8")
    (repo / "tools").mkdir()
    (repo / "tools" / "build.js").write_text("console.log(1);\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "web")
    return repo


def test_changed_files_belong_to_the_nearest_project_of_their_language(tmp_path: Path) -> None:
    repo = _two_projects(tmp_path)
    (repo / "svc").mkdir()
    (repo / "svc" / "go.mod").write_text("module example.com/svc\n", encoding="utf-8")

    assert change_verifier.project_of(repo, "web/slug.js") == ("web", "javascript")
    assert change_verifier.project_of(repo, "web/test/slug.test.js") == ("web", "javascript")
    assert change_verifier.project_of(repo, "svc/a/b.go") == ("svc", "go")
    assert change_verifier.project_of(repo, "src/calc/__init__.py") == ("", "python")
    # A Python file under web/ is still the root's: web/ has no Python project file.
    assert change_verifier.project_of(repo, "web/scripts/x.py") == ("", "python")
    assert change_verifier.project_of(repo, "tools/build.js") == ("", "javascript")
    assert change_verifier.project_of(repo, "README.md") == ("", "")
    assert change_verifier.project_of(repo, "web/node_modules/x/i.js") == ("", "")

    change = {
        "changed": [
            {"path": path, "status": "M"}
            for path in ("src/calc/__init__.py", "web/slug.js", "tools/build.js", "README.md")
        ]
    }
    assert change_verifier.untested_projects(repo, change, "pytest", "") == (
        ["web (node): web/slug.js"],
        ["tools/build.js"],
        [],
    )
    assert change_verifier.untested_projects(repo, change, "node", "web") == (
        [". (pytest): src/calc/__init__.py"],
        ["tools/build.js"],
        [],
    )


def test_a_change_is_seen_from_its_project_with_the_project_s_paths() -> None:
    diff = (
        "diff --git a/web/slug.js b/web/slug.js\n--- a/web/slug.js\n+++ b/web/slug.js\n"
        "@@ -1 +1 @@\n-a\n+b\n"
        "diff --git a/src/x.py b/src/x.py\n--- a/src/x.py\n+++ b/src/x.py\n@@ -1 +1 @@\n-a\n+b\n"
    )
    change = {
        "diff": diff,
        "changed": [
            {"path": "web/slug.js", "status": "M"},
            {"path": "web/new.js", "old_path": "web/old.js", "status": "R"},
            {"path": "src/x.py", "status": "M"},
        ],
        "head_sha": "h",
    }

    seen = change_verifier.within(change, "web")

    assert seen["diff"] == (
        "diff --git a/slug.js b/slug.js\n--- a/slug.js\n+++ b/slug.js\n@@ -1 +1 @@\n-a\n+b\n"
    )
    assert seen["changed"] == [
        {"path": "slug.js", "status": "M"},
        {"path": "new.js", "old_path": "old.js", "status": "R"},
    ]
    assert seen["head_sha"] == "h"
    assert change_verifier.within(change, "") == change


@pytest.mark.skipif(shutil.which("node") is None, reason="needs node")
def test_a_change_to_another_project_is_not_verified_and_project_runs_its_tests(
    tmp_path: Path,
) -> None:
    repo = _two_projects(tmp_path)
    # A bug in the web app: its own test fails, the root's Python tests cannot tell.
    diff = _patch(repo, {"web/slug.js": SLUG.replace(".toLowerCase()", "")})

    root = _verify(repo, tmp_path / "root", patch_text=diff, runner="pytest")
    web = _verify(repo, tmp_path / "web", patch_text=diff, project="web")

    assert root["status"] == "REVIEW"
    assert root["tests"]["runner"] == "pytest"  # type: ignore[index]
    assert root["reasons"] == [
        "changed_projects_not_tested: The change touches code of other projects, whose tests "
        "did not run here: verify each with --project FOLDER."
    ]
    finding = next(f for f in root["findings"] if f["code"] == "changed_projects_not_tested")  # type: ignore[union-attr]
    assert finding["items"] == ["web (node): web/slug.js"]

    assert web["status"] == "FAILED"
    assert web["project"] == "web"
    assert web["tests"]["runner"] == "node"  # type: ignore[index]
    assert web["reasons"] == ["1 test(s) fail on the change: test/slug.test.js::slug"]
    # The report's paths are the repository's; the patch is the whole change.
    coverage = web["changed_coverage"]
    assert [item["path"] for item in coverage["files"]] == ["web/slug.js"]  # type: ignore[index]
    assert [item["path"] for item in web["change"]["changed"]] == ["web/slug.js"]  # type: ignore[index]
    assert (tmp_path / "web" / "out" / "change.patch").read_text(encoding="utf-8") == diff


def test_a_project_must_be_a_folder_of_the_repository(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    diff = _patch(repo, {"src/calc/__init__.py": FIXED})

    for project in ("nope", "../elsewhere"):
        with pytest.raises(change_verifier.ChangeError, match="not a folder of the repository"):
            _verify(repo, tmp_path, patch_text=diff, project=project)


def test_the_projects_a_change_touches_are_planned_from_git(tmp_path: Path) -> None:
    repo = _two_projects(tmp_path)
    both = _patch(
        repo,
        {
            "src/calc/__init__.py": FIXED + "\n",
            "web/slug.js": SLUG + "\n",
            "tools/build.js": "console.log(2);\n",
            "README.md": "x\n",
        },
    )

    assert change_verifier.plan_projects(repo, "HEAD", patch_text=both) == [
        ("", "python", "pytest"),
        ("web", "javascript", "node"),
    ]
    # A commit as the head reads the same; Python alone is the root's one project.
    (repo / "src" / "calc" / "__init__.py").write_text(FIXED + "\n", encoding="utf-8")
    _git(repo, "commit", "-qam", "python only")
    assert change_verifier.plan_projects(repo, "HEAD~1", head="HEAD") == [("", "python", "pytest")]


@pytest.mark.skipif(shutil.which("node") is None, reason="needs node")
def test_each_project_a_change_touches_is_verified_in_one_report(tmp_path: Path) -> None:
    repo = _two_projects(tmp_path)
    # The Python side is fine, the web app's is broken.
    diff = _patch(
        repo,
        {
            "src/calc/__init__.py": "def add(a, b):\n    total = a + b\n    return total\n",
            "web/slug.js": SLUG.replace(".toLowerCase()", ""),
        },
    )

    report = _verify(repo, tmp_path, patch_text=diff)

    out = tmp_path / "out"
    assert report["status"] == "FAILED"
    assert report["reasons"] == [
        "web (node): 1 test(s) fail on the change: test/slug.test.js::slug"
    ]
    assert [(item["project"], item["runner"], item["status"]) for item in report["projects"]] == [  # type: ignore[union-attr]
        (".", "pytest", "VERIFIED"),
        ("web", "node", "FAILED"),
    ]
    tests = report["tests"]
    assert tests["runner"] == "pytest, node"  # type: ignore[index]
    assert tests["head"]["counts"] == {"passed": 2, "failed": 1, "skipped": 0}  # type: ignore[index]
    assert list(tests["failures"]) == ["web (node): test/slug.test.js::slug"]  # type: ignore[index]
    # Neither project's run flags the other as untested: both ran.
    assert "changed_projects_not_tested" not in [f["code"] for f in report["findings"]]  # type: ignore[union-attr]
    coverage = report["changed_coverage"]
    assert [item["path"] for item in coverage["files"]] == ["src/calc/__init__.py", "web/slug.js"]  # type: ignore[index]
    # Each project's own report, and one patch, summary and attestation for the change.
    for name in ("root", "web"):
        assert (out / "projects" / name / "change-verification.json").is_file()
    assert (out / "change.patch").read_text(encoding="utf-8") == diff
    summary = change_verifier.render_summary(report)
    assert "| `web` | node | :x: FAILED | 0 passed, 1 failed, 0 skipped |" in summary
    assert "| `.` | pytest | :white_check_mark: VERIFIED |" in summary
    predicate = json.loads((out / "change-verification.predicate.json").read_text())
    assert predicate["status"] == "FAILED"
    assert predicate["projects"] == [
        {"project": ".", "runner": "pytest", "status": "VERIFIED"},
        {"project": "web", "runner": "node", "status": "FAILED"},
    ]
    statement = json.loads((out / "change-verification.intoto.json").read_text())
    evidence = statement["predicate"]["evidence"]
    assert {
        "projects/root/change-verification.json",
        "projects/web/change-verification.json",
    } <= set(evidence)


def test_a_change_to_the_root_project_alone_is_one_run(tmp_path: Path) -> None:
    repo = _two_projects(tmp_path)
    diff = _patch(repo, {"src/calc/__init__.py": FIXED + "\n"})

    report = _verify(repo, tmp_path, patch_text=diff)

    assert report["status"] == "VERIFIED", report["reasons"]
    assert report["projects"] == []
    assert not (tmp_path / "out" / "projects").exists()


def test_code_of_a_language_without_tests_here_is_never_verified(tmp_path: Path) -> None:
    repo = _two_projects(tmp_path)
    # A service with a package.json whose tests are npm's placeholder, and a C# service.
    (repo / "svc").mkdir()
    (repo / "svc" / "package.json").write_text(
        '{"scripts": {"test": "echo \\"Error: no test specified\\" && exit 1"}}\n',
        encoding="utf-8",
    )
    (repo / "svc" / "server.js").write_text("const a = 1;\n", encoding="utf-8")
    (repo / "cart").mkdir()
    (repo / "cart" / "Cart.cs").write_text("class Cart {}\n", encoding="utf-8")
    (repo / "web" / "node_modules" / "x").mkdir(parents=True)
    change = {
        "changed": [
            {"path": path, "status": "M"}
            for path in ("svc/server.js", "cart/Cart.cs", "web/node_modules/x/a.cs")
        ]
    }

    assert change_verifier.untested_projects(repo, change, "pytest", "") == (
        [],
        ["svc/server.js"],
        ["cart/Cart.cs (C#)"],
    )

    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "services")
    diff = _patch(
        repo,
        {"src/calc/__init__.py": FIXED + "\n", "cart/Cart.cs": "class Cart { int n; }\n"},
    )
    report = _verify(repo, tmp_path, patch_text=diff)

    # The Python tests pass, but nothing checked the C#: it needs review.
    assert report["status"] == "REVIEW"
    assert report["reasons"] == [
        "changed_code_not_supported: The change touches code in a language verify change runs "
        "no tests for, so nothing here checked it."
    ]


def test_a_run_that_collects_no_tests_says_so() -> None:
    head = {
        "runner": "pytest",
        "pytest_missing": False,
        "timed_out": False,
        "exit_code": 5,
        "outcomes": {},
        "output_tail": "no tests ran in 0.01s\n  warnings.warn(PytestDeprecationWarning(X))\n",
    }
    comparison = change_verifier.compare_runs(None, head)

    status, reasons = change_verifier.decide(
        head_run=head, base_run=None, comparison=comparison, findings=[], not_imported=[]
    )

    assert (status, reasons) == (
        "NOT_RUN",
        ["no test ran (pytest exit code 5: pytest collected no tests)"],
    )
    head["exit_code"] = 4
    assert change_verifier.decide(
        head_run=head, base_run=None, comparison=comparison, findings=[], not_imported=[]
    )[1] == ["no test ran (pytest exit code 4: no tests ran in 0.01s)"]
