import argparse
import inspect
import json
import sys
from collections.abc import Callable
from typing import NoReturn

from .bools import coerce_bool
from .textutil import DuplicateKeyError, parse_kv_line

if not hasattr(argparse.ArgumentParser, "_sdetkit_orig_init"):
    # Preserve the original constructor on the class so tests/monkeypatches that
    # mutate __init__ later still have a deterministic initializer to call.
    argparse.ArgumentParser._sdetkit_orig_init = argparse.ArgumentParser.__init__  # type: ignore[attr-defined]


def _die(msg: str) -> NoReturn:
    sys.stderr.write(msg.rstrip() + "\n")
    raise SystemExit(2)


def _build_comment_aware_parser(
    parser: Callable[..., dict[str, str]],
    *,
    duplicate_policy: str = "last",
) -> Callable[[str], dict[str, str]]:
    supports_allow_comments = False
    supports_duplicate_policy = False
    try:
        sig = inspect.signature(parser)
        params = sig.parameters
        supports_allow_comments = "allow_comments" in params
        supports_duplicate_policy = "duplicate_policy" in params
        if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()):
            supports_allow_comments = True
            supports_duplicate_policy = True
    except (TypeError, ValueError):
        pass

    def _wrapped(line: str) -> dict[str, str]:
        kwargs: dict[str, object] = {}
        if supports_allow_comments:
            kwargs["allow_comments"] = True
        if supports_duplicate_policy:
            kwargs["duplicate_policy"] = duplicate_policy
        if kwargs:
            return parser(line, **kwargs)
        return parser(line)

    return _wrapped


def _process(raw: str, *, strict: bool, duplicates: str) -> int:
    parse_line = _build_comment_aware_parser(
        parse_kv_line,
        duplicate_policy=duplicates,
    )

    data: dict[str, str] = {}
    invalid_lines = 0

    for line_no, line in enumerate(raw.splitlines(), start=1):
        try:
            chunk = parse_line(line)
        except DuplicateKeyError as exc:
            _die(f"{exc} at line {line_no}")
        except ValueError:
            invalid_lines += 1
            if strict:
                _die(f"invalid input at line {line_no}")
            continue
        if chunk:
            for key, value in chunk.items():
                if duplicates == "error" and key in data:
                    _die(f"duplicate key: {key} at line {line_no}")
                if duplicates == "first" and key in data:
                    continue
                data[key] = value

    if raw.strip() != "" and (not data or (strict and invalid_lines > 0)):
        _die("invalid input")

    sys.stdout.write(json.dumps(data, sort_keys=True) + "\n")
    return 0


def _read_path(path: str) -> str:
    try:
        from pathlib import Path

        return Path(path).read_text(encoding="utf-8")
    except Exception:
        _die("cannot read file")
    raise AssertionError("unreachable")


def _usage() -> str:
    return (
        "usage: kvcli [--text TEXT] [--path PATH] [--strict] "
        "[--duplicates {last,first,error}] [--help]\n\n"
        "options:\n"
        "  --text TEXT\n"
        "  --path PATH\n"
        "  --strict\n"
        "  --duplicates {last,first,error}\n"
        "  --help\n"
    )


def _parse_fast(argv: list[str]) -> dict[str, object]:
    text: str | None = None
    path: str | None = None
    strict = False
    duplicates = "last"
    i = 0
    recognized_flags = {"--help", "--strict", "--text", "--path", "--duplicates"}
    while i < len(argv):
        arg = argv[i]
        if arg == "--help":
            sys.stdout.write(_usage())
            raise SystemExit(0)
        if arg == "--strict":
            strict = True
            i += 1
            continue
        if arg in {"--text", "--path", "--duplicates"}:
            if i + 1 >= len(argv):
                sys.stderr.write(_usage())
                _die(f"argument {arg}: expected one argument")
            value = argv[i + 1]
            if value in recognized_flags:
                sys.stderr.write(_usage())
                _die(f"argument {arg}: expected one argument")
            if arg == "--text":
                text = value
            elif arg == "--path":
                path = value
            else:
                duplicates = value
            i += 2
            continue
        sys.stderr.write(_usage())
        _die(f"unrecognized arguments: {arg}")
    if duplicates not in {"last", "first", "error"}:
        sys.stderr.write(_usage())
        _die(f"argument --duplicates: invalid choice: {duplicates}")
    return {"text": text, "path": path, "strict": strict, "duplicates": duplicates}


def _run_with_options(options: dict[str, object]) -> int:
    text = options.get("text")
    path = options.get("path")
    strict = coerce_bool(options.get("strict", False), default=False)
    duplicates = str(options.get("duplicates", "last"))

    if text is not None and path is not None:
        _die("use only one of --text or --path")

    if text is not None:
        raw = str(text)
    elif path is not None:
        raw = _read_path(str(path))
    else:
        raw = sys.stdin.read()

    return _process(raw, strict=strict, duplicates=duplicates)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser.__new__(argparse.ArgumentParser)
    init_parser = getattr(
        argparse.ArgumentParser,
        "_sdetkit_orig_init",
        getattr(argparse.ArgumentParser, "init_", argparse.ArgumentParser.__init__),
    )
    init_parser(p, prog="kvcli", add_help=True)
    p.add_argument("--text", default=None)
    p.add_argument("--path", default=None)
    p.add_argument("--strict", action="store_true")
    p.add_argument(
        "--duplicates",
        choices=("last", "first", "error"),
        default="last",
        help="duplicate key behavior: last wins, first wins, or error",
    )

    ns = p.parse_args(argv)
    return _run_with_options(
        {
            "text": ns.text,
            "path": ns.path,
            "strict": ns.strict,
            "duplicates": ns.duplicates,
        }
    )


def cli_entry(argv: list[str] | None = None) -> int:
    return _run_with_options(_parse_fast(list(sys.argv[1:] if argv is None else argv)))


if __name__ in {"__main__", "main_"}:
    raise SystemExit(cli_entry())
