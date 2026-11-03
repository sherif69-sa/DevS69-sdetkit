"""`sdetkit verify change` on Go tests: `go test -json`."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from sdetkit import change_verifier, go_tests

needs_go = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("go") is None, reason="needs git and go"
)

SOURCE = """\
package cart

import (
\t"fmt"
\t"testing"

\t"github.com/stretchr/testify/require"
)

func TestAdd(t *testing.T) {
\tif got := Add(nil, "a"); len(got) != 1 {
\t\tt.Errorf("got %v", got) // t.Fatal("in a comment") is not an assertion
\t}
\tcheckTotal(t, 2)
}

func TestSkipped(t *testing.T) {
\tt.Skip("needs a database")
\trequire.Equal(t, 1, Count())
}

func TestNothing(t *testing.T) {
\t_ = fmt.Errorf("an error value, not an assertion: %s", "}")
\trequire.True(t, true)
}

func TestTable(t *testing.T) {
\tfor _, name := range []string{"a", "b"} {
\t\tt.Run(name, func(t *testing.T) {
\t\t\trequire.NotEmpty(t, name)
\t\t})
\t}
}

func checkTotal(t *testing.T, want int) {
\tt.Helper()
\tif Total() != want {
\t\tt.Fatalf("total %d", Total())
\t}
}

func Testify(t *testing.T) {}
"""


def test_the_scanner_counts_assertions_with_helpers_and_skips() -> None:
    assert go_tests.go_test_facts(SOURCE) == {
        "TestAdd": {"assertions": 2, "skips": 0},
        "TestSkipped": {"assertions": 1, "skips": 1},
        "TestNothing": {"assertions": 0, "skips": 0},
        "TestTable": {"assertions": 1, "skips": 0},
    }


def test_a_renamed_go_test_keeps_its_fingerprint() -> None:
    before = go_tests.go_test_fingerprints(
        "func TestOld(t *testing.T) {\n\trequire.Equal(t, 1, F())\n}\n"
    )
    after = go_tests.go_test_fingerprints(
        "func TestNew(t *testing.T) { require.Equal(t, 1, F()) }\n"
    )

    assert before["TestOld"] == after["TestNew"]


def test_go_test_json_reads_to_package_ids() -> None:
    events = [
        {"Action": "run", "Package": "example.com/m/cart", "Test": "TestAdd"},
        {"Action": "pass", "Package": "example.com/m/cart", "Test": "TestAdd"},
        {"Action": "fail", "Package": "example.com/m/cart", "Test": "TestTable/b"},
        {"Action": "skip", "Package": "example.com/m", "Test": "TestRoot"},
        {"Action": "fail", "Package": "example.com/m/cart"},
        {"Action": "fail", "Package": "example.com/m/broken", "FailedBuild": "x"},
    ]

    outcomes = go_tests.read_go_json("\n".join(map(json.dumps, events)), "example.com/m")

    assert outcomes == {
        "cart::TestAdd": "passed",
        "cart::TestTable/b": "failed",
        ".::TestRoot": "skipped",
        "::broken": "failed",
    }


def test_go_test_json_keeps_what_a_failing_test_printed() -> None:
    events = [
        {
            "Action": "output",
            "Package": "example.com/m/cart",
            "Test": "TestAdd",
            "Output": "=== RUN   TestAdd\n",
        },
        {
            "Action": "output",
            "Package": "example.com/m/cart",
            "Test": "TestAdd",
            "Output": "    cart_test.go:7: got 1\n",
        },
        {
            "Action": "output",
            "Package": "example.com/m/cart",
            "Test": "TestAdd",
            "Output": "--- FAIL: TestAdd (0.00s)\n",
        },
        {"Action": "fail", "Package": "example.com/m/cart", "Test": "TestAdd"},
        {"Action": "output", "Package": "example.com/m/cart", "Test": "TestOk", "Output": "ok\n"},
        {"Action": "pass", "Package": "example.com/m/cart", "Test": "TestOk"},
        {
            "ImportPath": "example.com/m/broken [example.com/m/broken.test]",
            "Action": "build-output",
            "Output": "# example.com/m/broken\n",
        },
        {
            "ImportPath": "example.com/m/broken [example.com/m/broken.test]",
            "Action": "build-output",
            "Output": "broken/b.go:3:9: undefined: x\n",
        },
        {
            "Action": "fail",
            "Package": "example.com/m/broken",
            "FailedBuild": "example.com/m/broken [example.com/m/broken.test]",
        },
    ]

    failures = go_tests.read_go_failures("\n".join(map(json.dumps, events)), "example.com/m")

    assert failures["cart::TestAdd"] == "cart_test.go:7: got 1"
    assert failures["::broken"] == "# example.com/m/broken\nbroken/b.go:3:9: undefined: x"
    assert "cart::TestOk" not in failures


def test_go_package_arguments_and_runner_choice(tmp_path: Path) -> None:
    assert go_tests.go_package_args(["cart/cart_test.go", "x_test.go", "cart/b_test.go"]) == [
        "./",
        "./cart",
    ]
    (tmp_path / "go.mod").write_text("module example.com/m\n", encoding="utf-8")

    assert change_verifier.resolve_runner(tmp_path) == "go"


# --- end to end with go test ------------------------------------------------------------

BUGGY = "package calc\n\nfunc Add(a, b int) int { return a - b }\n"
FIXED = "package calc\n\nfunc Add(a, b int) int { return a + b }\n"
TEST = """\
package calc

