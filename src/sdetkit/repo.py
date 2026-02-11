from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .atomicio import atomic_write_text
from .security import SecurityError, safe_path

SKIP_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".hypothesis",
        ".nox",
        ".tox",
        ".venv",
        "venv",
        "node_modules",
    }
)

SKIP_FILES: frozenset[str] = frozenset({".coverage"})

BIDI_HIDDEN_CODEPOINTS: frozenset[str] = frozenset(
    {
        "\u200b",  # zero width space
        "\u200c",  # zero width non-joiner
        "\u200d",  # zero width joiner
        "\ufeff",  # zero width no-break space (BOM)
        "\u202a",  # LRE
        "\u202b",  # RLE
        "\u202c",  # PDF
        "\u202d",  # LRO
        "\u202e",  # RLO
        "\u2066",  # LRI
        "\u2067",  # RLI
        "\u2068",  # FSI
        "\u2069",  # PDI
    }
)

SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "auth_header",
        re.compile(
            r"(?i)\\b(?:authorization|x-api-key|api[_-]?key|token|password|cookie|set-cookie)\\b\\s*[:=]\\s*[^\\s]{4,}"
        ),
    ),
    ("aws_access_key", re.compile(r"\\bAKIA[0-9A-Z]{16}\\b")),
    (
        "aws_secret_key",
        re.compile(r"(?i)aws(.{0,20})?(?:secret|access).{0,5}[=:].{0,5}[A-Za-z0-9/+=]{40}"),
    ),
    (
        "private_key_header",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    ),
)


@dataclass(frozen=True)
class Finding:
    check: str
    severity: str
    path: str
    line: int
    column: int
    code: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "check": self.check,
            "code": self.code,
            "severity": self.severity,
            "path": self.path,
            "line": self.line,
            "column": self.column,
            "message": self.message,
        }


def _iter_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            d for d in dirnames if d not in SKIP_DIRS and not d.endswith(".egg-info")
        )
        for fname in sorted(filenames):
            if fname in SKIP_FILES:
                continue
            p = Path(dirpath) / fname
            if p.is_file():
                files.append(p)
    files.sort(key=lambda x: x.relative_to(root).as_posix())
    return files


def _line_for_offset(text: str, offset: int) -> tuple[int, int]:
    prefix = text[:offset]
    line = prefix.count("\n") + 1
    last_nl = prefix.rfind("\n")
    col = offset + 1 if last_nl == -1 else offset - last_nl
    return line, col


def run_checks(root: Path) -> list[Finding]:
    findings: list[Finding] = []

    for path in _iter_files(root):
        rel = path.relative_to(root).as_posix()
        try:
            data = path.read_bytes()
        except OSError as exc:
            findings.append(
                Finding("decode", "error", rel, 1, 1, "read_error", f"unable to read file: {exc}")
            )
            continue

        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            findings.append(
                Finding(
                    "decode",
                    "error",
                    rel,
                    1,
                    1,
                    "utf8_decode",
                    f"invalid UTF-8 at byte {exc.start}: {exc.reason}",
                )
            )
            continue

        if b"\r\n" in data and b"\n" in data.replace(b"\r\n", b""):
            findings.append(
                Finding(
                    "line_endings", "warn", rel, 1, 1, "mixed_eol", "mixed line endings detected"
                )
            )
        elif b"\r\n" in data:
            findings.append(
                Finding("line_endings", "warn", rel, 1, 1, "crlf_eol", "CRLF line endings detected")
            )
        elif b"\r" in data:
            findings.append(
                Finding(
                    "line_endings", "warn", rel, 1, 1, "cr_eol", "legacy CR line endings detected"
                )
            )

        lines = text.splitlines(keepends=True)
        for idx, line in enumerate(lines, start=1):
            content = line.rstrip("\r\n")
            stripped = content.rstrip(" \t")
            if content != stripped:
                findings.append(
                    Finding(
                        "trailing_whitespace",
                        "warn",
                        rel,
                        idx,
                        len(stripped) + 1,
                        "trailing_ws",
                        "trailing whitespace",
                    )
                )

        if data and not data.endswith(b"\n"):
            findings.append(
                Finding(
                    "eof_newline",
                    "warn",
                    rel,
                    max(1, len(lines)),
                    1,
                    "missing_eof_nl",
                    "missing EOF newline",
                )
            )

        for i, ch in enumerate(text):
            if ch in BIDI_HIDDEN_CODEPOINTS:
                line, col = _line_for_offset(text, i)
                findings.append(
                    Finding(
                        "hidden_unicode",
                        "error",
                        rel,
                        line,
                        col,
                        "hidden_unicode",
                        f"hidden/bidi Unicode character U+{ord(ch):04X}",
                    )
                )

        for idx, line in enumerate(text.splitlines(), start=1):
            for label, pattern in SECRET_PATTERNS:
                if pattern.search(line):
                    findings.append(
                        Finding(
                            "secret_scan",
                            "error",
                            rel,
                            idx,
                            1,
                            label,
                            f"potential secret matched pattern: {label}",
                        )
                    )

    findings.sort(key=lambda f: (f.path, f.line, f.column, f.check, f.code, f.message))
    return findings


