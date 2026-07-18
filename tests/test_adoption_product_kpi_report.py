from __future__ import annotations

import json
from pathlib import Path

from sdetkit.adoption_product_kpi_freshness import check_freshness, validate_freshness
from sdetkit.adoption_product_kpi_model import OBSERVATIONS_SCHEMA
from sdetkit.adoption_product_kpi_report import main, write_artifacts

SOURCE_CONTRACT = Path("docs/contracts/adoption-product-kpi-evidence.v1.json")


def _contract(tmp_path: Path) -> Path:
    path = tmp_path / "contract.json"
    path.write_text(SOURCE_CONTRACT.read_text(encoding="utf-8"), encoding="utf-8")
    return path


def _observations(tmp_path: Path, contract: Path) -> Path:
    contract_payload = json.loads(contract.read_text(encoding="utf-8"))
    outcomes = {item["metric_id"]: "pass" for item in contract_payload["metric_definitions"]}
    payload = {
        "schema_version": OBSERVATIONS_SCHEMA,
        "observations": [
            {
                "observation_id": "review-1",
                "repository_name": "example-repo",
                "repository_url": "https://example.invalid/repo",
                "source_commit_sha": "a" * 40,
                "evidence_path": "evidence/review-1.json",
                "evidence_sha256": "b" * 64,
                "reviewer_id": "reviewer-1",
                "reviewed_at": "2026-07-18T12:00:00Z",
                "metric_outcomes": outcomes,
                "review_notes": "Reviewed against retained source evidence.",
            }
        ],
    }
    path = tmp_path / "observations.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_product_kpi_report_writes_deterministic_json_and_markdown(tmp_path: Path) -> None:
    contract = _contract(tmp_path)
    observations = _observations(tmp_path, contract)
    out = tmp_path / "report.json"

    first = write_artifacts(
        observations_json=observations,
        contract_json=contract,
        out=out,
        root=tmp_path,
        current_head_sha="c" * 40,
    )
    first_json = out.read_text(encoding="utf-8")
    first_markdown = out.with_suffix(".md").read_text(encoding="utf-8")
    second = write_artifacts(
        observations_json=observations,
        contract_json=contract,
        out=out,
        root=tmp_path,
        current_head_sha="c" * 40,
    )

    assert first == second
    assert out.read_text(encoding="utf-8") == first_json
    assert out.with_suffix(".md").read_text(encoding="utf-8") == first_markdown
    assert "# SDETKit reviewed product KPI report" in first_markdown
    assert "discovery_precision" in first_markdown
    assert "input_digest:" in first_markdown


def test_product_kpi_freshness_detects_source_head_and_authority_drift(tmp_path: Path) -> None:
    contract = _contract(tmp_path)
    observations = _observations(tmp_path, contract)
    out = tmp_path / "report.json"
    payload = write_artifacts(
        observations_json=observations,
        contract_json=contract,
        out=out,
        root=tmp_path,
        current_head_sha="d" * 40,
    )

    fresh = validate_freshness(
        payload,
        observations_json=observations,
        contract_json=contract,
        root=tmp_path,
        current_head_sha="d" * 40,
    )
    assert fresh["fresh"] is True
    assert fresh["authority_valid"] is True

    head_stale = validate_freshness(
        payload,
        observations_json=observations,
        contract_json=contract,
        root=tmp_path,
        current_head_sha="e" * 40,
    )
    assert head_stale["fresh"] is False
    assert "input_provenance_mismatch" in head_stale["reasons"]

    tampered = json.loads(json.dumps(payload))
    tampered["automation_allowed"] = True
    authority_stale = validate_freshness(
        tampered,
        observations_json=observations,
        contract_json=contract,
        root=tmp_path,
        current_head_sha="d" * 40,
    )
    assert authority_stale["fresh"] is False
    assert authority_stale["authority_valid"] is False
    assert "automation_allowed_mismatch" in authority_stale["reasons"]

    source_payload = json.loads(observations.read_text(encoding="utf-8"))
    source_payload["observations"][0]["review_notes"] = "Changed review evidence."
    observations.write_text(json.dumps(source_payload), encoding="utf-8")
    source_stale = validate_freshness(
        payload,
        observations_json=observations,
        contract_json=contract,
        root=tmp_path,
        current_head_sha="d" * 40,
    )
    assert source_stale["fresh"] is False
    assert "input_provenance_mismatch" in source_stale["reasons"]


def test_product_kpi_freshness_handles_missing_report(tmp_path: Path) -> None:
    contract = _contract(tmp_path)
    observations = _observations(tmp_path, contract)

    payload = check_freshness(
        report_path=tmp_path / "missing.json",
        observations_json=observations,
        contract_json=contract,
        root=tmp_path,
        current_head_sha="f" * 40,
    )

    assert payload["fresh"] is False
    assert payload["reasons"] == ["report_missing"]


def test_product_kpi_report_module_cli_generates_artifacts(tmp_path: Path, capsys) -> None:
    contract = _contract(tmp_path)
    observations = _observations(tmp_path, contract)
    out = tmp_path / "report.json"

    rc = main(
        [
            "--observations-json",
            str(observations),
            "--contract-json",
            str(contract),
            "--out",
            str(out),
            "--root",
            ".",
            "--format",
            "text",
        ]
    )

    assert rc == 0
    assert out.is_file()
    assert out.with_suffix(".md").is_file()
    assert "# SDETKit reviewed product KPI report" in capsys.readouterr().out
