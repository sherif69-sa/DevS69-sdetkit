from __future__ import annotations

import json
from pathlib import Path

from sdetkit import workflow_governance_report
from sdetkit import workflow_permission_review_control_plane as control_plane


def _write_fixture(root: Path) -> None:
    workflow_dir = root / ".github" / "workflows"
    workflow_dir.mkdir(parents=True)
    (workflow_dir / "security.yml").write_text(
        """name: Security\npermissions:\n  contents: read\n  security-events: write\njobs:\n  scan:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: github/codeql-action/upload-sarif@0123456789012345678901234567890123456789\n""",
        encoding="utf-8",
    )
    (workflow_dir / "publisher.yml").write_text(
        """name: Publisher\npermissions:\n  contents: read\n  issues: write\n  pull-requests: write\njobs:\n  publish:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/github-script@0123456789012345678901234567890123456789\n        with:\n          script: |\n            await github.rest.issues.create({ owner: context.repo.owner, repo: context.repo.repo, title: 'x' })\n""",
        encoding="utf-8",
    )

    contract = root / control_plane.CONTRACT_PATH
    contract.parent.mkdir(parents=True)
    contract.write_text("{}\n", encoding="utf-8")

    decision_dir = root / control_plane.DECISION_DIR
    decision_dir.mkdir(parents=True)
    (decision_dir / "publisher.md").write_text(
        "# Scoped evidence\n\nworkflow=.github/workflows/publisher.yml\ndecision=approved_scoped_move\n",
        encoding="utf-8",
    )


def test_control_plane_builds_exact_digest_bound_human_review_queue(tmp_path: Path) -> None:
    _write_fixture(tmp_path)

    payload = control_plane.build_workflow_permission_review_control_plane(tmp_path)

    assert payload["schema_version"] == control_plane.SCHEMA_VERSION
    assert payload["status"] == "human_review_required"
    assert payload["summary"]["permission_review_count"] == 2
    assert payload["summary"]["permission_group_count"] == 2
    assert payload["summary"]["human_decision_recorded_count"] == 0
    assert payload["summary"]["automatic_permission_reduction_allowed"] is False

    by_workflow = {entry["workflow"]: entry for entry in payload["review_queue"]}
    security = by_workflow[".github/workflows/security.yml"]
    publisher = by_workflow[".github/workflows/publisher.yml"]

    assert security["permission_group"] == "security_upload"
    assert publisher["permission_group"] == "pr_issue_interaction"
    assert len(security["workflow_sha256"]) == 64
    assert len(publisher["workflow_sha256"]) == 64
    assert security["review_state"] == "pending_human_review"
    assert publisher["review_state"] == "decision_evidence_present"
    assert publisher["decision_evidence_refs"] == [
        "docs/ci/workflow-permission-decisions/publisher.md"
    ]

    for entry in payload["review_queue"]:
        assert entry["human_decision_recorded"] is False
        assert entry["human_decision"] is None
        assert entry["proposed_change"] is None
        assert entry["safe_to_patch"] is False
        assert entry["allowed_decisions"] == ["keep", "reduce", "split", "defer"]
        assert not any(entry["authority_boundary"].values())

    assert not any(payload["authority_boundary"].values())


def test_existing_decision_markdown_is_evidence_not_automatic_authority(tmp_path: Path) -> None:
    _write_fixture(tmp_path)

    payload = control_plane.build_workflow_permission_review_control_plane(tmp_path)
    publisher = next(
        entry
        for entry in payload["review_queue"]
        if entry["workflow"] == ".github/workflows/publisher.yml"
    )

    assert publisher["decision_evidence_refs"]
    assert publisher["review_state"] == "decision_evidence_present"
    assert publisher["human_decision_recorded"] is False
    assert publisher["human_decision"] is None
    assert publisher["next_allowed_action"] == "review_existing_decision_evidence"
    assert publisher["authority_boundary"]["workflow_mutation_allowed"] is False
    assert publisher["authority_boundary"]["merge_authorized"] is False


def test_control_plane_freshness_invalidates_when_workflow_bytes_change(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    payload = control_plane.build_workflow_permission_review_control_plane(tmp_path)

    workflow = tmp_path / ".github" / "workflows" / "security.yml"
    workflow.write_text(workflow.read_text(encoding="utf-8") + "# changed\n", encoding="utf-8")

    freshness = control_plane.validate_workflow_permission_review_control_plane(tmp_path, payload)

    assert freshness["fresh"] is False
    assert freshness["status"] == "stale"
    assert "input_digest_mismatch" in freshness["reasons"]
    assert any(reason.startswith("workflow_digest_mismatch:") for reason in freshness["reasons"])
    assert freshness["workflow_mutation_allowed"] is False


def test_control_plane_freshness_invalidates_when_decision_evidence_changes(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    payload = control_plane.build_workflow_permission_review_control_plane(tmp_path)

    decision = tmp_path / control_plane.DECISION_DIR / "publisher.md"
    decision.write_text(decision.read_text(encoding="utf-8") + "reviewer=human\n", encoding="utf-8")

    freshness = control_plane.validate_workflow_permission_review_control_plane(tmp_path, payload)

    assert freshness["fresh"] is False
    assert freshness["reasons"] == ["input_digest_mismatch"]


def test_control_plane_write_and_render_preserve_review_first_boundary(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    out = tmp_path / "build" / "permission-control-plane.json"
    markdown_out = tmp_path / "build" / "permission-control-plane.md"

    payload = control_plane.write_workflow_permission_review_control_plane(
        repo_root=tmp_path,
        out=out,
        markdown_out=markdown_out,
    )

    assert json.loads(out.read_text(encoding="utf-8")) == payload
    markdown = markdown_out.read_text(encoding="utf-8")
    assert "automatic_permission_reduction_allowed: false" in markdown
    assert "workflow_mutation_allowed: false" in markdown
    assert "human_decision_recorded: false" in markdown

    freshness = control_plane.validate_workflow_permission_review_control_plane(tmp_path, payload)
    assert freshness["fresh"] is True


def test_control_plane_contract_and_live_queue_align_with_governance_report() -> None:
    contract = json.loads(Path(control_plane.CONTRACT_PATH).read_text(encoding="utf-8"))
    governance = workflow_governance_report.build_workflow_governance_report(".")
    payload = control_plane.build_workflow_permission_review_control_plane(".")

    assert contract["control_plane_schema_version"] == control_plane.SCHEMA_VERSION
    assert contract["allowed_decisions"] == list(control_plane.ALLOWED_DECISIONS)
    assert not any(contract["authority_boundary"].values())
    assert payload["summary"]["permission_review_count"] == governance["permission_review_count"]
    assert [entry["workflow"] for entry in payload["review_queue"]] == sorted(
        task["workflow"] for task in governance["permission_review_evidence_packet"]["review_tasks"]
    )
    assert all(entry["human_decision_recorded"] is False for entry in payload["review_queue"])
    assert all(entry["safe_to_patch"] is False for entry in payload["review_queue"])
