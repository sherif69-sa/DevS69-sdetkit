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


def test_dependency_failure_flows_from_failure_bundle_to_graph_mission_control_and_pr_quality(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    failure_bundle = _write_json(
        tmp_path / "build/pr-quality/failure-intelligence/failure-bundle.json",
        {
            "schema_version": "sdetkit.adaptive.diagnosis.v1",
            "status": "review_required",
            "review_first": True,
            "safe_to_auto_fix": False,
            "primary_diagnosis_code": "PACKAGE_INSTALL_FAILURE",
            "diagnosis_count": 1,
            "diagnoses": [
                {
                    "code": "PACKAGE_INSTALL_FAILURE",
                    "title": "Dependency resolver failed",
                    "diagnosis": "pip could not resolve constraints before tests could prove behavior.",
                    "severity": "high",
                    "confidence": "high",
                    "affected_files": ["constraints-ci.txt", "requirements-test.txt"],
                    "recommended_fix": [
                        "Reproduce the exact install lane.",
                        "Align the smallest dependency surface instead of changing product code.",
                    ],
                    "proof_commands": [
                        "PYTHONPATH=src python -m pip install -c constraints-ci.txt -r requirements-test.txt -e ."
                    ],
                }
            ],
            "artifacts": {
                "operator_brief_markdown": str(
                    tmp_path / "build/pr-quality/failure-intelligence/operator-brief.md"
                ),
            },
        },
    )
    _write(
        tmp_path / "build/pr-quality/failure-intelligence/operator-brief.md",
        "# Operator brief\n\nDependency resolver failed.\n",
    )

    graph = build_evidence_graph(failure_bundle=failure_bundle)
    graph_manifest = write_evidence_graph(
        graph,
        output_dir=tmp_path / "build/sdetkit/evidence-graph",
    )
    graph_path = Path(graph_manifest["graph_path"])

    graph_payload = json.loads(graph_path.read_text(encoding="utf-8"))
    assert graph_payload["nodes"][0]["source"] == "failure_bundle"
    assert graph_payload["nodes"][0]["risk_surface"] == "dependency"
    assert graph_payload["nodes"][0]["title"] == "Dependency resolver failed"
    assert graph_payload["nodes"][0]["review_first"] is True
    assert graph_payload["nodes"][0]["safe_to_auto_fix"] is False

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
            "--failure-bundle",
            str(failure_bundle),
            "--no-ledger",
        ]
    )
    assert rc == 0

    mission_bundle = json.loads((mission_out / "mission-control.json").read_text(encoding="utf-8"))
    mission_graph = mission_bundle["evidence_graph"]

    assert mission_bundle["decision"] == "SHIP_WITH_FINDINGS"
    assert mission_bundle["risk_band"] == "medium"
    assert mission_graph["status"] == "review_required"
    assert mission_graph["top_blocker_surface"] == "dependency"
    assert mission_graph["top_blocker_title"] == "Dependency resolver failed"
    assert mission_graph["top_blocker_action"] == "review"
    assert mission_graph["next_commands"] == [
        "PYTHONPATH=src python -m pip install -c constraints-ci.txt -r requirements-test.txt -e .",
        "Reproduce the exact install lane.",
        "Align the smallest dependency surface instead of changing product code.",
    ]

    mission_markdown = (mission_out / "mission-control.md").read_text(encoding="utf-8")
    assert "Top blocker: Dependency resolver failed" in mission_markdown
    assert "Top blocker surface: dependency" in mission_markdown
    assert "PYTHONPATH=src python -m pip install -c constraints-ci.txt" in mission_markdown

    quality_log = _write(
        tmp_path / "quality.log",
        "quality.sh cov passed\nTotal coverage: 96.69%\n",
    )
    security_control_room = _write_json(
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

    pr_payload = narrative.build_narrative(
        quality_log=quality_log,
        quality_outcome="success",
        sentinel_control_room=security_control_room,
        evidence_graph=graph_path,
        failure_bundle=failure_bundle,
        changed_files=None,
    )

    pr_markdown = str(pr_payload["markdown"])

    assert pr_payload["quality"]["ok"] is True
    assert pr_payload["primary_signal"]["kind"] == "review_signal"
    assert pr_payload["primary_signal"]["surface"] == "dependency"
    assert pr_payload["primary_signal"]["title"] == "Dependency resolver failed"
    assert pr_payload["graph"]["top_blocker"]["surface"] == "dependency"
    assert pr_payload["graph"]["top_blocker"]["title"] == "Dependency resolver failed"
    assert "Evidence graph top blocker: Dependency resolver failed [dependency]." in pr_markdown
    assert "Security review evidence: collected; unresolved findings: 0." in pr_markdown
    assert "PYTHONPATH=src python -m pip install -c constraints-ci.txt" in pr_markdown
    assert "Reproduce the exact install lane." in pr_markdown
