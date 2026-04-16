from __future__ import annotations

import json
from pathlib import Path

from sdetkit import cli


def test_cli_portfolio_readiness_alias_json(tmp_path: Path, capsys) -> None:
    ship = tmp_path / "ship.json"
    enterprise = tmp_path / "enterprise.json"
    manifest = tmp_path / "manifest.json"

    ship.write_text(json.dumps({"summary": {"decision": "go", "blockers": []}}), encoding="utf-8")
    enterprise.write_text(
        json.dumps({"summary": {"score": 100}, "upgrade_contract": {"risk_band": "low"}}),
        encoding="utf-8",
    )
    manifest.write_text(
        json.dumps(
            [
                {
                    "repo": "repo-a",
                    "ship_summary": str(ship),
                    "enterprise_summary": str(enterprise),
                }
            ]
        ),
        encoding="utf-8",
    )

    rc = cli.main(["portfolio-readiness", "--manifest", str(manifest), "--format", "json"])

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["repo_count"] == 1


def test_cli_portfolio_alias_text(tmp_path: Path, capsys) -> None:
    ship = tmp_path / "ship.json"
    manifest = tmp_path / "manifest.json"

    ship.write_text(json.dumps({"summary": {"decision": "go", "blockers": []}}), encoding="utf-8")
    manifest.write_text(json.dumps([{"repo": "repo-b", "ship_summary": str(ship)}]), encoding="utf-8")

    rc = cli.main(["portfolio", "--manifest", str(manifest), "--format", "text"])

    assert rc == 0
    text = capsys.readouterr().out
    assert text.startswith("portfolio-readiness")
