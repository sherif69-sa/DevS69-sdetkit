from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdetkit import (
    _legacy_cli,
    artifact_contract_index,
    cross_report_consistency,
    report_dependency_graph,
    report_dependency_graph_dashboard,
)

HEAD = "1" * 40
GENERATED_AT = "2026-06-23T04:00:00Z"


def _write_contract_index(root: Path) -> None:
    path = root / "docs" / "artifact-contract-index.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(artifact_contract_index.build_index(), indent=2) + "\n",
        encoding="utf-8",
    )


def _artifact_payload(
    spec: cross_report_consistency.ReportSpec,
    *,
    dependencies: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": spec.expected_artifact_schema,
        "generated_at": GENERATED_AT,
        "current_head_sha": HEAD,
        "source_issue_numbers": [],
        "source_run_ids": [],
        "input_provenance": {
            "generated_at": GENERATED_AT,
            "generated_from_head_sha": HEAD,
            "input_digest": "a" * 64,
            "generator_schema_version": spec.expected_artifact_schema,
            "source_issue_numbers": [],
            "source_run_ids": [],
        },
        "reporting_only": True,
        "repo_mutation": False,
        "issue_mutation_allowed": False,
        "automation_allowed": False,
        "patch_application_allowed": False,
        "security_dismissal_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
        "authority_boundary": dict(report_dependency_graph.AUTHORITY_BOUNDARY),
    }
    if dependencies is not None:
        payload["report_dependencies"] = dependencies
    return payload


def _write_artifact(
    root: Path,
    spec: cross_report_consistency.ReportSpec,
    *,
    dependencies: list[dict[str, object]] | None = None,
) -> Path:
    path = root / spec.path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            _artifact_payload(spec, dependencies=dependencies),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _write_all_artifacts(root: Path) -> None:
    for spec in cross_report_consistency.REPORT_SPECS:
        _write_artifact(root, spec)


def test_discovery_graph_projects_canonical_nodes_and_edges(tmp_path: Path) -> None:
    _write_contract_index(tmp_path)

    payload = report_dependency_graph.build_report_dependency_graph(
        tmp_path,
        current_head_sha=HEAD,
        generated_at=GENERATED_AT,
    )

    assert payload["schema_version"] == report_dependency_graph.SCHEMA_VERSION
    assert payload["graph_status"] == "partial"
    assert payload["mode"] == "discovery"
    assert payload["report_node_count"] == len(cross_report_consistency.REPORT_SPECS)
    assert payload["node_count"] == len(cross_report_consistency.REPORT_SPECS) + 1
    assert payload["edge_count"] >= 16
    assert payload["cycle_count"] == 0
    assert payload["unmapped_dependency_count"] == 0
    assert payload["finding_counts"]["blocking"] == 0
    assert payload["finding_counts"]["partial"] == 1
    assert payload["current_head_sha"] == HEAD
    assert all(
        payload[field] is expected
        for field, expected in report_dependency_graph.AUTHORITY_BOUNDARY.items()
    )

    release_edges = [
        edge
        for edge in payload["edges"]
        if edge["kind"] == "projection_dependency"
        and edge["target"] == "release-anti-hijack-threat-model-json"
    ]
    assert len(release_edges) == 1
    assert release_edges[0]["schema_role"] == "producer"


def test_complete_current_graph_has_no_findings(tmp_path: Path) -> None:
    _write_contract_index(tmp_path)
    _write_all_artifacts(tmp_path)

    payload = report_dependency_graph.build_report_dependency_graph(
        tmp_path,
        complete=True,
        current_head_sha=HEAD,
        generated_at=GENERATED_AT,
    )

    assert payload["graph_status"] == "current"
    assert payload["finding_counts"] == {
        "blocking": 0,
        "partial": 0,
        "advisory": 0,
    }
    assert payload["state_counts"].get("contradictory", 0) == 0
    assert payload["state_counts"].get("stale", 0) == 0
    assert payload["state_counts"].get("invalid", 0) == 0
    assert sum(payload["state_counts"].values()) == len(cross_report_consistency.REPORT_SPECS) + 1
    assert payload["cycle_count"] == 0
    assert payload["unmapped_dependency_count"] == 0


def test_graph_detects_runtime_dependency_cycle(tmp_path: Path) -> None:
    _write_contract_index(tmp_path)
    _write_all_artifacts(tmp_path)
    specs = {spec.report_id: spec for spec in cross_report_consistency.REPORT_SPECS}
    radar = specs["product-maturity-radar-json"]
    workflow = specs["workflow-governance-report-json"]

    _write_artifact(
        tmp_path,
        radar,
        dependencies=[
            {
                "id": "",
                "path": workflow.path,
                "status": "fresh",
                "expected_schema_version": workflow.expected_artifact_schema,
                "observed_schema_version": workflow.expected_artifact_schema,
                "current_head_sha": HEAD,
                "reasons": [],
            }
        ],
    )
    _write_artifact(
        tmp_path,
        workflow,
        dependencies=[
            {
                "id": "",
                "path": radar.path,
                "status": "fresh",
                "expected_schema_version": radar.expected_artifact_schema,
                "observed_schema_version": radar.expected_artifact_schema,
                "current_head_sha": HEAD,
                "reasons": [],
            }
        ],
    )

    payload = report_dependency_graph.build_report_dependency_graph(
        tmp_path,
        current_head_sha=HEAD,
        generated_at=GENERATED_AT,
    )

    assert payload["graph_status"] == "blocked"
    assert payload["cycle_count"] == 1
    assert payload["finding_counts"]["blocking"] >= 1
    cycle_members = set(payload["cycles"][0]["members"])
    assert cycle_members == {
        "product-maturity-radar-json",
        "workflow-governance-report-json",
    }


