from __future__ import annotations

import datetime as dt


def parse_check_csv(value: str | None) -> list[str]:
    if value is None:
        return []
    out: list[str] = []
    for part in value.split(","):
        item = part.strip()
        if item:
            out.append(item)
    return out


def parse_iso_date(raw: str, *, field: str) -> dt.date:
    try:
        return dt.date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO date YYYY-MM-DD") from exc