def _severity_rank(level: str) -> int:
    return {"info": 0, "warn": 1, "error": 2}.get(level, 2)


def _score(findings: list[Finding]) -> int:
    if not findings:
        return 100
    weights = {"warn": 5, "error": 20}
    penalty = sum(weights.get(f.severity, 20) for f in findings)
    return max(0, 100 - min(100, penalty))


def _report_payload(root: Path, findings: list[Finding]) -> dict[str, Any]:
    counts = {"info": 0, "warn": 0, "error": 0}
    by_check: dict[str, int] = {}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1
        by_check[f.check] = by_check.get(f.check, 0) + 1
    return {
        "root": str(root),
        "summary": {
            "counts": {k: counts[k] for k in sorted(counts)},
            "by_check": {k: by_check[k] for k in sorted(by_check)},
            "findings": len(findings),
            "score": _score(findings),
            "ok": not findings,
        },
        "findings": [f.to_dict() for f in findings],
    }


def _render(payload: dict[str, Any], fmt: str) -> str:
    if fmt == "json":
        return json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n"
    if fmt == "md":
        lines = [
            "# sdetkit repo check report",
            "",
            f"- root: `{payload['root']}`",
            f"- score: {payload['summary']['score']}",
            f"- findings: {payload['summary']['findings']}",
            "",
            "## Findings",
        ]
        for item in payload["findings"]:
            lines.append(
                f"- `{item['severity']}` `{item['check']}` `{item['path']}:{item['line']}:{item['column']}` - {item['message']}"
            )
        return "\n".join(lines) + "\n"

    lines = [
        f"repo: {payload['root']}",
        f"score: {payload['summary']['score']}",
        f"findings: {payload['summary']['findings']}",
    ]
    for item in payload["findings"]:
        lines.append(
            f"[{item['severity']}] {item['path']}:{item['line']}:{item['column']} {item['check']}/{item['code']} {item['message']}"
        )
    return "\n".join(lines) + "\n"


def _needs_fail(findings: list[Finding], fail_on: str | None, min_score: int | None) -> bool:
    if min_score is not None and _score(findings) < min_score:
        return True
    if fail_on is None:
        return bool(findings)
    threshold = _severity_rank(fail_on)
    return any(_severity_rank(f.severity) >= threshold for f in findings)


