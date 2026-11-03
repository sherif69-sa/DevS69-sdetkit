"""Changed-line mutation for `sdetkit verify change` (`--mutate`)."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from sdetkit import change_verifier, changed_mutation, mcp_server
from sdetkit.changed_mutation import Mutant

needs_coverage = pytest.mark.skipif(
    shutil.which("git") is None or importlib.util.find_spec("coverage") is None,
    reason="needs git and coverage",
)
needs_node = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("node") is None, reason="needs git and node"
)
needs_go = pytest.mark.skipif(
    shutil.which("git") is None or shutil.which("go") is None, reason="needs git and go"
)


def _afters(path: str, source: str, line: int) -> list[tuple[str, str]]:
    return [
        (mutant.kind, mutant.after.strip())
        for mutant in changed_mutation.line_mutants(path, source, [line]).get(line, [])
    ]


# --- what gets mutated ----------------------------------------------------------------------


def test_python_mutants_come_from_the_tokens_most_telling_first() -> None:
    source = (
        "def grade(score, *, strict=False):\n"
        "    if score >= 50 and not strict:  # pass mark: 50 < x\n"
        '        return "pass < fail"\n'
        "    return None\n"
        "    total = total + 1\n"
        "    ok = name not in seen and value is not None\n"
    )

    assert _afters("g.py", source, 2) == [
        ("comparison", "if score > 50 and not strict:  # pass mark: 50 < x"),
        ("logic", "if score >= 50 or not strict:  # pass mark: 50 < x"),
        ("negation", "if score >= 50 and strict:  # pass mark: 50 < x"),
        ("constant", "if score >= 51 and not strict:  # pass mark: 50 < x"),
    ]
    # Strings and comments are never edited; a returned value becomes None.
    assert _afters("g.py", source, 3) == [("return", "return None")]
    assert _afters("g.py", source, 4) == []
    assert _afters("g.py", source, 5) == [
        ("arithmetic", "total = total - 1"),
        ("constant", "total = total + 2"),
    ]
    # `not in` and `is not` are comparisons of their own; only `and` is mutated there.
    assert _afters("g.py", source, 6) == [("logic", "ok = name not in seen or value is not None")]
    # The `*` that marks keyword-only arguments is not an operator; a product is.
    assert _afters("g.py", source, 1) == [("boolean", "def grade(score, *, strict=True):")]
    assert _afters("p.py", "y = f(-x) * a / 2\n", 1) == [
        ("arithmetic", "y = f(+x) * a / 2"),
        ("arithmetic", "y = f(-x) / a / 2"),
        ("arithmetic", "y = f(-x) * a * 2"),
        ("constant", "y = f(-x) * a / 3"),
    ]


def test_go_java_and_javascript_mutants_skip_strings_comments_and_types() -> None:
    go = (
        "package calc\n\n"
        'import "fmt"\n\n'
        "func Ok(a, b int, ok bool) bool {\n"
        "\tif a < b && !ok { // a < b\n"
        '\t\tfmt.Println("a + b")\n'
        "\t}\n"
        "\treturn a*2 > b - 1\n"
        "}\n"
    )
    assert _afters("calc.go", go, 3) == []
    assert _afters("calc.go", go, 6) == [
        ("comparison", "if a <= b && !ok { // a < b"),
        ("logic", "if a < b || !ok { // a < b"),
        ("negation", "if a < b && ok { // a < b"),
    ]
    # A `+` on a line with a string is concatenation: not mutated in Go or Java.
    assert _afters("calc.go", go, 7) == []
    assert _afters("calc.go", go, 9) == [
        ("comparison", "return a*2 >= b - 1"),
        ("arithmetic", "return a*2 > b + 1"),
        ("constant", "return a*3 > b - 1"),
        ("constant", "return a*2 > b - 2"),
    ]

    java = (
        "import java.util.List;\n"
        "class C {\n"
        "    List<String> names = new ArrayList<>();\n"
        '    String s = "a" + count;\n'
        "    boolean big(int n) { return n >= 10 || flag == true; }\n"
        "}\n"
    )
    assert _afters("C.java", java, 1) == []
    assert _afters("C.java", java, 3) == []
    assert _afters("C.java", java, 4) == []
    assert _afters("C.java", java, 5) == [
        ("comparison", "boolean big(int n) { return n > 10 || flag == true; }"),
        ("comparison", "boolean big(int n) { return n >= 10 || flag != true; }"),
        ("logic", "boolean big(int n) { return n >= 10 && flag == true; }"),
        ("boolean", "boolean big(int n) { return n >= 10 || flag == false; }"),
        ("constant", "boolean big(int n) { return n >= 11 || flag == true; }"),
    ]

    js = "export function f(a, b) {\n  return a === b ? `${a + b}` : a + 1;\n}\nconst x = y - 1;\n"
    assert _afters("f.js", js, 2) == [
        ("comparison", "return a !== b ? `${a + b}` : a + 1;"),
        ("return", "return undefined;"),
        ("constant", "return a === b ? `${a + b}` : a + 2;"),
    ]
    assert _afters("f.js", js, 4) == [
        ("arithmetic", "const x = y + 1;"),
        ("constant", "const x = y - 2;"),
    ]
    # TypeScript can type-check a returned value or an operator: those are left alone.
    assert _afters("f.ts", js, 4) == [("constant", "const x = y - 2;")]
    assert changed_mutation.line_mutants("notes.md", "a < b\n", [1]) == {}


def test_mutants_spread_over_the_lines_one_per_line_first() -> None:
    source = "".join(f"x{n} = {n} < y and z\n" for n in range(1, 7))
    candidates = {"m.py": changed_mutation.line_mutants("m.py", source, range(1, 7))}
    sources = {"m.py": source}

    three = changed_mutation.select_mutants(candidates, sources, 3)
    eight = changed_mutation.select_mutants(candidates, sources, 8)

    assert [(m.line, m.kind) for m in three] == [
        (1, "comparison"),
        (3, "comparison"),
        (5, "comparison"),
    ]
    assert [(m.line, m.kind) for m in eight] == [
        *((line, "comparison") for line in range(1, 7)),
        (1, "logic"),
        (2, "logic"),
    ]
    # A Python mutant that does not parse is skipped for the line's next one.
    bad = Mutant("m.py", 1, "comparison", "x1 = 1 < y and z", "x1 = 1 << < y and z")
    good = Mutant("m.py", 1, "logic", "x1 = 1 < y and z", "x1 = 1 < y or z")
    assert changed_mutation.select_mutants({"m.py": {1: [bad, good]}}, sources, 5) == [good]


def test_long_lines_are_shortened_in_the_report() -> None:
    fits = "x" * changed_mutation.LINE_CHARS
    longer = fits + "y"

    assert changed_mutation._short(f"    {fits}  ") == fits
    assert changed_mutation._short(longer) == fits[:-1] + "…"


def test_a_mutant_is_written_and_the_file_put_back(tmp_path: Path) -> None:
    file = tmp_path / "pkg" / "m.py"
    file.parent.mkdir()
    file.write_bytes(b"a = 1\r\nb = a < 2\r\n")
    compiled = file.parent / "__pycache__" / "m.cpython-311.pyc"
    compiled.parent.mkdir()
    compiled.write_bytes(b"stale")
    mutant = Mutant("pkg/m.py", 2, "comparison", "b = a < 2", "b = a <= 2")

    with changed_mutation.applied(tmp_path, mutant):
        assert file.read_bytes() == b"a = 1\r\nb = a <= 2\r\n"
        assert not compiled.exists()
    assert file.read_bytes() == b"a = 1\r\nb = a < 2\r\n"


def test_outcomes_tell_a_caught_mutant_from_one_that_did_not_build() -> None:
    passed = {"t::a": "passed", "t::b": "passed"}
    assert changed_mutation.outcome({"outcomes": passed}) == ("survived", "")
    assert changed_mutation.outcome({"outcomes": {**passed, "t::b": "failed"}}) == (
        "killed",
        "t::b",
    )
    assert changed_mutation.outcome({"outcomes": {"::calc": "failed"}}) == ("not_built", "")
    assert changed_mutation.outcome({"outcomes": {}}) == ("not_built", "")
    assert changed_mutation.outcome({"outcomes": {}, "timed_out": True}) == ("timed_out", "")


def test_the_summary_scores_caught_mutants_and_lists_the_survivors() -> None:
    a = Mutant("m.py", 2, "comparison", "if a >= 50:", "if a > 50:")
    b = Mutant("m.py", 3, "return", 'return "pass"', "return None")
    c = Mutant("m.py", 3, "constant", "x = 1", "x = 2")
    mutation = changed_mutation.summarize(
        [(a, "survived", ""), (b, "killed", "t::high"), (c, "timed_out", ""), (c, "not_built", "")],
        lines=4,
        minimum=80,
    )

    assert (
        mutation["killed"],
        mutation["survived"],
        mutation["timed_out"],
        mutation["not_built"],
    ) == (
        1,
        1,
        1,
        1,
    )
    assert (mutation["score"], mutation["lines"], mutation["lines_mutated"]) == (66.7, 4, 2)
    assert changed_mutation.survivor_items(mutation) == ["m.py:2: if a >= 50: → if a > 50:"]
    assert changed_mutation.mutation_line(mutation) == (
        "**Mutants:** the tests catch 2 of 3 mutant(s) of the changed lines (66.7%); "
        "1 survive: no test checks what those lines do."
    )
    findings = change_verifier.mutation_findings(mutation)
    assert [(f["code"], f["blocking"]) for f in findings] == [("changed_lines_not_checked", True)]
    assert "the minimum is 80%" in findings[0]["message"]
    noted = change_verifier.mutation_findings({**mutation, "minimum": 0})
    assert [(f["code"], f["blocking"]) for f in noted] == [("changed_lines_not_checked", False)]
    # Not asked for: nothing to say.
    assert change_verifier.mutation_findings(None) == []
    assert changed_mutation.mutation_line(None) == ""


def test_mutants_need_every_test_passing(tmp_path: Path) -> None:
    failing = {"counts": {"failed": 1}, "outcomes": {"t::a": "failed"}}

    def never() -> dict[str, object]:
        raise AssertionError("no mutant runs")

    mutation = changed_mutation.mutate_changed_lines(
        workspace=tmp_path, lines={"m.py": [1]}, head_run=failing, run=never, minimum=50
    )

    assert mutation["ran"] is False
    assert mutation["reason"] == "not every test passes on the change"
    assert changed_mutation.mutation_line(mutation) == (
        "**Mutants:** not run (not every test passes on the change)."
    )
    assert [f["code"] for f in change_verifier.mutation_findings(mutation)] == [
        "changed_lines_not_mutated"
    ]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        # One mutant is allowed: the score is what is wrong here.
        ({"max_mutants": 1, "min_mutation_score": 101}, "--min-mutation-score"),
        ({"max_mutants": 0}, "--max-mutants"),
    ],
)
def test_the_options_are_checked(tmp_path: Path, kwargs: dict[str, float], message: str) -> None:
    with pytest.raises(change_verifier.ChangeError, match=message):
        change_verifier.verify_change(repo_root=tmp_path, head="HEAD", **kwargs)  # type: ignore[arg-type]


def test_the_mcp_tool_passes_the_options_and_returns_the_survivors() -> None:
    assert mcp_server._mutation_args({}) == []
    assert mcp_server._mutation_args(
        {"mutate": True, "max_mutants": 5, "min_mutation_score": 80}
    ) == [
        "--mutate",
        "--max-mutants",
        "5",
        "--min-mutation-score",
        "80.0",
    ]
    for bad in (
        {"mutate": "yes"},
        {"max_mutants": 0},
        {"max_mutants": True},
        {"min_mutation_score": 120},
    ):
        with pytest.raises(mcp_server.ToolError):
            mcp_server._mutation_args(bad)
    mutant = Mutant("m.py", 2, "comparison", "if a >= 50:", "if a > 50:")

    assert mcp_server._mutation(None) is None
    assert mcp_server._mutation(
        changed_mutation.summarize([(mutant, "survived", "")], lines=1)
    ) == {
        "ran": True,
        "score": 0.0,
        "survived": [{"path": "m.py", "line": 2, "before": "if a >= 50:", "after": "if a > 50:"}],
        "reason": "",
    }


# --- end to end ---------------------------------------------------------------------------

GRADE = 'def grade(score):\n    return "fail"\n'
GRADED = (
    'def grade(score):\n    if score >= 50 and score <= 100:\n        return "pass"\n'
    '    return "fail"\n'
)
TEST = 'from grade import grade\n\n\ndef test_low():\n    assert grade(10) == "fail"\n'
TESTED = TEST + '\n\ndef test_high():\n    assert grade(80) == "pass"\n'


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _repo(tmp_path: Path, files: dict[str, str]) -> Path:
    repo = tmp_path / "repo"
    for path, text in files.items():
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_text(text, encoding="utf-8")
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


def _survivors(report: dict[str, object]) -> list[str]:
    return changed_mutation.survivor_items(report["mutation"])  # type: ignore[arg-type]


@needs_coverage
def test_python_lines_the_tests_do_not_check_are_found_and_can_block(tmp_path: Path) -> None:
    repo = _repo(
        tmp_path,
        {
            "pyproject.toml": '[project]\nname = "grade"\nversion = "0"\n'
            '[tool.pytest.ini_options]\npythonpath = ["src"]\n',
            "src/grade/__init__.py": GRADE,
            "tests/test_grade.py": TEST,
        },
    )
    diff = _patch(repo, {"src/grade/__init__.py": GRADED, "tests/test_grade.py": TESTED})

    noted = change_verifier.verify_change(
        repo_root=repo, out_dir=tmp_path / "a", python=sys.executable, patch_text=diff, mutate=True
    )
    blocked = change_verifier.verify_change(
        repo_root=repo,
        out_dir=tmp_path / "b",
        python=sys.executable,
        patch_text=diff,
        min_mutation_score=80,
        max_mutants=3,
    )

    assert noted["status"] == "VERIFIED", noted["reasons"]
    mutation = noted["mutation"]
    assert (mutation["killed"], mutation["survived"], mutation["not_built"]) == (2, 4, 0)
    # The tests check a low and a high score, never the edges at 50 and 100.
    assert _survivors(noted) == [
        "src/grade/__init__.py:2: if score >= 50 and score <= 100: → if score > 50 and score <= 100:",
        "src/grade/__init__.py:2: if score >= 50 and score <= 100: → if score >= 50 and score < 100:",
        "src/grade/__init__.py:2: if score >= 50 and score <= 100: → if score >= 51 and score <= 100:",
        "src/grade/__init__.py:2: if score >= 50 and score <= 100: → if score >= 50 and score <= 101:",
    ]
    killed = {
        item["after"]: item["test"] for item in mutation["mutants"] if item["outcome"] == "killed"
    }
    assert killed == {
        "return None": "tests.test_grade::test_high",
        "if score >= 50 or score <= 100:": "tests.test_grade::test_low",
    }
    assert "**Mutants:** the tests catch 2 of 6" in (
        tmp_path / "a" / "change-verification.md"
    ).read_text(encoding="utf-8")

    assert blocked["status"] == "REVIEW"
    assert blocked["reasons"][0].startswith("changed_lines_not_checked:")
    assert len(blocked["mutation"]["mutants"]) == 3
    predicate = json.loads((tmp_path / "b" / "change-verification.predicate.json").read_text())
    assert predicate["mutation"] == {
        "ran": True,
        "killed": 1,
        "survived": 2,
        "timed_out": 0,
        "not_built": 0,
        "score": 33.3,
        "minimum": 80.0,
    }
    # Every mutant was put back: the repository and the change are untouched.
    assert not _git(repo, "status", "--porcelain")


@needs_coverage
def test_without_mutate_there_is_no_mutation(tmp_path: Path) -> None:
    repo = _repo(
        tmp_path,
        {
            "pyproject.toml": '[project]\nname = "grade"\nversion = "0"\n'
            '[tool.pytest.ini_options]\npythonpath = ["src"]\n',
            "src/grade/__init__.py": GRADE,
            "tests/test_grade.py": TEST,
        },
    )
    diff = _patch(repo, {"src/grade/__init__.py": GRADED, "tests/test_grade.py": TESTED})

    report = change_verifier.verify_change(
        repo_root=repo, out_dir=tmp_path / "out", python=sys.executable, patch_text=diff
    )

    assert report["mutation"] is None
    predicate = json.loads((tmp_path / "out" / "change-verification.predicate.json").read_text())
    assert predicate["mutation"] is None


GO_BASE = "package calc\n\nfunc Add(a, b int) int {\n\treturn a - b\n}\n"
GO_CHANGED = (
    "package calc\n\nfunc Add(a, b int) int {\n\treturn a + b\n}\n\n"
    "func Positive(n int) bool {\n\treturn n > 0\n}\n"
)
GO_TEST = (
    'package calc\n\nimport "testing"\n\n'
    "func TestAdd(t *testing.T) {\n\tif Add(2, 3) != 5 {\n\t\tt.Fatal(Add(2, 3))\n\t}\n}\n\n"
    "func TestPositive(t *testing.T) {\n\tif !Positive(5) || Positive(-5) {\n\t\tt.Fatal()\n\t}\n}\n"
)


@needs_go
def test_go_mutants_run_with_failfast(tmp_path: Path) -> None:
    repo = _repo(
        tmp_path,
        {
            "go.mod": "module example.com/calc\n\ngo 1.21\n",
            "calc.go": GO_BASE,
            "calc_test.go": GO_TEST.split("\n\nfunc TestPositive")[0] + "\n",
        },
    )
    diff = _patch(repo, {"calc.go": GO_CHANGED, "calc_test.go": GO_TEST})

    report = change_verifier.verify_change(
        repo_root=repo,
        out_dir=tmp_path / "out",
        python=sys.executable,
        patch_text=diff,
        mutate=True,
    )

    assert report["status"] == "VERIFIED", report["reasons"]
    outcomes = {item["after"]: item["outcome"] for item in report["mutation"]["mutants"]}
    assert outcomes == {
        "return a - b": "killed",
        "return n >= 0": "survived",
        "return n > 1": "survived",
    }


@needs_node
def test_node_mutants_and_a_returned_value(tmp_path: Path) -> None:
    repo = _repo(
        tmp_path,
        {
            "package.json": '{"name": "c", "version": "1.0.0", "private": true}\n',
            "src/calc.mjs": "export function add(a, b) {\n  return a - b;\n}\n",
            "test/calc.test.mjs": 'import { test } from "node:test";\n'
            'import assert from "node:assert/strict";\n'
            'import { add } from "../src/calc.mjs";\n\n'
            'test("adds", () => {\n  assert.equal(add(2, 3), -1);\n});\n',
        },
    )
    diff = _patch(
        repo,
        {
            "src/calc.mjs": "export function add(a, b) {\n  return a + b;\n}\n\n"
            "export function positive(n) {\n  return n > 0;\n}\n",
            "test/calc.test.mjs": 'import { test } from "node:test";\n'
            'import assert from "node:assert/strict";\n'
            'import { add, positive } from "../src/calc.mjs";\n\n'
            'test("adds", () => {\n  assert.equal(add(2, 3), 5);\n});\n\n'
            'test("positive", () => {\n  assert.equal(positive(5), true);\n});\n',
        },
    )

    report = change_verifier.verify_change(
        repo_root=repo,
        out_dir=tmp_path / "out",
        python=sys.executable,
        patch_text=diff,
        runner="node",
        test_args=["test/calc.test.mjs"],
        mutate=True,
        measure_coverage=False,
    )

    assert report["status"] == "VERIFIED", report["reasons"]
    outcomes = {
        (item["line"], item["after"].strip()): item["outcome"]
        for item in report["mutation"]["mutants"]
    }
    assert outcomes == {
        (2, "return undefined;"): "killed",
        (6, "return undefined;"): "killed",
        (2, "return a - b;"): "killed",
        (6, "return n >= 0;"): "survived",
        (6, "return n > 1;"): "survived",
    }
