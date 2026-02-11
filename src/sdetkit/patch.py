from __future__ import annotations

import argparse
import ast
import difflib
import errno
import json
import os
import re
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

INDENT_TOKEN = "<<INDENT>>"
_DEFAULT_MAX_FILES = 200
_DEFAULT_MAX_BYTES_PER_FILE = 2 * 1024 * 1024
_DEFAULT_MAX_TOTAL_BYTES_CHANGED = 5 * 1024 * 1024
_DEFAULT_MAX_OP_COUNT = 5000
_DEFAULT_MAX_SPEC_BYTES = 1024 * 1024
_MAX_PATTERN_LENGTH = 2000
_MAX_MATCHES = 1000


class PatchSpecError(ValueError):
    pass


def _unescape_common(s: str) -> str:
    sent = "\x00PHBS\x00"
    s = s.replace("\\\\", sent)
    s = s.replace("\\r\\n", "\r\n")
    s = s.replace("\\n", "\n")
    s = s.replace("\\t", "\t")
    s = s.replace("\\r", "\r")
    s = s.replace(sent, "\\\\")
    return s


def _normalize_spec_strings(x: Any) -> Any:
    if isinstance(x, list):
        return [_normalize_spec_strings(v) for v in x]
    if isinstance(x, dict):
        out: dict[str, Any] = {}
        for k, v in x.items():
            if k in ("text", "repl") and isinstance(v, str):
                out[k] = _unescape_common(v)
            else:
                out[k] = _normalize_spec_strings(v)
        return out
    return x


def _load_json(path: str) -> tuple[Any, int]:
    if path == "-":
        raw = sys.stdin.read()
        return json.loads(raw), len(raw.encode("utf-8"))
    raw = Path(path).read_text(encoding="utf-8")
    return json.loads(raw), len(raw.encode("utf-8"))


def _read_text_raw(path: Path) -> str:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(path, flags)
    except OSError as e:
        if e.errno == errno.ELOOP:
            raise PatchSpecError(f"symlink target rejected: {path}") from e
        raise
    with os.fdopen(fd, "r", encoding="utf-8", newline="") as fh:
        return fh.read()


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    st = os.stat(path, follow_symlinks=False) if path.exists() else None
    if st is not None and os.path.islink(path):
        raise PatchSpecError(f"symlink target rejected: {path}")

    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        if st is not None:
            os.chmod(tmp, st.st_mode)
        if path.exists() and os.path.islink(path):
            raise PatchSpecError(f"symlink target rejected during write: {path}")
        os.replace(tmp, path)
        dir_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def _compile_regex(pattern: str, label: str) -> re.Pattern[str]:
    if len(pattern) > _MAX_PATTERN_LENGTH:
        raise PatchSpecError(f"{label}: regex pattern too long")
    try:
        return re.compile(pattern, re.M)
    except re.error as e:
        raise PatchSpecError(f"{label}: invalid regex: {e}") from e


def _find_matches(
    rx: re.Pattern[str], text: str, *, max_matches: int = _MAX_MATCHES
) -> list[re.Match[str]]:
    out: list[re.Match[str]] = []
    for m in rx.finditer(text):
        out.append(m)
        if len(out) > max_matches:
            raise PatchSpecError("regex produced too many matches")
    return out


def _one_match(rx: re.Pattern[str], text: str, label: str) -> re.Match[str]:
    ms = _find_matches(rx, text, max_matches=2)
    if len(ms) != 1:
        raise PatchSpecError(f"{label}: expected 1 match, got {len(ms)}")
    return ms[0]


def _indent_from_match(m: re.Match[str]) -> str:
    if m.lastindex:
        g1 = m.group(1)
        if isinstance(g1, str) and re.fullmatch(r"[ \t]*", g1):
            return g1
    return ""


def _apply_indent(template: str, indent: str) -> str:
    if INDENT_TOKEN not in template:
        return template
    return template.replace(INDENT_TOKEN, indent)


def _should_skip(text: str, op: dict[str, Any]) -> bool:
    v = op.get("skip_if_contains")
    if isinstance(v, str) and v:
        rx = _compile_regex(v, "skip_if_contains")
        return bool(rx.search(text))
    return False