def _fix_text(text: str, *, eol: str | None) -> str:
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    for line in lines:
        eol_part = ""
        content = line
        if line.endswith("\r\n"):
            content = line[:-2]
            eol_part = "\r\n"
        elif line.endswith("\n"):
            content = line[:-1]
            eol_part = "\n"
        elif line.endswith("\r"):
            content = line[:-1]
            eol_part = "\r"
        content = content.rstrip(" \t")
        if eol is None:
            out.append(content + eol_part)
        elif eol == "lf":
            out.append(content + ("\n" if eol_part else ""))
        else:
            out.append(content + ("\r\n" if eol_part else ""))

    fixed = "".join(out)
    if fixed and not fixed.endswith("\n") and not fixed.endswith("\r\n"):
        fixed += "\n" if eol != "crlf" else "\r\n"
    return fixed


def _apply_fixes(root: Path, *, check: bool, dry_run: bool, diff: bool, eol: str | None) -> int:
    changed = 0
    for path in _iter_files(root):
        rel = path.relative_to(root).as_posix()
        try:
            original_bytes = path.read_bytes()
            original = original_bytes.decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        fixed = _fix_text(original, eol=eol)
        if fixed == original:
            continue

        changed += 1
        if diff or check or dry_run:
            d = difflib.unified_diff(
                original.splitlines(keepends=True),
                fixed.splitlines(keepends=True),
                fromfile=f"a/{rel}",
                tofile=f"b/{rel}",
            )
            sys.stdout.write("".join(d))

        if not check and not dry_run:
            atomic_write_text(path, fixed)

    if check:
        return 1 if changed else 0
    if dry_run:
        return 0
    return 0


def _resolve_root(user_path: str, *, allow_absolute: bool) -> Path:
    base = Path.cwd().resolve()
    try:
        return safe_path(base, user_path, allow_absolute=allow_absolute)
    except SecurityError:
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sdetkit repo")
    sub = parser.add_subparsers(dest="repo_cmd", required=True)

    cp = sub.add_parser("check")
    cp.add_argument("path", nargs="?", default=".")
    cp.add_argument("--format", choices=["text", "json", "md"], default="text")
    cp.add_argument("--out", default=None)
    cp.add_argument("--force", action="store_true")
    cp.add_argument("--allow-absolute-path", action="store_true")
    cp.add_argument("--fail-on", choices=["info", "warn", "error"], default=None)
    cp.add_argument("--min-score", type=int, default=None)

    fp = sub.add_parser("fix")
    fp.add_argument("path", nargs="?", default=".")
    fp.add_argument("--check", action="store_true")
    fp.add_argument("--dry-run", action="store_true")
    fp.add_argument("--diff", action="store_true")
    fp.add_argument("--eol", choices=["lf", "crlf"], default=None)
    fp.add_argument("--force", action="store_true")
    fp.add_argument("--allow-absolute-path", action="store_true")

    ns = parser.parse_args(argv)

    try:
        root = _resolve_root(ns.path, allow_absolute=bool(ns.allow_absolute_path))
    except SecurityError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if ns.repo_cmd == "check":
        findings = run_checks(root)
        payload = _report_payload(root, findings)
        rendered = _render(payload, ns.format)
        sys.stdout.write(rendered)
        if ns.out:
            try:
                out_path = safe_path(root, ns.out, allow_absolute=bool(ns.allow_absolute_path))
                if out_path.exists() and not ns.force:
                    print("refusing to overwrite existing output (use --force)", file=sys.stderr)
                    return 2
                atomic_write_text(out_path, rendered)
            except (SecurityError, OSError, ValueError) as exc:
                print(str(exc), file=sys.stderr)
                return 2
        return 1 if _needs_fail(findings, ns.fail_on, ns.min_score) else 0

    if ns.check and ns.dry_run:
        print("cannot use --check and --dry-run together", file=sys.stderr)
        return 2
    try:
        return _apply_fixes(
            root,
            check=bool(ns.check),
            dry_run=bool(ns.dry_run),
            diff=bool(ns.diff),
            eol=ns.eol,
        )
    except OSError as exc:
        print(str(exc), file=sys.stderr)
        return 2
