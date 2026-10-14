from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from sdetkit import network_boundary as boundary_module
from sdetkit.network_boundary import (
    NETWORK_ISOLATION_ENFORCED,
    NETWORK_ISOLATION_REQUIRED,
    NOT_REQUESTED,
    PROBE_SCHEMA_VERSION,
    PROOF_EXECUTION_ALLOWED,
    REQUIRED_UNAVAILABLE,
    UNSHARE_USER_MAP_ROOT_NET,
    UNSHARE_VARIANT,
    VERIFIED_BACKEND_AVAILABLE,
    assess_network_boundary,
    build_network_isolated_argv,
    main,
    render_markdown,
)


def _verified_probe(executable: Path) -> dict:
    digest = hashlib.sha256(executable.read_bytes()).hexdigest()
    candidate = {
        "backend_id": UNSHARE_USER_MAP_ROOT_NET,
        "variant": UNSHARE_VARIANT,
        "executable": executable.as_posix(),
        "executable_sha256": digest,
        "available": True,
        "process_started": True,
        "exit_code": 0,
        "child_executed": True,
        "namespace_changed": True,
        "isolated_loopback_blocked": True,
        "network_namespace_isolation_verified": True,
    }
    return {
        "schema_version": PROBE_SCHEMA_VERSION,
        "baseline_control_passed": True,
        "candidates": [candidate],
        "verified_candidate_count": 1,
        "selected_candidate": {
            "backend_id": UNSHARE_USER_MAP_ROOT_NET,
            "variant": UNSHARE_VARIANT,
            "executable": executable.as_posix(),
            "executable_sha256": digest,
        },
    }


def _unverified_probe() -> dict:
    return {
        "schema_version": PROBE_SCHEMA_VERSION,
        "baseline_control_passed": True,
        "candidates": [],
        "verified_candidate_count": 0,
        "selected_candidate": {},
    }


def test_network_boundary_does_not_claim_unrequested_containment() -> None:
    boundary = assess_network_boundary(require_network_isolation=False)

    assert boundary["status"] == NOT_REQUESTED
    assert boundary[NETWORK_ISOLATION_REQUIRED] is False
    assert boundary[NETWORK_ISOLATION_ENFORCED] is False
    assert boundary[PROOF_EXECUTION_ALLOWED] is True
    assert boundary["backend_verified"] is False
    assert boundary["external_filesystem_containment_enforced"] is False
    assert boundary["process_escape_prevention_enforced"] is False
    assert boundary["decision_boundary"]["automation_allowed"] is False


def test_network_boundary_fails_closed_when_required_backend_is_unverified() -> None:
    boundary = assess_network_boundary(
        require_network_isolation=True,
        probe_report=_unverified_probe(),
    )

    assert boundary["status"] == REQUIRED_UNAVAILABLE
    assert boundary[NETWORK_ISOLATION_REQUIRED] is True
    assert boundary[NETWORK_ISOLATION_ENFORCED] is False
    assert boundary[PROOF_EXECUTION_ALLOWED] is False
    assert boundary["verified_backends"] == []
    assert "execution is blocked" in boundary["reason"]


def test_network_boundary_markdown_reports_unverified_backend() -> None:
    markdown = render_markdown(
        assess_network_boundary(
            require_network_isolation=True,
            probe_report=_unverified_probe(),
        )
    )

    assert "# Network boundary assessment" in markdown
    assert "Status: `required_unavailable`" in markdown
    assert "Backend verified: `false`" in markdown
    assert "Network isolation enforced: `false`" in markdown
    assert "Proof execution allowed: `false`" in markdown
    assert "Automation allowed: `false`" in markdown