def _op_insert_after(text: str, op: dict[str, Any]) -> str:
    if _should_skip(text, op):
        return text
    rx = _compile_regex(op["pattern"], "insert_after.pattern")
    m = _one_match(rx, text, "insert_after.pattern")
    indent = _indent_from_match(m)
    ins = _apply_indent(op["text"], indent)

    pos = m.end()
    if pos < len(text):
        if text.startswith("\r\n", pos):
            pos += 2
        elif text[pos] == "\n":
            pos += 1

    if text.startswith(ins, pos):
        return text

    return text[:pos] + ins + text[pos:]


def _op_insert_before(text: str, op: dict[str, Any]) -> str:
    if _should_skip(text, op):
        return text
    rx = _compile_regex(op["pattern"], "insert_before.pattern")
    m = _one_match(rx, text, "insert_before.pattern")
    indent = _indent_from_match(m)
    ins = _apply_indent(op["text"], indent)

    start = m.start()
    if text[max(0, start - len(ins)) : start] == ins:
        return text

    return text[:start] + ins + text[start:]


def _op_replace_once(text: str, op: dict[str, Any]) -> str:
    if _should_skip(text, op):
        return text
    rx = _compile_regex(op["pattern"], "replace_once.pattern")
    m = _one_match(rx, text, "replace_once.pattern")
    indent = _indent_from_match(m)
    repl = _apply_indent(op["repl"], indent)
    return text[: m.start()] + m.expand(repl) + text[m.end() :]


def _op_replace_block(text: str, op: dict[str, Any]) -> str:
    if _should_skip(text, op):
        return text

    rx_start = _compile_regex(op["start"], "replace_block.start")
    rx_end = _compile_regex(op["end"], "replace_block.end")

    m0 = _one_match(rx_start, text, "replace_block.start")
    indent = _indent_from_match(m0)

    tail = text[m0.end() :]
    m1 = rx_end.search(tail)
    if not m1:
        raise PatchSpecError("replace_block.end: no match after start")

    include_end = bool(op.get("include_end", False))
    cut_end = m0.end() + (m1.end() if include_end else m1.start())

    new_block = _apply_indent(op["text"], indent)
    return text[: m0.start()] + new_block + text[cut_end:]


def _op_replace_or_insert_block(text: str, op: dict[str, Any]) -> str:
    if _should_skip(text, op):
        return text

    rx_start = _compile_regex(op["start"], "replace_or_insert_block.start")
    ms = _find_matches(rx_start, text, max_matches=2)
    if len(ms) > 1:
        raise PatchSpecError("replace_or_insert_block.start: expected <= 1 match")
    if len(ms) == 1:
        m0 = ms[0]
        rx_end = _compile_regex(op["end"], "replace_or_insert_block.end")
        tail = text[m0.end() :]
        m1 = rx_end.search(tail)
        if m1:
            include_end = bool(op.get("include_end", False))
            indent = _indent_from_match(m0)
            cut_end = m0.end() + (m1.end() if include_end else m1.start())
            new_block = _apply_indent(op["text"], indent)
            return text[: m0.start()] + new_block + text[cut_end:]

    ia = op.get("insert_after")
    if not isinstance(ia, str) or not ia:
        raise PatchSpecError("replace_or_insert_block.insert_after: required when block not found")

    return _op_insert_after(
        text,
        {
            "op": "insert_after",
            "pattern": ia,
            "text": op["text"],
            "skip_if_contains": op.get("skip_if_contains"),
        },
    )


