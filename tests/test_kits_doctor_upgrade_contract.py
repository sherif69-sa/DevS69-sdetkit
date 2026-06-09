from __future__ import annotations

from pathlib import Path

from sdetkit import kits


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
dependencies = [
  "httpx>=0.28",
]
""".strip(),
        encoding="utf-8",
    )
    return tmp_path


def test_optimize_payload_materializes_doctor_upgrade_lane(tmp_path: Path) -> None:
    payload = kits.optimize_payload(_repo(tmp_path), goal="optimize repo")
    lane = payload["doctor_upgrade_lane"]

    assert lane["status"] == "materialized"
    assert lane["classification"] == "diagnostic_intelligence"
    assert lane["entrypoint"] == "sdetkit doctor --dev --ci --repo --upgrade-audit"
    assert lane["next_allowed_action"] == "run_doctor_upgrade_audit"
    assert (
        "python -m sdetkit doctor --dev --ci --repo --upgrade-audit --format json"
        in lane["proof_commands"]
    )
    assert "no remediation is applied automatically" in lane["acceptance_criteria"]

    boundary = lane["authority_boundary"]
    assert boundary["automation_allowed"] is False
    assert boundary["patch_application_allowed"] is False
    assert boundary["merge_authorized"] is False
    assert boundary["semantic_equivalence_proven"] is False


def test_optimize_payload_search_query_points_to_materialized_doctor_lane(tmp_path: Path) -> None:
    payload = kits.optimize_payload(_repo(tmp_path), goal="optimize repo")
    queries = payload["search_queries"]

    assert {
        "topic": "doctor-upgrade-lane",
        "status": "materialized",
        "owner_lane": "doctor_upgrade_lane",
        "next_allowed_action": "run_doctor_upgrade_audit",
    } in queries


def test_optimize_payload_keeps_autofix_behind_verified_safe_contract(tmp_path: Path) -> None:
    payload = kits.optimize_payload(_repo(tmp_path), goal="optimize repo")

    assert payload["doctor_quality_contract"]["auto_fix_requires"] == "verified_safe_fix_contract"
    assert payload["operating_sequence"] == [
        {"stage": "doctor-first"},
        {"stage": "intelligent-autofix"},
    ]
    assert payload["doctor_upgrade_lane"]["next_allowed_action"] == "run_doctor_upgrade_audit"
