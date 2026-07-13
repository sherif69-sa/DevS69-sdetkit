from __future__ import annotations

import re
from pathlib import Path
from typing import Any

JENKINSFILE = "Jenkinsfile"
_STAGE_RE = re.compile(r"^\s*stage\s*\(\s*(['\"])(.*?)\1\s*\)\s*\{")
_STAGE_CALL_RE = re.compile(r"^\s*stage\s*\(")
_SH_CALL_RE = re.compile(r"^\s*sh(?:\s|\()")
_SCRIPT_BLOCK_RE = re.compile(r"^\s*script\s*\{")
_NODE_BLOCK_RE = re.compile(r"^\s*node\s*\{")
_LIBRARY_RE = re.compile(r"^\s*(?:@Library\b|library(?:\s|\())")


def _brace_delta(raw_line: str) -> int:
    delta = 0
    quote = ""
    escaped = False
    index = 0
    while index < len(raw_line):
        if not quote and raw_line.startswith("//", index):
            break
        if not quote and raw_line.startswith(("'''", '\"\"\"'), index):
            marker = raw_line[index : index + 3]
            closing = raw_line.find(marker, index + 3)
            if closing < 0:
                break
            index = closing + 3
            continue

        char = raw_line[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
            index += 1
            continue

        if char in {"'", '"'}:
            quote = char
        elif char == "{":
            delta += 1
        elif char == "}":
            delta -= 1
        index += 1
    return delta


def _parse_literal_sh_step(raw_line: str) -> tuple[str | None, str | None]:
    stripped = raw_line.strip()
    if not _SH_CALL_RE.match(stripped):
        return None, None

    rest = stripped[2:].lstrip()
    parenthesized = rest.startswith("(")
    if parenthesized:
        rest = rest[1:].lstrip()

    if rest.startswith(("'''", '\"\"\"')):
        return None, "multiline"
    if not rest or rest[0] not in {"'", '"'}:
        return None, "dynamic_or_unsupported"

    quote = rest[0]
    escaped = False
    closing = -1
    for index, char in enumerate(rest[1:], start=1):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == quote:
            closing = index
            break
    if closing < 0:
        return None, "dynamic_or_unsupported"

    command = rest[1:closing].strip()
    tail = rest[closing + 1 :].strip()
    if parenthesized:
        if not tail.startswith(")"):
            return None, "dynamic_or_unsupported"
        tail = tail[1:].strip()
    if tail.startswith(";"):
        tail = tail[1:].strip()
    if tail and not tail.startswith("//"):
        return None, "dynamic_or_unsupported"
    if not command:
        return None, "dynamic_or_unsupported"
    return command, None


def _context(stage: str) -> str:
    return f"stage {stage}" if stage else "pipeline"


def extract_jenkins_pipeline(root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    path = root / JENKINSFILE
    if not path.is_file():
        return [], []

    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return [], []

    commands: list[dict[str, Any]] = []
    unknowns: set[str] = set()
    current_stage = ""
    stage_depth = -1
    brace_depth = 0

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("//"):
            brace_depth += _brace_delta(raw_line)
            continue

        stage_match = _STAGE_RE.match(raw_line)
        if stage_match:
            current_stage = stage_match.group(2).strip()
            stage_depth = brace_depth + max(1, _brace_delta(raw_line))
        elif _STAGE_CALL_RE.match(raw_line):
            unknowns.add("Jenkins pipeline uses a dynamic stage declaration that was not resolved")

        if _LIBRARY_RE.match(raw_line):
            unknowns.add(
                "Jenkins shared library detected; external pipeline behavior was not resolved"
            )
        if _SCRIPT_BLOCK_RE.match(raw_line):
            unknowns.add(
                f"Jenkins {_context(current_stage)} uses a script block; Groovy behavior was not evaluated"
            )
        if _NODE_BLOCK_RE.match(raw_line):
            unknowns.add(
                "Jenkins scripted node block detected; Groovy behavior was not evaluated"
            )

        command, unresolved = _parse_literal_sh_step(raw_line)
        if command is not None:
            item: dict[str, Any] = {"command": command, "file": JENKINSFILE}
            if current_stage:
                item["stage"] = current_stage
            commands.append(item)
        elif unresolved == "multiline":
            unknowns.add(
                f"Jenkins {_context(current_stage)} has multiline sh content that was not guessed"
            )
        elif unresolved == "dynamic_or_unsupported":
            unknowns.add(
                f"Jenkins {_context(current_stage)} has dynamic or unsupported sh content that was not guessed"
            )

        brace_depth += _brace_delta(raw_line)
        if current_stage and brace_depth < stage_depth:
            current_stage = ""
            stage_depth = -1

    return commands, sorted(unknowns)