import "testing"

func TestAddTwo(t *testing.T) {
\tif Add(2, 3) != 5 {
\t\tt.Fatalf("Add(2, 3) = %d", Add(2, 3))
\t}
}

func TestAddZero(t *testing.T) {
\tif Add(0, 0) != 0 {
\t\tt.Fatal("Add(0, 0) is not 0")
\t}
}
"""
ZERO = """\
func TestAddZero(t *testing.T) {
\tif Add(0, 0) != 0 {
\t\tt.Fatal("Add(0, 0) is not 0")
\t}
}
"""


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _repo(tmp_path: Path, source: str = BUGGY) -> Path:
    repo = tmp_path / "repo"
    (repo / "calc").mkdir(parents=True)
    (repo / "go.mod").write_text("module example.com/calc\n\ngo 1.21\n", encoding="utf-8")
    (repo / "calc" / "calc.go").write_text(source, encoding="utf-8")
    (repo / "calc" / "calc_test.go").write_text(TEST, encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    return repo


def _verify(repo: Path, tmp_path: Path, files: dict[str, str]) -> dict[str, object]:
    for path, text in files.items():
        (repo / path).write_text(text, encoding="utf-8")
    _git(repo, "add", "-A")
    diff = _git(repo, "diff", "--cached")
    _git(repo, "reset", "-q", "--hard")
    return change_verifier.verify_change(
        repo_root=repo,
        out_dir=tmp_path / "out",
        python=sys.executable,
        patch_text=diff,
        timeout_seconds=300,
    )


@needs_go
def test_a_go_fix_is_verified_with_the_test_that_proves_it(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    proving = TEST + (
        "\nfunc TestAddNegative(t *testing.T) {\n"
        '\tif Add(-1, -2) != -3 {\n\t\tt.Fatal("Add(-1, -2) is not -3")\n\t}\n}\n'
    )

    report = _verify(repo, tmp_path, {"calc/calc.go": FIXED, "calc/calc_test.go": proving})

    assert report["tests"]["runner"] == "go"
    assert report["status"] == "VERIFIED", report["reasons"]
    assert report["tests"]["comparison"]["fixed"] == ["calc::TestAddTwo"]
    assert report["tests"]["proof"]["proving"] == ["calc::TestAddNegative", "calc::TestAddTwo"]


@needs_go
def test_deleting_or_skipping_a_go_test_is_caught(tmp_path: Path) -> None:
    repo = _repo(tmp_path, source=FIXED)

    removed = _verify(repo, tmp_path / "a", {"calc/calc_test.go": TEST.replace(ZERO, "")})
    skipped = _verify(
        repo,
        tmp_path / "b",
        {"calc/calc_test.go": TEST.replace("\tif Add(0, 0)", '\tt.Skip("later")\n\tif Add(0, 0)')},
    )

    assert removed["status"] == "REVIEW"
    assert "tests_removed" in [finding["code"] for finding in removed["findings"]]
    assert removed["tests"]["comparison"]["missing"] == ["calc::TestAddZero"]
    assert skipped["status"] == "REVIEW"
    assert "skip_added" in [finding["code"] for finding in skipped["findings"]]
    assert skipped["tests"]["comparison"]["now_skipped"] == ["calc::TestAddZero"]


@needs_go
def test_a_go_regression_and_a_build_failure_fail(tmp_path: Path) -> None:
    repo = _repo(tmp_path, source=FIXED)

    regression = _verify(repo, tmp_path / "a", {"calc/calc.go": BUGGY})
    broken = _verify(
        repo, tmp_path / "b", {"calc/calc.go": FIXED + "\nfunc Broken() int { return x }\n"}
    )

    assert regression["status"] == "FAILED"
    assert regression["tests"]["comparison"]["regressions"] == ["calc::TestAddTwo"]
    assert regression["tests"]["failures"] == {"calc::TestAddTwo": "calc_test.go:7: Add(2, 3) = -1"}
    assert broken["status"] == "FAILED", broken["reasons"]
    assert "undefined: x" in broken["tests"]["failures"]["::calc"]


@needs_go
def test_a_renamed_go_test_is_not_a_removed_one(tmp_path: Path) -> None:
    repo = _repo(tmp_path, source=FIXED)

    report = _verify(
        repo, tmp_path, {"calc/calc_test.go": TEST.replace("TestAddZero", "TestAddNothing")}
    )

    assert report["status"] == "VERIFIED", report["reasons"]
    assert "tests_renamed" in [finding["code"] for finding in report["findings"]]
