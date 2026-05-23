from __future__ import annotations

import json
from pathlib import Path

from sdetkit.network_boundary import (
    NETWORK_ISOLATION_ENFORCED,
    NETWORK_ISOLATION_REQUIRED,
    NOT_REQUESTED,
    PROOF_EXECUTION_ALLOWED,
    REQUIRED_UNAVAILABLE,
    assess_network_boundary,
    main,
    render_markdown,
)


def test_network_boundary_does_not_claim_unrequested_containment() -> None:
    boundary = assess_network_boundary(require_network_isolation=False)

    assert boundary["status"] == NOT_REQUESTED
    assert boundary[NETWORK_ISOLATION_REQUIRED] is False
    assert boundary[NETWORK_ISOLATION_ENFORCED] is False
    assert boundary[PROOF_EXECUTION_ALLOWED] is True
    assert boundary["backend_verified"] is False
    assert boundary["decision_boundary"]["automation_allowed"] is False


def test_network_boundary_fails_closed_when_required_backend_is_unverified() -> None:
    boundary = assess_network_boundary(require_network_isolation=True)

    assert boundary["status"] == REQUIRED_UNAVAILABLE
    assert boundary[NETWORK_ISOLATION_REQUIRED] is True
    assert boundary[NETWORK_ISOLATION_ENFORCED] is False
    assert boundary[PROOF_EXECUTION_ALLOWED] is False
    assert boundary["verified_backends"] == []
    assert "execution is blocked" in boundary["reason"]


def test_network_boundary_markdown_reports_unverified_backend() -> None:
    markdown = render_markdown(assess_network_boundary(require_network_isolation=True))

    assert "# Network boundary assessment" in markdown
    assert "Status: `required_unavailable`" in markdown
    assert "Backend verified: `false`" in markdown
    assert "Network isolation enforced: `false`" in markdown
    assert "Proof execution allowed: `false`" in markdown
    assert "Automation allowed: `false`" in markdown


def test_network_boundary_cli_writes_evidence(tmp_path: Path, capsys) -> None:
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

    assert printed["status"] == REQUIRED_UNAVAILABLE
    assert saved[PROOF_EXECUTION_ALLOWED] is False
    assert saved[NETWORK_ISOLATION_ENFORCED] is False
    assert "# Network boundary assessment" in markdown
