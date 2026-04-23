from __future__ import annotations

import datetime as _dt
import importlib.util
import sys

if not hasattr(_dt, "UTC"):
    _dt.UTC = _dt.timezone.utc  # noqa: UP017

if importlib.util.find_spec("tomllib") is None and importlib.util.find_spec("tomli") is not None:
    import tomli as _tomli

    sys.modules.setdefault("tomllib", _tomli)
