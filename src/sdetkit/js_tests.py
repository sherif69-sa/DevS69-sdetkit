"""JavaScript and TypeScript tests for `sdetkit verify change`: vitest, jest and `node --test`.

Every runner's results get the same test ids, `<file>::<describe> > <test>` with the file relative
to the repository root, so the change's run, the base's run and what the test files say compare
by one name. A test file that fails to load is reported as `::<file>`.

The test files are read with a small scanner rather than a JavaScript parser: it blanks out
strings and comments, then follows `describe`/`it`/`test` calls by their parentheses. That is
enough to name the tests and count their assertions and skips; it is not a type checker.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

JsonObject = dict[str, Any]

RUNNERS = ("vitest", "jest", "node")
JS_EXTENSIONS = (".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts")
# Configuration that decides which tests run: a change here can make a failing suite pass.
_CONFIG_PREFIXES = ("vitest.config.", "vitest.workspace.", "jest.config.")
# node_modules entries that are caches the runners write to; the clone gets its own.
_CACHE_ENTRIES = frozenset({".cache", ".vite", ".vitest"})

_GROUPS = frozenset({"describe", "context", "suite", "xdescribe", "fdescribe"})
_CALL = re.compile(
    r"(?<![\w$.])(describe|context|suite|it|test|specify|xit|xtest|xdescribe|fit|ftest|fdescribe)"
    r"((?:\s*\.\s*(?:skip|only|todo|each|concurrent|sequential|skipIf|runIf|fails|failing))*)\s*\("
)
# Modifiers that take their own arguments before the test's: `test.each(table)(name, fn)`.
_CURRIED = ("each", "skipIf", "runIf")
_ASSERTION = re.compile(r"(?<![\w$])(?:expect|expectTypeOf|assert)(?:\s*\.\s*\w+)*\s*\(")
_ALWAYS_TRUE = re.compile(r"\s*(?:true|1|!0)\s*\)")
_BODY_SKIP = re.compile(r"(?<![\w$])(?:t|ctx|context|this)\s*\.\s*(?:skip|todo)\s*\(")
_OPTION_SKIP = re.compile(r"(?<![\w$])(?:skip|todo)\s*:\s*(?!false\b)")


def is_js_test_file(path: str) -> bool:
    """Whether a path is a test file for vitest, jest or `node --test` (their default patterns)."""

    pure = PurePosixPath(path)
    if not pure.name.endswith(JS_EXTENSIONS) or "node_modules" in pure.parts:
        return False
    stem = pure.name.split(".", 1)[0]
    return (
        ".test." in pure.name
        or ".spec." in pure.name
        or "__tests__" in pure.parts
        or stem in {"test", "spec"}
        or stem.startswith("test-")
        or stem.endswith(("-test", "_test"))
        or "test" in pure.parts[:-1]
    )


def is_js_config_file(path: str) -> bool:
    return PurePosixPath(path).name.startswith(_CONFIG_PREFIXES)


def _package_json(text: str | None) -> JsonObject:
    try:
        data = json.loads(text or "{}")
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _test_script(data: Mapping[str, Any]) -> Any:
    scripts = data.get("scripts")
    return scripts.get("test") if isinstance(scripts, dict) else None


def package_test_config(text: str | None) -> JsonObject:
    """The parts of a package.json that decide which tests run: `jest` and `scripts.test`."""

    data = _package_json(text)
    return {"jest": data.get("jest"), "test": _test_script(data)}


def detect_runner(root: Path) -> str:
    """vitest, jest or node, from the package.json at `root`; empty when it names none."""

    path = root / "package.json"
    data = _package_json(path.read_text(encoding="utf-8") if path.is_file() else None)
    names: set[str] = set()
    for key in ("dependencies", "devDependencies"):
        if isinstance(data.get(key), dict):
            names.update(data[key])
    script = str(_test_script(data) or "")
    for runner in ("vitest", "jest"):
        if runner in names or re.search(rf"\b{runner}\b", script):
            return runner
    return "node" if re.search(r"\bnode\b[^&|;]*--test\b", script) else ""


# --- reading test files -----------------------------------------------------------------


def mask(source: str) -> str:
    """`source` with the inside of every string, template and comment replaced by spaces.

    Offsets stay the same, so a match in the masked text points at the same code in the source.
    Quote characters stay, so a title is still found where its string starts.
    """

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
        elif char in "\"'`":
            k = i + 1
            while k < n and source[k] != char:
                if source[k] == "\\":
                    k += 1
                elif char != "`" and source[k] == "\n":
                    break
                k += 1
            blank(i + 1, k)
            i = k + 1
        else:
            i += 1
    return "".join(out)


def _closing(masked: str, open_index: int) -> int:
    """The index of the parenthesis that closes the one at `open_index` (-1 when none does)."""

    depth = 0
    for k in range(open_index, len(masked)):
        if masked[k] in "([{":
            depth += 1
        elif masked[k] in ")]}":
            depth -= 1
            if depth == 0:
                return k
    return -1


def _string_at(source: str, index: int) -> str | None:
    """The string literal starting at `index` (after whitespace), or None when there is none."""

    match = re.compile(r"\s*").match(source, index)
    k = match.end() if match else index
    if k >= len(source) or source[k] not in "\"'`":
        return None
    quote, start = source[k], k + 1
    k = start
    while k < len(source) and source[k] != quote:
        k += 2 if source[k] == "\\" else 1
    return source[start:k]


def _calls(source: str, masked: str) -> list[JsonObject]:
    calls: list[JsonObject] = []
    for match in _CALL.finditer(masked):
        name = match.group(1)
        modifiers = re.findall(r"\w+", match.group(2))
        open_index = match.end() - 1
        close = _closing(masked, open_index)
        if close < 0:
            continue
        if any(word in modifiers for word in _CURRIED):
            # `test.each(table)(title, fn)`: the test's own call follows the table's.
            follow = re.compile(r"\s*\(").match(masked, close + 1)
            if not follow:
                continue
            open_index = follow.end() - 1
            close = _closing(masked, open_index)
            if close < 0:
                continue
        title = _string_at(source, open_index + 1)
        if title is None:
            continue
        calls.append(
            {
                "kind": "group" if name in _GROUPS else "test",
                "skipped": name.startswith("x")
                or bool({"skip", "todo", "skipIf"} & set(modifiers)),
                "only": name.startswith("f") or "only" in modifiers,
                "title": title,
                "start": match.start(),
                "open": open_index,
                "end": close,
            }
        )
    return calls


def _tests(source: str) -> list[JsonObject]:
    """Every test in a file with its full name, the text of its call and what it inherits."""

    masked = mask(source)
    tests: list[JsonObject] = []
    stack: list[JsonObject] = []
    for call in _calls(source, masked):
        while stack and call["start"] > stack[-1]["end"]:
            stack.pop()
        # Options before the callback: `it("x", { skip: true }, () => ...)` in node:test.
        head = masked[call["open"] : call["end"]].split("=>", 1)[0].split("function", 1)[0]
        skipped = call["skipped"] or bool(_OPTION_SKIP.search(head))
        if call["kind"] == "group":
            stack.append({**call, "skipped": skipped})
            continue
        tests.append(
            {
                "name": " > ".join([*(group["title"] for group in stack), call["title"]]),
                "skipped": skipped or any(group["skipped"] for group in stack),
                "only": call["only"] or any(group["only"] for group in stack),
                "masked": masked[call["open"] : call["end"] + 1],
                "source": source[call["open"] : call["end"] + 1],
                "title": call["title"],
            }
        )
    return tests


def _assertions(masked_body: str, source_body: str) -> int:
    count = 0
    for match in _ASSERTION.finditer(masked_body):
        # `expect(true)` and `assert(true)` check nothing.
        if not _ALWAYS_TRUE.match(source_body, match.end()):
            count += 1
    return count


def js_test_facts(source: str) -> dict[str, JsonObject]:
    """{test name: {"assertions": n, "skips": n, "only": bool}} for every test in a file."""

    facts: dict[str, JsonObject] = {}
    for test in _tests(source):
        skips = int(test["skipped"]) + len(_BODY_SKIP.findall(test["masked"]))
        facts.setdefault(
            test["name"],
            {
                "assertions": _assertions(test["masked"], test["source"]),
                "skips": skips,
                "only": bool(test["only"]),
            },
        )
    return facts


def js_test_fingerprints(source: str) -> dict[str, str]:
    """{test name: fingerprint of its call without its title}, whitespace aside."""

    prints: dict[str, str] = {}
    for test in _tests(source):
        text = test["source"].replace(test["title"], "", 1)
        prints.setdefault(
            test["name"],
            hashlib.sha256(" ".join(text.split()).encode("utf-8")).hexdigest(),
        )
    return prints


# --- running the tests ------------------------------------------------------------------


def link_node_modules(repo_root: Path, workspace: Path) -> None:
    """Give the clone the repository's installed packages, without sharing their caches.

    The clone gets its own node_modules folder whose entries link to the repository's, so a
    runner's cache (node_modules/.vite and the like) is written in the clone.
    """

    source = repo_root / "node_modules"
    target = workspace / "node_modules"
    if not source.is_dir() or target.exists():
        return
    target.mkdir()
    for entry in source.iterdir():
        if entry.name in _CACHE_ENTRIES:
            continue
        try:
            (target / entry.name).symlink_to(entry, target_is_directory=entry.is_dir())
        except OSError:
            return


# A node:test reporter: one JSON line per finished test, with the names of its suites and, for a
# failure, the error and its stack. A suite is reported only when it fails on
# its own (a hook or its body threw), not because a test in it did.
_NODE_REPORTER = """\
function describeError(error) {
  const cause = (error && error.cause) || error;
  return cause ? String(cause.stack || cause.message || cause) : "";
}

