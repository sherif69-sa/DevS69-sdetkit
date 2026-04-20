from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import check_phase1_baseline_summary_contract as phase1_contract
from scripts import check_phase2_start_summary_contract as phase2_contract
from scripts import check_phase3_quality_contract as phase3_contract
from scripts import check_phase4_governance_contract as phase4_contract
from scripts import check_phase5_ecosystem_contract as phase5_contract
from scripts import check_phase6_metrics_contract as contract

EXPECTED_PHASE6_GATE_CHECK_IDS = [
    "schema_completeness",
    "metrics_policy_freshness_linkage",
    "kpi_snapshot_presence_schema",
    "commercial_scorecard_presence_schema",
    "drift_alerts_presence_schema",
    "deterministic_ordering",
    "reason_rationale_vocabulary_enforced",
]
EXPECTED_PHASE6_WORKFLOW_TARGETS = [
    "phase5-ecosystem-contract",
    "phase6-start",
    "phase6-status",
    "phase6-progress",
    "phase6-complete",
    "phase6-metrics-contract",
]


def _write_phase6_prereqs(root: Path) -> None:
    (root / "build/phase1-baseline").mkdir(parents=True, exist_ok=True)
    (root / "build/phase3-quality").mkdir(parents=True, exist_ok=True)
    (root / "build/phase5-ecosystem").mkdir(parents=True, exist_ok=True)
    (root / "build/phase1-baseline/phase1-baseline-summary.json").write_text(
        "{}\n", encoding="utf-8"
    )
    (root / "build/phase3-quality/phase3-trend-delta.json").write_text("{}\n", encoding="utf-8")
    (root / "build/phase5-ecosystem/phase5-ecosystem-contract.json").write_text(
        "{}\n", encoding="utf-8"
    )


