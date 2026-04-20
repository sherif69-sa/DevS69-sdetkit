from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import check_phase1_baseline_summary_contract as phase1_contract
from scripts import check_phase2_start_summary_contract as phase2_contract
from scripts import check_phase3_quality_contract as phase3_contract
from scripts import check_phase4_governance_contract as phase4_contract
from scripts import check_phase5_ecosystem_contract as contract

EXPECTED_GATE_CHECK_IDS = [
    "schema_completeness",
    "ecosystem_policy_compatibility",
    "partner_packaging_presence_schema",
    "reliability_presence_schema",
    "drift_alerts_presence_schema",
    "deterministic_ordering",
    "reason_rationale_vocabulary_enforced",
]
EXPECTED_ARTIFACT_KEYS = [
    "ecosystem_contract",
    "ecosystem_drift_alerts",
    "ecosystem_reliability",
    "partner_packaging",
]
EXPECTED_RESULT_KEYS = [
    "artifacts",
    "checks",
    "failures",
    "gate_checks",
    "legacy_checks",
    "ok",
    "out_dir",
    "schema_version",
]
REPO_PHASE_FLOW_TARGETS = [
    "phase2-seed",
    "phase3-quality-contract",
    "phase4-governance-contract",
    "phase5-ecosystem-contract",
]


