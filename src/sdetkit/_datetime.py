import datetime as _datetime

UTC = getattr(_datetime, "UTC", _datetime.timezone.utc)

__all__ = ["UTC"]
