from __future__ import annotations

import datetime as _dt
import importlib.util
import sys

if getattr(_dt, "UTC", None) is None:
    _dt.UTC = _dt.timezone.utc  # type: ignore[attr-defined]

if importlib.util.find_spec("tomllib") is None and importlib.util.find_spec("tomli") is not None:
    import tomli as _tomli

    sys.modules.setdefault("tomllib", _tomli)
