from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_workflow_overlap_report.py"


def _module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("build_workflow_overlap_report", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _fixture_repo(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_text(
        """name: CI
on:
  pull_request:
  push:
permissions:
  contents: read
jobs:
  tests:
    name: ci
    runs-on: ubuntu-latest
    steps:
      - run: python -m pytest -q
      - uses: actions/upload-artifact@1111111111111111111111111111111111111111
        with:
          name: proof
          path: build/proof.json
""",
        encoding="utf-8",
    )
    (workflows / "maintenance-autopilot.yml").write_text(
        """name: maintenance-autopilot
on:
  pull_request:
  schedule:
    - cron: '0 1 * * *'
permissions:
  contents: read
jobs:
  verify:
    runs-on: ubuntu-latest
    permissions:
      issues: write
    steps:
      - run: python -m pytest tests/test_contract.py
      - uses: actions/download-artifact@2222222222222222222222222222222222222222
        with:
          name: proof
""",
        encoding="utf-8",
    )
    topology = tmp_path / "docs" / "contracts" / "workflow-topology.v1.json"
    required = tmp_path / "docs" / "contracts" / "required-checks.v1.json"
    plan = tmp_path / "docs" / "contracts" / "workflow-consolidation-plan.v1.json"
    _write_json(
        topology,
        {
            "inventory": [
                ".github/workflows/ci.yml",
                ".github/workflows/maintenance-autopilot.yml",
            ]
        },
    )
    _write_json(required, {"contexts": ["ci", "maintenance-autopilot"]})
    _write_json(
        plan,
        {
            "keep_primary": ["ci.yml"],
            "merge_bundles": {},
            "candidate_retire_or_absorb": [],
            "standalone_supporting": ["maintenance-autopilot.yml"],
        },
    )
    return tmp_path, topology, required, plan


def test_fixture_report_records_triggers_permissions_artifacts_and_proof_overlap(
    tmp_path: Path,
) -> None:
    module = _module()
    root, topology, required, plan = _fixture_repo(tmp_path)

    report = module.build_report(
        root,
        topology_contract=topology,
        required_checks_contract=required,
        consolidation_plan=plan,
    )

    assert report["status"] == "passed", report["violations"]
    assert report["metrics"]["workflow_count"] == 2
    assert report["required_context_mapping"] == {
        "ci": ["ci.yml"],
        "maintenance-autopilot": ["maintenance-autopilot.yml"],
    }
    assert report["proof_command_occurrences"]["pytest"] == 2
    pytest_group = next(
        group
        for group in report["overlaps"]["proof_commands"]
        if group["proof_command"] == "pytest"
    )
    assert pytest_group["workflows"] == ["ci.yml", "maintenance-autopilot.yml"]
    maintenance = next(
        item for item in report["workflows"] if item["workflow"] == "maintenance-autopilot.yml"
    )
    assert maintenance["permissions"]["effective_write_scopes"] == ["issues"]
    assert maintenance["artifacts"][0]["direction"] == "consumes"
    assert report["overlaps"]["artifact_names"][0]["artifact_name"] == "proof"


def test_report_is_deterministic(tmp_path: Path) -> None:
    module = _module()
    root, topology, required, plan = _fixture_repo(tmp_path)

    first = module.build_report(
        root,
        topology_contract=topology,
        required_checks_contract=required,
        consolidation_plan=plan,
    )
    second = module.build_report(
        root,
        topology_contract=topology,
        required_checks_contract=required,
        consolidation_plan=plan,
    )

    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_missing_workflow_fails_closed(tmp_path: Path) -> None:
    module = _module()
    root, topology, required, plan = _fixture_repo(tmp_path)
    payload = json.loads(topology.read_text(encoding="utf-8"))
    payload["inventory"].append(".github/workflows/missing.yml")
    _write_json(topology, payload)

    report = module.build_report(
        root,
        topology_contract=topology,
        required_checks_contract=required,
        consolidation_plan=plan,
    )

    assert report["status"] == "failed"
    assert {item["code"] for item in report["violations"]} >= {"workflow_missing"}


def test_repository_overlap_inventory_covers_current_contracts() -> None:
    module = _module()

    report = module.build_report(
        ROOT,
        topology_contract=ROOT / "docs" / "contracts" / "workflow-topology.v1.json",
        required_checks_contract=ROOT / "docs" / "contracts" / "required-checks.v1.json",
        consolidation_plan=ROOT / "docs" / "contracts" / "workflow-consolidation-plan.v1.json",
    )

    assert report["status"] == "passed", report["violations"]
    assert report["metrics"]["workflow_count"] == 57
    assert report["required_status_contexts"] == ["ci", "maintenance-autopilot"]
    assert set(report["required_context_mapping"]) == {"ci", "maintenance-autopilot"}
    assert all(report["required_context_mapping"].values())
    assert len(report["workflows"]) == 57
    assert all(item["disposition"] != "unknown" for item in report["workflows"])
    assert report["metrics"]["duplicate_proof_command_group_count"] > 0
    assert report["authority_boundary"]["workflow_retirement_allowed"] is False
    assert report["authority_boundary"]["required_check_rename_allowed"] is False