def _write_phase5_prereqs(root: Path) -> None:
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "src/sdetkit").mkdir(parents=True, exist_ok=True)

    (root / "docs/integrations-and-extension-boundary.md").write_text("ok\n", encoding="utf-8")
    (root / "docs/operator-essentials.md").write_text("make phase5-ecosystem-contract\n", encoding="utf-8")
    (root / "src/sdetkit/plugin_system.py").write_text("# plugin system\n", encoding="utf-8")
    (root / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")


def test_phase5_contract_constants_are_non_empty_and_unique() -> None:
    assert EXPECTED_GATE_CHECK_IDS
    assert EXPECTED_ARTIFACT_KEYS
    assert EXPECTED_RESULT_KEYS
    assert len(EXPECTED_GATE_CHECK_IDS) == len(set(EXPECTED_GATE_CHECK_IDS))
    assert len(EXPECTED_ARTIFACT_KEYS) == len(set(EXPECTED_ARTIFACT_KEYS))
    assert len(EXPECTED_RESULT_KEYS) == len(set(EXPECTED_RESULT_KEYS))


def _run_phase5_subprocess(*, cwd: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    script = Path(__file__).resolve().parents[1] / "scripts" / "check_phase5_ecosystem_contract.py"
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def test_phase5_ecosystem_contract_positive_path(tmp_path: Path, monkeypatch) -> None:
    _write_phase5_prereqs(tmp_path)
    monkeypatch.chdir(tmp_path)

    rc = contract.main(["--format", "json"])
    assert rc == 0

    payload = json.loads((tmp_path / "build/phase5-ecosystem/phase5-ecosystem-contract.json").read_text())
    assert payload["schema_version"] == contract.SCHEMA_VERSION
    assert payload["legacy_schema_version"] == contract.LEGACY_SCHEMA_VERSION
    assert payload["ecosystem_checks"] == sorted(payload["ecosystem_checks"], key=lambda row: row["check_id"])
    assert payload["extension_policy"] == sorted(payload["extension_policy"], key=lambda row: row["policy_id"])
    result = contract._build_result_payload(
        failures=[],
        ecosystem_payload=payload,
        out_dir=tmp_path / "build/phase5-ecosystem",
        artifacts={"ecosystem_contract": "build/phase5-ecosystem/phase5-ecosystem-contract.json"},
    )
    assert result["gate_checks"]
    assert result["checks"] == payload["checks"]
    assert result["legacy_checks"] == payload["checks"]
    assert all(row["ok"] for row in result["gate_checks"])


def test_phase5_missing_reason_or_rationale_code_fails() -> None:
    failures = contract._validate_policy_and_compatibility(
        {
            "ecosystem_checks": [
                {
                    "check_id": "plugin.runtime.boundary",
                    "status": "pass",
                    "reason_code": "",
                    "evidence_refs": ["src/sdetkit/plugin_system.py"],
                    "owner_hint": "ecosystem-ops",
                    "ecosystem_domain": "plugin_reliability",
                }
            ],
            "extension_policy": [
                {
                    "policy_id": "extension.failure.isolation",
                    "disposition": "accepted",
                    "rationale_code": "",
                    "impact_tier": "now",
                }
            ],
            "plugin_reliability_contract": {
                "supported_extension_modes": ["entry_points"],
                "failure_isolation_guards": ["guard"],
                "compatibility_guards": ["make phase5-ecosystem-contract"],
            },
            "partner_packaging_contract": {
                "required_artifacts": ["pyproject.toml"],
                "support_surface": ["make phase5-ecosystem-contract"],
                "auditability_status": "pass",
            },
        }
    )
    assert any("ecosystem_checks.reason_code" in failure for failure in failures)
    assert any("extension_policy.rationale_code" in failure for failure in failures)


def test_phase5_regression_contracts_for_phase1_to_phase4_unchanged() -> None:
    makefile_text = Path("Makefile").read_text(encoding="utf-8")
    assert "phase3-quality-contract" in makefile_text
    assert "phase4-governance-contract" in makefile_text
    assert "phase5-ecosystem-contract" in makefile_text

    assert phase1_contract.REQUIRED_TOP_LEVEL["schema_version"] == "sdetkit.phase1_baseline.v1"
    assert phase2_contract.EXPECTED_SCHEMA == "sdetkit.phase2_start_workflow.v1"
    assert callable(phase3_contract.main)
    assert phase4_contract.SCHEMA_VERSION == "sdetkit.phase4_governance_contract.v2"


def test_phase5_flow_alignment_with_repo_phase_order() -> None:
    makefile_text = Path("Makefile").read_text(encoding="utf-8")
    positions = [makefile_text.find(target) for target in REPO_PHASE_FLOW_TARGETS]
    assert all(pos >= 0 for pos in positions)
    assert positions == sorted(positions)


def test_phase5_main_json_result_includes_artifact_map(tmp_path: Path, monkeypatch, capsys) -> None:
    _write_phase5_prereqs(tmp_path)
    monkeypatch.chdir(tmp_path)

    rc = contract.main(["--format", "json"])
    result = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert sorted(result["artifacts"]) == EXPECTED_ARTIFACT_KEYS
    assert [row["id"] for row in result["gate_checks"]] == EXPECTED_GATE_CHECK_IDS
    assert result["checks"] == result["legacy_checks"]
    assert result["gate_checks"]


def test_phase5_cli_json_subprocess_smoke(tmp_path: Path) -> None:
    _write_phase5_prereqs(tmp_path)
    proc = _run_phase5_subprocess(cwd=tmp_path, args=["--format", "json", "--out-dir", "build/phase5-ecosystem"])

    assert proc.returncode == 0
    result = json.loads(proc.stdout)
    assert result["ok"] is True
    assert "artifacts" in result
    assert (tmp_path / "build/phase5-ecosystem/phase5-ecosystem-contract.json").is_file()


def test_phase5_cli_subprocess_rejects_invalid_format(tmp_path: Path) -> None:
    proc = _run_phase5_subprocess(cwd=tmp_path, args=["--format", "yaml"])

    assert proc.returncode != 0
    assert "invalid choice" in proc.stderr
    assert "--format" in proc.stderr


def test_phase5_cli_subprocess_fails_with_unwritable_out_dir(tmp_path: Path) -> None:
    _write_phase5_prereqs(tmp_path)
    blocked = tmp_path / "blocked-out-dir"
    blocked.write_text("not-a-directory\n", encoding="utf-8")

    proc = _run_phase5_subprocess(cwd=tmp_path, args=["--format", "json", "--out-dir", str(blocked)])

    assert proc.returncode != 0
    assert proc.stderr
    assert re.search(r"FileExistsError|NotADirectoryError", proc.stderr)


def test_phase5_json_result_shape_contract(tmp_path: Path, monkeypatch, capsys) -> None:
    _write_phase5_prereqs(tmp_path)
    monkeypatch.chdir(tmp_path)

    rc = contract.main(["--format", "json"])
    result = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert sorted(result) == EXPECTED_RESULT_KEYS
    assert isinstance(result["artifacts"], dict)
    assert isinstance(result["checks"], list)
    assert isinstance(result["gate_checks"], list)
    assert isinstance(result["legacy_checks"], list)
    assert isinstance(result["failures"], list)


@pytest.mark.parametrize(
    ("corrupt_name", "expected_failure", "expected_gate_check"),
    [
        (
            "phase5-ecosystem-contract.json",
            "ecosystem payload schema_version must be",
            "schema_completeness",
        ),
        (
            "phase5-partner-packaging.json",
            "partner packaging schema_version must be",
            "partner_packaging_presence_schema",
        ),
        (
            "phase5-ecosystem-reliability.json",
            "reliability schema_version must be",
            "reliability_presence_schema",
        ),
        (
            "phase5-ecosystem-drift-alerts.json",
            "drift schema_version must be",
            "drift_alerts_presence_schema",
        ),
    ],
)
def test_phase5_main_fails_when_emitted_artifact_is_unreadable(
    tmp_path: Path,
    monkeypatch,
    capsys,
    corrupt_name: str,
    expected_failure: str,
    expected_gate_check: str,
) -> None:
    _write_phase5_prereqs(tmp_path)
    monkeypatch.chdir(tmp_path)

    original_write_json = contract._write_json

    def _write_with_corrupt_drift(path: Path, payload: dict[str, object]) -> None:
        if path.name == corrupt_name:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{not-valid-json", encoding="utf-8")
            return
        original_write_json(path, payload)

    monkeypatch.setattr(contract, "_write_json", _write_with_corrupt_drift)
    rc = contract.main(["--format", "json"])
    result = json.loads(capsys.readouterr().out)

    assert rc == 1
    assert any(expected_failure in failure for failure in result["failures"])
    gate_checks = {row["id"]: row["ok"] for row in result["gate_checks"]}
    assert sorted(gate_checks) == sorted(EXPECTED_GATE_CHECK_IDS)
    assert gate_checks[expected_gate_check] is False
