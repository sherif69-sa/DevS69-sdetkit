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
