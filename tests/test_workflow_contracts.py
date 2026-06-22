from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType


def _load_checker() -> ModuleType:
    path = Path("scripts/check_workflow_contracts.py")
    spec = importlib.util.spec_from_file_location("check_workflow_contracts", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _minimal_workflow(
    *, pinned: bool = True, exact_annotation: bool = True, write: bool = False
) -> str:
    ref = "a" * 40 if pinned else "v4"
    annotation = "v4.2.2" if exact_annotation else "v4"
    permission = "  contents: write\n" if write else "  contents: read\n"
    return (
        "name: CI\n"
        "on: [pull_request]\n"
        "permissions:\n"
        f"{permission}"
        "jobs:\n"
        "  workflow-contracts:\n"
        "    name: Workflow contracts\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        f"      - uses: actions/checkout@{ref}  # {annotation}\n"
        "      - run: python scripts/check_workflow_contracts.py\n"
    )


def _fixture(tmp_path: Path, **workflow_kwargs: bool):
    module = _load_checker()
    workflow_root = tmp_path / ".github" / "workflows"
    workflow_root.mkdir(parents=True)
    (workflow_root / "ci.yml").write_text(
        _minimal_workflow(**workflow_kwargs),
        encoding="utf-8",
    )
    topology = module.build_topology_contract(
        tmp_path,
        baseline_main_sha="b" * 40,
        primary_anchors=["ci.yml"],
    )
    required = module.build_required_checks_contract(
        ["CI / Workflow contracts"],
        baseline_main_sha="b" * 40,
    )
    return module, topology, required


def test_repository_workflow_contracts_pass() -> None:
    module = _load_checker()
    topology = json.loads(
        Path("docs/contracts/workflow-topology.v1.json").read_text(encoding="utf-8")
    )
    required = json.loads(
        Path("docs/contracts/required-checks.v1.json").read_text(encoding="utf-8")
    )
    report = module.evaluate_contracts(Path(".").resolve(), topology, required)
    assert report["status"] == "passed", report["violations"]


def test_unpinned_action_is_rejected(tmp_path: Path) -> None:
    module, topology, required = _fixture(tmp_path)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text(
        _minimal_workflow(pinned=False),
        encoding="utf-8",
    )
    report = module.evaluate_contracts(tmp_path, topology, required)
    assert report["status"] == "failed"
    assert any(item["code"] == "unpinned_actions" for item in report["violations"])


def test_new_workflow_requires_contract_update(tmp_path: Path) -> None:
    module, topology, required = _fixture(tmp_path)
    (tmp_path / ".github" / "workflows" / "extra.yml").write_text(
        "name: Extra\non: [push]\njobs:\n  noop:\n    runs-on: ubuntu-latest\n    steps:\n      - run: true\n",
        encoding="utf-8",
    )
    report = module.evaluate_contracts(tmp_path, topology, required)
    assert any(item["code"] == "workflow_inventory_mismatch" for item in report["violations"])


def test_write_permission_budget_cannot_regress(tmp_path: Path) -> None:
    module, topology, required = _fixture(tmp_path)
    topology["budgets"]["maximum_write_permission_workflow_count"] = 0
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text(
        _minimal_workflow(write=True),
        encoding="utf-8",
    )
    report = module.evaluate_contracts(tmp_path, topology, required)
    assert any(
        item.get("metric") == "write_permission_workflow_count" for item in report["violations"]
    )


def test_action_annotation_debt_cannot_regress(tmp_path: Path) -> None:
    module, topology, required = _fixture(tmp_path)
    topology["budgets"]["maximum_metadata_drift_workflow_count"] = 0
    topology["budgets"]["maximum_metadata_drift_occurrence_count"] = 0
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text(
        _minimal_workflow(exact_annotation=False),
        encoding="utf-8",
    )
    report = module.evaluate_contracts(tmp_path, topology, required)
    assert any(
        item.get("metric") == "metadata_drift_workflow_count" for item in report["violations"]
    )


def test_live_required_context_drift_is_rejected(tmp_path: Path) -> None:
    module, topology, required = _fixture(tmp_path)
    report = module.evaluate_contracts(
        tmp_path,
        topology,
        required,
        live_required_contexts=["CI / Different check"],
    )
    assert any(item["code"] == "required_context_drift" for item in report["violations"])
