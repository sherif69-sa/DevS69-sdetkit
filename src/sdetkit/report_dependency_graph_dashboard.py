from __future__ import annotations

import argparse
import html
import json
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from sdetkit import report_dependency_graph
from sdetkit.atomicio import atomic_write_text

SCHEMA_VERSION = "sdetkit.report_dependency_graph_dashboard.v1"
DEFAULT_OUT = Path("build") / "sdetkit" / "report-dependency-graph-dashboard.html"

JsonObject = dict[str, Any]

_EXPECTED_SOURCE_AUTHORITY: dict[str, bool] = {
    "reporting_only": True,
    "repo_mutation": False,
    "issue_mutation_allowed": False,
    "automation_allowed": False,
    "patch_application_allowed": False,
    "security_dismissal_allowed": False,
    "merge_authorized": False,
    "semantic_equivalence_proven": False,
}


def _as_dict(value: Any) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


def _integer(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _decision_boundary() -> JsonObject:
    return {
        "current_pr_decision_input": False,
        "automation_allowed": False,
        "issue_mutation_allowed": False,
        "security_dismissal_allowed": False,
        "proof_commands_executed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }


def _validate_source_authority(payload: Mapping[str, Any]) -> None:
    for field, expected in _EXPECTED_SOURCE_AUTHORITY.items():
        if payload.get(field) is not expected:
            raise ValueError(f"source graph authority boundary mismatch: {field}")
    boundary = payload.get("authority_boundary")
    if not isinstance(boundary, Mapping):
        raise ValueError("source graph authority_boundary must be an object")
    for field, expected in _EXPECTED_SOURCE_AUTHORITY.items():
        if boundary.get(field) is not expected:
            raise ValueError(f"source graph nested authority mismatch: {field}")


def _load_graph(path: Path) -> JsonObject:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("expected report dependency graph JSON object")
    if payload.get("schema_version") != report_dependency_graph.SCHEMA_VERSION:
        raise ValueError(
            "unsupported report dependency graph schema: "
            + (_string(payload.get("schema_version")) or "missing")
        )
    _validate_source_authority(payload)
    return payload


def _node(value: Any) -> JsonObject:
    item = _as_dict(value)
    return {
        "id": _string(item.get("id")),
        "type": _string(item.get("type")),
        "name": _string(item.get("name")),
        "family": _string(item.get("family")),
        "artifact_path": _string(item.get("artifact_path")),
        "state": _string(item.get("state")) or "unknown",
        "artifact_state": _string(item.get("artifact_state")),
        "producer_schema_version": _string(item.get("producer_schema_version")),
        "expected_artifact_schema_version": _string(item.get("expected_artifact_schema_version")),
        "observed_schema_version": _string(item.get("observed_schema_version")),
        "current_head_sha": _string(item.get("current_head_sha")),
        "reasons": sorted(_string(reason) for reason in _as_list(item.get("reasons"))),
        "source_authority": False,
    }


def _edge(value: Any) -> JsonObject:
    item = _as_dict(value)
    return {
        "source": _string(item.get("source")),
        "target": _string(item.get("target")),
        "kind": _string(item.get("kind")),
        "declared_by": _string(item.get("declared_by")),
        "dependency_id": _string(item.get("dependency_id")),
        "path": _string(item.get("path")),
        "expected_schema_version": _string(item.get("expected_schema_version")),
        "schema_role": _string(item.get("schema_role")) or "unknown",
        "observed_status": _string(item.get("observed_status")),
        "observed_schema_version": _string(item.get("observed_schema_version")),
        "current_head_sha": _string(item.get("current_head_sha")),
        "reasons": sorted(_string(reason) for reason in _as_list(item.get("reasons"))),
    }


def _finding(value: Any) -> JsonObject:
    item = _as_dict(value)
    return {
        "finding_id": _string(item.get("finding_id")),
        "severity": _string(item.get("severity")) or "unknown",
        "summary": _string(item.get("summary")),
        "evidence": _string(item.get("evidence")),
    }


def _validate_counts(
    graph: Mapping[str, Any],
    nodes: Sequence[Mapping[str, Any]],
    edges: Sequence[Mapping[str, Any]],
    cycles: Sequence[Mapping[str, Any]],
    findings: Sequence[Mapping[str, Any]],
) -> None:
    if _integer(graph.get("node_count")) != len(nodes):
        raise ValueError("node_count does not match nodes")
    if _integer(graph.get("edge_count")) != len(edges):
        raise ValueError("edge_count does not match edges")
    if _integer(graph.get("cycle_count")) != len(cycles):
        raise ValueError("cycle_count does not match cycles")

    unmapped = sum(_string(edge.get("target")).startswith("unmapped:") for edge in edges)
    if _integer(graph.get("unmapped_dependency_count")) != unmapped:
        raise ValueError("unmapped_dependency_count does not match edges")

    expected_states = dict(
        sorted(Counter(_string(node.get("state")) or "unknown" for node in nodes).items())
    )
    if _as_dict(graph.get("state_counts")) != expected_states:
        raise ValueError("state_counts does not match nodes")

    expected_relations = dict(
        sorted(Counter(_string(edge.get("kind")) or "unknown" for edge in edges).items())
    )
    if _as_dict(graph.get("relation_counts")) != expected_relations:
        raise ValueError("relation_counts does not match edges")

    expected_findings = dict(
        sorted(
            Counter(_string(finding.get("severity")) or "unknown" for finding in findings).items()
        )
    )
    source_finding_counts = {
        key: _integer(value)
        for key, value in sorted(_as_dict(graph.get("finding_counts")).items())
        if _integer(value) != 0
    }
    if source_finding_counts != expected_findings:
        raise ValueError("finding_counts does not match findings")


def build_dashboard(
    graph_path: Path,
    *,
    out_path: Path,
) -> JsonObject:
    del out_path
    graph = _load_graph(graph_path)
    nodes = [_node(item) for item in _as_list(graph.get("nodes"))]
    edges = [_edge(item) for item in _as_list(graph.get("edges"))]
    cycles = [
        {
            "members": sorted(
                _string(member) for member in _as_list(_as_dict(item).get("members"))
            ),
            "size": _integer(_as_dict(item).get("size")),
            "self_loop": _as_dict(item).get("self_loop") is True,
        }
        for item in _as_list(graph.get("cycles"))
    ]
    findings = [_finding(item) for item in _as_list(graph.get("findings"))]
    _validate_counts(graph, nodes, edges, cycles, findings)

    state_counts = dict(
        sorted(Counter(_string(node.get("state")) or "unknown" for node in nodes).items())
    )
    relation_counts = dict(
        sorted(Counter(_string(edge.get("kind")) or "unknown" for edge in edges).items())
    )
    source_status = _string(graph.get("graph_status")) or "unknown"
    status = (
        "blocked"
        if source_status == "blocked"
        else ("review_required" if source_status == "partial" else "current")
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "graph_path": graph_path.as_posix(),
        "graph_exists": graph_path.is_file(),
        "source_graph_schema_version": _string(graph.get("schema_version")),
        "source_graph_status": source_status,
        "source_graph_mode": _string(graph.get("mode")),
        "current_head_sha": _string(graph.get("current_head_sha")),
        "generated_at": _string(graph.get("generated_at")),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "cycle_count": len(cycles),
        "unmapped_dependency_count": sum(
            _string(edge.get("target")).startswith("unmapped:") for edge in edges
        ),
        "state_counts": state_counts,
        "relation_counts": relation_counts,
        "nodes": nodes,
        "edges": edges,
        "cycles": cycles,
        "findings": findings,
        "local_only": True,
        "read_only": True,
        "decision_boundary": _decision_boundary(),
    }


def _escape(value: Any) -> str:
    return html.escape(_string(value))


def _state_class(value: object) -> str:
    state = _string(value).lower()
    if state in {"blocked", "contradictory", "invalid", "stale"}:
        return "bad"
    if state in {"partial", "missing", "review_required"}:
        return "warn"
    return "good"


def render_html(payload: Mapping[str, Any]) -> str:
    nodes = [_as_dict(item) for item in _as_list(payload.get("nodes"))]
    edges = [_as_dict(item) for item in _as_list(payload.get("edges"))]
    findings = [_as_dict(item) for item in _as_list(payload.get("findings"))]
    cycles = [_as_dict(item) for item in _as_list(payload.get("cycles"))]

    node_rows = "".join(
        "<tr>"
        f"<td><code>{_escape(node.get('id'))}</code><br>"
        f"<span>{_escape(node.get('name')) or '—'}</span></td>"
        f"<td>{_escape(node.get('family'))}</td>"
        f"<td><span class='badge {_state_class(node.get('state'))}'>{_escape(node.get('state'))}</span></td>"
        f"<td><code>{_escape(node.get('expected_artifact_schema_version'))}</code></td>"
        f"<td><code>{_escape(node.get('producer_schema_version'))}</code></td>"
        f"<td><code>{_escape(node.get('current_head_sha')) or '—'}</code></td>"
        "</tr>"
        for node in nodes
    )
    if not node_rows:
        node_rows = "<tr><td colspan='6' class='muted'>No nodes</td></tr>"

    edge_rows = "".join(
        "<tr>"
        f"<td><code>{_escape(edge.get('source'))}</code></td>"
        f"<td><code>{_escape(edge.get('target'))}</code></td>"
        f"<td>{_escape(edge.get('kind'))}</td>"
        f"<td>{_escape(edge.get('schema_role'))}</td>"
        f"<td>{_escape(edge.get('observed_status')) or 'declared'}</td>"
        "</tr>"
        for edge in edges
    )
    if not edge_rows:
        edge_rows = "<tr><td colspan='5' class='muted'>No edges</td></tr>"

    finding_items = "".join(
        "<li>"
        f"<strong>{_escape(item.get('severity'))}</strong> "
        f"<code>{_escape(item.get('finding_id'))}</code> — "
        f"{_escape(item.get('summary'))} "
        f"<span class='muted'>{_escape(item.get('evidence'))}</span>"
        "</li>"
        for item in findings
    )
    if not finding_items:
        finding_items = "<li class='muted'>none</li>"

    cycle_items = "".join(
        "<li><code>"
        + html.escape(" → ".join(_string(member) for member in _as_list(item.get("members"))))
        + "</code></li>"
        for item in cycles
    )
    if not cycle_items:
        cycle_items = "<li class='muted'>none</li>"

    state_items = "".join(
        f"<li><strong>{html.escape(key)}</strong>: {_integer(value)}</li>"
        for key, value in sorted(_as_dict(payload.get("state_counts")).items())
    )
    relation_items = "".join(
        f"<li><strong>{html.escape(key)}</strong>: {_integer(value)}</li>"
        for key, value in sorted(_as_dict(payload.get("relation_counts")).items())
    )
    boundary_items = "".join(
        f"<li><strong>{html.escape(key)}</strong>: {str(value).lower()}</li>"
        for key, value in sorted(_as_dict(payload.get("decision_boundary")).items())
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Report dependency graph and freshness dashboard</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #172033; background: #f6f7fb; }}
    header, section {{ background: white; border: 1px solid #d7dce8; border-radius: 14px; padding: 1rem; margin-bottom: 1rem; }}
    .summary {{ display: flex; flex-wrap: wrap; gap: .6rem; margin: 1rem 0; }}
    .pill {{ border: 1px solid #d7dce8; border-radius: 999px; padding: .4rem .75rem; }}
    .badge {{ border-radius: 999px; padding: .15rem .5rem; font-weight: 700; }}
    .good {{ background: #dcfae6; color: #166534; }}
    .warn {{ background: #fff3cd; color: #854d0e; }}
    .bad {{ background: #fee4e2; color: #b42318; }}
    .muted {{ color: #667085; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ border-bottom: 1px solid #e4e7ec; padding: .55rem; text-align: left; vertical-align: top; }}
    code {{ overflow-wrap: anywhere; }}
    .two {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1rem; }}
  </style>
</head>
<body>
  <header>
    <h1>Report dependency graph and freshness dashboard</h1>
    <p>Static, local-only, read-only projection of report nodes, dependency edges, schema roles, and current-head freshness.</p>
    <div class="summary">
      <span class="pill">status: {_escape(payload.get("status"))}</span>
      <span class="pill">source: {_escape(payload.get("source_graph_status"))}</span>
      <span class="pill">nodes: {_integer(payload.get("node_count"))}</span>
      <span class="pill">edges: {_integer(payload.get("edge_count"))}</span>
      <span class="pill">cycles: {_integer(payload.get("cycle_count"))}</span>
      <span class="pill">unmapped: {_integer(payload.get("unmapped_dependency_count"))}</span>
      <span class="pill">read only: {str(payload.get("read_only")).lower()}</span>
    </div>
    <p><strong>Graph:</strong> <code>{_escape(payload.get("graph_path"))}</code></p>
    <p><strong>Current head:</strong> <code>{_escape(payload.get("current_head_sha"))}</code></p>
  </header>
  <section>
    <h2>Report nodes</h2>
    <table>
      <thead><tr><th>Node</th><th>Family</th><th>State</th><th>Artifact schema</th><th>Producer schema</th><th>Head</th></tr></thead>
      <tbody>{node_rows}</tbody>
    </table>
  </section>
  <section>
    <h2>Dependency edges</h2>
    <table>
      <thead><tr><th>Source</th><th>Target</th><th>Kind</th><th>Schema role</th><th>Status</th></tr></thead>
      <tbody>{edge_rows}</tbody>
    </table>
  </section>
  <div class="two">
    <section><h2>Node states</h2><ul>{state_items}</ul></section>
    <section><h2>Relation types</h2><ul>{relation_items}</ul></section>
    <section><h2>Cycles</h2><ul>{cycle_items}</ul></section>
    <section><h2>Findings</h2><ul>{finding_items}</ul></section>
    <section>
      <h2>Authority boundary</h2>
      <ul>{boundary_items}</ul>
      <p>This dashboard does not execute proof, mutate repositories or issues, apply patches, dismiss security findings, authorize merge, or claim semantic equivalence.</p>
    </section>
  </div>
</body>
</html>
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sdetkit report-dependency-graph-dashboard",
        description="Render a deterministic static dashboard from a report dependency graph.",
    )
    parser.add_argument("--graph-path", type=Path, required=True)
    parser.add_argument("--format", choices=("html", "json"), default="html")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    try:
        payload = build_dashboard(args.graph_path, out_path=args.out)
        rendered = (
            json.dumps(payload, indent=2, sort_keys=True) + "\n"
            if args.format == "json"
            else render_html(payload)
        )
        atomic_write_text(args.out, rendered)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={_string(exc) or type(exc).__name__}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