def _run_phase6_subprocess(*, cwd: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    script = Path(__file__).resolve().parents[1] / "scripts" / "check_phase6_metrics_contract.py"
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture
def phase6_workspace(tmp_path: Path, monkeypatch) -> Path:
    _write_phase6_prereqs(tmp_path)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_phase6_metrics_contract_positive_path(phase6_workspace: Path, capsys) -> None:

    rc = contract.main(["--format", "json"])
    result = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert result["ok"] is True
    payload = json.loads(
        (phase6_workspace / "build/phase6-metrics/phase6-metrics-contract.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["schema_version"] == contract.SCHEMA_VERSION
    assert payload["metric_snapshots"] == sorted(
        payload["metric_snapshots"], key=lambda row: row["metric_id"]
    )
    assert payload["scorecard_policies"] == sorted(
        payload["scorecard_policies"], key=lambda row: row["policy_id"]
    )


def test_phase6_legacy_cli_args_are_accepted(phase6_workspace: Path) -> None:
    rc = contract.main(
        [
            "--format",
            "json",
            "--docs-index",
            "docs/index.md",
            "--operator-essentials",
            "docs/operator-essentials.md",
        ]
    )
    assert rc == 0


def test_phase6_missing_reason_or_rationale_code_fails() -> None:
    failures = contract._validate_policy_and_contract_fields(
        {
            "metric_snapshots": [
                {
                    "metric_id": "m1",
                    "status": "green",
                    "value": 1,
                    "unit": "count",
                    "trend": "flat",
                    "reason_code": "",
                    "evidence_refs": ["a.json"],
                    "owner_hint": "ops",
                    "metric_domain": "kpi_snapshot",
                }
            ],
            "scorecard_policies": [
                {
                    "policy_id": "p1",
                    "disposition": "accepted",
                    "rationale_code": "",
                    "impact_tier": "now",
                }
            ],
            "metrics_contract": {
                "required_kpis": ["kpi_a"],
                "freshness_sla_days": 7,
                "linkage_guards": ["g1"],
            },
            "commercialization_contract": {
                "required_evidence_surfaces": ["a.json"],
                "reporting_audience": ["operators"],
                "auditability_status": "partial",
            },
        }
    )

    assert any("metric_snapshots.reason_code" in failure for failure in failures)
    assert any("scorecard_policies.rationale_code" in failure for failure in failures)


def test_phase6_missing_required_contract_keys_fail() -> None:
    failures = contract._validate_policy_and_contract_fields(
        {
            "metric_snapshots": [],
            "scorecard_policies": [],
            "metrics_contract": {
                "required_kpis": [],
                "freshness_sla_days": 0,
                "linkage_guards": [],
            },
            "commercialization_contract": {
                "required_evidence_surfaces": [],
                "reporting_audience": [],
            },
        }
    )
    assert "metrics_contract.required_kpis missing/empty" in failures
    assert "metrics_contract.freshness_sla_days must be positive int" in failures
    assert "metrics_contract.linkage_guards missing/empty" in failures
    assert "commercialization_contract.required_evidence_surfaces missing/empty" in failures
    assert "commercialization_contract.reporting_audience missing/empty" in failures


def test_phase6_missing_metric_and_policy_lists_fail() -> None:
    failures = contract._validate_policy_and_contract_fields(
        {
            "metric_snapshots": [],
            "scorecard_policies": [],
            "metrics_contract": {
                "required_kpis": ["kpi_a"],
                "freshness_sla_days": 7,
                "linkage_guards": ["guard"],
            },
            "commercialization_contract": {
                "required_evidence_surfaces": ["a.json"],
                "reporting_audience": ["operators"],
                "auditability_status": "partial",
            },
        }
    )
    assert "metric_snapshots missing/empty" in failures
    assert "scorecard_policies missing/empty" in failures


def test_phase6_deterministic_list_order_failures_are_enforced() -> None:
    failures = contract._validate_policy_and_contract_fields(
        {
            "metric_snapshots": [
                {
                    "metric_id": "m1",
                    "status": "green",
                    "value": 1,
                    "unit": "count",
                    "trend": "flat",
                    "reason_code": "contract_satisfied",
                    "evidence_refs": ["z.json", "a.json"],
                    "owner_hint": "ops",
                    "metric_domain": "kpi_snapshot",
                }
            ],
            "scorecard_policies": [
                {
                    "policy_id": "p1",
                    "disposition": "accepted",
                    "rationale_code": "signal_quality",
                    "impact_tier": "now",
                }
            ],
            "metrics_contract": {
                "required_kpis": ["kpi_b", "kpi_a"],
                "freshness_sla_days": 7,
                "linkage_guards": ["g2", "g1"],
            },
            "commercialization_contract": {
                "required_evidence_surfaces": ["z.json", "a.json"],
                "reporting_audience": ["operators", "buyers"],
                "auditability_status": "partial",
            },
        }
    )
    assert any("metric_snapshots.evidence_refs must be sorted" in failure for failure in failures)
    assert "metrics_contract.required_kpis must be sorted list" in failures
    assert "metrics_contract.linkage_guards must be sorted list" in failures
    assert "commercialization_contract.required_evidence_surfaces must be sorted list" in failures
    assert "commercialization_contract.reporting_audience must be sorted list" in failures


def test_phase6_validate_output_contracts_missing_subartifact_keys_fail() -> None:
    failures = contract._validate_output_contracts(
        metrics_payload={
            "schema_version": contract.SCHEMA_VERSION,
            "metric_snapshots": [],
            "scorecard_policies": [],
            "metrics_contract": {
                "required_kpis": ["kpi_a"],
                "freshness_sla_days": 7,
                "linkage_guards": ["guard"],
            },
            "commercialization_contract": {
                "required_evidence_surfaces": ["a.json"],
                "reporting_audience": ["operators"],
                "auditability_status": "partial",
            },
            "generated_at": "2026-01-01T00:00:00Z",
        },
        kpi_snapshot={"schema_version": contract.KPI_SNAPSHOT_SCHEMA_VERSION},
        commercial_scorecard={"schema_version": contract.COMMERCIAL_SCORECARD_SCHEMA_VERSION},
        drift_alerts={"schema_version": contract.METRICS_DRIFT_ALERTS_SCHEMA_VERSION},
    )
    assert any("kpi snapshot missing key" in failure for failure in failures)
    assert any("commercial scorecard missing key" in failure for failure in failures)
    assert any("drift alerts missing key" in failure for failure in failures)


def test_phase6_gate_check_fails_on_missing_metric_snapshots() -> None:
    checks = contract._build_gate_checks(["metric_snapshots missing/empty"])
    by_id = {row["id"]: row["ok"] for row in checks}
    assert by_id["metrics_policy_freshness_linkage"] is False


def test_phase6_gate_check_fails_on_missing_scorecard_policies() -> None:
    checks = contract._build_gate_checks(["scorecard_policies missing/empty"])
    by_id = {row["id"]: row["ok"] for row in checks}
    assert by_id["metrics_policy_freshness_linkage"] is False


def test_phase6_gate_check_schema_completeness_fails_on_subartifact_missing_key() -> None:
    checks = contract._build_gate_checks(["kpi snapshot missing key: freshness_status"])
    by_id = {row["id"]: row["ok"] for row in checks}
    assert by_id["schema_completeness"] is False


def test_phase6_gate_check_ids_order_is_stable() -> None:
    checks = contract._build_gate_checks([])
    assert [row["id"] for row in checks] == EXPECTED_PHASE6_GATE_CHECK_IDS


@pytest.mark.parametrize(
    ("corrupt_name", "expected_gate_id"),
    [
        ("phase6-metrics-contract.json", "schema_completeness"),
        ("phase6-kpi-snapshot.json", "kpi_snapshot_presence_schema"),
        ("phase6-commercial-scorecard.json", "commercial_scorecard_presence_schema"),
        ("phase6-metrics-drift-alerts.json", "drift_alerts_presence_schema"),
    ],
)
def test_phase6_main_fails_when_emitted_artifact_is_unreadable(
    phase6_workspace: Path,
    monkeypatch,
    capsys,
    corrupt_name: str,
    expected_gate_id: str,
) -> None:

    original_write_json = contract._write_json

    def _write_with_corruption(path: Path, payload: dict[str, object]) -> None:
        original_write_json(path, payload)
        if path.name == corrupt_name:
            path.write_text("not-json\n", encoding="utf-8")

    monkeypatch.setattr(contract, "_write_json", _write_with_corruption)
    rc = contract.main(["--format", "json"])
    result = json.loads(capsys.readouterr().out)

    assert rc == 1
    assert result["ok"] is False
    gate = {row["id"]: row["ok"] for row in result["gate_checks"]}
    assert gate[expected_gate_id] is False


def test_phase6_main_positive_path_has_all_gate_checks_true(phase6_workspace: Path, capsys) -> None:

    rc = contract.main(["--format", "json"])
    result = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert result["ok"] is True
    assert all(row["ok"] is True for row in result["gate_checks"])
    assert [row["id"] for row in result["gate_checks"]] == EXPECTED_PHASE6_GATE_CHECK_IDS


def test_phase6_legacy_cli_args_subprocess_smoke(tmp_path: Path) -> None:
    _write_phase6_prereqs(tmp_path)
    proc = _run_phase6_subprocess(
        cwd=tmp_path,
        args=[
            "--format",
            "json",
            "--out-dir",
            "build/phase6-metrics",
            "--docs-index",
            "docs/index.md",
            "--operator-essentials",
            "docs/operator-essentials.md",
        ],
    )

    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert (tmp_path / "build/phase6-metrics/phase6-metrics-contract.json").is_file()


def test_phase6_regression_contracts_phase1_to_phase5_unchanged() -> None:
    assert phase1_contract.REQUIRED_TOP_LEVEL["schema_version"] == "sdetkit.phase1_baseline.v1"
    assert phase2_contract.EXPECTED_SCHEMA == "sdetkit.phase2_start_workflow.v1"
    assert callable(phase3_contract.main)
    assert phase4_contract.SCHEMA_VERSION == "sdetkit.phase4_governance_contract.v2"
    assert phase5_contract.SCHEMA_VERSION == "sdetkit.phase5_ecosystem_contract.v2"

    makefile_text = Path("Makefile").read_text(encoding="utf-8")
    for target in (
        "phase2-seed",
        "phase3-quality-contract",
        "phase4-governance-contract",
        "phase5-ecosystem-contract",
        "phase6-start",
        "phase6-status",
        "phase6-progress",
        "phase6-complete",
        "phase6-metrics-contract",
    ):
        assert target in makefile_text


def test_phase6_workflow_targets_follow_existing_phase_pattern() -> None:
    makefile_text = Path("Makefile").read_text(encoding="utf-8")
    positions = [makefile_text.find(target) for target in EXPECTED_PHASE6_WORKFLOW_TARGETS]
    assert all(pos >= 0 for pos in positions)
    assert positions == sorted(positions)
