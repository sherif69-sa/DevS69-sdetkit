from __future__ import annotations

import json
from pathlib import Path

from sdetkit import adaptive_diagnosis, mission_control
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


def _security_control_room(tmp_path: Path, surface: str) -> Path:
    return _write_json(
        tmp_path / f"build/{surface}/control-room-with-security-review.json",
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


def _failure_bundle_from_raw_log(tmp_path: Path, surface: str, raw_log: str) -> Path:
    diagnosis = adaptive_diagnosis.analyze_evidence(log_text=raw_log)
    diagnoses = diagnosis["diagnoses"]
    assert diagnoses, diagnosis

    first_diagnosis = diagnoses[0]
    primary_code = str(diagnosis.get("primary_diagnosis_code") or first_diagnosis.get("code") or "")
    primary_diagnoses = [
        item
        for item in diagnoses
        if isinstance(item, dict) and str(item.get("code", "")) == primary_code
    ]
    assert primary_diagnoses, diagnosis

    return _write_json(
        tmp_path / f"build/{surface}/failure-bundle.json",
        {
            "schema_version": "sdetkit.adaptive.diagnosis.v1",
            "status": "review_required",
            "review_first": True,
            "safe_to_auto_fix": False,
            "primary_diagnosis_code": primary_code,
            "diagnosis_count": len(primary_diagnoses),
            "diagnoses": primary_diagnoses,
        },
    )


def _assert_raw_log_full_spine(
    *,
    tmp_path: Path,
    surface: str,
    raw_log: str,
    expected_code: str,
    expected_title: str,
    expected_command_fragment: str,
) -> None:
    repo = tmp_path / f"repo-{surface}"
    repo.mkdir()

    failure_bundle = _failure_bundle_from_raw_log(tmp_path, surface, raw_log)
    bundle_payload = json.loads(failure_bundle.read_text(encoding="utf-8"))

    assert bundle_payload["primary_diagnosis_code"] == expected_code
    assert bundle_payload["diagnoses"][0]["code"] == expected_code
    assert bundle_payload["diagnoses"][0]["title"] == expected_title

    graph = build_evidence_graph(failure_bundle=failure_bundle)
    graph_manifest = write_evidence_graph(
        graph,
        output_dir=tmp_path / f"build/{surface}/evidence-graph",
    )
    graph_path = Path(graph_manifest["graph_path"])
    graph_payload = json.loads(graph_path.read_text(encoding="utf-8"))
    graph_node = graph_payload["nodes"][0]

    assert graph_node["source"] == "failure_bundle"
    assert graph_node["risk_surface"] == surface
    assert graph_node["title"] == expected_title
    assert graph_node["review_first"] is True
    assert graph_node["safe_to_auto_fix"] is False

    mission_out = tmp_path / f"build/{surface}/mission-control"
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
    assert mission_graph["top_blocker_surface"] == surface
    assert mission_graph["top_blocker_title"] == expected_title
    assert mission_graph["top_blocker_action"] == "review"
    assert expected_command_fragment in " ".join(mission_graph["next_commands"])

    quality_log = _write(
        tmp_path / f"build/{surface}/quality.log",
        "quality.sh cov passed\nTotal coverage: 96.69%\n",
    )

    pr_payload = narrative.build_narrative(
        quality_log=quality_log,
        quality_outcome="success",
        sentinel_control_room=_security_control_room(tmp_path, surface),
        evidence_graph=graph_path,
        failure_bundle=failure_bundle,
        changed_files=None,
    )
    pr_markdown = str(pr_payload["markdown"])

    assert pr_payload["primary_signal"]["kind"] == "review_signal"
    assert pr_payload["primary_signal"]["surface"] == surface
    assert pr_payload["primary_signal"]["title"] == expected_title
    assert pr_payload["graph"]["top_blocker"]["surface"] == surface
    assert pr_payload["graph"]["top_blocker"]["title"] == expected_title
    assert f"Evidence graph top blocker: {expected_title} [{surface}]." in pr_markdown
    assert "Security review evidence: collected; unresolved findings: 0." in pr_markdown
    assert expected_command_fragment in pr_markdown


def test_raw_dependency_log_flows_through_full_spine(tmp_path: Path) -> None:
    _assert_raw_log_full_spine(
        tmp_path=tmp_path,
        surface="dependency",
        raw_log="\n".join(
            [
                "ERROR: Cannot install -r requirements-test.txt because these package versions have conflicting dependencies.",
                "ResolutionImpossible: for help visit https://pip.pypa.io/",
                "Process completed with exit code 1",
            ]
        ),
        expected_code="PACKAGE_INSTALL_FAILURE",
        expected_title="Dependency resolver failed",
        expected_command_fragment="requirements-test.txt",
    )


def test_raw_security_log_flows_through_full_spine(tmp_path: Path) -> None:
    _assert_raw_log_full_spine(
        tmp_path=tmp_path,
        surface="security",
        raw_log="\n".join(
            [
                "github-advanced-security",
                "sdetkit-security-gate / High entropy string",
                "High-entropy string literal detected.",
                "Dismissing the alert will mark this conversation as resolved.",
                "Process completed with exit code 1",
            ]
        ),
        expected_code="SECURITY_FINDING_REVIEW_REQUIRED",
        expected_title="Security finding requires review",
        expected_command_fragment="pre_commit",
    )


def test_raw_release_log_flows_through_full_spine(tmp_path: Path) -> None:
    _assert_raw_log_full_spine(
        tmp_path=tmp_path,
        surface="release",
        raw_log="\n".join(
            [
                "Run python -m build && python -m twine check dist/*",
                "ERROR InvalidDistribution: Metadata is missing required fields",
                "Process completed with exit code 1",
            ]
        ),
        expected_code="RELEASE_ARTIFACT_INVALID",
        expected_title="Release artifact validation failed",
        expected_command_fragment="twine check",
    )
