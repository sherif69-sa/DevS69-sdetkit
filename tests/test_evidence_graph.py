from __future__ import annotations

import json
from pathlib import Path

from sdetkit.evidence_graph import (
    SCHEMA_VERSION,
    build_evidence_graph,
    main,
    write_evidence_graph,
)


def test_evidence_graph_normalizes_sentinel_control_room_active_threat(
    tmp_path: Path,
) -> None:
    control_room = tmp_path / "sentinel-control-room.json"
    control_room.write_text(
        json.dumps(
            {
                "schema_version": "sdetkit.sentinel-control-room.v1",
                "status": "attention_required",
                "active_threats": [
                    {
                        "finding_id": "sentinel-workflow-001",
                        "title": "Protected workflow changed",
                        "summary": "A protected workflow surface changed.",
                        "risk_surface": "workflow",
                        "severity": "critical",
                        "review_first": True,
                        "safe_to_auto_fix": True,
                        "owner_files": [".github/workflows/ci.yml"],
                        "source_artifacts": ["build/sdetkit/adaptive-sentinel/control-room.json"],
                        "recommended_commands": [
                            "python -m pytest -q tests/test_workflow_alias_regression_guards.py -o addopts="
                        ],
                        "proof_commands": ["python -m pre_commit run -a"],
                        "recurrence_state": "recurring",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    graph = build_evidence_graph(sentinel_control_room=control_room)

    assert graph["schema_version"] == SCHEMA_VERSION
    assert len(graph["nodes"]) == 1
    node = graph["nodes"][0]
    assert node["source"] == "sentinel"
    assert node["finding_id"] == "sentinel-workflow-001"
    assert node["risk_surface"] == "workflow"
    assert node["severity"] == "critical"
    assert node["review_first"] is True
    assert node["safe_to_auto_fix"] is False
    assert node["automation_allowed_now"] is False
    assert node["owner_files"] == [".github/workflows/ci.yml"]
    assert node["recurrence_state"] == "recurring"
    assert node["operator_action"] == "review"
    assert graph["source_summary"][0]["findings_seen"] == 1
    assert graph["source_summary"][0]["findings_emitted"] == 1


def test_evidence_graph_preserves_clear_source_metadata_without_nodes(
    tmp_path: Path,
) -> None:
    control_room = tmp_path / "sentinel-control-room.json"
    control_room.write_text(
        json.dumps(
            {
                "schema_version": "sdetkit.sentinel-control-room.v1",
                "status": "healthy",
                "active_threats": [],
            }
        ),
        encoding="utf-8",
    )

    graph = build_evidence_graph(sentinel_control_room=control_room)

    assert graph["nodes"] == []
    assert graph["source_summary"][0] == {
        "source": "sentinel",
        "path": control_room.as_posix(),
        "found": True,
        "status": "healthy",
        "findings_seen": 0,
        "findings_emitted": 0,
    }


def test_evidence_graph_writes_json_markdown_and_manifest(tmp_path: Path) -> None:
    mission_control = tmp_path / "mission-control.json"
    mission_control.write_text(
        json.dumps(
            {
                "status": "warning",
                "findings": [
                    {
                        "title": "Dependency evidence needs review",
                        "summary": "A constraints-alignment signal needs review.",
                        "severity": "warning",
                        "owner_files": ["constraints-ci.txt", "pyproject.toml"],
                        "recommended_commands": [
                            "python -m pip install -c constraints-ci.txt -e '.[dev,test]'"
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    graph = build_evidence_graph(mission_control=mission_control)
    manifest = write_evidence_graph(graph, output_dir=tmp_path / "evidence-graph")

    graph_path = tmp_path / "evidence-graph" / "evidence-graph.json"
    markdown_path = tmp_path / "evidence-graph" / "evidence-graph.md"
    manifest_path = tmp_path / "evidence-graph" / "evidence-graph-manifest.json"

    assert graph_path.exists()
    assert markdown_path.exists()
    assert manifest_path.exists()
    assert manifest["node_count"] == 1
    assert manifest["automation_allowed_now"] is False

    markdown = markdown_path.read_text(encoding="utf-8")
    assert "Dependency evidence needs review" in markdown
    assert "constraints-ci.txt" in markdown
    assert "python -m pip install -c constraints-ci.txt -e '.[dev,test]'" in markdown
    assert "Automation allowed now: `false`" in markdown


def test_evidence_graph_module_cli_writes_read_only_artifacts(
    tmp_path: Path,
    capsys,
) -> None:
    control_room = tmp_path / "sentinel-control-room.json"
    control_room.write_text(
        json.dumps(
            {
                "status": "attention_required",
                "active_threats": [
                    {
                        "finding_id": "sentinel-security-001",
                        "title": "Security surface changed",
                        "summary": "A security-owned file changed and needs review.",
                        "severity": "critical",
                        "owner_files": ["docs/security-posture.md"],
                        "recommended_commands": [
                            "python -m pytest -q tests/test_owned_surface_hygiene_contract.py -o addopts="
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    out_dir = tmp_path / "graph-out"

    assert (
        main(
            [
                "--sentinel-control-room",
                control_room.as_posix(),
                "--out-dir",
                out_dir.as_posix(),
            ]
        )
        == 0
    )

    printed = json.loads(capsys.readouterr().out)
    assert printed["node_count"] == 1
    assert printed["automation_allowed_now"] is False

    graph_path = out_dir / "evidence-graph.json"
    markdown_path = out_dir / "evidence-graph.md"
    manifest_path = out_dir / "evidence-graph-manifest.json"

    assert graph_path.exists()
    assert markdown_path.exists()
    assert manifest_path.exists()

    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    assert graph["nodes"][0]["source"] == "sentinel"
    assert graph["nodes"][0]["risk_surface"] == "security"
    assert graph["nodes"][0]["review_first"] is True
    assert graph["nodes"][0]["automation_allowed_now"] is False


def test_evidence_graph_docs_describe_advisory_artifacts() -> None:
    docs = Path("docs/evidence-graph.md").read_text(encoding="utf-8")

    assert "python -m sdetkit.evidence_graph" in docs
    assert "evidence-graph.json" in docs
    assert "evidence-graph.md" in docs
    assert "evidence-graph-manifest.json" in docs
    assert "automation_allowed_now=false" in docs
    assert "does not auto-fix" in docs
    assert "review_first=true" in docs


def test_evidence_graph_classifies_quality_verdict_without_owner_files(
    tmp_path: Path,
) -> None:
    control_room = tmp_path / "control-room.json"
    control_room.write_text(
        json.dumps(
            {
                "status": "attention_required",
                "active_threats": [
                    {
                        "title": "Quality verdict signal",
                        "summary": "blocking_failures=coverage",
                        "severity": "warning",
                        "recommended_commands": ["bash quality.sh cov"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    graph = build_evidence_graph(sentinel_control_room=control_room)

    assert graph["nodes"][0]["risk_surface"] == "quality"
    assert graph["nodes"][0]["review_first"] is True


def test_evidence_graph_classifies_pr_quality_workflow_signal(
    tmp_path: Path,
) -> None:
    control_room = tmp_path / "control-room.json"
    control_room.write_text(
        json.dumps(
            {
                "status": "attention_required",
                "active_threats": [
                    {
                        "title": "PR Quality comment workflow changed",
                        "summary": "The PR Quality evidence comment path changed.",
                        "severity": "warning",
                        "owner_files": [".github/workflows/pr-quality-comment.yml"],
                        "recommended_commands": [
                            "python -m pytest -q tests/test_pr_quality_adaptive_sentinel_workflow.py -o addopts="
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    graph = build_evidence_graph(sentinel_control_room=control_room)

    assert graph["nodes"][0]["risk_surface"] == "pr_quality"
    assert graph["nodes"][0]["review_first"] is True


def test_evidence_graph_classifies_diagnostic_artifacts_from_source_paths(
    tmp_path: Path,
) -> None:
    control_room = tmp_path / "control-room.json"
    control_room.write_text(
        json.dumps(
            {
                "status": "attention_required",
                "active_threats": [
                    {
                        "title": "Control-room evidence needs review",
                        "summary": "Sentinel emitted a control-room finding.",
                        "severity": "warning",
                        "source_artifacts": [
                            "build/sdetkit/sentinel/control-room.json",
                            "build/sdetkit/evidence-graph/evidence-graph.json",
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    graph = build_evidence_graph(sentinel_control_room=control_room)

    assert graph["nodes"][0]["risk_surface"] == "diagnostic_engine"
    assert graph["nodes"][0]["review_first"] is True


def test_evidence_graph_normalizes_failure_bundle_diagnoses(tmp_path: Path) -> None:
    failure_bundle = tmp_path / "failure-bundle.json"
    failure_bundle.write_text(
        json.dumps(
            {
                "schema_version": "sdetkit.adaptive.diagnosis.v1",
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
                    },
                    {
                        "code": "SECURITY_FINDING_REVIEW_REQUIRED",
                        "title": "Security finding requires review",
                        "diagnosis": "A security-sensitive finding must be reviewed before treating coverage as the blocker.",
                        "severity": "high",
                        "confidence": "high",
                        "recommended_fix": [
                            "Inspect the security finding and affected surface.",
                        ],
                        "proof_commands": [
                            "PYTHONPATH=src python -m pre_commit run -a",
                        ],
                    },
                    {
                        "code": "RELEASE_ARTIFACT_INVALID",
                        "title": "Release artifact validation failed",
                        "diagnosis": "The release/package validation log shows an artifact contract failure.",
                        "severity": "high",
                        "confidence": "high",
                        "proof_commands": [
                            "PYTHONPATH=src python -m build && PYTHONPATH=src python -m twine check dist/*",
                        ],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    graph = build_evidence_graph(failure_bundle=failure_bundle)

    assert graph["source_summary"][-1]["source"] == "failure_bundle"
    assert graph["source_summary"][-1]["found"] is True
    assert graph["source_summary"][-1]["findings_seen"] == 3
    assert graph["source_summary"][-1]["findings_emitted"] == 3

    nodes = {node["title"]: node for node in graph["nodes"]}

    dependency = nodes["Dependency resolver failed"]
    assert dependency["source"] == "failure_bundle"
    assert dependency["risk_surface"] == "dependency"
    assert dependency["review_first"] is True
    assert dependency["safe_to_auto_fix"] is False
    assert dependency["owner_files"] == ["constraints-ci.txt", "requirements-test.txt"]
    assert "PYTHONPATH=src python -m pip install -c constraints-ci.txt" in " ".join(
        dependency["proof_commands"]
    )
    assert "Reproduce the exact install lane." in dependency["recommended_commands"]

    security = nodes["Security finding requires review"]
    assert security["risk_surface"] == "security"
    assert security["review_first"] is True
    assert security["safe_to_auto_fix"] is False

    release = nodes["Release artifact validation failed"]
    assert release["risk_surface"] == "release"
    assert release["review_first"] is True
    assert release["safe_to_auto_fix"] is False


def test_evidence_graph_module_cli_accepts_failure_bundle(tmp_path: Path, capsys) -> None:
    failure_bundle = tmp_path / "failure-bundle.json"
    failure_bundle.write_text(
        json.dumps(
            {
                "diagnoses": [
                    {
                        "code": "PACKAGE_INSTALL_FAILURE",
                        "title": "Dependency resolver failed",
                        "diagnosis": "pip dependency resolver failed.",
                        "severity": "high",
                        "proof_commands": [
                            "PYTHONPATH=src python -m pip install -c constraints-ci.txt -r requirements-test.txt -e ."
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    rc = main(
        [
            "--failure-bundle",
            str(failure_bundle),
            "--out-dir",
            str(tmp_path / "evidence-graph"),
        ]
    )

    assert rc == 0
    captured = capsys.readouterr().out
    assert "evidence-graph.json" in captured

    graph = json.loads(
        (tmp_path / "evidence-graph" / "evidence-graph.json").read_text(encoding="utf-8")
    )
    assert graph["nodes"][0]["source"] == "failure_bundle"
    assert graph["nodes"][0]["risk_surface"] == "dependency"
