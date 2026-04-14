from __future__ import annotations

import argparse


def build_serve_args(ns: argparse.Namespace) -> list[str]:
    serve_args: list[str] = []
    if ns.host:
        serve_args.extend(["--host", ns.host])
    if ns.port is not None:
        serve_args.extend(["--port", str(ns.port)])
    return serve_args
