from __future__ import annotations

import pytest

from sdetkit import doctor


def test_doctor_help_works_without_upgrade_audit_release_freshness_buckets(monkeypatch) -> None:
    if hasattr(doctor.upgrade_audit, "RELEASE_FRESHNESS_BUCKETS"):
        monkeypatch.delattr(doctor.upgrade_audit, "RELEASE_FRESHNESS_BUCKETS", raising=False)

    with pytest.raises(SystemExit) as exc:
        doctor.main(["--help"])

    assert int(exc.value.code) == 0
