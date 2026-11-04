"""Changed-line mutation for `sdetkit verify change`: do the tests check what the changed lines do?

Coverage says that a test ran a line, not that any test would notice if the line did something
else: a test can call the code and assert nothing that depends on it. A mutant changes one
operator or constant on one changed line (`<` to `<=`, `and` to `or`, `True` to `False`, a
number to the next one, a returned value to `None`) and the tests run again on it. When a test
that passed on the change fails, the tests check that line: the mutant is killed. When every
test still passes, no test checks what the line does: the mutant survives. A mutant the code
does not build or load with says nothing, and does not count.

Only changed lines that the tests run are mutated: a line no test runs survives every mutant,
and the changed-line coverage already reports it.
"""

from __future__ import annotations

import ast
import io
import re
import time
import tokenize
from collections.abc import Callable, Collection, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sdetkit.go_tests import mask as go_mask
from sdetkit.java_tests import mask as java_mask
from sdetkit.js_tests import mask as js_mask

JsonObject = dict[str, Any]

DEFAULT_MAX_MUTANTS = 20
# The most a line shows in a report.
LINE_CHARS = 100

_JS_SUFFIXES = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".mts", ".cts")
_TS_SUFFIXES = (".ts", ".tsx", ".mts", ".cts")

# The order mutants of a line are tried in: the likeliest to show a missing check first.
KINDS = (
    "comparison",
    "logic",
    "negation",
    "counterpart",
    "boolean",
    "return",
    "arithmetic",
    "constant",
)

# The test a surviving mutant of each kind asks for.
HINTS = {
    "comparison": "test the boundary: inputs where the two sides are equal",
    "logic": "test a case where only one of the two conditions holds",
    "negation": "test both outcomes of the condition",
    "counterpart": "test an input where the two differ (one that has it twice, or at both ends)",
    "boolean": "assert on what this value changes",
    "return": "assert on the value it returns",
    "arithmetic": "assert on the exact value it computes",
    "constant": "test at the constant itself, where it and the next number differ",
}

_COMPARISON = {"==": "!=", "!=": "==", "<": "<=", "<=": "<", ">": ">=", ">=": ">"}
_ARITHMETIC = {"+": "-", "-": "+", "*": "/", "/": "*", "+=": "-=", "-=": "+="}


def _both_ways(*pairs: tuple[str, str]) -> dict[str, str]:
    return {**dict(pairs), **{b: a for a, b in pairs}}


# Calls with a counterpart that reads from the other end, or picks the other extreme: the
# change may have picked the wrong one. Python methods (after a `.`) and builtins.
_PY_METHODS = _both_ways(
    ("partition", "rpartition"),
    ("split", "rsplit"),
    ("find", "rfind"),
    ("lstrip", "rstrip"),
    ("startswith", "endswith"),
    ("removeprefix", "removesuffix"),
    ("ljust", "rjust"),
    ("upper", "lower"),
    ("min", "max"),
)
_PY_BUILTINS = _both_ways(("min", "max"), ("any", "all"))
# Go, Java and JavaScript methods; one that the receiver lacks does not build (not_built).
_C_METHODS = _both_ways(
    ("startsWith", "endsWith"),
    ("indexOf", "lastIndexOf"),
    ("trimStart", "trimEnd"),
    ("padStart", "padEnd"),
    ("toUpperCase", "toLowerCase"),
    ("some", "every"),
    ("min", "max"),
    ("HasPrefix", "HasSuffix"),
    ("TrimLeft", "TrimRight"),
    ("TrimPrefix", "TrimSuffix"),
    ("Index", "LastIndex"),
    ("ToUpper", "ToLower"),
    ("Min", "Max"),
)


def _has_two_arguments(tokens: Sequence[tokenize.TokenInfo], opening: int) -> bool:
    """Whether the call whose `(` is tokens[opening] passes more than one argument."""

    depth = 0
    for index in range(opening, len(tokens)):
        text = tokens[index].string
        if text in "([{":
            depth += 1
        elif text in ")]}":
            depth -= 1
            if depth == 0:
                return False
        elif text == "," and depth == 1 and tokens[index + 1].string != ")":
            return True
    return False


@dataclass(frozen=True)
class Mutant:
    path: str
    line: int
    kind: str
    before: str
    after: str


def _short(line: str) -> str:
    text = line.strip()
    return text if len(text) <= LINE_CHARS else text[: LINE_CHARS - 1] + "…"


