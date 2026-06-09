from __future__ import annotations

import json
from pathlib import Path

import yaml

from sdetkit.agent.templates import template_by_id


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_integration_topology_worker_evidence_contract_matches_templates() -> None:
    repo_root = Path.cwd()
    evidence_path = repo_root / "build/sdetkit/integration-topology-worker-evidence.json"

    payload = json.loads(evidence_path.read_text(encoding="utf-8"))

    assert payload["schema_version"] == 1
    assert payload["report_status"] == "review_required"
    assert payload["evidence_type"] == "integration_topology_worker_evidence"
    assert payload["review_first"] is True
    assert payload["safe_to_patch"] is False
    assert payload["repo_mutation"] is False
    assert payload["workflow_mutation"] is False
    assert payload["automation_allowed"] is False
    assert payload["patch_application_allowed"] is False
    assert payload["merge_authorized"] is False
    assert payload["semantic_equivalence_proven"] is False
    assert payload["authority_boundary"] == {
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }

    workers = {worker["id"]: worker for worker in payload["workers"]}
    assert set(workers) == {"integration-topology-worker", "worker-alignment-radar"}

    for worker_id, worker in workers.items():
        template = template_by_id(repo_root, worker_id)
        template_path = repo_root / worker["template_path"]
        template_doc = _load_yaml(template_path)

        assert template.metadata["id"] == worker_id
        assert template_doc["metadata"]["description"] == worker["purpose"]

        workflow = template_doc["workflow"]
        assert [step["id"] for step in workflow] == worker["expected_step_ids"]

        rendered_commands = [
            step.get("with", {}).get("cmd")
            for step in workflow
            if step.get("action") == "shell.run"
        ]
        assert rendered_commands == worker["command_surfaces"]


def test_integration_topology_worker_evidence_contract_names_expected_outputs() -> None:
    payload = json.loads(
        Path("build/sdetkit/integration-topology-worker-evidence.json").read_text(encoding="utf-8")
    )

    workers = {worker["id"]: worker for worker in payload["workers"]}

    assert workers["integration-topology-worker"]["expected_outputs"] == [
        "topology-check.json",
        "optimize.json",
        "summary.md",
        "bundle.tar",
    ]
    assert workers["worker-alignment-radar"]["expected_outputs"] == [
        "expand.json",
        "automation-check.json",
        "templates.json",
        "summary.md",
        "bundle.tar",
    ]

    next_actions = payload["recommended_next_actions"]
    assert "Keep this contract as evidence only." in next_actions
    assert any("before topology/platform/premium-gate refactors" in item for item in next_actions)
    assert any("Do not auto-apply" in item for item in next_actions)
