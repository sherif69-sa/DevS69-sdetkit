from __future__ import annotations

import json
from pathlib import Path

from sdetkit import portfolio_readiness as pr


def test_build_portfolio_readiness_ranks_highest_risk_first() -> None:
    rows = [
        {
            "repo": "repo-green",
            "ship_summary": {"summary": {"decision": "go", "blockers": []}},
            "enterprise_summary": {"summary": {"score": 100}, "upgrade_contract": {"risk_band": "low"}},
        },
        {
            "repo": "repo-red",
            "ship_summary": {"summary": {"decision": "no-go", "blockers": ["a", "b"]}},
            "enterprise_summary": {"summary": {"score": 70}, "upgrade_contract": {"risk_band": "high"}},
        },
    ]

    payload = pr.build_portfolio_readiness(rows)

    assert payload["summary"]["repo_count"] == 2
    assert payload["repos"][0]["repo"] == "repo-red"
    assert payload["summary"]["critical_count"] >= 1


def test_main_writes_json_output_and_supports_strict(tmp_path: Path, capsys) -> None:
    ship = tmp_path / "ship.json"
    enterprise = tmp_path / "enterprise.json"
    manifest = tmp_path / "manifest.json"
    out = tmp_path / "out.json"

    ship.write_text(json.dumps({"summary": {"decision": "no-go", "blockers": ["x"]}}), encoding="utf-8")
    enterprise.write_text(
        json.dumps({"summary": {"score": 75}, "upgrade_contract": {"risk_band": "high"}}),
        encoding="utf-8",
    )
    manifest.write_text(
        json.dumps(
            [
                {
                    "repo": "repo-x",
                    "ship_summary": str(ship),
                    "enterprise_summary": str(enterprise),
                }
            ]
        ),
        encoding="utf-8",
    )

    rc = pr.main(["--manifest", str(manifest), "--format", "json", "--out", str(out), "--strict"])

    assert rc == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["critical_count"] == 1
    assert out.exists()