def test_complete_mode_blocks_unmapped_dependency(tmp_path: Path) -> None:
    _write_contract_index(tmp_path)
    _write_all_artifacts(tmp_path)
    radar = next(
        spec
        for spec in cross_report_consistency.REPORT_SPECS
        if spec.report_id == "product-maturity-radar-json"
    )
    _write_artifact(
        tmp_path,
        radar,
        dependencies=[
            {
                "id": "outside_registry",
                "path": "build/sdetkit/outside-registry.json",
                "status": "fresh",
                "expected_schema_version": "sdetkit.outside.v1",
                "current_head_sha": HEAD,
                "reasons": [],
            }
        ],
    )

    payload = report_dependency_graph.build_report_dependency_graph(
        tmp_path,
        complete=True,
        current_head_sha=HEAD,
        generated_at=GENERATED_AT,
    )

    assert payload["graph_status"] == "blocked"
    assert payload["unmapped_dependency_count"] == 1
    findings = {finding["finding_id"]: finding for finding in payload["findings"]}
    assert findings["unmapped_dependency_reference"]["severity"] == "blocking"
    assert findings["dependency_schema_role_unknown"]["severity"] == "blocking"


def test_graph_freshness_round_trip(tmp_path: Path) -> None:
    _write_contract_index(tmp_path)
    out = tmp_path / "report-dependency-graph.json"
    markdown = tmp_path / "report-dependency-graph.md"

    report_dependency_graph.write_report_dependency_graph(
        repo_root=tmp_path,
        out=out,
        markdown_out=markdown,
        current_head_sha=HEAD,
        generated_at=GENERATED_AT,
    )
    before = out.read_bytes()

    freshness = report_dependency_graph.check_report_dependency_graph_freshness(
        repo_root=tmp_path,
        report_path=out,
        current_head_sha=HEAD,
    )

    assert freshness["status"] == "fresh"
    assert freshness["fresh"] is True
    assert freshness["reasons"] == []
    assert freshness["mode"] == "discovery"
    assert out.read_bytes() == before
    assert markdown.is_file()


def test_graph_root_cli_routes_generation_and_freshness(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_contract_index(tmp_path)
    monkeypatch.setattr(
        report_dependency_graph,
        "resolve_current_head",
        lambda root, override=None: override or HEAD,
    )
    out = tmp_path / "graph.json"
    markdown = tmp_path / "graph.md"

    rc = _legacy_cli.main(
        [
            "report-dependency-graph",
            "--root",
            str(tmp_path),
            "--out",
            str(out),
            "--markdown-out",
            str(markdown),
            "--format",
            "json",
        ]
    )
    assert rc == 0
    assert out.is_file()
    assert markdown.is_file()

    rc = _legacy_cli.main(
        [
            "report-dependency-graph",
            "--root",
            str(tmp_path),
            "--out",
            str(out),
            "--check-freshness",
            "--format",
            "text",
        ]
    )
    assert rc == 0


def test_graph_markdown_contains_nodes_edges_and_boundary(tmp_path: Path) -> None:
    _write_contract_index(tmp_path)
    payload = report_dependency_graph.build_report_dependency_graph(
        tmp_path,
        current_head_sha=HEAD,
        generated_at=GENERATED_AT,
    )

    rendered = report_dependency_graph.render_report_dependency_graph_markdown(payload)

    assert "# SDETKit report dependency graph" in rendered
    assert "## Nodes" in rendered
    assert "## Edges" in rendered
    assert "## Authority boundary" in rendered
    assert "- merge_authorized: false" in rendered


def test_artifact_contract_index_registers_graph_and_dashboard() -> None:
    entries = {item["id"]: item for item in artifact_contract_index.build_index()["artifacts"]}

    graph = entries["report-dependency-graph-json"]
    dashboard = entries["report-dependency-graph-dashboard-json"]

    assert graph["schema_version"] == report_dependency_graph.SCHEMA_VERSION
    assert dashboard["schema_version"] == report_dependency_graph_dashboard.SCHEMA_VERSION
    assert {
        "schema_version",
        "graph_status",
        "nodes",
        "edges",
        "cycles",
        "finding_counts",
        "authority_boundary",
    }.issubset(set(graph["required_fields"]))
    assert {
        "schema_version",
        "source_graph_status",
        "nodes",
        "edges",
        "decision_boundary",
    }.issubset(set(dashboard["required_fields"]))


def test_unknown_report_override_is_rejected(tmp_path: Path) -> None:
    _write_contract_index(tmp_path)

    with pytest.raises(ValueError, match="unknown report id"):
        report_dependency_graph.build_report_dependency_graph(
            tmp_path,
            report_json=("unknown=/tmp/report.json",),
            current_head_sha=HEAD,
        )
