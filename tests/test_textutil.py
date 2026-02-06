import pytest

from sdetkit.textutil import normalize_line, parse_kv_line


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("", ""),
        ("   ", ""),
        ("\t a \n", "a"),
        ("a", "a"),
        (" a b ", "a b"),
    ],
)
def test_normalize_line(raw, expected):
    assert normalize_line(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("", {}),
        ("   ", {}),
        ("a=1", {"a": "1"}),
        ("a=1 b=2", {"a": "1", "b": "2"}),
        ("a=1 a=2", {"a": "2"}),
        ("\n a=1 \t b=two \n", {"a": "1", "b": "two"}),
    ],
)
def test_parse_kv_line_ok(raw, expected):
    assert parse_kv_line(raw) == expected


@pytest.mark.parametrize("raw", ["a", "=", "a=", "=1", "a=1 b"])
def test_parse_kv_line_bad(raw):
    with pytest.raises(ValueError):
        parse_kv_line(raw)

def test_parse_kv_line_returns_fresh_dict_each_time():
    a = parse_kv_line("")
    b = parse_kv_line("")
    a["x"] = "1"
    assert b == {}
    assert a is not b

def test_parse_kv_line_supports_double_quoted_values_with_spaces():
    assert parse_kv_line('a="hello world" b=2') == {"a": "hello world", "b": "2"}

def test_parse_kv_line_allows_equals_inside_double_quotes():
    assert parse_kv_line('a="x=y" b=2') == {"a": "x=y", "b": "2"}
