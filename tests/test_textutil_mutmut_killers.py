import pytest

import sdetkit.textutil as textutil
from sdetkit.textutil import parse_kv_line


def test_parse_kv_line_blank_is_empty_dict():
    assert parse_kv_line("") == {}
    assert parse_kv_line("   \t  ") == {}
    assert parse_kv_line("\r\n") == {}


def test_parse_kv_line_bad_token_valueerror_message_is_exact():
    for s in ["abc", "a=b c"]:
        with pytest.raises(ValueError) as exc:
            parse_kv_line(s)
        assert exc.value.args == ("bad token",)


def test_parse_kv_line_bad_kv_valueerror_message_is_exact():
    for s in ["a=", "=b"]:
        with pytest.raises(ValueError) as exc:
            parse_kv_line(s)
        assert exc.value.args == ("bad kv",)


def test_parse_kv_line_does_not_short_circuit_on_normalize_line_XXXX(monkeypatch):
    monkeypatch.setattr(textutil, "normalize_line", lambda _: "XXXX")
    with pytest.raises(ValueError) as exc:
        parse_kv_line("anything")
    assert exc.value.args == ("bad token",)
