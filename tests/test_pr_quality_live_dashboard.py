from __future__ import annotations

import json
from pathlib import Path

from sdetkit import pr_quality_action_report as report
from sdetkit.pr_quality_live_dashboard import (
    build_live_evidence_snapshot,
    render_live_evidence_html,
    render_live_evidence_markdown,
)


def _model() -> dict:
    return {
        "schema_version": "sdetkit.pr_quality.review_model.v2",
        "decision": {
            "review_state": "ready",
            "status": "green",
            "source_status": "green",
            "merge_assessment": ("automated_proof_complete_human_decision_required"),
            "next_action": "review_and_decide",
            "risk_surface": "diagnostic_engine",
            "failed_checks": 0,
            "required_queued_checks": 0,
            "required_startup_failures": 0,
            "missing_required_contexts": 0,
        },
        "ghas_blocker_details": {
            "collected": True,
            "current_alerts": 0,
            "stale_alerts": 1,
            "current_head_sha": "head-sha",
        },
        "authority_boundary": {
            "boundary_mode": "reporting_only",
            "patch_automation": False,
            "security_dismissal": False,
            "merge_authorization": False,
            "semantic_equivalence_claim": False,
        },
        "artifact_index": [],
        "primary_blocker": {},
        "failure_vector_signal": {},
        "proof_to_rerun": [],
        "recommended_actions": [],
        "failed_check_names": [],
        "required_queued_check_names": [],
        "required_startup_failure_names": [],
        "missing_required_context_names": [],
    }


def _runtime() -> dict:
    return {
        "isolated_proof": {
            "status": "passed",
            "profiles_requested": 2,
            "profiles_executed": 2,
            "profiles_passed": 2,
            "profiles_failed": 0,
            "runtime_guard_violation_count": 0,
        },
        "live_benchmark": {
            "status": "passed",
            "scenario_count": 6,
            "passed_count": 6,
            "failed_count": 0,
            "anti_cheat_rejection_count": 2,
        },
        "trusted_history": {
            "status": "trusted_history_verified",
            "record_count": 370,
            "base_ancestry_verified": True,
            "prior_history_is_read_only_input": True,
        },
    }


def _manifest() -> dict:
    return {
        "expected_artifact_inventory_verification": {
            "status": "passed",
            "expected_artifact_count": 14,
            "missing_authority_evidence_paths": [],
        }
    }


def _env() -> dict[str, str]:
    return {
        "GITHUB_SERVER_URL": "https://github.com",
        "GITHUB_REPOSITORY": "example/sdetkit",
        "GITHUB_RUN_ID": "123456",
        "GITHUB_RUN_ATTEMPT": "2",
        "GITHUB_WORKFLOW": "PR Quality Comment",
        "GITHUB_JOB": "produce",
        "GITHUB_REF_NAME": "feature/live-dashboard",
    }


def _snapshot() -> dict:
    return build_live_evidence_snapshot(
        pr_number=1879,
        head_sha="head-sha",
        base_sha="base-sha",
        review_model=_model(),
        check_intelligence={"current_head_sha": "head-sha"},
        runtime_proof_artifacts=_runtime(),
        artifact_manifest=_manifest(),
        environment=_env(),
        generated_at="2026-06-26T05:45:00+00:00",
    )


def test_snapshot_binds_exact_pr_head_run_and_artifact() -> None:
    snapshot = _snapshot()
    provenance = snapshot["provenance"]

    assert snapshot["snapshot_status"] == "complete"
    assert provenance["head_binding_status"] == "verified"
    assert provenance["pr_url"].endswith("/pull/1879")
    assert provenance["workflow_run_url"].endswith("/actions/runs/123456")
    assert provenance["artifacts_url"].endswith("/actions/runs/123456#artifacts")
    assert provenance["artifact_entrypoint"] == "pr-quality/index.html"


def test_snapshot_metrics_come_from_structured_sources() -> None:
    facts = {item["id"]: item for item in _snapshot()["facts"]}

    assert facts["required_checks"]["value"] == ("0 failed · 0 queued · 0 startup · 0 missing")
    assert facts["security"]["value"] == ("0 current · 1 stale alert(s)")
    assert facts["runtime_proof"]["value"] == (
        "2/2 profiles passed (2 requested) · 0 guard violation(s)"
    )
    assert facts["live_benchmark"]["value"] == (
        "6/6 scenarios passed · 0 failed · 2 anti-cheat rejection(s)"
    )
    assert facts["trusted_history"]["value"] == (
        "370 record(s) · ancestry true · read-only input true"
    )
    assert facts["artifact_inventory"]["value"] == (
        "14 expected artifact(s) · 0 missing authority path(s)"
    )
    assert all(item["source_path"] for item in facts.values())


