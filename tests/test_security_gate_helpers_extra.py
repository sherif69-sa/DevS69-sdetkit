from __future__ import annotations

import ast

from sdetkit import security_gate as sg


def _call(expr: str):
    node = ast.parse(expr).body[0]
    assert isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
    return node.value


def test_ast_helper_detectors() -> None:
    c1 = _call("open('/tmp/x', 'w')")
    assert sg._call_name(c1) == "open"
    assert sg._is_write_mode_open(c1)
    assert sg._is_absolute_literal(c1)

    c2 = _call("yaml.load(data, Loader=yaml.SafeLoader)")
    assert sg._is_safe_yaml_loader(c2)

    c3 = _call("requests.get(url)")
    assert sg._looks_untrusted_path_args(c3) is False


def test_misc_helper_functions() -> None:
    assert sg._looks_like_slug("very-long-token-with-many-segments")
    assert sg._looks_like_uuid("123e4567-e89b-12d3-a456-426614174000")
    assert sg._looks_like_hex_digest("a" * 64)
    assert sg._looks_like_path("src/app.py")
    assert sg._normalized_message("  hi  ") == "hi"
    fp = sg._fingerprint("R", "p", 1, "m")
    assert isinstance(fp, str) and fp