def _op_ensure_import(text: str, op: dict[str, Any]) -> str:
    if _should_skip(text, op):
        return text

    name = str(op.get("name", "")).strip()
    if not name:
        raise PatchSpecError("ensure_import.name: empty")

    rx = re.compile(rf"(?m)^(?:import\s+{re.escape(name)}\b|from\s+{re.escape(name)}\s+import\b)")
    if rx.search(text):
        return text

    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        raise PatchSpecError(f"ensure_import: target not parseable: {e}") from None

    insert_line = 1
    body = getattr(tree, "body", [])
    if body:
        first = body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(getattr(first, "value", None), ast.Constant)
            and isinstance(first.value.value, str)
        ):
            insert_line = int(getattr(first, "end_lineno", 1) or 1) + 1

        i = 1 if insert_line != 1 else 0
        while i < len(body):
            n = body[i]
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                insert_line = int(getattr(n, "end_lineno", n.lineno) or n.lineno) + 1
                i += 1
                continue
            break

    lines = text.splitlines(True)
    idx = max(0, min(len(lines), insert_line - 1))

    ins = f"import {name}\n"
    before = "".join(lines[:idx])
    after = "".join(lines[idx:])

    if before and not before.endswith("\n"):
        before += "\n"

    if (
        before
        and not before.endswith("\n\n")
        and (before.splitlines() and before.splitlines()[-1].strip() != "")
    ):
        ins = "\n" + ins

    return before + ins + after


def _op_upsert_def(text: str, op: dict[str, Any]) -> str:
    if _should_skip(text, op):
        return text
    name = str(op.get("name", "")).strip()
    if not name:
        raise PatchSpecError("upsert_def.name: empty")
    if "text" not in op or not isinstance(op["text"], str):
        raise PatchSpecError("upsert_def.text: required string")

    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        raise PatchSpecError(f"upsert_def: target not parseable: {e}") from None

    hits: list[ast.AST] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            hits.append(node)

    if len(hits) > 1:
        raise PatchSpecError(f"upsert_def: multiple matches for {name}")

    new_block: str

    if len(hits) == 1:
        node = hits[0]
        start = int(getattr(node, "lineno", 0) or 0)
        end = int(getattr(node, "end_lineno", 0) or start)
        if start <= 0 or end <= 0:
            raise PatchSpecError(f"upsert_def: missing line info for {name}")

        decos = getattr(node, "decorator_list", None)
        if decos:
            ds = [int(getattr(d, "lineno", 0) or 0) for d in decos]
            ds = [x for x in ds if x > 0]
            if ds:
                start = min(start, *ds)

        lines = text.splitlines(True)
        indent = re.match(r"^(\s*)", lines[start - 1]).group(1)

        new_block = _apply_indent(op["text"], indent)
        if not new_block.endswith("\n"):
            new_block += "\n"

        lines[start - 1 : end] = [new_block]
        return "".join(lines)

    insert_after = op.get("insert_after")
    if isinstance(insert_after, str) and insert_after:
        return _op_insert_after(
            text,
            {
                "op": "insert_after",
                "pattern": insert_after,
                "text": op["text"],
                "skip_if_contains": op.get("skip_if_contains"),
            },
        )

    lines = text.splitlines(True)

    insert_line = 1
    body = getattr(tree, "body", [])
    if body:
        first = body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(getattr(first, "value", None), ast.Constant)
            and isinstance(first.value.value, str)
        ):
            insert_line = int(getattr(first, "end_lineno", 1) or 1) + 1

        i = 1 if insert_line != 1 else 0
        while i < len(body):
            n = body[i]
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                insert_line = int(getattr(n, "end_lineno", n.lineno) or n.lineno) + 1
                i += 1
                continue
            break

    idx = max(0, min(len(lines), insert_line - 1))
    new_block = _apply_indent(op["text"], "")
    if not new_block.endswith("\n"):
        new_block += "\n"

    before = "".join(lines[:idx])
    after = "".join(lines[idx:])

    if before and not before.endswith("\n\n"):
        if before.endswith("\n"):
            new_block = "\n" + new_block
        else:
            new_block = "\n\n" + new_block

    return before + new_block + after