def test_head_mismatch_is_visible_without_decision_change() -> None:
    snapshot = build_live_evidence_snapshot(
        pr_number=12,
        head_sha="expected-head",
        base_sha="base-sha",
        review_model=_model(),
        check_intelligence={"current_head_sha": "other-head"},
        runtime_proof_artifacts=_runtime(),
        artifact_manifest=_manifest(),
        environment=_env(),
        generated_at="2026-06-26T05:45:00+00:00",
    )

    assert snapshot["snapshot_status"] == "partial"
    assert snapshot["provenance"]["head_binding_status"] == "mismatch"
    assert snapshot["decision_observation"]["review_state"] == "ready"
    assert snapshot["authority_boundary"]["merge_authorization"] is False


def test_all_rendered_surfaces_share_the_same_snapshot() -> None:
    model = _model()
    model["live_evidence"] = _snapshot()

    summary = report.render_pr_quality_review_summary(model)
    dashboard = report.render_pr_quality_review_html(model)
    index = report.render_pr_quality_artifact_index_html(model)
    manifest = report.build_pr_quality_artifacts_manifest(model)

    assert "## Live evidence snapshot" in summary
    assert "actions/runs/123456" in summary
    assert "runtime-proof/summary/runtime-proof-artifacts.json" in summary
    assert 'id="live-evidence"' in dashboard
    assert 'id="live-evidence"' in index
    assert "6/6 scenarios passed" in dashboard
    assert "6/6 scenarios passed" in index
    assert manifest["live_evidence"]["provenance"]["workflow_run_id"] == "123456"


def test_render_helpers_are_safe_without_a_snapshot() -> None:
    assert render_live_evidence_markdown({}) == ""
    assert render_live_evidence_html({}) == ""


def test_write_comment_body_carries_snapshot_to_outputs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    for key, value in _env().items():
        monkeypatch.setenv(key, value)

    action = {
        "status": "green",
        "primary_blocker": {},
        "recommended_actions": [],
        "proof_commands": ["python -m pre_commit run -a"],
    }
    intelligence = {
        "current_head_sha": "head-sha",
        "failed_checks": [],
        "queued_checks": [],
        "startup_failures": [],
        "missing_required_contexts": [],
        "security_review": {
            "collected": True,
            "unresolved_findings": 0,
        },
        "code_scanning_review": {
            "collected": True,
            "collection_status": "collected",
            "open_alerts": 0,
            "current_alerts": 0,
            "stale_alerts": 0,
            "current_head_sha": "head-sha",
            "findings": [],
        },
    }

    action_path = tmp_path / "action.json"
    intelligence_path = tmp_path / "intelligence.json"
    runtime_path = tmp_path / "runtime.json"
    out = tmp_path / "comment.md"
    model_out = tmp_path / "model.json"
    summary_out = tmp_path / "summary.md"
    dashboard_out = tmp_path / "dashboard.html"
    index_out = tmp_path / "index.html"
    manifest_out = tmp_path / "manifest.json"

    action_path.write_text(json.dumps(action), encoding="utf-8")
    intelligence_path.write_text(
        json.dumps(intelligence),
        encoding="utf-8",
    )
    runtime_path.write_text(json.dumps(_runtime()), encoding="utf-8")

    result = report.write_comment_body(
        action_report_path=action_path,
        check_intelligence_path=intelligence_path,
        runtime_proof_artifacts_path=runtime_path,
        out=out,
        review_model_out=model_out,
        review_summary_out=summary_out,
        review_html_out=dashboard_out,
        review_index_out=index_out,
        review_artifacts_manifest_out=manifest_out,
        pr_number=1879,
        head_sha="head-sha",
        base_sha="base-sha",
    )

    model = json.loads(model_out.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_out.read_text(encoding="utf-8"))

    assert model["live_evidence"]["provenance"]["workflow_run_id"] == "123456"
    assert manifest["live_evidence"]["provenance"]["head_sha"] == ("head-sha")
    assert "## Live evidence snapshot" in summary_out.read_text()
    assert 'id="live-evidence"' in dashboard_out.read_text()
    assert 'id="live-evidence"' in index_out.read_text()
    assert result["live_evidence_snapshot_status"] == "complete"
    assert result["live_evidence_head_binding_status"] == "verified"
    assert result["live_evidence_fact_count"] == 7
    assert result["live_evidence_reporting_only"] is True
