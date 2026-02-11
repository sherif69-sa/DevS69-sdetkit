from __future__ import annotations

import argparse
import ast
import difflib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

INDENT_TOKEN = "<<INDENT>>"


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


def _load_json(path: str) -> Any:
    if path == "-":
        return json.loads(sys.stdin.read())
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_atomic(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _one_match(rx: re.Pattern[str], text: str, label: str) -> re.Match[str]:
    ms = list(rx.finditer(text))
    if len(ms) != 1:
        raise SystemExit(f"{label}: expected 1 match, got {len(ms)}")
    return ms[0]


def _indent_from_match(m: re.Match[str]) -> str:
    if m.lastindex:
        g1 = m.group(1)
        if isinstance(g1, str) and re.fullmatch(r"[ 	]*", g1):
            return g1
    return ""


def _apply_indent(template: str, indent: str) -> str:
    if INDENT_TOKEN not in template:
        return template
    return template.replace(INDENT_TOKEN, indent)


def _should_skip(text: str, op: dict[str, Any]) -> bool:
    v = op.get("skip_if_contains")
    if isinstance(v, str) and v:
        return bool(re.search(v, text, re.M))
    return False


def _op_insert_after(text: str, op: dict[str, Any]) -> str:
    if _should_skip(text, op):
        return text
    rx = re.compile(op["pattern"], re.M)
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
    rx = re.compile(op["pattern"], re.M)
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
    rx = re.compile(op["pattern"], re.M)
    m = _one_match(rx, text, "replace_once.pattern")
    indent = _indent_from_match(m)
    repl = _apply_indent(op["repl"], indent)
    return text[: m.start()] + m.expand(repl) + text[m.end() :]


def _op_replace_block(text: str, op: dict[str, Any]) -> str:
    if _should_skip(text, op):
        return text

    rx_start = re.compile(op["start"], re.M)
    rx_end = re.compile(op["end"], re.M)

    m0 = _one_match(rx_start, text, "replace_block.start")
    indent = _indent_from_match(m0)

    tail = text[m0.end() :]
    m1 = rx_end.search(tail)
    if not m1:
        raise SystemExit("replace_block.end: no match after start")

    include_end = bool(op.get("include_end", False))
    cut_end = m0.end() + (m1.end() if include_end else m1.start())

    new_block = _apply_indent(op["text"], indent)
    return text[: m0.start()] + new_block + text[cut_end:]


def _op_replace_or_insert_block(text: str, op: dict[str, Any]) -> str:
    if _should_skip(text, op):
        return text

    rx_start = re.compile(op["start"], re.M)
    ms = list(rx_start.finditer(text))
    if len(ms) > 1:
        raise SystemExit("replace_or_insert_block.start: expected <= 1 match")
    if len(ms) == 1:
        m0 = ms[0]
        rx_end = re.compile(op["end"], re.M)
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
        raise SystemExit("replace_or_insert_block.insert_after: required when block not found")

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
        raise SystemExit("ensure_import.name: empty")

    rx = re.compile(rf"(?m)^(?:import\s+{re.escape(name)}\b|from\s+{re.escape(name)}\s+import\b)")
    if rx.search(text):
        return text

    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        raise SystemExit(f"ensure_import: target not parseable: {e}") from None

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
        raise SystemExit("upsert_def.name: empty")
    if "text" not in op or not isinstance(op["text"], str):
        raise SystemExit("upsert_def.text: required string")

    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        raise SystemExit(f"upsert_def: target not parseable: {e}") from None

    hits: list[ast.AST] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            hits.append(node)

    if len(hits) > 1:
        raise SystemExit(f"upsert_def: multiple matches for {name}")

    new_block: str

    if len(hits) == 1:
        node = hits[0]
        start = int(getattr(node, "lineno", 0) or 0)
        end = int(getattr(node, "end_lineno", 0) or start)
        if start <= 0 or end <= 0:
            raise SystemExit(f"upsert_def: missing line info for {name}")

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
        raise SystemExit("upsert_class.name: empty")
    if "text" not in op or not isinstance(op["text"], str):
        raise SystemExit("upsert_class.text: required string")

    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        raise SystemExit(f"upsert_class: target not parseable: {e}") from None

    hits: list[ast.AST] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == name:
            hits.append(node)

    if len(hits) > 1:
        raise SystemExit(f"upsert_class: multiple matches for {name}")

    if len(hits) == 1:
        node = hits[0]
        start = int(getattr(node, "lineno", 0) or 0)
        end = int(getattr(node, "end_lineno", 0) or start)
        if start <= 0 or end <= 0:
            raise SystemExit(f"upsert_class: missing line info for {name}")

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
        raise SystemExit("upsert_method.class: empty")
    if not meth_name:
        raise SystemExit("upsert_method.name: empty")
    if "text" not in op or not isinstance(op["text"], str):
        raise SystemExit("upsert_method.text: required string")

    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        raise SystemExit(f"upsert_method: target not parseable: {e}") from None

    classes: list[ast.ClassDef] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == cls_name:
            classes.append(node)

    if len(classes) != 1:
        raise SystemExit(f"upsert_method: expected 1 class {cls_name}, got {len(classes)}")

    cls = classes[0]
    cls_start = int(getattr(cls, "lineno", 0) or 0)
    cls_end = int(getattr(cls, "end_lineno", 0) or cls_start)
    if cls_start <= 0 or cls_end <= 0:
        raise SystemExit(f"upsert_method: missing class line info for {cls_name}")

    meths: list[ast.AST] = []
    for node in getattr(cls, "body", []):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == meth_name:
            meths.append(node)

    if len(meths) > 1:
        raise SystemExit(f"upsert_method: multiple matches for {cls_name}.{meth_name}")

    lines = text.splitlines(True)

    def _ws(i: int) -> str:
        return re.match(r"^(\s*)", lines[i]).group(1)

    if len(meths) == 1:
        node = meths[0]
        start = int(getattr(node, "lineno", 0) or 0)
        end = int(getattr(node, "end_lineno", 0) or start)
        if start <= 0 or end <= 0:
            raise SystemExit(f"upsert_method: missing method line info for {cls_name}.{meth_name}")

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


def apply_ops(path: Path, ops: list[dict[str, Any]]) -> tuple[str, str]:
    old = path.read_text(encoding="utf-8")
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
            raise SystemExit(f"unknown op: {kind}")
    return old, new


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="sdetkit patch")
    ap.add_argument("spec", help="json spec path, or '-' for stdin")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ns = ap.parse_args(argv)

    spec = _load_json(ns.spec)
    spec = _normalize_spec_strings(spec)

    files = spec.get("files") if isinstance(spec, dict) else None
    if not isinstance(files, list) or not files:
        raise SystemExit("spec.files: expected non-empty list")

    any_change = False
    printed = False

    for f in files:
        if not isinstance(f, dict):
            raise SystemExit("spec.files[]: expected object")
        p = f.get("path")
        ops = f.get("ops")
        if not isinstance(p, str) or not p:
            raise SystemExit("spec.files[].path: expected string")
        if not isinstance(ops, list) or not ops:
            raise SystemExit("spec.files[].ops: expected non-empty list")

        path = Path(p)
        old, new = apply_ops(path, ops)
        if old == new:
            continue

        any_change = True
        diff = difflib.unified_diff(
            old.splitlines(True),
            new.splitlines(True),
            fromfile=str(path),
            tofile=str(path),
        )
        sys.stdout.writelines(diff)
        printed = True

        if not ns.dry_run and not ns.check:
            _write_atomic(path, new)

    if not printed:
        print("no changes")

    if ns.check and any_change:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