def language(path: str) -> str:
    if path.endswith(".py"):
        return "python"
    if path.endswith(".go"):
        return "go"
    if path.endswith(".java"):
        return "java"
    if path.endswith(_JS_SUFFIXES):
        return "js"
    return ""


# --- Python: from the tokens, so strings, comments and names are never touched ------------


def _python_mutants(path: str, source: str, wanted: set[int]) -> dict[int, list[Mutant]]:
    lines = source.splitlines()
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except (tokenize.TokenError, SyntaxError):
        return {}
    found: dict[int, list[tuple[int, Mutant]]] = {}

    def add(kind: str, row: int, start: int, end: int, replacement: str) -> None:
        before = lines[row - 1]
        after = before[:start] + replacement + before[end:]
        found.setdefault(row, []).append(
            (KINDS.index(kind), Mutant(path, row, kind, before, after))
        )

    for index, token in enumerate(tokens):
        (row, start), (end_row, end) = token.start, token.end
        if row not in wanted or row != end_row:
            continue
        text = token.string
        previous = tokens[index - 1].string if index else ""
        following = tokens[index + 1].string if index + 1 < len(tokens) else ""
        if token.type == tokenize.OP and text in _COMPARISON:
            add("comparison", row, start, end, _COMPARISON[text])
        elif token.type == tokenize.OP and text in _ARITHMETIC:
            # `*` and `/` also mark arguments (`def f(a, *, b)`), where the other one parses.
            if text in {"*", "/"} and (
                previous in {"(", ",", "[", "{", ""} or following in {",", ")"}
            ):
                continue
            add("arithmetic", row, start, end, _ARITHMETIC[text])
        elif token.type == tokenize.NAME and text in {"and", "or"}:
            add("logic", row, start, end, "or" if text == "and" else "and")
        elif (
            token.type == tokenize.NAME
            and text == "not"
            and previous != "is"
            and following != "in"
            and tokens[index + 1].start[0] == row
        ):
            # `not x` to `x`; `is not` and `not in` are comparisons of their own.
            add("negation", row, start, tokens[index + 1].start[1], "")
        elif (
            token.type == tokenize.NAME
            and following == "("
            and (
                (previous == "." and text in _PY_METHODS)
                or (previous not in {".", "def"} and text in _PY_BUILTINS)
            )
        ):
            # split and rsplit differ only with a maximum number of splits.
            if text not in {"split", "rsplit"} or _has_two_arguments(tokens, index + 1):
                counterpart = (_PY_METHODS if previous == "." else _PY_BUILTINS)[text]
                add("counterpart", row, start, end, counterpart)
        elif token.type == tokenize.NAME and text in {"True", "False"}:
            add("boolean", row, start, end, "False" if text == "True" else "True")
        elif token.type == tokenize.NUMBER and text.isdigit():
            add("constant", row, start, end, str(int(text) + 1))
        elif token.type == tokenize.NAME and text == "return" and following not in {"None", ""}:
            # A return of one line: the value becomes None.
            rest = tokens[index + 1 :]
            newline = next(
                (t for t in rest if t.type in {tokenize.NEWLINE, tokenize.ENDMARKER}), None
            )
            if newline is not None and newline.start[0] == row and rest[0].type != tokenize.NEWLINE:
                add("return", row, end, newline.start[1], " None")
    return {
        row: [mutant for _, mutant in sorted(items, key=lambda item: item[0])]
        for row, items in found.items()
    }


# --- Go, Java, JavaScript: from the line with its strings and comments blanked ------------

# Comparison, logic and arithmetic operators count with a space on both sides, as gofmt,
# google-java-format and prettier write them: `List<String>`, `->`, `<-ch`, `x++` and JSX
# are not operators of that shape.
_C_COMPARISON = re.compile(r"(?<=\s)(===|!==|==|!=|<=|>=|<|>)(?=\s)")
_C_SWAP = {**_COMPARISON, "===": "!==", "!==": "==="}
_C_LOGIC = re.compile(r"(?<=\s)(&&|\|\|)(?=\s)")
_C_NEGATION = re.compile(r"(?<=[\s(])!(?=[\w($])")
_C_BOOLEAN = re.compile(r"\b(true|false)\b")
_C_COUNTERPART = re.compile(
    r"(?<=\.)(" + "|".join(sorted(_C_METHODS, key=len, reverse=True)) + r")(?=\()"
)
_C_ARITHMETIC = re.compile(r"(?<=\s)([-+*/])(?=\s)")
_C_NUMBER = re.compile(r"(?<![\w.$])\d+(?![\w.$])")
_JS_RETURN = re.compile(r"\breturn\s+(?!undefined\b|null\b)[^;\s][^;]*;")
_DECLARATION = re.compile(r"^\s*(?:import|package|export\s+\*|@)")


