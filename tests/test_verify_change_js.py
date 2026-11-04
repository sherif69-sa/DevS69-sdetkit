"""`sdetkit verify change` on JavaScript and TypeScript tests: vitest, jest and `node --test`."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from sdetkit import change_verifier, js_tests

needs_node = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("node") is None, reason="needs git and node"
)

SOURCE = """\
import { describe, it, test } from "vitest";

describe("cart", () => {
  it("adds an item", () => {
    expect(add([], "a")).toEqual(["a"]);
    expect(add([], "a")).toHaveLength(1);
  });
  it.skip("removes an item", () => {
    expect(remove(["a"], "a")).toEqual([]);
  });
  describe("totals", () => {
    test("sums prices (with tax)", () => {
      // expect(total([])).toBe(1) is a comment, not an assertion
      const label = "expect(nothing)";
      expect(total([{ price: 2 }])).toBe(2);
    });
  });
});

test.each([[1, 2]])("doubles %i", (a, b) => {
  assert.strictEqual(a * 2, b);
});

test("checks nothing", () => {
  expect(true).toBe(true);
});

it("is skipped by an option", { skip: "flaky" }, () => {
  assert.ok(run());
});

const pattern = /x/;
pattern.test("not a test");
"""


def test_the_scanner_names_tests_with_their_groups_and_counts_assertions() -> None:
    facts = js_tests.js_test_facts(SOURCE)

    assert facts == {
        "cart > adds an item": {"assertions": 2, "skips": 0, "only": False},
        "cart > removes an item": {"assertions": 1, "skips": 1, "only": False},
        "cart > totals > sums prices (with tax)": {"assertions": 1, "skips": 0, "only": False},
        "doubles %i": {"assertions": 1, "skips": 0, "only": False},
        "checks nothing": {"assertions": 0, "skips": 0, "only": False},
        "is skipped by an option": {"assertions": 1, "skips": 1, "only": False},
    }


def test_the_scanner_sees_only_on_a_test_and_inherits_skips_from_a_group() -> None:
    source = (
        'describe.skip("group", () => { it("inner", () => { expect(1).toBe(1); }); });\n'
        'fit("focused", () => { expect(a).toBe(b); });\n'
        'xit("off", () => {});\n'
        'test("runs", (t) => { t.skip(); });\n'
    )

    facts = js_tests.js_test_facts(source)

    assert facts["group > inner"]["skips"] == 1
    assert facts["focused"]["only"] is True
    assert facts["off"]["skips"] == 1
    assert facts["runs"]["skips"] == 1


def test_a_renamed_test_keeps_its_fingerprint() -> None:
    before = js_tests.js_test_fingerprints('it("old name", () => {\n  expect(f()).toBe(1);\n});\n')
    after = js_tests.js_test_fingerprints('it("new name", () => { expect(f()).toBe(1); });\n')
    changed = js_tests.js_test_fingerprints('it("new name", () => { expect(f()).toBe(2); });\n')

    assert before["old name"] == after["new name"]
    assert changed["new name"] != after["new name"]


@pytest.mark.parametrize(
    ("path", "is_test"),
    [
        ("src/cart.test.ts", True),
        ("src/cart.spec.jsx", True),
        ("src/__tests__/cart.js", True),
        ("test/cart.mjs", True),
        ("test-cart.cjs", True),
        ("src/cart.ts", False),
        ("node_modules/x/cart.test.js", False),
        ("tests/test_cart.py", False),
    ],
)
def test_js_test_files_follow_the_runners_default_patterns(path: str, is_test: bool) -> None:
    assert js_tests.is_js_test_file(path) is is_test


@pytest.mark.parametrize(
    ("package", "runner"),
    [
        ({"devDependencies": {"vitest": "3"}}, "vitest"),
        ({"devDependencies": {"jest": "30"}}, "jest"),
        ({"scripts": {"test": "node --test test/"}}, "node"),
        ({"scripts": {"test": "mocha"}}, ""),
    ],
)
def test_the_runner_comes_from_package_json(
    tmp_path: Path, package: dict[str, object], runner: str
) -> None:
    (tmp_path / "package.json").write_text(json.dumps(package), encoding="utf-8")

    assert js_tests.detect_runner(tmp_path) == runner
    assert change_verifier.resolve_runner(tmp_path) == (runner or "pytest")


def test_a_python_project_runs_pytest_even_with_a_package_json(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text('{"devDependencies": {"vitest": "3"}}', "utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n", encoding="utf-8")

    assert change_verifier.resolve_runner(tmp_path) == "pytest"
    assert change_verifier.resolve_runner(tmp_path, "vitest") == "vitest"


def test_vitest_and_jest_reports_read_to_the_same_ids(tmp_path: Path) -> None:
    (tmp_path / "vitest.xml").write_text(
        '<testsuites><testsuite name="a.test.js">'
        '<testcase classname="src/a.test.js" name="cart &gt; adds"/>'
        '<testcase classname="src/a.test.js" name="cart &gt; off"><skipped/></testcase>'
        '<testcase classname="src/b.test.js" name="src/b.test.js"><failure/></testcase>'
        "</testsuite></testsuites>",
        encoding="utf-8",
    )
    (tmp_path / "jest.json").write_text(
        json.dumps(
            {
                "testResults": [
                    {
                        "name": str(tmp_path / "src" / "a.test.js"),
                        "status": "passed",
                        "assertionResults": [
                            {"ancestorTitles": ["cart"], "title": "adds", "status": "passed"},
                            {"ancestorTitles": ["cart"], "title": "off", "status": "pending"},
                        ],
                    },
                    {
                        "name": str(tmp_path / "src" / "b.test.js"),
                        "status": "failed",
                        "assertionResults": [],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    expected = {
        "src/a.test.js::cart > adds": "passed",
        "src/a.test.js::cart > off": "skipped",
        "::src/b.test.js": "failed",
    }

    assert js_tests.read_vitest_junit(tmp_path / "vitest.xml") == expected
    assert js_tests.read_jest_json(tmp_path / "jest.json", tmp_path) == expected


def test_vitest_and_jest_reports_keep_why_a_test_fails(tmp_path: Path) -> None:
    (tmp_path / "vitest.xml").write_text(
        '<testsuites><testsuite name="a.test.js">'
        '<testcase classname="src/a.test.js" name="cart &gt; adds">'
        '<failure message="expected 1 to be 2">AssertionError: expected 1 to be 2\n'
        " at src/a.test.js:4:15</failure></testcase>"
        '<testcase classname="src/a.test.js" name="cart &gt; off"><skipped/></testcase>'
        "</testsuite></testsuites>",
        encoding="utf-8",
    )
    (tmp_path / "jest.json").write_text(
        json.dumps(
            {
                "testResults": [
                    {
                        "name": str(tmp_path / "src" / "a.test.js"),
                        "status": "failed",
                        "assertionResults": [
                            {
                                "ancestorTitles": ["cart"],
                                "title": "adds",
                                "status": "failed",
                                "failureMessages": ["Error: expect(received).toBe(expected)"],
                            },
                            {"ancestorTitles": ["cart"], "title": "off", "status": "pending"},
                        ],
                    },
                    {
                        "name": str(tmp_path / "src" / "b.test.js"),
                        "status": "failed",
                        "message": "SyntaxError: Unexpected token (3:4)",
                        "assertionResults": [],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    vitest = js_tests._failures(js_tests._vitest_records(tmp_path / "vitest.xml"))
    jest = js_tests._failures(js_tests._jest_records(tmp_path / "jest.json", tmp_path))

    assert vitest == {
        "src/a.test.js::cart > adds": "AssertionError: expected 1 to be 2\n at src/a.test.js:4:15"
    }
    assert jest == {
        "src/a.test.js::cart > adds": "Error: expect(received).toBe(expected)",
        "::src/b.test.js": "SyntaxError: Unexpected token (3:4)",
    }


def test_a_missing_runner_is_not_run(tmp_path: Path) -> None:
    run = js_tests.run_js_tests(
        "vitest",
        workspace=tmp_path,
        junit_path=tmp_path / "out.xml",
        test_args=[],
        timeout_seconds=10,
        environment={},
        output_tail_chars=100,
    )

    assert run["runner_missing"] is True
    status, reasons = change_verifier.decide(
        head_run=run, base_run=None, comparison={}, findings=[], not_imported=[]
    )
    assert status == "NOT_RUN"
    assert "vitest is not installed" in reasons[0]


def test_the_clone_links_installed_packages_but_keeps_its_own_caches(tmp_path: Path) -> None:
    repo, clone = tmp_path / "repo", tmp_path / "clone"
    (repo / "node_modules" / "left-pad").mkdir(parents=True)
    (repo / "node_modules" / ".vite").mkdir()
    clone.mkdir()

    js_tests.link_node_modules(repo, clone)

    assert (clone / "node_modules" / "left-pad").resolve() == (
        repo / "node_modules" / "left-pad"
    ).resolve()
    assert not (clone / "node_modules" / ".vite").exists()


# --- end to end with node --test --------------------------------------------------------

BUGGY = "exports.add = (a, b) => a - b;\n"
FIXED = "exports.add = (a, b) => a + b;\n"
TEST = """\
const { describe, it } = require("node:test");
const assert = require("node:assert");
const { add } = require("../calc.js");

