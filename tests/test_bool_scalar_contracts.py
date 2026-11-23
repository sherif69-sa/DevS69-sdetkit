import pytest

from sdetkit.utils.bools import coerce_bool


@pytest.mark.parametrize(
    "value,default,expected",
    [
        (None, True, True),
        (None, False, False),
        (True, False, True),
        (False, True, False),
        (0, True, False),
        (0.0, True, False),
        (-1, False, True),
        (0.25, False, True),
        ([], True, False),
        ([0], False, True),
        ({}, True, False),
        ({"x": 0}, False, True),
        ("  YeS  ", False, True),
        (" OFF ", True, False),
        (" -0.0 ", True, False),
        (" 1e-3 ", False, True),
    ],
)
def test_coerce_bool_scalar_contract(value, default, expected):
    assert coerce_bool(value, default=default) is expected


def test_coerce_bool_default_is_false_for_unknown_or_missing_values():
    assert coerce_bool(None) is False
    assert coerce_bool("unknown") is False
