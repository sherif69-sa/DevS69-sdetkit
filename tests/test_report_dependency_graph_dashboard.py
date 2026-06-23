from __future__ import annotations

import json
from pathlib import Path

from sdetkit import _legacy_cli, report_dependency_graph, report_dependency_graph_dashboard

HEAD = "1" * 40


def _graph_payload() -> dict[str, object]:
    nodes = [
        {
            "id": "cross-report-consistency-json",
            "type": "aggregate_controller",
            "name": "cross_report_consistency",
            "family": "aggregate_consistency",
            "artifact_path": "build/sdetkit/cross-report-consistency.json",
            "state": "current",
            "artifact_state": "virtual",
            "producer_schema_version": "sdetkit.cross_report_consistency.v1",
            "expected_artifact_schema_version": "sdetkit.cross_report_consistency.v1",
            "observed_schema_version": "sdetkit.cross_report_consistency.v1",
            "current_head_sha": HEAD,
            "reasons": [],
            "source_authority": False,
        },
        {
            "id": "product-maturity-radar-json",
            "type": "report_artifact",
            "name": "product_maturity_radar",
            "family": "decision_projection",
            "artifact_path": "build/sdetkit/product-maturity-radar.json",
            "state": "missing",
            "artifact_state": "missing",
            "producer_schema_version": "sdetkit.product_maturity_radar.v2",
            "expected_artifact_schema_version": "sdetkit.product_maturity_radar.v2",
            "observed_schema_version": "",
            "current_head_sha": "",
            "reasons": ["report_missing"],
            "source_authority": False,
        },
    ]
    edges = [
        {
            "source": "cross-report-consistency-json",
            "target": "product-maturity-radar-json",
            "kind": "consistency_input",
            "declared_by": "src/sdetkit/cross_report_consistency.py",
            "dependency_id": "product-maturity-radar-json",
            "path": "build/sdetkit/product-maturity-radar.json",
            "expected_schema_version": "sdetkit.product_maturity_radar.v2",
            "schema_role": "artifact",
            "observed_status": "",
            "observed_schema_version": "",
            "current_head_sha": "",
            "reasons": [],
        }
    ]
    findings = [
        {
            "finding_id": "report_nodes_missing",
            "severity": "partial",
            "summary": "Expected report nodes are absent.",
            "evidence": "product-maturity-radar-json",
        }
    ]
    return {
        "schema_version": report_dependency_graph.SCHEMA_VERSION,
        "report_status": "review_required",
        "graph_status": "partial",
        "mode": "discovery",
        "generated_at": "2026-06-23T04:00:00Z",
        "current_head_sha": HEAD,
        "node_count": len(nodes),
        "report_node_count": 1,
        "edge_count": len(edges),
        "cycle_count": 0,
        "unmapped_dependency_count": 0,
        "state_counts": {"current": 1, "missing": 1},
        "relation_counts": {"consistency_input": 1},
        "nodes": nodes,
        "edges": edges,
        "cycles": [],
        "findings": findings,
        "finding_counts": {"blocking": 0, "partial": 1, "advisory": 0},
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


def _write_graph(
    path: Path,
    *,
    payload: dict[str, object] | None = None,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload or _graph_payload(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def test_dashboard_builds_read_only_graph_summary(tmp_path: Path) -> None:
    graph = _write_graph(tmp_path / "graph.json")
    before = graph.read_bytes()

    payload = report_dependency_graph_dashboard.build_dashboard(
        graph,
        out_path=tmp_path / "dashboard.html",
    )

    assert payload["schema_version"] == report_dependency_graph_dashboard.SCHEMA_VERSION
    assert payload["status"] == "review_required"
    assert payload["source_graph_status"] == "partial"
    assert payload["node_count"] == 2
    assert payload["edge_count"] == 1
    assert payload["cycle_count"] == 0
    assert payload["unmapped_dependency_count"] == 0
    assert payload["state_counts"] == {"current": 1, "missing": 1}
    assert payload["relation_counts"] == {"consistency_input": 1}
    assert payload["local_only"] is True
    assert payload["read_only"] is True
    assert all(value is False for value in payload["decision_boundary"].values())
    assert graph.read_bytes() == before


def test_dashboard_renders_static_escaped_html(tmp_path: Path) -> None:
    payload = _graph_payload()
    nodes = payload["nodes"]
    assert isinstance(nodes, list)
    assert isinstance(nodes[1], dict)
    nodes[1]["name"] = "<script>alert('x')</script>"
    findings = payload["findings"]
    assert isinstance(findings, list)
    assert isinstance(findings[0], dict)
    findings[0]["summary"] = "<img src=x onerror=alert(1)>"
    graph = _write_graph(tmp_path / "graph.json", payload=payload)
    out = tmp_path / "dashboard.html"

    rc = report_dependency_graph_dashboard.main(
        [
            "--graph-path",
            str(graph),
            "--format",
            "html",
            "--out",
            str(out),
        ]
    )

    assert rc == 0
    text = out.read_text(encoding="utf-8")
    assert "Report dependency graph and freshness dashboard" in text
    assert "Static, local-only, read-only" in text
    assert "&lt;script&gt;" in text
    assert "&lt;img src=x onerror=alert(1)&gt;" in text
    assert "<script>" not in text
    assert "issue_mutation_allowed</strong>: false" in text
    assert "security_dismissal_allowed</strong>: false" in text
    assert "merge_authorized</strong>: false" in text
    assert "<script src=" not in text


def test_dashboard_writes_deterministic_json(tmp_path: Path) -> None:
    graph = _write_graph(tmp_path / "graph.json")
    first = tmp_path / "dashboard-1.json"
    second = tmp_path / "dashboard-2.json"

    for out in (first, second):
        rc = report_dependency_graph_dashboard.main(
            [
                "--graph-path",
                str(graph),
                "--format",
                "json",
                "--out",
                str(out),
            ]
        )
        assert rc == 0

    assert first.read_bytes() == second.read_bytes()
    payload = json.loads(first.read_text(encoding="utf-8"))
    assert payload["node_count"] == 2
    assert payload["decision_boundary"]["automation_allowed"] is False
    assert payload["decision_boundary"]["merge_authorized"] is False


def test_dashboard_root_cli_routes_json_generation(tmp_path: Path) -> None:
    graph = _write_graph(tmp_path / "graph.json")
    out = tmp_path / "dashboard.json"

    rc = _legacy_cli.main(
        [
            "report-dependency-graph-dashboard",
            "--graph-path",
            str(graph),
            "--format",
            "json",
            "--out",
            str(out),
        ]
    )

    assert rc == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == report_dependency_graph_dashboard.SCHEMA_VERSION


def test_dashboard_rejects_missing_malformed_or_unknown_schema(
    tmp_path: Path,
    capsys,
) -> None:
    out = tmp_path / "dashboard.json"

    rc = report_dependency_graph_dashboard.main(
        [
            "--graph-path",
            str(tmp_path / "missing.json"),
            "--format",
            "json",
            "--out",
            str(out),
        ]
    )
    assert rc == 2
    assert not out.exists()
    assert "error=" in capsys.readouterr().err

    malformed = tmp_path / "malformed.json"
    malformed.write_text("{not-json", encoding="utf-8")
    rc = report_dependency_graph_dashboard.main(
        [
            "--graph-path",
            str(malformed),
            "--format",
            "json",
            "--out",
            str(out),
        ]
    )
    assert rc == 2
    assert not out.exists()
    assert "error=" in capsys.readouterr().err

    unknown = _graph_payload()
    unknown["schema_version"] = "sdetkit.report_dependency_graph.v999"
    unknown_path = _write_graph(tmp_path / "unknown.json", payload=unknown)
    rc = report_dependency_graph_dashboard.main(
        [
            "--graph-path",
            str(unknown_path),
            "--format",
            "json",
            "--out",
            str(out),
        ]
    )
    assert rc == 2
    assert not out.exists()
    assert "unsupported report dependency graph schema" in capsys.readouterr().err


def test_dashboard_rejects_count_drift(tmp_path: Path, capsys) -> None:
    payload = _graph_payload()
    payload["node_count"] = 99
    graph = _write_graph(tmp_path / "drift.json", payload=payload)
    out = tmp_path / "dashboard.json"

    rc = report_dependency_graph_dashboard.main(
        [
            "--graph-path",
            str(graph),
            "--format",
            "json",
            "--out",
            str(out),
        ]
    )

    assert rc == 2
    assert not out.exists()
    assert "node_count does not match nodes" in capsys.readouterr().err


def test_dashboard_rejects_authority_expansion(tmp_path: Path, capsys) -> None:
    payload = _graph_payload()
    payload["automation_allowed"] = True
    graph = _write_graph(tmp_path / "expanded.json", payload=payload)
    out = tmp_path / "dashboard.json"

    rc = report_dependency_graph_dashboard.main(
        [
            "--graph-path",
            str(graph),
            "--format",
            "json",
            "--out",
            str(out),
        ]
    )

    assert rc == 2
    assert not out.exists()
    assert "source graph authority boundary mismatch" in capsys.readouterr().err

    nested = _graph_payload()
    boundary = nested["authority_boundary"]
    assert isinstance(boundary, dict)
    boundary["merge_authorized"] = True
    nested_path = _write_graph(tmp_path / "nested-expanded.json", payload=nested)

    rc = report_dependency_graph_dashboard.main(
        [
            "--graph-path",
            str(nested_path),
            "--format",
            "json",
            "--out",
            str(out),
        ]
    )

    assert rc == 2
    assert not out.exists()
    assert "source graph nested authority mismatch" in capsys.readouterr().err