def _c_mutants(path: str, source: str, wanted: set[int]) -> dict[int, list[Mutant]]:
    kind_of_language = language(path)
    masker = {"go": go_mask, "java": java_mask}.get(kind_of_language, js_mask)
    masked_lines = masker(source).splitlines()
    lines = source.splitlines()
    found: dict[int, list[Mutant]] = {}
    for row in sorted(wanted):
        if row > len(lines) or row > len(masked_lines):
            continue
        before, masked = lines[row - 1], masked_lines[row - 1]
        if _DECLARATION.match(masked):
            continue
        # (kind, start, end, replacement), in the masked line's offsets, which are the line's.
        edits: list[tuple[str, int, int, str]] = []
        edits += [
            ("comparison", m.start(), m.end(), _C_SWAP[m.group()])
            for m in _C_COMPARISON.finditer(masked)
        ]
        edits += [
            ("logic", m.start(), m.end(), "||" if m.group() == "&&" else "&&")
            for m in _C_LOGIC.finditer(masked)
        ]
        edits += [("negation", m.start(), m.end(), "") for m in _C_NEGATION.finditer(masked)]
        edits += [
            ("counterpart", m.start(), m.end(), _C_METHODS[m.group()])
            for m in _C_COUNTERPART.finditer(masked)
        ]
        edits += [
            ("boolean", m.start(), m.end(), "false" if m.group() == "true" else "true")
            for m in _C_BOOLEAN.finditer(masked)
        ]
        if kind_of_language == "js" and not path.endswith(_TS_SUFFIXES):
            # TypeScript can type-check the value; a type error would read as a test failing.
            edits += [
                ("return", m.start(), m.end(), "return undefined;")
                for m in _JS_RETURN.finditer(masked)
            ]
        # A `+` next to a string is concatenation: Go and Java do not build with `-` there.
        if not path.endswith(_TS_SUFFIXES) and not any(quote in masked for quote in "\"'`"):
            edits += [
                ("arithmetic", m.start(), m.end(), _ARITHMETIC[m.group()])
                for m in _C_ARITHMETIC.finditer(masked)
            ]
        edits += [
            ("constant", m.start(), m.end(), str(int(m.group()) + 1))
            for m in _C_NUMBER.finditer(masked)
        ]
        if edits:
            found[row] = [
                Mutant(path, row, kind, before, before[:start] + replacement + before[end:])
                for kind, start, end, replacement in sorted(edits, key=lambda e: KINDS.index(e[0]))
            ]
    return found


def line_mutants(path: str, source: str, lines: Sequence[int]) -> dict[int, list[Mutant]]:
    """{line: its mutants, the likeliest to show a missing check first} for `lines` of a file."""

    wanted = set(lines)
    if language(path) == "python":
        return _python_mutants(path, source, wanted)
    if language(path):
        return _c_mutants(path, source, wanted)
    return {}


def _mutated_source(source: str, mutant: Mutant) -> str:
    lines = source.splitlines(keepends=True)
    line = lines[mutant.line - 1]
    lines[mutant.line - 1] = mutant.after + line[len(line.rstrip("\r\n")) :]
    return "".join(lines)


def _builds(mutant: Mutant, source: str) -> bool:
    """False for a Python mutant that does not parse; the other languages build to tell."""

    if language(mutant.path) != "python":
        return True
    try:
        ast.parse(_mutated_source(source, mutant))
    except (SyntaxError, ValueError):
        return False
    return True


