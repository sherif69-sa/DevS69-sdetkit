from __future__ import annotations

import argparse

from sdetkit.serve_forwarding import build_serve_args


def test_build_serve_args_with_host_and_port() -> None:
    ns = argparse.Namespace(host="0.0.0.0", port=8080)
    assert build_serve_args(ns) == ["--host", "0.0.0.0", "--port", "8080"]


def test_build_serve_args_omits_empty_values() -> None:
    ns = argparse.Namespace(host="", port=None)
    assert build_serve_args(ns) == []
