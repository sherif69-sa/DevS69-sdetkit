from __future__ import annotations

import datetime as dt

from sdetkit import doctor, repo
from sdetkit.phase2_utilities import parse_check_csv, parse_iso_date


def test_parse_check_csv_handles_empty_and_whitespace() -> None:
    assert parse_check_csv(None) == []
    assert parse_check_csv("a, b, ,c") == ["a", "b", "c"]


def test_parse_iso_date_parses_and_raises_field_specific_error() -> None:
    assert parse_iso_date("2026-04-24", field="x") == dt.date(2026, 4, 24)
    try:
        parse_iso_date("2026-13-40", field="allowlist expires")
    except ValueError as exc:
        assert "allowlist expires must be ISO date YYYY-MM-DD" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError for invalid date")


def test_doctor_wrapper_stays_compatible() -> None:
    assert doctor._parse_check_csv("one,two, three") == ["one", "two", "three"]


def test_repo_wrapper_stays_compatible_error_type() -> None:
    assert repo._parse_iso_date("2026-04-24", field="f") == dt.date(2026, 4, 24)
    try:
        repo._parse_iso_date("bad-date", field="allowlist expires")
    except repo.RepoAuditConfigError as exc:
        assert "allowlist expires must be ISO date YYYY-MM-DD" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected RepoAuditConfigError")
