"""Changed-line coverage for `sdetkit verify change`: which of a change's lines its tests run.

Passing tests say nothing about code they never reach. While the tests run on the change,
coverage is recorded (coverage.py for pytest, `go test -coverprofile` for Go), and the lines
the change adds or modifies in source files are read against it: a line that is code and that
no test ran is reported. Comments, blank lines and other non-code lines do not count.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

JsonObject = dict[str, Any]

_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def _diff_path(line: str) -> str:
    path = line[4:].rstrip("\n").split("\t")[0]
    if path.startswith('"') and path.endswith('"'):
        # git C-quotes unusual paths: octal escapes of the UTF-8 bytes.
        path = path[1:-1].encode("utf-8").decode("unicode_escape").encode("latin-1").decode("utf-8")
    return path[2:] if path.startswith("b/") else ""


def changed_lines(diff: str, keep: Callable[[str], bool]) -> dict[str, list[int]]:
    """{path: the change's line numbers that it added or modified} from a unified diff, for the
    files `keep` accepts. Deleted files have none."""

    found: dict[str, list[int]] = {}
    path = ""
    line_no = 0
    in_hunk = False
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            path, in_hunk = "", False
        elif not in_hunk and line.startswith("+++ "):
            path = _diff_path(line)
            path = path if path and keep(path) else ""
        elif line.startswith("@@"):
            match = _HUNK.match(line)
            in_hunk = bool(match)
            line_no = int(match.group(1)) if match else 0
        elif in_hunk and path:
            if line.startswith("+"):
                found.setdefault(path, []).append(line_no)
                line_no += 1
            elif line.startswith(" "):
                line_no += 1
            # "-" lines are not in the change; "\ No newline at end of file" is no line.
    return {path: sorted(set(lines)) for path, lines in found.items()}


def line_ranges(lines: Iterable[int]) -> str:
    """`3-5, 9` for 3, 4, 5, 9."""

    ordered = sorted(set(lines))
    parts: list[str] = []
    i = 0
    while i < len(ordered):
        j = i
        while j + 1 < len(ordered) and ordered[j + 1] == ordered[j] + 1:
            j += 1
        parts.append(str(ordered[i]) if i == j else f"{ordered[i]}-{ordered[j]}")
        i = j + 1
    return ", ".join(parts)


# --- coverage.py --------------------------------------------------------------------------


def coverage_rcfile(path: Path, data_file: Path, source_dirs: Sequence[Path]) -> None:
    """A coverage.py configuration of our own: the project's (thresholds, plugins) does not
    apply, and only the directories of the changed files are measured, so a changed module
    that no test imports reads as not run."""

    sources = "".join(f"\n    {directory}" for directory in source_dirs)
    path.write_text(
        "[run]\n"
        f"data_file = {data_file}\n"
        # A data file per process, so subprocesses (pytest-xdist workers) count too.
        "parallel = true\n"
        "patch = subprocess\n"
        f"source ={sources}\n"
        "disable_warnings =\n"
        "    no-data-collected\n"
        "    module-not-imported\n"
        "    module-not-measured\n",
        encoding="utf-8",
    )


def read_coverage_json(path: Path, workspace: Path) -> dict[str, tuple[set[int], set[int]]]:
    """{repository path: (code lines, lines that ran)} from `coverage json`."""

    try:
        files = json.loads(path.read_text(encoding="utf-8")).get("files", {})
    except (OSError, ValueError, AttributeError):
        return {}
    root = workspace.resolve()
    measured: dict[str, tuple[set[int], set[int]]] = {}
    for name, data in files.items():
        file = Path(name)
        file = file.resolve() if file.is_absolute() else (root / file).resolve()
        try:
            relative = file.relative_to(root).as_posix()
        except ValueError:
            continue
        ran = set(data.get("executed_lines", []))
        measured[relative] = (ran | set(data.get("missing_lines", [])), ran)
    return measured


# --- go test -coverprofile ----------------------------------------------------------------

_PROFILE_BLOCK = re.compile(r"^(.+):(\d+)\.\d+,(\d+)\.\d+ (\d+) (\d+)$")


def read_go_profile(text: str, module: str) -> dict[str, tuple[set[int], set[int]]]:
    """{repository path: (code lines, lines that ran)} from a Go cover profile."""

    measured: dict[str, tuple[set[int], set[int]]] = {}
    for line in text.splitlines():
        match = _PROFILE_BLOCK.match(line.strip())
        if not match:
            continue
        name, start, end, statements, count = match.groups()
        if module and name.startswith(f"{module}/"):
            name = name[len(module) + 1 :]
        if not int(statements):
            continue
        code, ran = measured.setdefault(name, (set(), set()))
        lines = range(int(start), int(end) + 1)
        code.update(lines)
        if int(count):
            ran.update(lines)
    return measured


# --- the summary ----------------------------------------------------------------------------


def summarize(
    changed: Mapping[str, Sequence[int]],
    measured: Mapping[str, tuple[set[int], set[int]]],
    *,
    tool: str,
    minimum: float = 0.0,
) -> JsonObject:
    """How many of the changed code lines ran, per file and in all.

    A changed file the coverage data does not know at all (no test binary or import reached
    it, and the tool could not list its code) is listed under `unmeasured`."""

    files: list[JsonObject] = []
    unmeasured: list[str] = []
    total = run = 0
    for path, lines in sorted(changed.items()):
        if path not in measured:
            unmeasured.append(path)
            continue
        code, ran = measured[path]
        changed_code = [line for line in lines if line in code]
        if not changed_code:
            continue
        not_run = [line for line in changed_code if line not in ran]
        total += len(changed_code)
        run += len(changed_code) - len(not_run)
        files.append(
            {
                "path": path,
                "changed": len(changed_code),
                "run": len(changed_code) - len(not_run),
                "not_run": not_run,
            }
        )
    return {
        "measured": True,
        "tool": tool,
        "reason": "",
        "changed_lines": total,
        "run_lines": run,
        "percent": round(100.0 * run / total, 1) if total else None,
        "minimum": minimum,
        "files": files,
        "unmeasured": unmeasured,
    }


def not_measured(reason: str, *, minimum: float = 0.0) -> JsonObject:
    return {
        "measured": False,
        "tool": "",
        "reason": reason,
        "changed_lines": 0,
        "run_lines": 0,
        "percent": None,
        "minimum": minimum,
        "files": [],
        "unmeasured": [],
    }


def not_run_items(coverage: Mapping[str, Any]) -> list[str]:
    """`path:3-5, 9` for each file with changed lines no test ran."""

    return [
        f"{item['path']}:{line_ranges(item['not_run'])}"
        for item in coverage.get("files", [])
        if item["not_run"]
    ]


def coverage_line(coverage: Mapping[str, Any] | None) -> str:
    """One sentence for the report and the job summary (empty when there is nothing to say)."""

    if not coverage:
        return ""
    if not coverage.get("measured"):
        reason = coverage.get("reason") or ""
        return f"**Changed lines:** not measured ({reason})." if reason else ""
    if not coverage["changed_lines"]:
        return ""
    return (
        f"**Changed lines:** the tests run {coverage['run_lines']} of the "
        f"{coverage['changed_lines']} changed line(s) of code ({coverage['percent']:g}%)."
    )
