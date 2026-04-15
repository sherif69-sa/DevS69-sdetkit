from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_build_portfolio_scorecard_emits_versioned_contract(tmp_path: Path) -> None:
    infile = tmp_path / "portfolio-input.jsonl"
    outfile = tmp_path / "portfolio-out.json"

    infile.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "repo": "svc-a",
                        "team": "checkout",
                        "lane": "scale",
                        "timestamp": "2026-04-16T10:00:00Z",
                        "gate_fast_ok": True,
                        "gate_release_ok": True,
                        "doctor_ok": True,
                        "failed_steps_count": 0,
                    }
                ),
                json.dumps(
                    {
                        "repo": "svc-b",
                        "team": "growth",
                        "lane": "startup",
                        "timestamp": "2026-04-16T11:00:00Z",
                        "gate_fast_ok": True,
                        "gate_release_ok": False,
                        "doctor_ok": True,
                        "failed_steps_count": 2,
                    }
                ),
            ]
        )
        + "\n"
    )

    cmd = [
        sys.executable,
        "scripts/build_portfolio_scorecard.py",
        "--in",
        str(infile),
        "--out",
        str(outfile),
        "--schema-version",
        "1.0.0",
        "--window-start",
        "2026-04-11",
        "--window-end",
        "2026-04-17",
        "--generated-at",
        "2026-04-17T10:00:00Z",
    ]
    subprocess.run(cmd, check=True)

    payload = json.loads(outfile.read_text())

    assert payload["schema_name"] == "sdetkit.portfolio.aggregate"
    assert payload["schema_version"] == "1.0.0"
    assert payload["generated_at"] == "2026-04-17T10:00:00Z"
    assert payload["window"] == {"start_date": "2026-04-11", "end_date": "2026-04-17"}

    totals = payload["totals"]
    assert totals["repo_count_total"] == 2
    assert totals["repo_count_reporting"] == 2
    assert totals["high_risk_repo_count"] == 1
    assert totals["low_risk_repo_count"] == 1
    assert totals["release_gate_failure_rate_percent"] == 50.0

    repos = {row["repo_id"]: row for row in payload["repos"]}
    assert repos["svc-a"]["risk_tier"] == "low"
    assert repos["svc-a"]["release_confidence_ok"] is True
    assert repos["svc-b"]["risk_tier"] == "high"
    assert repos["svc-b"]["release_confidence_ok"] is False


def test_portfolio_scorecard_sample_artifact_matches_contract_shape() -> None:
    sample = Path("docs/artifacts/portfolio-scorecard-sample-2026-04-17.json")
    payload = json.loads(sample.read_text())

    assert payload["schema_name"] == "sdetkit.portfolio.aggregate"
    assert payload["schema_version"] == "1.0.0"

    totals = payload["totals"]
    assert totals["repo_count_total"] == len(payload["repos"])
    assert set(totals).issuperset(
        {
            "repo_count_total",
            "repo_count_reporting",
            "high_risk_repo_count",
            "medium_risk_repo_count",
            "low_risk_repo_count",
        }
    )

    for row in payload["repos"]:
        assert "repo_id" in row
        assert row["risk_tier"] in {"low", "medium", "high"}
        assert "evidence_window_end" in row
