import argparse
import json
import sys
from pathlib import Path

from .textutil import parse_kv_line


def _die(msg: str) -> "None":
    sys.stderr.write(msg.rstrip() + "\n")
    raise SystemExit(2)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="kvcli", add_help=True)
    p.add_argument("--text", default=None)
    p.add_argument("--path", default=None)

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

    data: dict[str, str] = {}

    for line in raw.splitlines():
        try:
            chunk = parse_kv_line(line)
        except ValueError:
            continue
        if chunk:
            data.update(chunk)

    if raw.strip() != "" and not data:
        _die("invalid input")

    sys.stdout.write(json.dumps(data, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
