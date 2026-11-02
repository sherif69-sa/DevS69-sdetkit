from __future__ import annotations

import tomllib

import sdetkit._toml as toml_compat


def test_toml_loads_is_the_standard_library_parser() -> None:
    assert toml_compat.loads is tomllib.loads
    assert toml_compat.loads("k = 'v'") == {"k": "v"}