def _op_upsert_class(text: str, op: dict[str, Any]) -> str:
    if _should_skip(text, op):
        return text
    name = str(op.get("name", "")).strip()
    if not name:
        raise PatchSpecError("upsert_class.name: empty")
    if "text" not in op or not isinstance(op["text"], str):
        raise PatchSpecError("upsert_class.text: required string")

    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        raise PatchSpecError(f"upsert_class: target not parseable: {e}") from None

    hits: list[ast.AST] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == name:
            hits.append(node)

    if len(hits) > 1:
        raise PatchSpecError(f"upsert_class: multiple matches for {name}")

    if len(hits) == 1:
        node = hits[0]
        start = int(getattr(node, "lineno", 0) or 0)
        end = int(getattr(node, "end_lineno", 0) or start)
        if start <= 0 or end <= 0:
            raise PatchSpecError(f"upsert_class: missing line info for {name}")

        decos = getattr(node, "decorator_list", None)
        if decos:
            ds = [int(getattr(d, "lineno", 0) or 0) for d in decos]
            ds = [x for x in ds if x > 0]
            if ds:
                start = min(start, *ds)

        lines = text.splitlines(True)
        indent = re.match(r"^(\s*)", lines[start - 1]).group(1)

        new_block = _apply_indent(op["text"], indent)
        if not new_block.endswith("\n"):
            new_block += "\n"

        lines[start - 1 : end] = [new_block]
        return "".join(lines)

    insert_after = op.get("insert_after")
    if isinstance(insert_after, str) and insert_after:
        return _op_insert_after(
            text,
            {
                "op": "insert_after",
                "pattern": insert_after,
                "text": op["text"],
                "skip_if_contains": op.get("skip_if_contains"),
            },
        )

    lines = text.splitlines(True)

    insert_line = 1
    body = getattr(tree, "body", [])
    if body:
        first = body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(getattr(first, "value", None), ast.Constant)
            and isinstance(first.value.value, str)
        ):
            insert_line = int(getattr(first, "end_lineno", 1) or 1) + 1

        i = 1 if insert_line != 1 else 0
        while i < len(body):
            n = body[i]
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                insert_line = int(getattr(n, "end_lineno", n.lineno) or n.lineno) + 1
                i += 1
                continue
            break

    idx = max(0, min(len(lines), insert_line - 1))
    new_block = _apply_indent(op["text"], "")
    if not new_block.endswith("\n"):
        new_block += "\n"

    before = "".join(lines[:idx])
    after = "".join(lines[idx:])

    if before and not before.endswith("\n\n"):
        if before.endswith("\n"):
            new_block = "\n" + new_block
        else:
            new_block = "\n\n" + new_block

    return before + new_block + after


def _op_upsert_method(text: str, op: dict[str, Any]) -> str:
    if _should_skip(text, op):
        return text

    cls_name = str(op.get("class", "")).strip()
    meth_name = str(op.get("name", "")).strip()
    if not cls_name:
        raise PatchSpecError("upsert_method.class: empty")
    if not meth_name:
        raise PatchSpecError("upsert_method.name: empty")
    if "text" not in op or not isinstance(op["text"], str):
        raise PatchSpecError("upsert_method.text: required string")

    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        raise PatchSpecError(f"upsert_method: target not parseable: {e}") from None

    classes: list[ast.ClassDef] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == cls_name:
            classes.append(node)

    if len(classes) != 1:
        raise PatchSpecError(f"upsert_method: expected 1 class {cls_name}, got {len(classes)}")

    cls = classes[0]
    cls_start = int(getattr(cls, "lineno", 0) or 0)
    cls_end = int(getattr(cls, "end_lineno", 0) or cls_start)
    if cls_start <= 0 or cls_end <= 0:
        raise PatchSpecError(f"upsert_method: missing class line info for {cls_name}")

    meths: list[ast.AST] = []
    for node in getattr(cls, "body", []):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == meth_name:
            meths.append(node)

    if len(meths) > 1:
        raise PatchSpecError(f"upsert_method: multiple matches for {cls_name}.{meth_name}")

    lines = text.splitlines(True)

    def _ws(i: int) -> str:
        return re.match(r"^(\s*)", lines[i]).group(1)

    if len(meths) == 1:
        node = meths[0]
        start = int(getattr(node, "lineno", 0) or 0)
        end = int(getattr(node, "end_lineno", 0) or start)
        if start <= 0 or end <= 0:
            raise PatchSpecError(
                f"upsert_method: missing method line info for {cls_name}.{meth_name}"
            )

        decos = getattr(node, "decorator_list", None)
        if decos:
            ds = [int(getattr(d, "lineno", 0) or 0) for d in decos]
            ds = [x for x in ds if x > 0]
            if ds:
                start = min(start, *ds)

        indent = _ws(start - 1)
        new_block = _apply_indent(op["text"], indent)
        if not new_block.endswith("\n"):
            new_block += "\n"
        lines[start - 1 : end] = [new_block]
        return "".join(lines)

    class_indent = _ws(cls_start - 1)
    body_indent = None
    for i in range(cls_start, min(len(lines), cls_end)):
        ln = lines[i]
        if ln.strip() == "" or ln.lstrip().startswith("#"):
            continue
        ind = _ws(i)
        if len(ind) > len(class_indent):
            body_indent = ind
            break
    if body_indent is None:
        body_indent = class_indent + " " * 4

    new_block = _apply_indent(op["text"], body_indent)
    if not new_block.endswith("\n"):
        new_block += "\n"

    insert_at = max(0, min(len(lines), cls_end))
    if insert_at > 0 and not lines[insert_at - 1].endswith("\n\n"):
        if lines[insert_at - 1].endswith("\n"):
            new_block = "\n" + new_block
        else:
            new_block = "\n\n" + new_block

    lines[insert_at:insert_at] = [new_block]
    return "".join(lines)


