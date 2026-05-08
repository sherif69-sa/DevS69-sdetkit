from __future__ import annotations

import json
from pathlib import Path

from sdetkit import adaptive_portfolio_rollup
from sdetkit.cli import main as top_level_main


def _diagnosis_payload(repo: str, status: str, code: str, risk_score: int) -> dict[str, object]:
    return {
        "schema_version": "sdetkit.adaptive.diagnosis.v1",
        "repo": repo,
        "status": status,
        "risk_score": risk_score,
        "confidence": "high",
        "diagnosis_count": 1,
        "diagnoses": [
            {
                "code": code,
                "title": f"{code} title",
                "severity": "high" if status == "needs_fix" else "medium",
                "confidence": "high",
                "repeat_count": 2 if status == "needs_fix" else 0,
                "evidence": [
                    "candidate_scenarios=PACKAGE_INSTALL_FAILURE,CACHE_ARTIFACT_POISONING"
                ],
            }
        ],
    }


def test_adaptive_portfolio_rollup_prioritizes_cross_repo_risks() -> None:
    payload = adaptive_portfolio_rollup.build_portfolio_rollup(
        [
            _diagnosis_payload("api", "needs_fix", "PYTEST_ASSERTION_FAILURE", 70),
            _diagnosis_payload("web", "needs_attention", "PYTEST_ASSERTION_FAILURE", 35),
            _diagnosis_payload("ops", "monitor", "KNOWN_ADAPTIVE_PATTERN_AVAILABLE", 8),
        ]
    )

    assert payload["schema_version"] == "sdetkit.adaptive.portfolio_rollup.v1"
    assert payload["ok"] is False
    assert payload["recommendation"] == "NO_SHIP"
    assert payload["repo_count"] == 3
    assert payload["needs_fix_repos"] == ["api"]
    assert payload["top_risk_scenarios"][0]["code"] == "PYTEST_ASSERTION_FAILURE"
    assert payload["top_risk_scenarios"][0]["repo_count"] == 2
    assert any(
        row["code"] == "PACKAGE_INSTALL_FAILURE" and row["candidate_mentions"] == 3
        for row in payload["top_risk_scenarios"]
    )
    assert payload["next_owner_action"].startswith("Block release signoff for api")


def test_adaptive_portfolio_rollup_cli_writes_markdown(tmp_path: Path) -> None:
    api = tmp_path / "api" / "diagnosis.json"
    web = tmp_path / "web" / "diagnosis.json"
    out = tmp_path / "rollup.md"
    api.parent.mkdir()
    web.parent.mkdir()
    api.write_text(json.dumps(_diagnosis_payload("api", "needs_fix", "RUFF_LINT_FAILURE", 64)))
    web.write_text(json.dumps(_diagnosis_payload("web", "monitor", "LEARNING_DB_EMPTY", 12)))

    rc = adaptive_portfolio_rollup.main([str(api), str(web), "--format", "md", "--out", str(out)])

    assert rc == 0
    text = out.read_text(encoding="utf-8")
    assert "# Adaptive Portfolio Rollup" in text
    assert "`RUFF_LINT_FAILURE`" in text
    assert "Block release signoff for api" in text


def test_top_level_cli_adaptive_portfolio_rollup_passthrough(tmp_path: Path) -> None:
    artifact = tmp_path / "diagnosis.json"
    out = tmp_path / "rollup.json"
    artifact.write_text(
        json.dumps(_diagnosis_payload("api", "needs_attention", "MYPY_TYPE_FAILURE", 40)),
        encoding="utf-8",
    )

    rc = top_level_main(
        ["adaptive", "portfolio-rollup", str(artifact), "--format", "json", "--out", str(out)]
    )

    assert rc == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["recommendation"] == "SHIP_WITH_CONTROLS"
    assert payload["top_risk_scenarios"][0]["code"] == "MYPY_TYPE_FAILURE"
