from __future__ import annotations

from sdetkit import diagnostic_execution_plan
from sdetkit.artifact_contract_index import build_index


def test_diagnostic_execution_plan_artifact_contract_is_registered() -> None:
    entries = {item["id"]: item for item in build_index()["artifacts"]}

    entry = entries["diagnostic-execution-plan-json"]
    assert entry["schema_version"] == diagnostic_execution_plan.SCHEMA_VERSION
    assert entry["path"] == diagnostic_execution_plan.DEFAULT_OUT
    assert entry["stability"] == "advanced"
    assert {
        "schema_version",
        "plan_status",
        "repo_root",
        "repo_identity",
        "source_artifacts",
        "summary",
        "commands",
        "review_first_items",
        "policies",
        "rules",
        "execution_allowed",
        "automation_allowed",
        "patch_application_allowed",
        "merge_authorized",
        "semantic_equivalence_proven",
        "authority_boundary",
    }.issubset(entry["required_fields"])
    assert entry["produced_by"] == (
        "python -m sdetkit.diagnostic_execution_plan --root . "
        "--out build/sdetkit/diagnostic-execution-plan.json --format json"
    )