def _normalize_rel_path(raw_path: str) -> str:
    if not isinstance(raw_path, str) or raw_path.strip() == "":
        raise PatchSpecError("spec.files[].path: expected non-empty string")
    if "\x00" in raw_path:
        raise PatchSpecError("spec.files[].path: contains NUL byte")
    path = raw_path.replace("\\", "/")
    if path.startswith("/") or path.startswith("//"):
        raise PatchSpecError(f"unsafe path rejected: {raw_path}")
    if re.match(r"^[A-Za-z]:", path):
        raise PatchSpecError(f"unsafe path rejected: {raw_path}")
    pp = PurePosixPath(path)
    if str(pp) in ("", "."):
        raise PatchSpecError(f"unsafe path rejected: {raw_path}")
    if any(part in ("", ".", "..") for part in pp.parts):
        raise PatchSpecError(f"unsafe path rejected: {raw_path}")
    return pp.as_posix()


def _resolve_target(root: Path, rel_path: str, allow_symlinks: bool) -> Path:
    root_real = root.resolve(strict=True)
    target = root_real / Path(rel_path)

    cursor = root_real
    for part in Path(rel_path).parts[:-1]:
        cursor = cursor / part
        if cursor.exists() and cursor.is_symlink() and not allow_symlinks:
            raise PatchSpecError(f"symlink parent rejected: {rel_path}")

    if target.exists() and target.is_symlink() and not allow_symlinks:
        raise PatchSpecError(f"symlink target rejected: {rel_path}")

    resolved = target.resolve(strict=False)
    if resolved != root_real and root_real not in resolved.parents:
        raise PatchSpecError(f"path escapes root: {rel_path}")
    return target


def _count_changed_bytes(old: str, new: str) -> int:
    changed = 0
    for line in difflib.ndiff(old.splitlines(True), new.splitlines(True)):
        if line.startswith("+ ") or line.startswith("- "):
            changed += len(line[2:].encode("utf-8"))
    return changed


def _validate_op(op: Any) -> dict[str, Any]:
    if not isinstance(op, dict):
        raise PatchSpecError("spec.files[].ops[]: expected object")
    kind = op.get("op")
    if not isinstance(kind, str) or not kind:
        raise PatchSpecError("spec.files[].ops[].op: expected non-empty string")

    allowed: dict[str, set[str]] = {
        "insert_after": {"op", "pattern", "text", "skip_if_contains"},
        "insert_before": {"op", "pattern", "text", "skip_if_contains"},
        "replace_once": {"op", "pattern", "repl", "skip_if_contains"},
        "replace_block": {"op", "start", "end", "text", "include_end", "skip_if_contains"},
        "replace_or_insert_block": {
            "op",
            "start",
            "end",
            "text",
            "include_end",
            "insert_after",
            "skip_if_contains",
        },
        "ensure_import": {"op", "name", "skip_if_contains"},
        "upsert_def": {"op", "name", "text", "insert_after", "skip_if_contains"},
        "upsert_class": {"op", "name", "text", "insert_after", "skip_if_contains"},
        "upsert_method": {"op", "class", "name", "text", "skip_if_contains"},
    }
    req: dict[str, set[str]] = {
        "insert_after": {"pattern", "text"},
        "insert_before": {"pattern", "text"},
        "replace_once": {"pattern", "repl"},
        "replace_block": {"start", "end", "text"},
        "replace_or_insert_block": {"start", "end", "text"},
        "ensure_import": {"name"},
        "upsert_def": {"name", "text"},
        "upsert_class": {"name", "text"},
        "upsert_method": {"class", "name", "text"},
    }

    if kind not in allowed:
        raise PatchSpecError(f"unknown op: {kind}")

    extra = set(op.keys()) - allowed[kind]
    if extra:
        extras = ", ".join(sorted(extra))
        raise PatchSpecError(f"{kind}: unknown keys: {extras}")

    missing = req[kind] - set(op.keys())
    if missing:
        miss = ", ".join(sorted(missing))
        raise PatchSpecError(f"{kind}: missing required keys: {miss}")

    for key in req[kind]:
        if not isinstance(op[key], str) or op[key] == "":
            raise PatchSpecError(f"{kind}.{key}: expected non-empty string")

    if "include_end" in op and not isinstance(op["include_end"], bool):
        raise PatchSpecError(f"{kind}.include_end: expected boolean")
    if "skip_if_contains" in op and not isinstance(op["skip_if_contains"], str):
        raise PatchSpecError(f"{kind}.skip_if_contains: expected string")

    return op


