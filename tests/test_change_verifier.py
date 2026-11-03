"""`sdetkit verify change`: run a change's tests in a clone and catch weakened tests."""

from __future__ import annotations

import hashlib
import json
import shutil
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

    report = _verify(repo, tmp_path, patch_text=_patch(repo, {"src/calc/__init__.py": FIXED}))

    assert report["status"] == change_verifier.VERIFIED, report["reasons"]
    comparison = report["tests"]["comparison"]  # type: ignore[index]
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
