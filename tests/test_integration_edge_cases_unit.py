from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit import integration


def test_integration_low_level_edge_helpers(tmp_path: Path) -> None:
    profile_path = tmp_path / "profile.json"
    profile_path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="profile must be a JSON object"):
        integration._load_profile(profile_path)

    assert integration._service_exposes_protocol({"interfaces": "bad"}, protocol="rest") is False
    assert integration._normalize_deployments({"deployments": "bad"}) == []
    assert integration._parse_replicas(False) == 0
    assert integration._telemetry_signal_enabled({"metrics": "off"}, "metrics") is False

    dep = integration._normalize_dependency_entry(
        {"kind": "service", "target": "svc-a"},
        application_names={"svc-a"},
        data_names=set(),
        mock_names=set(),
    )
    assert dep == {"kind": "application", "target": "svc-a"}


def test_integration_validate_cassette_and_main_failures(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    cassette = tmp_path / "cassette.json"
    cassette.write_text(
        json.dumps(
            {
                "version": 1,
                "interactions": [
                    {
                        "request": {"method": "GET", "url": "https://ok"},
                        "response": {"status_code": 200},
                    },
                    {
                        "request": {"method": "", "url": "https://missing"},
                        "response": {"status_code": 200},
                    },
                    {
                        "request": {"method": "POST", "url": "https://bad-status"},
                        "response": {"status_code": 9999},
                    },
                    {"request": "bad", "response": {}},
                ],
            }
        ),
        encoding="utf-8",
    )
    payload = integration._validate_cassette(cassette)
    assert payload["summary"]["invalid"] >= 2
    assert payload["summary"]["passed"] is False

    # topology-check input validation path
    broken_profile = tmp_path / "broken-profile.json"
    broken_profile.write_text(json.dumps({"name": "x", "topology": []}), encoding="utf-8")
    rc = integration.main(["topology-check", "--profile", str(broken_profile)])
    assert rc == 2
    assert "integration error:" in capsys.readouterr().err

    # check path returns non-zero when checks fail
    failing_profile = tmp_path / "failing-profile.json"
    failing_profile.write_text(
        json.dumps({"required_env": ["MISSING_ENV"], "required_files": [], "services": []}),
        encoding="utf-8",
    )
    rc = integration.main(["check", "--profile", str(failing_profile)])
    assert rc == 1
    assert "profile-check" in capsys.readouterr().out