def _normalize_files(spec: dict[str, Any]) -> list[dict[str, Any]]:
    files = spec.get("files")
    entries: list[dict[str, Any]] = []

    if isinstance(files, dict):
        for path, ops in files.items():
            entries.append({"path": path, "ops": ops})
    elif isinstance(files, list):
        entries = list(files)
    else:
        raise PatchSpecError("spec.files: expected non-empty list or object")

    if not entries:
        raise PatchSpecError("spec.files: expected non-empty list or object")

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise PatchSpecError("spec.files[]: expected object")
        if set(entry.keys()) - {"path", "ops"}:
            extra = ", ".join(sorted(set(entry.keys()) - {"path", "ops"}))
            raise PatchSpecError(f"spec.files[]: unknown keys: {extra}")

        rel_path = _normalize_rel_path(entry.get("path"))
        ops = entry.get("ops")
        if not isinstance(ops, list) or not ops:
            raise PatchSpecError("spec.files[].ops: expected non-empty list")

        if rel_path in seen:
            raise PatchSpecError(f"spec.files[]: duplicate path: {rel_path}")
        seen.add(rel_path)

        normalized.append({"path": rel_path, "ops": [_validate_op(op) for op in ops]})

    normalized.sort(key=lambda x: x["path"])
    return normalized


def _validate_spec(spec: Any) -> list[dict[str, Any]]:
    if not isinstance(spec, dict):
        raise PatchSpecError("spec: expected object")
    if set(spec.keys()) - {"spec_version", "files"}:
        extra = ", ".join(sorted(set(spec.keys()) - {"spec_version", "files"}))
        raise PatchSpecError(f"spec: unknown keys: {extra}")

    version = spec.get("spec_version", 1)
    if version != 1:
        raise PatchSpecError("spec.spec_version: expected integer value 1")

    return _normalize_files(spec)


def apply_ops(path: Path, ops: list[dict[str, Any]]) -> tuple[str, str]:
    old = _read_text_raw(path)
    new = old
    for op in ops:
        kind = op["op"]
        if kind == "insert_after":
            new = _op_insert_after(new, op)
        elif kind == "insert_before":
            new = _op_insert_before(new, op)
        elif kind == "replace_once":
            new = _op_replace_once(new, op)
        elif kind == "replace_block":
            new = _op_replace_block(new, op)
        elif kind == "replace_or_insert_block":
            new = _op_replace_or_insert_block(new, op)
        elif kind == "ensure_import":
            new = _op_ensure_import(new, op)
        elif kind == "upsert_def":
            new = _op_upsert_def(new, op)
        elif kind == "upsert_class":
            new = _op_upsert_class(new, op)
        elif kind == "upsert_method":
            new = _op_upsert_method(new, op)
        else:
            raise PatchSpecError(f"unknown op: {kind}")
    return old, new


