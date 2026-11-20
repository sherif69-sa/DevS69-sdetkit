"""Tests for adaptive risk-tiered release gate and loopback-safe air-gap mode."""

from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest

from sdetkit import cli, network_boundary, safety_gate


def test_risk_tier_determination(tmp_path: Path) -> None:
    # Explicit tiers
    assert safety_gate.determine_risk_tier(tmp_path, "1")[0] == 1
    assert safety_gate.determine_risk_tier(tmp_path, "2")[0] == 2
    assert safety_gate.determine_risk_tier(tmp_path, "3")[0] == 3

    # Auto tier based on blast radius
    t1, name1, br1, _ = safety_gate.determine_risk_tier(tmp_path, "auto", blast_radius=12.5)
    assert t1 == 1
    assert name1 == "Fast Path"
    assert br1 == 12.5

    t2, name2, br2, _ = safety_gate.determine_risk_tier(tmp_path, "auto", blast_radius=45.0)
    assert t2 == 2
    assert name2 == "Elevated Path"
    assert br2 == 45.0

    t3, name3, br3, _ = safety_gate.determine_risk_tier(tmp_path, "auto", blast_radius=78.0)
    assert t3 == 3
    assert name3 == "Sovereign Release Path"
    assert br3 == 78.0


def test_loopback_audit_guard_allowlist() -> None:
    guard = network_boundary.LoopbackAuditGuard(strict=True)

    # Valid loopback addresses
    assert guard.is_allowed_address(("127.0.0.1", 8080)) is True
    assert guard.is_allowed_address(("localhost", 3000)) is True
    assert guard.is_allowed_address(("::1", 5432)) is True
    assert guard.is_allowed_address("127.0.0.1") is True
    assert guard.is_allowed_address("localhost") is True
    assert guard.is_allowed_address("/tmp/test.sock") is True

    # Check AF_UNIX family if supported
    if hasattr(socket, "AF_UNIX"):
        assert (
            guard.is_allowed_address(
                "/var/run/docker.sock", family=getattr(socket, "AF_UNIX", None)
            )
            is True
        )

    # Disallowed external addresses
    assert guard.is_allowed_address(("api.github.com", 443)) is False
    assert guard.is_allowed_address(("93.184.216.34", 80)) is False
    assert guard.is_allowed_address(("10.0.0.1", 8080)) is False
    assert guard.is_allowed_address(("192.168.1.1", 80)) is False


def test_loopback_audit_guard_hook_blocking() -> None:
    guard = network_boundary.LoopbackAuditGuard(strict=True)

    # Allowed loopback connect does not raise
    guard.hook("socket.connect", (None, ("127.0.0.1", 8080)))
    assert len(guard.blocked_attempts) == 0

    # Disallowed external connect raises NetworkEgressViolation
    with pytest.raises(
        network_boundary.NetworkEgressViolation, match="Outbound network egress blocked"
    ):
        guard.hook("socket.connect", (None, ("api.github.com", 443)))

    assert len(guard.blocked_attempts) == 1
    assert guard.blocked_attempts[0]["event"] == "socket.connect"
    assert "api.github.com" in guard.blocked_attempts[0]["address"]

    # Disallowed external DNS lookup raises NetworkEgressViolation
    with pytest.raises(network_boundary.NetworkEgressViolation, match="DNS resolution blocked"):
        guard.hook("socket.getaddrinfo", ("evil-tracker.com", 443))

    assert len(guard.blocked_attempts) == 2


def test_evaluate_ship_gate_tier_1(tmp_path: Path) -> None:
    report = safety_gate.evaluate_ship_gate(
        repo_root=tmp_path,
        tier="1",
        blast_radius=5.0,
        offline_strict=False,
    )
    assert report["schema_version"] == safety_gate.SHIP_SCHEMA_VERSION
    assert report["tier"] == 1
    assert report["tier_name"] == "Fast Path"
    assert report["blast_radius_percent"] == 5.0
    assert report["verdict"] in ("SHIP", "REVIEW", "NO_SHIP")
    assert report["checks_count"] >= 3
    assert len(report["checks"]) >= 3


def test_evaluate_ship_gate_offline_strict_certified(tmp_path: Path) -> None:
    report = safety_gate.evaluate_ship_gate(
        repo_root=tmp_path,
        tier="1",
        blast_radius=10.0,
        offline_strict=True,
    )
    assert report["offline_strict"] is True
    assert report["network_egress"] == "ZERO_BYTES"
    assert report["air_gap_certified"] is True
    assert report["blocked_network_attempts"] == []


def test_render_ship_markdown_and_text(tmp_path: Path) -> None:
    sample_report = {
        "schema_version": "sdetkit.ship_gate.v1",
        "repo_root": str(tmp_path),
        "verdict": "SHIP",
        "tier": 1,
        "tier_name": "Fast Path",
        "blast_radius_percent": 14.5,
        "reasons": ["Localized blast radius < 20%"],
        "offline_strict": True,
        "network_egress": "ZERO_BYTES",
        "air_gap_certified": True,
        "total_duration_seconds": 1.25,
        "checks_count": 3,
        "passed_checks_count": 3,
        "failed_checks_count": 0,
        "checks": [
            {
                "name": "doctor",
                "description": "Hygiene check",
                "passed": True,
                "duration_seconds": 0.45,
                "summary": "100% pure ASCII",
            },
            {
                "name": "gate_fast",
                "description": "Static gate",
                "passed": True,
                "duration_seconds": 0.50,
                "summary": "0 warnings",
            },
            {
                "name": "test_integrity",
                "description": "Integrity proof",
                "passed": True,
                "duration_seconds": 0.30,
                "summary": "Tests verified",
            },
        ],
    }

    md = safety_gate.render_ship_markdown(sample_report)
    assert "# SDETKit Sovereign Release Gate: [SHIP]" in md
    assert "Tier 1 (Fast Path)" in md
    assert "ZERO_BYTES" in md
    assert "Check Execution Matrix" in md
    assert all(ord(c) < 128 for c in md)

    txt = safety_gate.render_ship_text(sample_report)
    assert "SDETKit Sovereign Release Gate: verdict=SHIP" in txt
    assert "Tier: 1 (Fast Path)" in txt
    assert all(ord(c) < 128 for c in txt)


def test_ship_cli_main_and_subcommand_routing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = safety_gate.ship_main(["--tier", "1", "--blast-radius", "8.0", "--format", "json"])
    assert rc in (0, 1)
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["schema_version"] == "sdetkit.ship_gate.v1"
    assert payload["tier"] == 1

    # Test via cli.main
    rc_cli = cli.main(["ship", "--tier", "1", "--blast-radius", "5.0", "--format", "text"])
    assert rc_cli in (0, 1)
    captured_cli = capsys.readouterr()
    assert "SDETKit Sovereign Release Gate" in captured_cli.out

    # Test via verify ship subcommand
    rc_sub = cli.main(["verify", "ship", "--tier", "1", "--format", "json"])
    assert rc_sub in (0, 1)
    captured_sub = capsys.readouterr()
    payload_sub = json.loads(captured_sub.out)
    assert payload_sub["tier"] == 1
