import argparse
import inspect
import json
import sys
from collections.abc import Callable
from pathlib import Path

from .textutil import parse_kv_line


def _die(msg: str) -> "None":
    sys.stderr.write(msg.rstrip() + "\n")
    raise SystemExit(2)


def _supports_allow_comments(parser: Callable[..., dict[str, str]]) -> bool:
    try:
        sig = inspect.signature(parser)
    except (TypeError, ValueError):
        return False

    for param in sig.parameters.values():
        if param.name == "allow_comments":
            return True
    return False


def _build_comment_aware_parser(
    parser: Callable[..., dict[str, str]],
) -> Callable[[str], dict[str, str]]:
    if _supports_allow_comments(parser):
        return lambda line: parser(line, allow_comments=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="kvcli", add_help=True)
    p.add_argument("--text", default=None)
    p.add_argument("--path", default=None)
    p.add_argument("--strict", action="store_true")

    ns = p.parse_args(argv)

    if ns.text is not None and ns.path is not None:
        _die("use only one of --text or --path")

    if ns.text is not None:
        raw = ns.text
    elif ns.path is not None:
        try:
            raw = Path(ns.path).read_text(encoding="utf-8")
        except Exception:
            _die("cannot read file")
    else:
        raw = sys.stdin.read()

    parse_line = _build_comment_aware_parser(parse_kv_line)

    data: dict[str, str] = {}
    invalid_lines = 0

    for line_no, line in enumerate(raw.splitlines(), start=1):
        try:
            chunk = parse_line(line)
        except ValueError:
            invalid_lines += 1
            if ns.strict:
                _die(f"invalid input at line {line_no}")
            continue
        if chunk:
            data.update(chunk)

    if raw.strip() != "" and (not data or (ns.strict and invalid_lines > 0)):
        _die("invalid input")

    sys.stdout.write(json.dumps(data, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