def _write_report(path: str, report: dict[str, Any]) -> None:
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if path == "-":
        sys.stdout.write(payload)
        return
    Path(path).write_text(payload, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="sdetkit patch")
    ap.add_argument("spec", help="json spec path, or '-' for stdin")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--root", default=".", help="Project root confinement path")
    ap.add_argument("--allow-symlinks", action="store_true")
    ap.add_argument("--max-files", type=int, default=_DEFAULT_MAX_FILES)
    ap.add_argument("--max-bytes-per-file", type=int, default=_DEFAULT_MAX_BYTES_PER_FILE)
    ap.add_argument("--max-total-bytes-changed", type=int, default=_DEFAULT_MAX_TOTAL_BYTES_CHANGED)
    ap.add_argument("--max-op-count", type=int, default=_DEFAULT_MAX_OP_COUNT)
    ap.add_argument("--max-spec-bytes", type=int, default=_DEFAULT_MAX_SPEC_BYTES)
    ap.add_argument(
        "--report-json", default=None, help="Write operation report to path or '-' for stdout"
    )
    ns = ap.parse_args(argv)

    report: dict[str, Any] = {
        "files_touched": [],
        "operations_applied": 0,
        "safety_checks": [
            "spec_version",
            "path_validation",
            "symlink_policy",
            "resource_limits",
            "spec_size_limit",
            "atomic_write",
        ],
        "status_code": 2,
    }

    try:
        if ns.max_files <= 0:
            raise PatchSpecError("--max-files must be > 0")
        if ns.max_bytes_per_file <= 0:
            raise PatchSpecError("--max-bytes-per-file must be > 0")
        if ns.max_total_bytes_changed <= 0:
            raise PatchSpecError("--max-total-bytes-changed must be > 0")
        if ns.max_op_count <= 0:
            raise PatchSpecError("--max-op-count must be > 0")
        if ns.max_spec_bytes <= 0:
            raise PatchSpecError("--max-spec-bytes must be > 0")

        root = Path(ns.root).resolve(strict=True)
        if not root.is_dir():
            raise PatchSpecError("--root must resolve to a directory")

        raw_spec, spec_bytes = _load_json(ns.spec)
        if spec_bytes > ns.max_spec_bytes:
            raise PatchSpecError(f"spec exceeds max bytes ({ns.max_spec_bytes})")
        spec = _normalize_spec_strings(raw_spec)
        files = _validate_spec(spec)

        total_ops = sum(len(item["ops"]) for item in files)
        if len(files) > ns.max_files:
            raise PatchSpecError(f"spec exceeds max files ({ns.max_files})")
        if total_ops > ns.max_op_count:
            raise PatchSpecError(f"spec exceeds max op count ({ns.max_op_count})")

        any_change = False
        printed = False
        total_changed_bytes = 0

        for f in files:
            path = _resolve_target(root, f["path"], allow_symlinks=ns.allow_symlinks)
            if not path.exists():
                raise PatchSpecError(f"target file does not exist: {f['path']}")
            old, new = apply_ops(path, f["ops"])
            if len(old.encode("utf-8")) > ns.max_bytes_per_file:
                raise PatchSpecError(f"file exceeds max size: {f['path']}")
            if old == new:
                continue

            any_change = True
            total_changed_bytes += _count_changed_bytes(old, new)
            if total_changed_bytes > ns.max_total_bytes_changed:
                raise PatchSpecError(
                    f"changes exceed max total bytes ({ns.max_total_bytes_changed})"
                )

            diff = difflib.unified_diff(
                old.splitlines(True),
                new.splitlines(True),
                fromfile=f["path"],
                tofile=f["path"],
                lineterm="",
            )
            for line in diff:
                sys.stdout.write(f"{line}\n")
            printed = True
            report["files_touched"].append(f["path"])
            report["operations_applied"] += len(f["ops"])

            if not ns.dry_run and not ns.check:
                _write_atomic(path, new)

        if not printed:
            print("no changes")

        rc = 1 if ns.check and any_change else 0
        report["status_code"] = rc
    except (PatchSpecError, json.JSONDecodeError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        rc = 2
        report["status_code"] = rc

    if ns.report_json:
        _write_report(ns.report_json, report)

    return rc


if __name__ == "__main__":
    raise SystemExit(main())
