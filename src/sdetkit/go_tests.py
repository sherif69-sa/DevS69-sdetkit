"""Go tests for `sdetkit verify change`: `go test -json`.

Test ids are `<package dir>::<TestName>` (subtests `<package dir>::<TestName>/<subtest>`), the
package directory relative to the module root and `.` for the root package, so the change's run,
the base's run and what the test files say compare by one name. A package whose tests do not
build is reported as `::<package dir>`.

Test files are read with a small scanner, as for JavaScript: strings, runes and comments are
blanked, then each `func TestXxx(t *testing.T)` body is followed by its braces.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

JsonObject = dict[str, Any]

_TEST_FUNC = re.compile(
    r"^func\s+(Test(?:[A-Z0-9_]\w*)?)\s*\(\s*\w+\s+\*\s*testing\.T\s*\)\s*\{", re.M
)
_HELPER_FUNC = re.compile(r"^func\s+([A-Za-z_]\w*)\s*\(", re.M)
# t.Error, t.Fatalf, b.Fail... and testify's assert.X / require.X.
_ASSERTION = re.compile(
    r"(?<![\w.])(?:(?!(?:fmt|errors|log)\b)\w+\s*\.\s*(?:Errorf?|Fatalf?|Fail|FailNow)"
    r"|(?:assert|require)\s*\.\s*[A-Z]\w*)"
    r"\s*\("
)
_ALWAYS_TRUE = re.compile(r"\s*\w+\s*,\s*true\s*[,)]")
_SKIP = re.compile(r"(?<![\w])\w+\s*\.\s*(?:Skip|Skipf|SkipNow)\s*\(")


def is_go_test_file(path: str) -> bool:
    return path.endswith("_test.go") and "vendor" not in PurePosixPath(path).parts


def package_dir(path: str) -> str:
    """The directory of a Go file, as test ids name its package (`.` for the root)."""

    parent = PurePosixPath(path).parent.as_posix()
    return parent if parent not in {"", "."} else "."


def go_package_args(paths: Sequence[str]) -> list[str]:
    """`go test` package arguments for test files: their directories, as `./dir`."""

    return sorted(
        {"./" if package_dir(path) == "." else f"./{package_dir(path)}" for path in paths}
    )


# --- reading test files -----------------------------------------------------------------


def mask(source: str) -> str:
    """`source` with the inside of every string, rune and comment replaced by spaces."""

    out = list(source)
    i, n = 0, len(source)

    def blank(start: int, end: int) -> None:
        for k in range(start, min(end, n)):
            if out[k] != "\n":
                out[k] = " "

    while i < n:
        char = source[i]
        if source.startswith("//", i):
            end = source.find("\n", i)
            end = n if end < 0 else end
            blank(i, end)
            i = end
        elif source.startswith("/*", i):
            end = source.find("*/", i + 2)
            end = n if end < 0 else end + 2
            blank(i, end)
            i = end
        elif char == "`":
            end = source.find("`", i + 1)
            end = n if end < 0 else end
            blank(i + 1, end)
            i = end + 1
        elif char in "\"'":
            k = i + 1
            while k < n and source[k] != char and source[k] != "\n":
                k += 2 if source[k] == "\\" else 1
            blank(i + 1, k)
            i = k + 1
        else:
            i += 1
    return "".join(out)


def _closing(masked: str, open_index: int) -> int:
    depth = 0
    for k in range(open_index, len(masked)):
        if masked[k] == "{":
            depth += 1
        elif masked[k] == "}":
            depth -= 1
            if depth == 0:
                return k
    return -1


def _functions(source: str) -> tuple[list[JsonObject], dict[str, str]]:
    """The test functions of a file, and the bodies of its other top-level functions."""

    masked = mask(source)
    tests: list[JsonObject] = []
    for match in _TEST_FUNC.finditer(masked):
        close = _closing(masked, match.end() - 1)
        if close < 0:
            continue
        tests.append(
            {
                "name": match.group(1),
                "masked": masked[match.end() - 1 : close + 1],
                # The signature after the name and the body: what the test is, not what it is called.
                "text": source[match.end(1) : close + 1],
            }
        )
    helpers: dict[str, str] = {}
    for match in _HELPER_FUNC.finditer(masked):
        name = match.group(1)
        if name.startswith("Test") or name in helpers:
            continue
        brace = masked.find("{", match.end())
        close = _closing(masked, brace) if brace >= 0 else -1
        if close > 0:
            helpers[name] = masked[brace : close + 1]
    return tests, helpers


def _assertions(masked_body: str) -> int:
    count = 0
    for match in _ASSERTION.finditer(masked_body):
        # assert.True(t, true) checks nothing.
        if match.group(0).replace(" ", "").endswith(".True(") and _ALWAYS_TRUE.match(
            masked_body, match.end()
        ):
            continue
        count += 1
    return count


def go_test_facts(source: str) -> dict[str, JsonObject]:
    """{test name: {"assertions": n, "skips": n}} for every test function in a file."""

    tests, helpers = _functions(source)
    helper_counts: dict[str, int] = {}

    def with_helpers(body: str, seen: frozenset[str]) -> int:
        count = _assertions(body)
        for name, helper_body in helpers.items():
            if name in seen or not re.search(rf"(?<![\w.]){re.escape(name)}\s*\(", body):
                continue
            if name not in helper_counts:
                helper_counts[name] = with_helpers(helper_body, seen | {name})
            count += helper_counts[name]
        return count

    return {
        test["name"]: {
            "assertions": with_helpers(test["masked"], frozenset()),
            "skips": len(_SKIP.findall(test["masked"])),
        }
        for test in tests
    }


def go_test_fingerprints(source: str) -> dict[str, str]:
    tests, _ = _functions(source)
    return {
        test["name"]: hashlib.sha256(" ".join(test["text"].split()).encode("utf-8")).hexdigest()
        for test in tests
    }


# --- running the tests ------------------------------------------------------------------


def _module_path(workspace: Path) -> str:
    try:
        text = (workspace / "go.mod").read_text(encoding="utf-8")
    except OSError:
        return ""
    match = re.search(r"^module\s+(\S+)", text, re.M)
    return match.group(1).strip('"') if match else ""


def _dir_of(package: str, module: str) -> str:
    if module and package == module:
        return "."
    if module and package.startswith(f"{module}/"):
        return package[len(module) + 1 :]
    return package


def read_go_json(text: str, module: str) -> dict[str, str]:
    """{test id: passed | failed | skipped} from `go test -json` output."""

    outcomes: dict[str, str] = {}
    tested: set[str] = set()
    failed_packages: list[str] = []
    for line in text.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict) or "Package" not in event:
            continue
        action = event.get("Action")
        directory = _dir_of(str(event["Package"]), module)
        test = event.get("Test")
        if test and action in {"pass", "fail", "skip"}:
            tested.add(directory)
            outcomes[f"{directory}::{test}"] = {"pass": "passed", "fail": "failed"}.get(
                str(action), "skipped"
            )
        elif not test and action == "fail":
            failed_packages.append(directory)
    # A package that failed without running a test did not build (or crashed before a test).
    for directory in failed_packages:
        if directory not in tested:
            outcomes[f"::{directory}"] = "failed"
    return outcomes


# The lines go test writes around a test's own output.
_FRAME = re.compile(r"^\s*(?:=== (?:RUN|PAUSE|CONT|NAME)|--- (?:FAIL|PASS|SKIP)):?\s")


def read_go_failures(text: str, module: str) -> dict[str, str]:
    """{test id: what it printed} for the failed tests, and the compiler's errors for a package
    that did not build, from `go test -json` output."""

    printed: dict[str, list[str]] = {}
    build: dict[str, list[str]] = {}
    failed: dict[str, str] = {}
    for line in text.splitlines():
        event = _event(line)
        action = event.get("Action")
        if action == "build-output":
            build.setdefault(str(event.get("ImportPath")), []).append(str(event.get("Output", "")))
            continue
        if "Package" not in event:
            continue
        directory = _dir_of(str(event["Package"]), module)
        test = event.get("Test")
        key = f"{directory}::{test}" if test else f"::{directory}"
        if action == "output":
            printed.setdefault(key, []).append(str(event.get("Output", "")))
        elif action == "fail":
            failed[key] = str(event.get("FailedBuild") or "")
    failures: dict[str, str] = {}
    for key, failed_build in failed.items():
        lines = build.get(failed_build, []) if failed_build else printed.get(key, [])
        why = "".join(line for line in lines if not _FRAME.match(line)).strip()
        if why:
            failures[key] = why
    return failures


def write_junit(outcomes: Mapping[str, str], path: Path) -> None:
    suite = ET.Element("testsuite", name="sdetkit", tests=str(len(outcomes)))
    for test_id, outcome in sorted(outcomes.items()):
        directory, _, name = test_id.partition("::")
        case = ET.SubElement(suite, "testcase", classname=directory, name=name)
        if outcome == "failed":
            ET.SubElement(case, "failure")
        elif outcome == "skipped":
            ET.SubElement(case, "skipped")
    ET.ElementTree(suite).write(path, encoding="utf-8", xml_declaration=True)


def run_go_tests(
    *,
    workspace: Path,
    junit_path: Path,
    test_args: Sequence[str],
    timeout_seconds: int,
    environment: Mapping[str, str],
    output_tail_chars: int,
    isolate: Callable[[list[str]], list[str]] | None = None,
    cover_profile: Path | None = None,
) -> JsonObject:
    """Run `go test -json`; the result has the same shape as a pytest run's. `isolate` wraps
    the command, to run it without network access (modules must then be in the module cache).
    `cover_profile` records coverage there, of every package of the module (`-coverpkg=./...`),
    so code a test in another package runs counts too."""

    go = shutil.which("go", path=environment.get("PATH"))
    args = list(test_args) or ["./..."]
    result: JsonObject = {
        "runner": "go",
        "command": " ".join(["go", "test", *args]),
        "exit_code": 127,
        "timed_out": False,
        "pytest_missing": False,
        "runner_missing": not go,
        "counts": {"passed": 0, "failed": 0, "skipped": 0},
        "outcomes": {},
        "failures": {},
        "output_tail": "",
    }
    if not go:
        result["output_tail"] = "go is not installed"
        return result
    try:
        cover = [f"-coverprofile={cover_profile}", "-coverpkg=./..."] if cover_profile else []
        argv = [go, "test", "-json", *cover, *args]
        completed = subprocess.run(
            isolate(argv) if isolate else argv,
            cwd=workspace,
            env=dict(environment),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
            shell=False,
        )
        result["exit_code"] = completed.returncode
        stdout, stderr = completed.stdout, completed.stderr
    except subprocess.TimeoutExpired as exc:
        result.update(exit_code=-1, timed_out=True)
        stdout, stderr = (
            part.decode("utf-8", errors="replace") if isinstance(part, bytes) else part or ""
            for part in (exc.stdout, exc.stderr)
        )
    outcomes = read_go_json(stdout, _module_path(workspace))
    write_junit(outcomes, junit_path)
    output = "\n".join(
        str(event.get("Output", ""))
        for event in map(_event, stdout.splitlines())
        if event.get("Action") in {"output", "build-output"}
    )
    result["outcomes"] = outcomes
    result["failures"] = {
        test: why
        for test, why in read_go_failures(stdout, _module_path(workspace)).items()
        if outcomes.get(test) == "failed"
    }
    result["counts"] = {
        key: sum(1 for value in outcomes.values() if value == key)
        for key in ("passed", "failed", "skipped")
    }
    result["output_tail"] = f"{output}\n{stderr}".strip()[-output_tail_chars:]
    return result


def _event(line: str) -> JsonObject:
    try:
        event = json.loads(line)
    except ValueError:
        return {}
    return event if isinstance(event, dict) else {}
