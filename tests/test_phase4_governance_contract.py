from __future__ import annotations

import json
from pathlib import Path

from scripts import check_phase4_governance_contract as contract


def _write_baseline_docs(root: Path) -> None:
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "docs/index.md").write_text(
        "\n".join(
            [
                "# index",
                "- [Versioning and support posture](versioning-and-support.md)",
                "- [Stability levels](stability-levels.md)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "docs/operator-essentials.md").write_text(
        "\n".join(
            [
                "make phase4-governance-contract",
                "python scripts/validate_enterprise_contracts.py",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    for name in (
        "versioning-and-support.md",
        "stability-levels.md",
        "integrations-and-extension-boundary.md",
    ):
        (root / "docs" / name).write_text("ok\n", encoding="utf-8")


def test_phase4_governance_contract_positive_path(tmp_path: Path, monkeypatch) -> None:
    _write_baseline_docs(tmp_path)
    monkeypatch.chdir(tmp_path)

    rc = contract.main(["--format", "json", "--last-review-at", "2026-04-01"])
    assert rc == 0

    payload = json.loads((tmp_path / "build/phase4-governance/phase4-governance-contract.json").read_text())
    assert payload["schema_version"] == "sdetkit.phase4_governance_contract.v2"
    assert payload["legacy_schema_version"] == "sdetkit.phase4_governance_contract.v1"
    assert payload["governance_checks"] == sorted(payload["governance_checks"], key=lambda r: r["check_id"])
    assert payload["policy_decisions"] == sorted(payload["policy_decisions"], key=lambda r: r["decision_id"])


def test_phase4_governance_contract_missing_docs_fails(tmp_path: Path, monkeypatch) -> None:
    _write_baseline_docs(tmp_path)
    (tmp_path / "docs/stability-levels.md").unlink()
    monkeypatch.chdir(tmp_path)

    rc = contract.main(["--format", "json", "--last-review-at", "2026-04-01"])
    assert rc == 1


def test_phase4_governance_contract_invalid_last_review_date_fails(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    _write_baseline_docs(tmp_path)
    monkeypatch.chdir(tmp_path)

    rc = contract.main(["--format", "json", "--last-review-at", "04/01/2026"])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 1
    assert "last_review_at must use YYYY-MM-DD" in payload["failures"]


def test_phase4_validate_output_contracts_handles_invalid_row_types() -> None:
    failures = contract._validate_output_contracts(
        governance_payload={
            "schema_version": "sdetkit.phase4_governance_contract.v2",
            "governance_checks": ["not-an-object"],
            "policy_decisions": "not-a-list",
            "compatibility_contract": {},
            "release_evidence_contract": {},
            "generated_at": "2026-04-19T00:00:00Z",
        },
        release_payload={
            "schema_version": "sdetkit.phase4_release_evidence.v1",
            "required_artifacts": [],
            "discovered_artifacts": [],
            "missing_artifacts": [],
            "retention_window_days": 90,
            "evidence_status": "complete",
            "generated_at": "2026-04-19T00:00:00Z",
        },
        adherence_payload={
            "schema_version": "sdetkit.phase4_governance_adherence.v1",
            "review_cadence_days": 30,
            "last_review_at": "",
            "next_review_due_at": "",
            "adherence_status": "unknown",
            "blockers": [],
            "recommended_actions": ["set review"],
        },
    )

    assert "governance_checks rows must be objects" in failures
    assert "policy_decisions must be a list" in failures


def test_phase4_validate_output_contracts_flags_unsorted_policy_decisions() -> None:
    failures = contract._validate_output_contracts(
        governance_payload={
            "schema_version": "sdetkit.phase4_governance_contract.v2",
            "governance_checks": [],
            "policy_decisions": [
                {"decision_id": "z", "disposition": "accepted", "rationale_code": "audit_readiness", "impact_tier": "now"},
                {"decision_id": "a", "disposition": "accepted", "rationale_code": "audit_readiness", "impact_tier": "now"},
            ],
            "compatibility_contract": {"deprecation_boundaries": ["x"], "compatibility_guards": ["y"]},
            "release_evidence_contract": {"required_artifacts": ["docs/index.md"], "retention_window_days": 10},
            "generated_at": "2026-04-19T00:00:00Z",
        },
        release_payload={
            "schema_version": "sdetkit.phase4_release_evidence.v1",
            "required_artifacts": ["docs/index.md"],
            "discovered_artifacts": [],
            "missing_artifacts": ["docs/index.md"],
            "retention_window_days": 10,
            "evidence_status": "incomplete",
            "generated_at": "2026-04-19T00:00:00Z",
        },
        adherence_payload={
            "schema_version": "sdetkit.phase4_governance_adherence.v1",
            "review_cadence_days": 30,
            "last_review_at": "",
            "next_review_due_at": "",
            "adherence_status": "unknown",
            "blockers": [],
            "recommended_actions": ["set review"],
        },
    )

    assert "policy_decisions not deterministically sorted" in failures


def test_phase4_validate_output_contracts_flags_release_contract_type() -> None:
    failures = contract._validate_output_contracts(
        governance_payload={
            "schema_version": "sdetkit.phase4_governance_contract.v2",
            "governance_checks": [],
            "policy_decisions": [],
            "compatibility_contract": {},
            "release_evidence_contract": "not-an-object",
            "generated_at": "2026-04-19T00:00:00Z",
        },
        release_payload={
            "schema_version": "sdetkit.phase4_release_evidence.v1",
            "required_artifacts": [],
            "discovered_artifacts": [],
            "missing_artifacts": [],
            "retention_window_days": 90,
            "evidence_status": "complete",
            "generated_at": "2026-04-19T00:00:00Z",
        },
        adherence_payload={
            "schema_version": "sdetkit.phase4_governance_adherence.v1",
            "review_cadence_days": 30,
            "last_review_at": "",
            "next_review_due_at": "",
            "adherence_status": "unknown",
            "blockers": [],
            "recommended_actions": ["set review"],
        },
    )

    assert "release_evidence_contract must be an object" in failures


def test_phase4_validate_output_contracts_flags_compatibility_contract_type() -> None:
    failures = contract._validate_output_contracts(
        governance_payload={
            "schema_version": "sdetkit.phase4_governance_contract.v2",
            "governance_checks": [],
            "policy_decisions": [],
            "compatibility_contract": "not-an-object",
            "release_evidence_contract": {},
            "generated_at": "2026-04-19T00:00:00Z",
        },
        release_payload={
            "schema_version": "sdetkit.phase4_release_evidence.v1",
            "required_artifacts": [],
            "discovered_artifacts": [],
            "missing_artifacts": [],
            "retention_window_days": 90,
            "evidence_status": "complete",
            "generated_at": "2026-04-19T00:00:00Z",
        },
        adherence_payload={
            "schema_version": "sdetkit.phase4_governance_adherence.v1",
            "review_cadence_days": 30,
            "last_review_at": "",
            "next_review_due_at": "",
            "adherence_status": "unknown",
            "blockers": [],
            "recommended_actions": ["set review"],
        },
    )

    assert "compatibility_contract must be an object" in failures


def test_phase4_main_reports_malformed_governance_check_rows(tmp_path: Path, monkeypatch, capsys) -> None:
    _write_baseline_docs(tmp_path)
    monkeypatch.chdir(tmp_path)

    def _bad_payload(_ns):
        return {
            "schema_version": "sdetkit.phase4_governance_contract.v2",
            "governance_checks": [
                {
                    "check_id": "broken",
                    "status": "pass",
                    "reason_code": "",
                    "evidence_refs": [],
                    "owner_hint": "ops",
                    "policy_domain": "contract",
                }
            ],
            "policy_decisions": [
                {
                    "decision_id": "d1",
                    "policy_id": "p1",
                    "disposition": "accepted",
                    "rationale_code": "audit_readiness",
                    "impact_tier": "now",
                }
            ],
            "compatibility_contract": {
                "supported_tiers": ["tier0"],
                "deprecation_boundaries": ["notice"],
                "compatibility_guards": ["make phase4-governance-contract"],
            },
            "release_evidence_contract": {"required_artifacts": ["docs/index.md"], "retention_window_days": 90},
            "generated_at": "2026-04-19T00:00:00Z",
            "ok": True,
            "checks": [],
            "failures": [],
        }

    monkeypatch.setattr(contract, "_build_governance_payload", _bad_payload)
    rc = contract.main(["--format", "json", "--last-review-at", "2026-04-01"])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 1
    assert any("governance_checks.reason_code" in failure for failure in payload["failures"])
    assert any("governance_checks.evidence_refs" in failure for failure in payload["failures"])


def test_phase4_corrupt_emitted_contract_reports_schema_errors(tmp_path: Path, monkeypatch) -> None:
    _write_baseline_docs(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert contract.main(["--format", "json", "--last-review-at", "2026-04-01"]) == 0

    out_dir = tmp_path / "build/phase4-governance"
    governance = json.loads((out_dir / "phase4-governance-contract.json").read_text(encoding="utf-8"))
    release = json.loads((out_dir / "phase4-release-evidence.json").read_text(encoding="utf-8"))
    adherence = json.loads((out_dir / "phase4-governance-adherence.json").read_text(encoding="utf-8"))

    governance.pop("generated_at", None)
    governance["policy_decisions"] = "invalid"

    failures = contract._validate_output_contracts(governance, release, adherence)
    assert "governance payload missing key: generated_at" in failures
    assert "policy_decisions must be a list" in failures


def test_phase4_governance_emits_overlay_template_and_drift_artifacts(tmp_path: Path, monkeypatch) -> None:
    _write_baseline_docs(tmp_path)
    monkeypatch.chdir(tmp_path)

    rc = contract.main(["--format", "json", "--last-review-at", "2026-04-01"])
    assert rc == 0

    out_dir = tmp_path / "build/phase4-governance"
    overlay = json.loads((out_dir / "phase4-compliance-overlay-pack.json").read_text(encoding="utf-8"))
    template = json.loads((out_dir / "phase4-policy-as-code-template.json").read_text(encoding="utf-8"))
    drift = json.loads((out_dir / "phase4-governance-drift-alerts.json").read_text(encoding="utf-8"))

    assert overlay["schema_version"] == "sdetkit.phase4_compliance_overlay_pack.v1"
    assert [row["domain"] for row in overlay["overlays"]] == sorted([row["domain"] for row in overlay["overlays"]])
    assert template["schema_version"] == "sdetkit.phase4_policy_as_code_template.v1"
    assert [row["rule_id"] for row in template["rules"]] == sorted([row["rule_id"] for row in template["rules"]])
    assert drift["schema_version"] == "sdetkit.phase4_governance_drift_alerts.v1"
    assert drift["alerts"] == sorted(drift["alerts"])


def test_phase4_drift_alerts_detect_release_missing_artifacts() -> None:
    drift = contract._build_governance_drift_alerts(
        governance_payload={"governance_checks": []},
        release_payload={"missing_artifacts": ["b", "a"]},
        adherence_payload={"adherence_status": "on_track"},
    )
    assert drift["drift_status"] == "drift"
    assert drift["drift_score"] == 2
    assert drift["alerts"] == ["release_missing_artifacts:a,b"]


def test_phase4_drift_threshold_treats_due_only_as_healthy() -> None:
    drift = contract._build_governance_drift_alerts(
        governance_payload={"governance_checks": []},
        release_payload={"missing_artifacts": []},
        adherence_payload={"adherence_status": "due"},
    )
    assert drift["drift_score"] == 1
    assert drift["drift_status"] == "healthy"


def test_phase4_end_to_end_artifacts_are_non_empty_json_objects(tmp_path: Path, monkeypatch) -> None:
    _write_baseline_docs(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert contract.main(["--format", "json", "--last-review-at", "2026-04-01"]) == 0

    out_dir = tmp_path / "build/phase4-governance"
    artifact_names = [
        "phase4-governance-contract.json",
        "phase4-release-evidence.json",
        "phase4-governance-adherence.json",
        "phase4-compliance-overlay-pack.json",
        "phase4-policy-as-code-template.json",
        "phase4-governance-drift-alerts.json",
        "phase4-compliance-overlay-privacy.json",
        "phase4-compliance-overlay-regulated.json",
        "phase4-compliance-overlay-security.json",
    ]
    for name in artifact_names:
        payload = json.loads((out_dir / name).read_text(encoding="utf-8"))
        assert isinstance(payload, dict)
        assert payload


def test_phase4_drift_alerts_markdown_emitted(tmp_path: Path, monkeypatch) -> None:
    _write_baseline_docs(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert contract.main(["--format", "json", "--last-review-at", "2026-04-01"]) == 0

    md_path = tmp_path / "build/phase4-governance/phase4-governance-drift-alerts.md"
    assert md_path.exists()
    text = md_path.read_text(encoding="utf-8")
    assert "# Phase 4 governance drift alerts" in text
    assert "drift_threshold" in text


def test_phase4_drift_score_mapping_constant_is_applied() -> None:
    assert contract.DEFAULT_DRIFT_SCORE_BY_SIGNAL["adherence_status"] == 1
    drift = contract._build_governance_drift_alerts(
        governance_payload={"governance_checks": []},
        release_payload={"missing_artifacts": []},
        adherence_payload={"adherence_status": "overdue"},
    )
    assert drift["drift_score"] == 1


def test_phase4_drift_markdown_parity_with_json(tmp_path: Path, monkeypatch) -> None:
    _write_baseline_docs(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert contract.main(["--format", "json", "--last-review-at", "2026-04-01"]) == 0

    out_dir = tmp_path / "build/phase4-governance"
    drift = json.loads((out_dir / "phase4-governance-drift-alerts.json").read_text(encoding="utf-8"))
    md = (out_dir / "phase4-governance-drift-alerts.md").read_text(encoding="utf-8")

    assert f"`{drift['drift_status']}`" in md
    assert f"`{drift['drift_score']}`" in md
    for alert in drift["alerts"]:
        assert f"`{alert}`" in md


def test_phase4_loads_external_drift_scoring_config(tmp_path: Path) -> None:
    cfg = tmp_path / "drift.json"
    cfg.write_text('{"adherence_status": 3}', encoding="utf-8")
    loaded = contract._load_drift_scoring_config(cfg)
    assert loaded["adherence_status"] == 3
    assert loaded["governance_check_failures"] == 2


def test_phase4_malformed_drift_config_falls_back_to_defaults(tmp_path: Path) -> None:
    cfg = tmp_path / "bad.json"
    cfg.write_text('{"adherence_status":"oops"}', encoding="utf-8")
    loaded = contract._load_drift_scoring_config(cfg)
    assert loaded == contract.DEFAULT_DRIFT_SCORE_BY_SIGNAL


def test_phase4_drift_threshold_cli_override(tmp_path: Path, monkeypatch) -> None:
    _write_baseline_docs(tmp_path)
    monkeypatch.chdir(tmp_path)
    rc = contract.main(["--format", "json", "--drift-threshold", "1", "--last-review-at", "2026-04-01"])
    assert rc == 0

    drift = json.loads((tmp_path / "build/phase4-governance/phase4-governance-drift-alerts.json").read_text(encoding="utf-8"))
    assert drift["drift_threshold"] == 1


def test_phase4_negative_drift_threshold_is_clamped_to_zero(tmp_path: Path, monkeypatch) -> None:
    _write_baseline_docs(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert contract.main(["--format", "json", "--drift-threshold", "-1", "--last-review-at", "2026-04-01"]) == 0

    drift = json.loads((tmp_path / "build/phase4-governance/phase4-governance-drift-alerts.json").read_text(encoding="utf-8"))
    assert drift["drift_threshold"] == 0


def test_phase4_validate_drift_alerts_rejects_malformed_schema() -> None:
    failures = contract._validate_drift_alerts(
        {
            "schema_version": "sdetkit.phase4_governance_drift_alerts.v1",
            "drift_status": "bad",
            "alerts": "not-a-list",
            "drift_score": "x",
            "drift_threshold": -1,
            "generated_at": "2026-04-20T00:00:00Z",
        }
    )
    assert "invalid drift_status: bad" in failures
    assert "drift alerts list must be sorted" in failures
    assert "drift_score must be int" in failures
    assert "drift_threshold must be non-negative int" in failures