describe("add", () => {
  it("adds two numbers", () => {
    assert.strictEqual(add(2, 3), 5);
  });
  it("adds zero", () => {
    assert.strictEqual(add(0, 0), 0);
  });
});
"""


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
    (repo / "test").mkdir(parents=True)
    (repo / "calc.js").write_text(source, encoding="utf-8")
    (repo / "test" / "calc.test.js").write_text(test, encoding="utf-8")
    (repo / "package.json").write_text(
        json.dumps({"name": "calc", "private": True, "scripts": {"test": "node --test"}}),
        encoding="utf-8",
    )
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    return repo


def _patch(repo: Path, files: dict[str, str]) -> str:
    for path, text in files.items():
        (repo / path).write_text(text, encoding="utf-8")
    _git(repo, "add", "-A")
    diff = _git(repo, "diff", "--cached")
    _git(repo, "reset", "-q", "--hard")
    return diff


def _verify(repo: Path, tmp_path: Path, files: dict[str, str]) -> dict[str, object]:
    return change_verifier.verify_change(
        repo_root=repo,
        out_dir=tmp_path / "out",
        python=sys.executable,
        patch_text=_patch(repo, files),
        timeout_seconds=120,
    )


@needs_node
def test_a_javascript_fix_is_verified_with_the_test_that_proves_it(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    proving = TEST.replace(
        '  it("adds zero"',
        '  it("adds negatives", () => {\n    assert.strictEqual(add(-1, -2), -3);\n  });\n'
        '  it("adds zero"',
    )

    report = _verify(repo, tmp_path, {"calc.js": FIXED, "test/calc.test.js": proving})

    assert report["tests"]["runner"] == "node"
    assert report["status"] == "VERIFIED", report["reasons"]
    assert report["tests"]["comparison"]["fixed"] == ["test/calc.test.js::add > adds two numbers"]
    assert report["tests"]["proof"]["proving"] == [
        "test/calc.test.js::add > adds negatives",
        "test/calc.test.js::add > adds two numbers",
    ]
    assert (tmp_path / "out" / "tests-head.xml").is_file()


@needs_node
def test_deleting_a_javascript_test_is_caught(tmp_path: Path) -> None:
    repo = _repo(tmp_path, source=FIXED)
    without = TEST.replace(
        '  it("adds zero", () => {\n    assert.strictEqual(add(0, 0), 0);\n  });\n', ""
    )

    report = _verify(repo, tmp_path, {"test/calc.test.js": without})

    assert report["status"] == "REVIEW"
    codes = [finding["code"] for finding in report["findings"]]
    assert "tests_removed" in codes
    assert report["tests"]["comparison"]["missing"] == ["test/calc.test.js::add > adds zero"]


@needs_node
def test_only_and_skip_on_javascript_tests_are_caught(tmp_path: Path) -> None:
    repo = _repo(tmp_path, source=FIXED)
    weakened = TEST.replace('it("adds two numbers"', 'it.skip("adds two numbers"').replace(
        'it("adds zero", () => {\n    assert.strictEqual(add(0, 0), 0);',
        'it.only("adds zero", () => {',
    )

    report = _verify(repo, tmp_path, {"test/calc.test.js": weakened})

    codes = {finding["code"] for finding in report["findings"]}
    assert report["status"] == "REVIEW"
    assert {"skip_added", "only_added", "assertions_removed"} <= codes


@needs_node
def test_a_javascript_regression_fails(tmp_path: Path) -> None:
    repo = _repo(tmp_path, source=FIXED)

    report = _verify(repo, tmp_path, {"calc.js": BUGGY})

    assert report["status"] == "FAILED"
    assert report["tests"]["comparison"]["regressions"] == [
        "test/calc.test.js::add > adds two numbers"
    ]
    why = report["tests"]["failures"]["test/calc.test.js::add > adds two numbers"]
    # node's assertion message and the test's own frame, without node's internal frames.
    assert "-1 !== 5" in why and "(test/calc.test.js:7:" in why
    assert "node:internal" not in why and "(node:" not in why


@needs_node
def test_a_renamed_javascript_test_is_not_a_removed_one(tmp_path: Path) -> None:
    repo = _repo(tmp_path, source=FIXED)

    report = _verify(
        repo, tmp_path, {"test/calc.test.js": TEST.replace('"adds zero"', '"adds nothing"')}
    )

    assert report["status"] == "VERIFIED", report["reasons"]
    assert "tests_renamed" in [finding["code"] for finding in report["findings"]]
    assert report["tests"]["comparison"]["missing"] == []


@needs_node
def test_a_coding_agent_can_verify_javascript_work_over_mcp(tmp_path: Path) -> None:
    from sdetkit import mcp_server

    repo = _repo(tmp_path, source=FIXED)
    (repo / "test" / "calc.test.js").write_text(
        TEST.replace(
            '  it("adds zero", () => {\n    assert.strictEqual(add(0, 0), 0);\n  });\n', ""
        ),
        encoding="utf-8",
    )

    response = mcp_server.Server(cwd=repo, timeout=300).handle(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "verify_change", "arguments": {"runner": "node"}},
        }
    )

    assert response is not None
    structured = response["result"]["structuredContent"]
    assert structured["status"] == "REVIEW", structured
    assert "tests_removed" in structured["findings"]
    assert structured["failures"] == {}


@needs_node
def test_an_agent_over_mcp_gets_why_its_change_fails(tmp_path: Path) -> None:
    from sdetkit import mcp_server

    repo = _repo(tmp_path, source=FIXED)
    (repo / "calc.js").write_text(BUGGY, encoding="utf-8")

    response = mcp_server.Server(cwd=repo, timeout=300).handle(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "verify_change", "arguments": {"runner": "node"}},
        }
    )

    assert response is not None
    structured = response["result"]["structuredContent"]
    assert structured["status"] == "FAILED", structured
    assert "-1 !== 5" in structured["failures"]["test/calc.test.js::add > adds two numbers"]
    assert "Why they fail" in response["result"]["content"][0]["text"]


@pytest.mark.skipif(os.name == "nt", reason="the stand-in runners are POSIX paths")
def test_related_runs_only_the_test_files_that_import_a_file(tmp_path: Path) -> None:
    bin_dir = tmp_path / "node_modules" / ".bin"
    bin_dir.mkdir(parents=True)
    for runner in ("jest", "vitest"):
        (bin_dir / runner).write_text("", encoding="utf-8")
    report = tmp_path / "report.json"

    vitest = js_tests.runner_argv("vitest", tmp_path, report, ["--bail=1"], related=["src/a.ts"])
    jest = js_tests.runner_argv("jest", tmp_path, report, ["--bail"], related=["src/a.js"])

    assert vitest[1:3] == ["related", "--run"] and vitest[-2:] == ["--bail=1", "src/a.ts"]
    assert jest[-3:] == ["--bail", "--findRelatedTests", "src/a.js"]
    # Without it, the usual commands.
    assert js_tests.runner_argv("vitest", tmp_path, report, [])[1] == "run"
    assert "--findRelatedTests" not in js_tests.runner_argv("jest", tmp_path, report, [])


@pytest.mark.skipif(os.name == "nt", reason="the stand-in runners are shell scripts")
def test_a_run_that_writes_no_report_never_reads_the_last_one(tmp_path: Path) -> None:
    from sdetkit.isolated_proof_runner import _execution_environment

    bin_dir = tmp_path / "node_modules" / ".bin"
    bin_dir.mkdir(parents=True)
    for runner in ("jest", "vitest"):
        # Records its arguments, writes no report, fails: as jest 30 does with --bail.
        (bin_dir / runner).write_text(
            f'#!/bin/sh\necho "$@" > "{tmp_path}/{runner}.args"\nexit 1\n', encoding="utf-8"
        )
        (bin_dir / runner).chmod(0o755)
    junit = tmp_path / "tests-mutant.xml"
    # What the run before left: every test passing.
    stale = {
        "testResults": [
            {
                "name": str(tmp_path / "a.test.js"),
                "assertionResults": [{"title": "adds", "status": "passed", "ancestorTitles": []}],
            }
        ]
    }
    junit.with_suffix(".runner.json").write_text(json.dumps(stale), encoding="utf-8")

    def run(runner: str) -> dict[str, object]:
        return js_tests.run_js_tests(
            runner,
            workspace=tmp_path,
            junit_path=junit,
            test_args=[],
            timeout_seconds=60,
            environment=_execution_environment(),
            output_tail_chars=500,
            fail_fast=True,
        )

    assert run("jest")["outcomes"] == {}
    # jest's --bail ends the run before it writes its report: jest runs to the end.
    assert "--bail" not in (tmp_path / "jest.args").read_text(encoding="utf-8")
    run("vitest")
    assert "--bail=1" in (tmp_path / "vitest.args").read_text(encoding="utf-8").split()