def test_network_boundary_accepts_only_controlled_verified_backend(
    tmp_path: Path,
) -> None:
    executable = tmp_path / "unshare"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o700)

    boundary = assess_network_boundary(
        require_network_isolation=True,
        probe_report=_verified_probe(executable),
    )

    assert boundary["status"] == VERIFIED_BACKEND_AVAILABLE
    assert boundary["backend"] == UNSHARE_USER_MAP_ROOT_NET
    assert boundary["backend_variant"] == UNSHARE_VARIANT
    assert boundary["backend_verified"] is True
    assert boundary[NETWORK_ISOLATION_REQUIRED] is True
    assert boundary[NETWORK_ISOLATION_ENFORCED] is True
    assert boundary[PROOF_EXECUTION_ALLOWED] is True
    assert boundary["external_filesystem_containment_enforced"] is False
    assert boundary["process_escape_prevention_enforced"] is False
    assert boundary["decision_boundary"]["automation_allowed"] is False
    assert boundary["decision_boundary"]["merge_authorized"] is False


def test_network_isolated_argv_uses_exact_registered_prefix(tmp_path: Path) -> None:
    executable = tmp_path / "unshare"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o700)
    boundary = assess_network_boundary(
        require_network_isolation=True,
        probe_report=_verified_probe(executable),
    )

    argv = build_network_isolated_argv(
        boundary,
        ["python", "-m", "ruff", "check", "src", "tests"],
    )

    assert argv == [
        executable.as_posix(),
        "--user",
        "--map-root-user",
        "--net",
        "python",
        "-m",
        "ruff",
        "check",
        "src",
        "tests",
    ]


def test_network_isolated_argv_rejects_executable_identity_drift(
    tmp_path: Path,
) -> None:
    executable = tmp_path / "unshare"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o700)
    boundary = assess_network_boundary(
        require_network_isolation=True,
        probe_report=_verified_probe(executable),
    )
    executable.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="identity changed"):
        build_network_isolated_argv(boundary, ["python", "-m", "ruff"])


def test_network_boundary_rejects_unregistered_verified_candidate(
    tmp_path: Path,
) -> None:
    executable = tmp_path / "unshare"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o700)
    probe = _verified_probe(executable)
    probe["selected_candidate"]["backend_id"] = "forged_backend"
    probe["candidates"][0]["backend_id"] = "forged_backend"

    boundary = assess_network_boundary(
        require_network_isolation=True,
        probe_report=probe,
    )

    assert boundary["status"] == REQUIRED_UNAVAILABLE
    assert boundary[PROOF_EXECUTION_ALLOWED] is False


def test_network_boundary_markdown_reports_verified_narrow_scope(
    tmp_path: Path,
) -> None:
    executable = tmp_path / "unshare"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o700)
    markdown = render_markdown(
        assess_network_boundary(
            require_network_isolation=True,
            probe_report=_verified_probe(executable),
        )
    )

    assert "# Network boundary assessment" in markdown
    assert "Status: `verified_backend_available`" in markdown
    assert "Backend verified: `true`" in markdown
    assert "Network isolation enforced: `true`" in markdown
    assert "Proof execution allowed: `true`" in markdown
    assert "External filesystem containment enforced: `false`" in markdown
    assert "Process escape prevention enforced: `false`" in markdown
    assert "Automation allowed: `false`" in markdown


def test_network_boundary_cli_writes_evidence(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = tmp_path / "unshare"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o700)
    monkeypatch.setattr(
        boundary_module,
        "probe_registered_backends",
        lambda: _verified_probe(executable),
    )
    out_dir = tmp_path / "network-boundary"

    rc = main(
        [
            "--require-network-isolation",
            "--out-dir",
            str(out_dir),
            "--format",
            "json",
        ]
    )

    assert rc == 0
    printed = json.loads(capsys.readouterr().out)
    saved = json.loads((out_dir / "network-boundary.json").read_text(encoding="utf-8"))
    markdown = (out_dir / "network-boundary.md").read_text(encoding="utf-8")

    assert printed["status"] == VERIFIED_BACKEND_AVAILABLE
    assert printed["backend"] == UNSHARE_USER_MAP_ROOT_NET
    assert saved[PROOF_EXECUTION_ALLOWED] is True
    assert saved[NETWORK_ISOLATION_ENFORCED] is True
    assert "# Network boundary assessment" in markdown
