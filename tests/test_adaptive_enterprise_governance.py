from __future__ import annotations

import json
from pathlib import Path

from sdetkit import adaptive_enterprise_governance
from sdetkit.cli import main as top_level_main


def _pack(code: str, tags: list[str]) -> dict[str, object]:
    return {
        "schema_version": "sdetkit.adaptive.scenario_pack.v1",
        "pack_id": "enterprise.test",
        "title": "Enterprise test pack",
        "scenarios": [
            {
                "code": code,
                "title": "Enterprise scenario",
                "signals": ["error-prefix"],
                "keywords": ["enterprise"],
                "checks": ["Check enterprise scenario."],
                "commands": ["python -m pytest -q tests/test_enterprise.py"],
                "risk_band": "high",
                "prior_weight": 2,
                "tags": tags,
            }
        ],
    }


def _write_local_pack(root: Path, payload: dict[str, object]) -> Path:
    local_dir = root / ".sdetkit" / "adaptive"
    local_dir.mkdir(parents=True)
    path = local_dir / "scenarios.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_enterprise_governance_blocks_sensitive_pack_without_isolation(tmp_path: Path) -> None:
    _write_local_pack(tmp_path, _pack("ENTERPRISE_SECRET_SIGNAL", ["security-sensitive"]))

    report = adaptive_enterprise_governance.build_governance_report(tmp_path)

    assert report["ok"] is False
    assert report["recommendation"] == "BLOCKED"
    assert report["sensitive_scenario_count"] == 1
    assert report["violations"][0]["kind"] == "sensitive_scenario_not_isolated"


def test_enterprise_governance_allows_isolated_sensitive_pack(tmp_path: Path) -> None:
    _write_local_pack(
        tmp_path,
        _pack("ENTERPRISE_SECRET_SIGNAL", ["security-sensitive", "security-isolated"]),
    )

    report = adaptive_enterprise_governance.build_governance_report(tmp_path)

    assert report["ok"] is True
    assert report["recommendation"] == "APPROVED"
    assert report["sensitive_scenario_count"] == 1
    assert report["violations"] == []


def test_enterprise_governance_anonymizes_learning_records() -> None:
    payload = adaptive_enterprise_governance.build_anonymized_learning_export(
        [
            {
                "repo": "private/repo",
                "source_path": "build/private-plan.json",
                "changed_file_scope": ["src/private.py"],
                "affected_files": ["tests/private_test.py"],
                "source_code": "UNKNOWN_REVIEW_REQUIRED",
                "nested": {"note": "customer context"},
            }
        ]
    )

    record = payload["records"][0]
    assert record["repo"] == "<redacted>"
    assert record["source_path"] == "<redacted>"
    assert record["changed_file_scope"] == ["<redacted>"]
    assert record["affected_files"] == ["<redacted>"]
    assert record["source_code"] == "UNKNOWN_REVIEW_REQUIRED"
    assert record["nested"]["note"] == "<redacted>"


def test_top_level_cli_enterprise_governance_passthrough(tmp_path: Path) -> None:
    _write_local_pack(
        tmp_path,
        _pack("ENTERPRISE_SECRET_SIGNAL", ["security-sensitive", "security-isolated"]),
    )
    out = tmp_path / "governance.json"

    rc = top_level_main(
        [
            "adaptive",
            "enterprise-governance",
            "report",
            "--root",
            str(tmp_path),
            "--format",
            "json",
            "--out",
            str(out),
        ]
    )

    assert rc == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["recommendation"] == "APPROVED"