export default async function* reporter(source) {
  const stacks = new Map();
  for await (const event of source) {
    const data = event.data || {};
    const file = data.file || "";
    if (event.type === "test:start") {
      const stack = stacks.get(file) || [];
      stack.length = data.nesting;
      stack.push(data.name);
      stacks.set(file, stack);
    } else if (event.type === "test:pass" || event.type === "test:fail") {
      const details = data.details || {};
      if (details.type === "suite") {
        const cause = (details.error && details.error.failureType) || "";
        if (event.type === "test:pass" || cause === "subtestsFailed") continue;
      }
      const names = [...(stacks.get(file) || []).slice(0, data.nesting), data.name];
      const outcome =
        event.type === "test:fail" ? "failed" : data.skip || data.todo ? "skipped" : "passed";
      const error = outcome === "failed" ? describeError(details.error) : "";
      yield JSON.stringify({ file, names, nesting: data.nesting, outcome, error }) + "\\n";
    }
  }
}
"""


def _relative(workspace: Path, file: str) -> str:
    if not file:
        return ""
    path = Path(file)
    if path.is_absolute():
        try:
            path = path.resolve().relative_to(workspace.resolve())
        except ValueError:
            return path.as_posix()
    return PurePosixPath(path.as_posix()).as_posix()


# Each reader yields (test id, outcome, why it failed); the `read_*` functions keep the outcomes.
Record = tuple[str, str, str]


def _node_records(path: Path, workspace: Path) -> list[Record]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    records: list[Record] = []
    for line in lines:
        try:
            event = json.loads(line)
        except ValueError:
            continue
        file = _relative(workspace, str(event.get("file") or ""))
        names = [str(name) for name in event.get("names") or []]
        outcome = str(event.get("outcome") or "failed")
        error = str(event.get("error") or "")
        if not names:
            continue
        # A file that fails to load is one failed top-level test named after the file.
        first = _relative(workspace, names[0])
        if len(names) == 1 and first.endswith(JS_EXTENSIONS) and first == (file or first):
            records.append((f"::{first}", outcome, error))
            continue
        records.append((f"{file}::{' > '.join(names)}", outcome, error))
    return records


def _vitest_records(path: Path) -> list[Record]:
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return []
    records: list[Record] = []
    for case in root.iter("testcase"):
        file, name = case.get("classname", ""), case.get("name", "")
        failure = case.find("failure")
        if failure is None:
            failure = case.find("error")
        tags = {child.tag for child in case}
        outcome = "failed" if failure is not None else "skipped" if "skipped" in tags else "passed"
        why = "" if failure is None else (failure.text or failure.get("message") or "").strip()
        records.append((f"::{file}" if name == file else f"{file}::{name}", outcome, why))
    return records


def _jest_records(path: Path, workspace: Path) -> list[Record]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    records: list[Record] = []
    for result in data.get("testResults") or []:
        file = _relative(workspace, str(result.get("name") or ""))
        assertions = result.get("assertionResults") or []
        if not assertions and result.get("status") == "failed":
            records.append((f"::{file}", "failed", str(result.get("message") or "").strip()))
        for item in assertions:
            name = " > ".join([*item.get("ancestorTitles", []), str(item.get("title", ""))])
            status = str(item.get("status") or "")
            why = "\n".join(str(message) for message in item.get("failureMessages") or [])
            records.append(
                (
                    f"{file}::{name}",
                    status if status in {"passed", "failed"} else "skipped",
                    why.strip(),
                )
            )
    return records


def _outcomes(records: Sequence[Record]) -> dict[str, str]:
    return {test: outcome for test, outcome, _ in records}


def _failures(records: Sequence[Record]) -> dict[str, str]:
    return {test: why for test, outcome, why in records if outcome == "failed" and why}


def read_node_results(path: Path, workspace: Path) -> dict[str, str]:
    return _outcomes(_node_records(path, workspace))


def read_vitest_junit(path: Path) -> dict[str, str]:
    return _outcomes(_vitest_records(path))


def read_jest_json(path: Path, workspace: Path) -> dict[str, str]:
    return _outcomes(_jest_records(path, workspace))


def write_junit(outcomes: Mapping[str, str], path: Path) -> None:
    """The outcomes as a JUnit file, so every runner leaves the same kind of evidence."""

    suite = ET.Element("testsuite", name="sdetkit", tests=str(len(outcomes)))
    for test_id, outcome in sorted(outcomes.items()):
        file, _, name = test_id.partition("::")
        case = ET.SubElement(suite, "testcase", classname=file, name=name)
        if outcome == "failed":
            ET.SubElement(case, "failure")
        elif outcome == "skipped":
            ET.SubElement(case, "skipped")
    ET.ElementTree(suite).write(path, encoding="utf-8", xml_declaration=True)


def runner_argv(runner: str, workspace: Path, report: Path, test_args: Sequence[str]) -> list[str]:
    """The command for a runner, or an empty list when the runner is not installed."""

    if runner == "node":
        node = shutil.which("node")
        if not node:
            return []
        reporter = report.parent / "sdetkit-node-reporter.mjs"
        reporter.write_text(_NODE_REPORTER, encoding="utf-8")
        return [
            node,
            "--test",
            f"--test-reporter={reporter.as_uri()}",
            f"--test-reporter-destination={report}",
            *test_args,
        ]
    binary = workspace / "node_modules" / ".bin" / (f"{runner}.cmd" if os.name == "nt" else runner)
    if not binary.exists():
        return []
    if runner == "vitest":
        return [str(binary), "run", "--reporter=junit", f"--outputFile={report}", *test_args]
    return [str(binary), "--ci", "--json", f"--outputFile={report}", *test_args]


def run_js_tests(
    runner: str,
    *,
    workspace: Path,
    junit_path: Path,
    test_args: Sequence[str],
    timeout_seconds: int,
    environment: Mapping[str, str],
    output_tail_chars: int,
) -> JsonObject:
    """Run a JavaScript test runner; the result has the same shape as a pytest run's."""

    report = junit_path.with_suffix(".runner" + (".xml" if runner == "vitest" else ".json"))
    argv = runner_argv(runner, workspace, report, test_args)
    shown = " ".join(
        [
            "node --test"
            if runner == "node"
            else f"npx {runner}" + (" run" if runner == "vitest" else ""),
            *test_args,
        ]
    )
    result: JsonObject = {
        "runner": runner,
        "command": shown,
        "exit_code": 127,
        "timed_out": False,
        "pytest_missing": False,
        "runner_missing": not argv,
        "counts": {"passed": 0, "failed": 0, "skipped": 0},
        "outcomes": {},
        "failures": {},
        "output_tail": "",
    }
    if not argv:
        result["output_tail"] = (
            f"{runner} is not installed: install the project's packages (npm ci) first"
        )
        return result
    try:
        completed = subprocess.run(
            argv,
            cwd=workspace,
            env={**environment, "CI": "1", "FORCE_COLOR": "0", "NO_COLOR": "1"},
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
            shell=False,
        )
        result["exit_code"] = completed.returncode
        output = f"{completed.stdout}\n{completed.stderr}"
    except subprocess.TimeoutExpired as exc:
        result.update(exit_code=-1, timed_out=True)
        output = "\n".join(
            part.decode("utf-8", errors="replace") if isinstance(part, bytes) else part or ""
            for part in (exc.stdout, exc.stderr)
        )
    if runner == "vitest":
        records = _vitest_records(report)
    elif runner == "jest":
        records = _jest_records(report, workspace)
    else:
        records = _node_records(report, workspace)
    outcomes = _outcomes(records)
    write_junit(outcomes, junit_path)
    result["outcomes"] = outcomes
    result["failures"] = _failures(records)
    result["counts"] = {
        key: sum(1 for value in outcomes.values() if value == key)
        for key in ("passed", "failed", "skipped")
    }
    result["output_tail"] = output.strip()[-output_tail_chars:]
    return result
