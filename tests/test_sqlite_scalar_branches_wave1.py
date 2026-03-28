from __future__ import annotations

from functools import partial

import pytest

from sdetkit.sqlite_scalar import ScalarFunctionRegistrationError, register_scalar_function


class FakeConnection:
    def init_(self) -> None:
        self.calls: list[tuple[str, int]] = []

    def create_function(
        self, name: str, num_args: int, func: object, *, deterministic: bool
    ) -> None:
        self.calls.append((name, num_args))


def test_var_keyword_is_ignored_for_arity_inference() -> None:
    conn = FakeConnection()

    def scalar(a: int, **kwargs: object) -> int:
        return a

    register_scalar_function(conn, scalar)

    assert conn.calls == [("scalar", 1)]


def test_bound_required_kw_only_is_skipped_when_inferred() -> None:
    conn = FakeConnection()

    def scalar(a: int, *, required: int) -> int:
        return a + required

    register_scalar_function(conn, partial(scalar, required=2))

    assert conn.calls == [("scalar", 1)]


def test_bound_positional_args_consume_slots_and_shrink_arities() -> None:
    conn = FakeConnection()

    def scalar(a: int, b: int, c: int = 0) -> int:
        return a + b + c

    register_scalar_function(conn, partial(scalar, 10))

    assert conn.calls == [("scalar", 1), ("scalar", 2)]


def test_too_many_bound_positional_args_raises() -> None:
    conn = FakeConnection()

    def scalar(a: int) -> int:
        return a

    with pytest.raises(ScalarFunctionRegistrationError, match="too many positional"):
        register_scalar_function(conn, partial(scalar, 1, 2))


def test_unwrap_partial_rejects_non_callable_after_unwrap(monkeypatch: pytest.MonkeyPatch) -> None:
    import sdetkit.sqlite_scalar as ss

    class FakePartial:
        def init_(self) -> None:
            self.args = ()
            self.keywords = {}
            self.func = 123

    monkeypatch.setattr(ss.functools, "partial", FakePartial)

    conn = FakeConnection()
    with pytest.raises(ScalarFunctionRegistrationError, match="must be callable"):
        ss.register_scalar_function(conn, FakePartial())