def select_mutants(
    candidates: Mapping[str, Mapping[int, Sequence[Mutant]]],
    sources: Mapping[str, str],
    limit: int,
) -> list[Mutant]:
    """At most `limit` mutants: one per line first, the lines spread over the change when there
    are more of them than the limit, then a second mutant per line, and so on."""

    lines = [(path, line) for path in sorted(candidates) for line in sorted(candidates[path])]
    if limit <= 0 or not lines:
        return []
    if len(lines) > limit:
        lines = [lines[i * len(lines) // limit] for i in range(limit)]
    queues = {key: list(candidates[key[0]][key[1]]) for key in lines}
    chosen: list[Mutant] = []
    while len(chosen) < limit and any(queues.values()):
        for key in lines:
            queue = queues[key]
            while queue:
                mutant = queue.pop(0)
                if _builds(mutant, sources[mutant.path]):
                    chosen.append(mutant)
                    break
            if len(chosen) >= limit:
                break
    return chosen


def _write(file: Path, data: bytes) -> None:
    file.write_bytes(data)
    if file.suffix == ".py":
        # Python keeps a compiled copy keyed on the file's size and modification second, which
        # a mutant written back within the same second can share.
        for compiled in (file.parent / "__pycache__").glob(f"{file.stem}.*.pyc"):
            compiled.unlink(missing_ok=True)


@contextmanager
def applied(workspace: Path, mutant: Mutant) -> Iterator[None]:
    """The mutant written into the clone, and the file put back after."""

    file = workspace / mutant.path
    original = file.read_bytes()
    _write(file, _mutated_source(original.decode("utf-8"), mutant).encode("utf-8"))
    try:
        yield
    finally:
        _write(file, original)


def outcome(run: Mapping[str, Any], ignore: Collection[str] = ()) -> tuple[str, str]:
    """(killed | survived | timed_out | not_built | unfinished, the first test that failed).
    `unfinished`: the run was stopped because the time budget ended, so it tells nothing. A test
    in `ignore` (one that fails without the mutant too) failing does not kill it."""

    if run.get("unfinished"):
        return "unfinished", ""
    if run.get("timed_out"):
        return "timed_out", ""
    outcomes: Mapping[str, str] = run.get("outcomes") or {}
    failed = sorted(
        test for test, result in outcomes.items() if result == "failed" and test not in ignore
    )
    tests = [test for test in failed if not test.startswith("::")]
    if tests:
        return "killed", tests[0]
    # `::package` / `::module` stand for code that did not build (or a module that did not
    # load): no test ran against the mutant.
    if failed or not any(test not in ignore for test in outcomes):
        return "not_built", ""
    return "survived", ""


def not_mutated(
    reason: str, *, minimum: float = 0.0, max_mutants: int = DEFAULT_MAX_MUTANTS
) -> JsonObject:
    return {
        "ran": False,
        "reason": reason,
        "minimum": minimum,
        "max_mutants": max_mutants,
        "lines": 0,
        "lines_mutated": 0,
        "mutants": [],
        "killed": 0,
        "survived": 0,
        "timed_out": 0,
        "not_built": 0,
        "unfinished": 0,
        "score": None,
        "seconds": 0.0,
        "selected": 0,
        "max_seconds": None,
        "not_started": 0,
        "left_out": 0,
    }


def summarize(
    results: Sequence[tuple[Mutant, str, str]],
    *,
    lines: int,
    selected: Sequence[int | None] = (),
    minimum: float = 0.0,
    max_mutants: int = DEFAULT_MAX_MUTANTS,
    seconds: float = 0.0,
    max_seconds: float | None = None,
    not_started: int = 0,
    left_out: int = 0,
) -> JsonObject:
    counts = {name: 0 for name in ("killed", "survived", "timed_out", "not_built", "unfinished")}
    for _, result, _ in results:
        counts[result] += 1
    caught = counts["killed"] + counts["timed_out"]
    judged = caught + counts["survived"]
    return {
        "ran": True,
        "reason": "",
        "minimum": minimum,
        "max_mutants": max_mutants,
        "lines": lines,
        "lines_mutated": len({(mutant.path, mutant.line) for mutant, _, _ in results}),
        "mutants": [
            {
                "path": mutant.path,
                "line": mutant.line,
                "kind": mutant.kind,
                "before": _short(mutant.before),
                "after": _short(mutant.after),
                "outcome": result,
                "test": test,
                "hint": HINTS.get(mutant.kind, ""),
                # How many tests ran on it: the ones that ran its line (None: the whole command).
                "tests": tests,
            }
            for (mutant, result, test), tests in zip(
                results, [*selected, *([None] * (len(results) - len(selected)))], strict=True
            )
        ],
        "selected": sum(1 for tests in selected if tests is not None),
        **counts,
        "score": round(100.0 * caught / judged, 1) if judged else None,
        "seconds": round(seconds, 1),
        # The time budget, and the chosen mutants it left no time for.
        "max_seconds": max_seconds,
        "not_started": not_started,
        # The tests that failed before the change too, which no mutant run counted.
        "left_out": left_out,
    }


def mutate_changed_lines(
    *,
    workspace: Path,
    lines: Mapping[str, Sequence[int]],
    head_run: Mapping[str, Any],
    run: Callable[[Mutant], Mapping[str, Any]],
    max_mutants: int = DEFAULT_MAX_MUTANTS,
    minimum: float = 0.0,
    max_seconds: float | None = None,
    clock: Callable[[], float] = time.monotonic,
    known_failures: Collection[str] = (),
) -> JsonObject:
    """Mutate `lines` ({path: line numbers}, the changed lines the tests run) in the clone at
    the change, run the tests on each mutant with `run(mutant)`, and summarize. A run result's
    `selected` is how many tests it ran when it ran a selection (None: all of them). Once
    `max_seconds` have gone, no further mutant starts (one already running finishes).
    `known_failures` are tests that failed before the change too: `run` leaves them out, and
    they neither stop the mutants nor kill one."""

    outcomes: Mapping[str, str] = head_run.get("outcomes") or {}
    failed = {test for test, result in outcomes.items() if result == "failed"}
    if head_run.get("timed_out") or not outcomes or failed - set(known_failures):
        # A mutant is killed when a test that passed fails: that needs every other test passing.
        return not_mutated(
            "not every test passes on the change", minimum=minimum, max_mutants=max_mutants
        )
    sources: dict[str, str] = {}
    candidates: dict[str, dict[int, list[Mutant]]] = {}
    for path, numbers in sorted(lines.items()):
        file = workspace / path
        if not numbers or not language(path) or not file.is_file():
            continue
        try:
            sources[path] = file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        found = line_mutants(path, sources[path], numbers)
        if found:
            candidates[path] = found
    started = clock()
    results: list[tuple[Mutant, str, str]] = []
    selected: list[int | None] = []
    chosen = select_mutants(candidates, sources, max_mutants)
    for mutant in chosen:
        if max_seconds is not None and clock() - started >= max_seconds:
            break
        with applied(workspace, mutant):
            run_result = run(mutant)
        result, test = outcome(run_result, failed)
        results.append((mutant, result, test))
        selected.append(run_result.get("selected"))
    return summarize(
        results,
        selected=selected,
        lines=sum(len(numbers) for numbers in candidates.values()),
        minimum=minimum,
        max_mutants=max_mutants,
        seconds=clock() - started,
        max_seconds=max_seconds,
        not_started=len(chosen) - len(results),
        left_out=len(failed),
    )


def survivor_items(mutation: Mapping[str, Any]) -> list[str]:
    """`path:line: before → after` for each mutant every test passed with."""

    return [
        f"{item['path']}:{item['line']}: {item['before']} → {item['after']}"
        for item in mutation.get("mutants", [])
        if item["outcome"] == "survived"
    ]


def mutation_line(mutation: Mapping[str, Any] | None) -> str:
    """One sentence for the report and the job summary (empty when there is nothing to say)."""

    if not mutation:
        return ""
    if not mutation.get("ran"):
        return f"**Mutants:** not run ({mutation.get('reason')})."
    caught = mutation["killed"] + mutation["timed_out"]
    judged = caught + mutation["survived"]
    survived = mutation["survived"]
    not_started = (mutation.get("not_started") or 0) + (mutation.get("unfinished") or 0)
    if not judged:
        # Say so when the budget left no mutant finished; nothing to say when none was made.
        return (
            f"**Mutants:** none finished: the {mutation['max_seconds']:g}-second budget ran out "
            f"({not_started} did not run or finish)."
            if not_started
            else ""
        )
    return (
        f"**Mutants:** the tests catch {caught} of {judged} mutant(s) of the changed lines "
        f"({mutation['score']:g}%)"
        + (f"; {survived} survive: no test checks what those lines do." if survived else ".")
        + (
            f" {not_started} more did not run or finish: the {mutation['max_seconds']:g}-second "
            "budget ran out."
            if not_started
            else ""
        )
        + (
            f" The {left_out} test(s) that failed before the change too were left out."
            if (left_out := mutation.get("left_out") or 0)
            else ""
        )
    )
