from __future__ import annotations

import json
from pathlib import Path

from sdetkit import mission_control
from sdetkit import pr_quality_evidence_narrative as narrative
from sdetkit.evidence_graph import build_evidence_graph, write_evidence_graph


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _healthy_security_control_room(tmp_path: Path) -> Path:
    return _write_json(
        tmp_path / "build/sdetkit/sentinel/control-room-with-security-review.json",
        {
            "schema_version": "sdetkit.adaptive.sentinel.control_room.v1",
            "state": "healthy",
            "active_threat_count": 0,
            "active_threats": [],
            "review_first_count": 0,
            "automation_allowed_now": False,
            "security_review_collection_status": "collected",
            "security_review_finding_count": 0,
            "security_review_state": "healthy",
        },
    )


def test_missing_required_context_action_report_flows_through_full_spine(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    action_report = _write_json(
        tmp_path / "build/pr-quality/check-intelligence/action-report.json",
        {
            "status": "incomplete",
            "primary_blocker": {
                "check": "ci",
                "title": "Required checks are not complete",
                "surface": "workflow",
                "code": "CHECKS_INCOMPLETE",
                "impact": "Required context has not reported yet.",
                "path": ".github/workflows/ci.yml",
            },
            "automation": {
                "attempted": False,
                "allowed": False,
                "reason": "required check completion is needed before remediation or green signoff",
            },
            "recommended_actions": ["Wait for required queued checks to complete."],
            "proof_commands": ["gh pr checks --required"],
            "evidence": {
                "missing_required_contexts": ["ci"],
                "required_queued_check_count": 1,
            },
        },
    )

    graph = build_evidence_graph(pr_quality_action_report=action_report)
    graph_manifest = write_evidence_graph(
        graph,
        output_dir=tmp_path / "build/sdetkit/evidence-graph",
    )
    graph_path = Path(graph_manifest["graph_path"])
    graph_payload = json.loads(graph_path.read_text(encoding="utf-8"))
    graph_node = graph_payload["nodes"][0]

    assert graph_node["source"] == "pr_quality"
    assert graph_node["risk_surface"] == "workflow"
    assert graph_node["title"] == "Required checks are not complete"
    assert graph_node["summary"] == "Required context has not reported yet."
    assert graph_node["severity"] == "critical"
    assert graph_node["review_first"] is True
    assert graph_node["safe_to_auto_fix"] is False
    assert graph_node["automation_allowed_now"] is False
    assert graph_node["owner_files"] == [".github/workflows/ci.yml"]
    assert graph_node["source_artifacts"] == [action_report.as_posix()]
    assert graph_node["proof_commands"] == ["gh pr checks --required"]
    assert "Wait for required queued checks to complete." in graph_node["recommended_commands"]

    mission_out = tmp_path / "build/mission-control"
    rc = mission_control.main(
        [
            "run",
            "--repo",
            str(repo),
            "--out-dir",
            str(mission_out),
            "--evidence-graph",
            str(graph_path),
            "--no-ledger",
        ]
    )

    assert rc == 0
    mission_bundle = json.loads((mission_out / "mission-control.json").read_text(encoding="utf-8"))
    mission_graph = mission_bundle["evidence_graph"]

    assert mission_bundle["decision"] == "SHIP_WITH_FINDINGS"
    assert mission_bundle["risk_band"] == "medium"
    assert mission_graph["status"] == "review_required"
    assert mission_graph["top_blocker_surface"] == "workflow"
    assert mission_graph["top_blocker_title"] == "Required checks are not complete"
    assert mission_graph["top_blocker_action"] == "review"
    assert "gh pr checks --required" in mission_graph["next_commands"]
    assert "Wait for required queued checks to complete." in mission_graph["next_commands"]

    mission_markdown = (mission_out / "mission-control.md").read_text(encoding="utf-8")
    assert "Top blocker: Required checks are not complete" in mission_markdown
    assert "Top blocker surface: workflow" in mission_markdown
    assert "gh pr checks --required" in mission_markdown

    quality_log = _write(
        tmp_path / "build/pr-quality/quality.log",
        "quality.sh cov passed\nTotal coverage: 96.69%\n",
    )

    pr_payload = narrative.build_narrative(
        quality_log=quality_log,
        quality_outcome="success",
        sentinel_control_room=_healthy_security_control_room(tmp_path),
        evidence_graph=graph_path,
        failure_bundle=None,
        changed_files=None,
    )
    pr_markdown = str(pr_payload["markdown"])

    assert pr_payload["quality"]["ok"] is True
    assert pr_payload["primary_signal"]["kind"] == "review_signal"
    assert pr_payload["primary_signal"]["surface"] == "workflow"
    assert pr_payload["primary_signal"]["title"] == "Required checks are not complete"
    assert pr_payload["graph"]["top_blocker"]["surface"] == "workflow"
    assert pr_payload["graph"]["top_blocker"]["title"] == "Required checks are not complete"
    assert (
        "Evidence graph top blocker: Required checks are not complete [workflow]."
        in pr_markdown
    )
    assert "Security review evidence: collected; unresolved findings: 0." in pr_markdown
    assert "gh pr checks --required" in pr_markdown
    assert "Wait for required queued checks to complete." in pr_markdown
