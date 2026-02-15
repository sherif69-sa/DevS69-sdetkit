from __future__ import annotations

from functools import partial

import pytest

from sdetkit.sqlite_scalar import ScalarFunctionRegistrationError, register_scalar_function


class FakeConnection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int, object, bool]] = []

    def create_function(
        self, name: str, num_args: int, func: object, *, deterministic: bool
    ) -> None:
        self.calls.append((name, num_args, func, deterministic))


def test_infers_positional_arities_from_signature_defaults_and_positional_only() -> None:
    conn = FakeConnection()

    def scalar(a: int, /, b: int, c: int = 1, *, flag: bool = False) -> int:
        return a + b + c + int(flag)

    returned = register_scalar_function(conn, scalar)

    assert returned is scalar
    assert [(name, arity) for name, arity, _, _ in conn.calls] == [
        ("scalar", 2),
        ("scalar", 3),
    ]


def test_required_kw_only_must_be_bound_when_registering() -> None:
    conn = FakeConnection()

    def scalar(a: int, *, required: int) -> int:
        return a + required

    with pytest.raises(ScalarFunctionRegistrationError, match="required keyword-only"):
        register_scalar_function(conn, scalar)


def test_nested_partials_apply_bound_arguments_and_keep_gaps() -> None:
    conn = FakeConnection()

    def scalar(a: int, b: int, c: int = 0, d: int = 1) -> int:
        return a + b + c + d

    nested = partial(partial(scalar, b=2), d=4)
    register_scalar_function(conn, nested)

    assert [(name, arity) for name, arity, _, _ in conn.calls] == [
        ("scalar", 1),
        ("scalar", 2),
    ]


def test_kw_only_defaults_never_add_arities() -> None:
    conn = FakeConnection()

    def scalar(a: int = 1, *, mode: str = "strict") -> int:
        return a

    register_scalar_function(conn, scalar)

    assert [(name, arity) for name, arity, _, _ in conn.calls] == [
        ("scalar", 0),
        ("scalar", 1),
    ]


def test_num_args_override_takes_precedence_over_inference() -> None:
    conn = FakeConnection()

    def scalar(a: int, b: int = 1) -> int:
        return a + b

    register_scalar_function(conn, scalar, num_args=5)

    assert [(name, arity) for name, arity, _, _ in conn.calls] == [("scalar", 5)]


def test_num_args_negative_one_registers_varargs() -> None:
    conn = FakeConnection()

    def scalar(a: int) -> int:
        return a

    register_scalar_function(conn, scalar, num_args=-1)

    assert [(name, arity) for name, arity, _, _ in conn.calls] == [("scalar", -1)]


def test_invalid_num_args_raises() -> None:
    conn = FakeConnection()

    def scalar() -> int:
        return 1

    with pytest.raises(ScalarFunctionRegistrationError, match="num_args"):
        register_scalar_function(conn, scalar, num_args=-2)


def test_decorator_forms_return_original_callable() -> None:
    conn = FakeConnection()

    @register_scalar_function(conn)
    def one(a: int) -> int:
        return a

    @register_scalar_function(conn, name="explicit_name")
    def two(a: int, b: int = 0) -> int:
        return a + b

    assert one.__name__ == "one"
    assert two.__name__ == "two"
    assert [(name, arity) for name, arity, _, _ in conn.calls] == [
        ("one", 1),
        ("explicit_name", 1),
        ("explicit_name", 2),
    ]


def test_default_name_uses_partial_base_callable() -> None:
    conn = FakeConnection()

    def target(a: int, b: int = 0) -> int:
        return a + b

    register_scalar_function(conn, partial(target, b=1))

    assert {(name, arity) for name, arity, _, _ in conn.calls} == {("target", 1)}


def test_default_name_for_callable_instance_uses_class_name() -> None:
    conn = FakeConnection()

    class CallableThing:
        def __call__(self, a: int, b: int = 0) -> int:
            return a + b

    register_scalar_function(conn, CallableThing())

    assert [(name, arity) for name, arity, _, _ in conn.calls] == [
        ("CallableThing", 1),
        ("CallableThing", 2),
    ]


def test_default_name_for_class_uses_class_name() -> None:
    conn = FakeConnection()

    class Build:
        def __init__(self, a: int, b: int = 0) -> None:
            self.value = a + b

    register_scalar_function(conn, Build)

    assert [(name, arity) for name, arity, _, _ in conn.calls] == [
        ("Build", 1),
        ("Build", 2),
    ]


def test_replace_false_keeps_existing_arity_registrations() -> None:
    conn = FakeConnection()

    def base(a: int, b: int = 0) -> int:
        return a + b

    def newer(a: int, b: int = 0) -> int:
        return a * b

    register_scalar_function(conn, base, name="calc")
    first_count = len(conn.calls)
    register_scalar_function(conn, newer, name="calc", replace=False)

    assert len(conn.calls) == first_count


def test_replace_true_replaces_fixed_arities_but_preserves_varargs() -> None:
    conn = FakeConnection()

    def var(*args: int) -> int:
        return sum(args)

    def fixed(a: int, b: int = 0) -> int:
        return a + b

    register_scalar_function(conn, var, name="calc")
    register_scalar_function(conn, fixed, name="calc", replace=True)

    assert [(name, arity) for name, arity, _, _ in conn.calls] == [
        ("calc", -1),
        ("calc", 1),
        ("calc", 2),
    ]


def test_inference_for_varargs_signature_registers_varargs() -> None:
    conn = FakeConnection()

    def scalar(a: int, *rest: int) -> int:
        return a + sum(rest)

    register_scalar_function(conn, scalar)

    assert [(name, arity) for name, arity, _, _ in conn.calls] == [("scalar", -1)]
