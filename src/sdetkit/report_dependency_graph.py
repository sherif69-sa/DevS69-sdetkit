from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from . import cross_report_consistency, product_maturity_radar
from .report_provenance import (
    attach_provenance,
    build_input_provenance,
    check_report_path,
    render_freshness_text,
    resolve_current_head,
)

SCHEMA_VERSION = "sdetkit.report_dependency_graph.v1"
DEFAULT_OUT = "build/sdetkit/report-dependency-graph.json"
GENERATOR_SOURCE = "src/sdetkit/report_dependency_graph.py"
CONTRACT_INDEX_PATH = "docs/artifact-contract-index.json"

AUTHORITY_BOUNDARY: dict[str, bool] = {
    "reporting_only": True,
    "repo_mutation": False,
    "issue_mutation_allowed": False,
    "automation_allowed": False,
    "patch_application_allowed": False,
    "security_dismissal_allowed": False,
    "merge_authorized": False,
    "semantic_equivalence_proven": False,
}

_CONTRADICTORY_REASONS = {
    "report_schema_mismatch",
    "artifact_contract_schema_mismatch",
    "report_internal_head_conflict",
    "report_head_mismatch",
    "authority_expansion",
}
_INVALID_REASONS = {
    "report_unreadable",
    "invalid_json",
    "invalid_type",
    "report_schema_missing",
    "report_head_invalid",
}
_STALE_REASONS = {"stale_or_invalid_dependency"}


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return payload if isinstance(payload, dict) else None


def _parse_report_overrides(values: Sequence[str]) -> dict[str, str]:
    known = {spec.report_id for spec in cross_report_consistency.REPORT_SPECS}
    overrides: dict[str, str] = {}
    for value in values:
        report_id, separator, raw_path = value.partition("=")
        report_id = report_id.strip()
        raw_path = raw_path.strip()
        if not separator or not report_id or not raw_path:
            raise ValueError("--report-json values must use <report-id>=<path>")
        if report_id not in known:
            supported = ", ".join(sorted(known))
            raise ValueError(f"unknown report id {report_id!r}; supported: {supported}")
        overrides[report_id] = raw_path
    return overrides


def _resolve_report_paths(root: Path, report_json: Sequence[str]) -> dict[str, Path]:
    overrides = _parse_report_overrides(report_json)
    paths: dict[str, Path] = {}
    for spec in cross_report_consistency.REPORT_SPECS:
        raw = overrides.get(spec.report_id, spec.path)
        path = Path(raw)
        paths[spec.report_id] = path if path.is_absolute() else root / path
    return paths


def _normalize_path(root: Path, value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    path = Path(text)
    if path.is_absolute():
        try:
            return path.resolve().relative_to(root).as_posix()
        except ValueError:
            return path.as_posix()
    return path.as_posix()


def _record_state(record: Mapping[str, Any]) -> str:
    load_state = str(record.get("load_state") or "")
    reasons = {str(reason) for reason in record.get("reasons", [])}
    if load_state == "missing":
        return "missing"
    if reasons.intersection(_CONTRADICTORY_REASONS):
        return "contradictory"
    if reasons.intersection(_STALE_REASONS):
        return "stale"
    if reasons.intersection(_INVALID_REASONS) or record.get("status") == "invalid":
        return "invalid"
    if reasons:
        return "partial"
    return "current"


def _node_from_record(
    spec: cross_report_consistency.ReportSpec,
    record: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "id": spec.report_id,
        "type": "report_artifact",
        "name": spec.name,
        "family": spec.family,
        "artifact_path": spec.path,
        "producer_schema_version": spec.producer_schema,
        "expected_artifact_schema_version": spec.expected_artifact_schema,
        "observed_schema_version": str(record.get("observed_schema_version") or ""),
        "artifact_contract_schema_version": str(record.get("contract_schema_version") or ""),
        "artifact_sha256": str(record.get("artifact_sha256") or ""),
        "artifact_state": str(record.get("load_state") or "missing"),
        "state": _record_state(record),
        "current_head_sha": str(record.get("current_head_sha") or ""),
        "generated_at": str(record.get("generated_at") or ""),
        "reasons": sorted({str(reason) for reason in record.get("reasons", [])}),
        "required_in_complete": bool(spec.required_in_complete),
        "source_authority": False,
    }


def _controller_node(current_head_sha: str) -> dict[str, Any]:
    return {
        "id": "cross-report-consistency-json",
        "type": "aggregate_controller",
        "name": "cross_report_consistency",
        "family": "aggregate_consistency",
        "artifact_path": cross_report_consistency.DEFAULT_OUT,
        "producer_schema_version": cross_report_consistency.SCHEMA_VERSION,
        "expected_artifact_schema_version": cross_report_consistency.SCHEMA_VERSION,
        "observed_schema_version": cross_report_consistency.SCHEMA_VERSION,
        "artifact_contract_schema_version": cross_report_consistency.SCHEMA_VERSION,
        "artifact_sha256": "",
        "artifact_state": "virtual",
        "state": "current",
        "current_head_sha": current_head_sha,
        "generated_at": "",
        "reasons": [],
        "required_in_complete": False,
        "source_authority": False,
    }


def _schema_role(
    expected_schema: str,
    target_spec: cross_report_consistency.ReportSpec | None,
) -> str:
    if target_spec is None or not expected_schema:
        return "unknown"
    if expected_schema == target_spec.expected_artifact_schema:
        return "artifact"
    if expected_schema == target_spec.producer_schema:
        return "producer"
    return "unknown"


def _edge_key(edge: Mapping[str, Any]) -> tuple[str, ...]:
    return (
        str(edge.get("source") or ""),
        str(edge.get("target") or ""),
        str(edge.get("kind") or ""),
        str(edge.get("dependency_id") or ""),
        str(edge.get("path") or ""),
        str(edge.get("expected_schema_version") or ""),
    )


def _deduplicate_edges(edges: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[tuple[str, ...], dict[str, Any]] = {}
    for edge in edges:
        unique[_edge_key(edge)] = dict(edge)
    return [unique[key] for key in sorted(unique)]


def _dependency_target(
    *,
    root: Path,
    dependency_id: str,
    raw_path: str,
    specs_by_id: Mapping[str, cross_report_consistency.ReportSpec],
    specs_by_path: Mapping[str, cross_report_consistency.ReportSpec],
) -> tuple[str, cross_report_consistency.ReportSpec | None]:
    normalized_path = _normalize_path(root, raw_path)
    direct = specs_by_id.get(dependency_id)
    if direct is not None:
        return direct.report_id, direct
    by_path = specs_by_path.get(normalized_path)
    if by_path is not None:
        return by_path.report_id, by_path
    label = dependency_id or normalized_path or "unknown"
    return f"unmapped:{label}", None


def _declared_edges(root: Path) -> list[dict[str, Any]]:
    specs = cross_report_consistency.REPORT_SPECS
    specs_by_id = {spec.report_id: spec for spec in specs}
    specs_by_path = {Path(spec.path).as_posix(): spec for spec in specs}
    edges: list[dict[str, Any]] = []

    for spec in specs:
        edges.append(
            {
                "source": "cross-report-consistency-json",
                "target": spec.report_id,
                "kind": "consistency_input",
                "declared_by": cross_report_consistency.GENERATOR_SOURCE,
                "dependency_id": spec.report_id,
                "path": spec.path,
                "expected_schema_version": spec.expected_artifact_schema,
                "schema_role": "artifact",
                "observed_status": "",
                "observed_schema_version": "",
                "current_head_sha": "",
                "reasons": [],
            }
        )

    for dependency_id, dependency in product_maturity_radar.REPORT_DEPENDENCY_SPECS.items():
        raw_path = str(dependency.get("path") or "")
        target, target_spec = _dependency_target(
            root=root,
            dependency_id="",
            raw_path=raw_path,
            specs_by_id=specs_by_id,
            specs_by_path=specs_by_path,
        )
        expected_schema = str(dependency.get("schema_version") or "")
        edges.append(
            {
                "source": "product-maturity-radar-json",
                "target": target,
                "kind": "projection_dependency",
                "declared_by": product_maturity_radar.GENERATOR_SOURCE,
                "dependency_id": dependency_id,
                "path": _normalize_path(root, raw_path),
                "expected_schema_version": expected_schema,
                "schema_role": _schema_role(expected_schema, target_spec),
                "observed_status": "",
                "observed_schema_version": "",
                "current_head_sha": "",
                "reasons": [],
                "surfaces": sorted(str(value) for value in dependency.get("surfaces", ())),
            }
        )
    return edges


def _runtime_edges(root: Path, paths: Mapping[str, Path]) -> list[dict[str, Any]]:
    specs = cross_report_consistency.REPORT_SPECS
    specs_by_id = {spec.report_id: spec for spec in specs}
    specs_by_path = {Path(spec.path).as_posix(): spec for spec in specs}
    edges: list[dict[str, Any]] = []

    for source_spec in specs:
        payload = _load_json(paths[source_spec.report_id])
        if payload is None:
            continue
        dependencies = payload.get("report_dependencies")
        if not isinstance(dependencies, list):
            continue
        for dependency in dependencies:
            if not isinstance(dependency, Mapping):
                continue
            dependency_id = str(dependency.get("id") or "")
            raw_path = str(dependency.get("path") or "")
            target, target_spec = _dependency_target(
                root=root,
                dependency_id=dependency_id,
                raw_path=raw_path,
                specs_by_id=specs_by_id,
                specs_by_path=specs_by_path,
            )
            expected_schema = str(
                dependency.get("expected_schema_version") or dependency.get("schema_version") or ""
            )
            edges.append(
                {
                    "source": source_spec.report_id,
                    "target": target,
                    "kind": "observed_runtime_dependency",
                    "declared_by": source_spec.path,
                    "dependency_id": dependency_id,
                    "path": _normalize_path(root, raw_path),
                    "expected_schema_version": expected_schema,
                    "schema_role": _schema_role(expected_schema, target_spec),
                    "observed_status": str(dependency.get("status") or ""),
                    "observed_schema_version": str(
                        dependency.get("observed_schema_version")
                        or dependency.get("schema_version")
                        or ""
                    ),
                    "current_head_sha": str(dependency.get("current_head_sha") or ""),
                    "reasons": sorted({str(reason) for reason in dependency.get("reasons", [])}),
                }
            )
    return edges


def _cycles(
    node_ids: Sequence[str],
    edges: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    known = set(node_ids)
    adjacency: dict[str, set[str]] = {node_id: set() for node_id in known}
    for edge in edges:
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        if source in known and target in known:
            adjacency[source].add(target)

    index = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    indexes: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    components: list[list[str]] = []

    def visit(node: str) -> None:
        nonlocal index
        indexes[node] = index
        lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)

        for target in sorted(adjacency[node]):
            if target not in indexes:
                visit(target)
                lowlinks[node] = min(lowlinks[node], lowlinks[target])
            elif target in on_stack:
                lowlinks[node] = min(lowlinks[node], indexes[target])

        if lowlinks[node] != indexes[node]:
            return
        component: list[str] = []
        while stack:
            member = stack.pop()
            on_stack.remove(member)
            component.append(member)
            if member == node:
                break
        components.append(sorted(component))

    for node in sorted(known):
        if node not in indexes:
            visit(node)

    cycles: list[dict[str, Any]] = []
    for component in sorted(components):
        self_loop = len(component) == 1 and component[0] in adjacency.get(component[0], set())
        if len(component) > 1 or self_loop:
            cycles.append(
                {
                    "members": component,
                    "size": len(component),
                    "self_loop": self_loop,
                }
            )
    return cycles


def _registry_snapshot() -> bytes:
    payload = {
        "report_specs": [
            {
                "report_id": spec.report_id,
                "name": spec.name,
                "path": spec.path,
                "expected_artifact_schema": spec.expected_artifact_schema,
                "producer_schema": spec.producer_schema,
                "family": spec.family,
                "required_in_complete": spec.required_in_complete,
            }
            for spec in cross_report_consistency.REPORT_SPECS
        ],
        "product_maturity_dependencies": {
            dependency_id: {
                "path": str(spec.get("path") or ""),
                "schema_version": str(spec.get("schema_version") or ""),
                "surfaces": sorted(str(value) for value in spec.get("surfaces", ())),
            }
            for dependency_id, spec in sorted(
                product_maturity_radar.REPORT_DEPENDENCY_SPECS.items()
            )
        },
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _input_provenance(
    *,
    root: Path,
    paths: Mapping[str, Path],
    nodes: Sequence[Mapping[str, Any]],
    complete: bool,
    current_head_sha: str,
    generated_at: str | None,
) -> dict[str, Any]:
    contract_path = root / CONTRACT_INDEX_PATH
    data_inputs: dict[str, bytes] = {
        "registry_snapshot": _registry_snapshot(),
        "artifact_contract_index": (
            contract_path.read_bytes() if contract_path.is_file() else b"<missing>"
        ),
        "cross_report_consistency_source": Path(cross_report_consistency.__file__).read_bytes(),
        "product_maturity_radar_source": Path(product_maturity_radar.__file__).read_bytes(),
        "mode": ("complete" if complete else "discovery").encode("utf-8"),
    }
    for report_id, path in sorted(paths.items()):
        data_inputs[f"report:{report_id}"] = path.read_bytes() if path.is_file() else b"<missing>"

    generator = Path(__file__).resolve()
    schemas = {
        str(node["id"]): str(
            node.get("observed_schema_version") or node.get("artifact_state") or "unknown"
        )
        for node in nodes
        if node.get("type") == "report_artifact"
    }
    return build_input_provenance(
        schema_version=SCHEMA_VERSION,
        generator_source=GENERATOR_SOURCE,
        generator_bytes=generator.read_bytes(),
        data_inputs=data_inputs,
        root=root,
        source_issue_numbers=(),
        source_run_ids=(),
        input_artifact_schemas=schemas,
        current_head_sha=current_head_sha,
        generated_at=generated_at,
    )


def _findings(
    *,
    consistency: Mapping[str, Any],
    nodes: Sequence[Mapping[str, Any]],
    edges: Sequence[Mapping[str, Any]],
    cycles: Sequence[Mapping[str, Any]],
    complete: bool,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    consistency_counts = consistency.get("finding_counts")
    consistency_counts = consistency_counts if isinstance(consistency_counts, Mapping) else {}
    if int(consistency_counts.get("blocking", 0) or 0) > 0:
        findings.append(
            {
                "finding_id": "source_consistency_blocked",
                "severity": "blocking",
                "summary": "The source cross-report consistency model has blocking contradictions.",
                "evidence": json.dumps(
                    dict(consistency_counts),
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            }
        )

    missing = sorted(str(node["id"]) for node in nodes if node.get("state") == "missing")
    if missing:
        findings.append(
            {
                "finding_id": "report_nodes_missing",
                "severity": "blocking" if complete else "partial",
                "summary": "Expected report nodes are absent.",
                "evidence": ",".join(missing),
            }
        )

    unhealthy = sorted(
        str(node["id"])
        for node in nodes
        if node.get("state") in {"contradictory", "stale", "invalid"}
    )
    if unhealthy:
        findings.append(
            {
                "finding_id": "report_nodes_unhealthy",
                "severity": "blocking",
                "summary": "Present report nodes contain contradictory, stale, or invalid evidence.",
                "evidence": ",".join(unhealthy),
            }
        )

    unmapped = sorted(
        {
            str(edge.get("target") or "")
            for edge in edges
            if str(edge.get("target") or "").startswith("unmapped:")
        }
    )
    if unmapped:
        findings.append(
            {
                "finding_id": "unmapped_dependency_reference",
                "severity": "blocking" if complete else "partial",
                "summary": "Dependency edges reference reports outside the canonical registry.",
                "evidence": ",".join(unmapped),
            }
        )

    unknown_roles = sorted(
        {
            f"{edge.get('source')}->{edge.get('target')}"
            for edge in edges
            if edge.get("schema_role") == "unknown"
            and str(edge.get("expected_schema_version") or "")
        }
    )
    if unknown_roles:
        findings.append(
            {
                "finding_id": "dependency_schema_role_unknown",
                "severity": "blocking" if complete else "partial",
                "summary": "Dependency schema expectations map to neither producer nor artifact schema.",
                "evidence": ",".join(unknown_roles),
            }
        )

    for cycle in cycles:
        findings.append(
            {
                "finding_id": "dependency_cycle_detected",
                "severity": "blocking",
                "summary": "The report dependency graph contains a directed cycle.",
                "evidence": ",".join(str(member) for member in cycle.get("members", [])),
            }
        )

    return sorted(
        findings,
        key=lambda item: (
            {"blocking": 0, "partial": 1, "advisory": 2}.get(str(item["severity"]), 9),
            str(item["finding_id"]),
        ),
    )


def build_report_dependency_graph(
    repo_root: str | Path = ".",
    *,
    report_json: Sequence[str] = (),
    complete: bool = False,
    current_head_sha: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    live_head = resolve_current_head(root, override=current_head_sha)
    paths = _resolve_report_paths(root, report_json)
    consistency = cross_report_consistency.build_cross_report_consistency(
        root,
        report_json=report_json,
        complete=complete,
        current_head_sha=live_head,
        generated_at=generated_at,
    )
    records = {
        str(record.get("report_id") or ""): record
        for record in consistency.get("report_records", [])
        if isinstance(record, Mapping)
    }

    nodes = [_controller_node(live_head)]
    for spec in cross_report_consistency.REPORT_SPECS:
        nodes.append(_node_from_record(spec, records.get(spec.report_id, {})))
    nodes = sorted(nodes, key=lambda item: str(item["id"]))

    edges = _deduplicate_edges([*_declared_edges(root), *_runtime_edges(root, paths)])
    cycles = _cycles([str(node["id"]) for node in nodes], edges)
    findings = _findings(
        consistency=consistency,
        nodes=nodes,
        edges=edges,
        cycles=cycles,
        complete=complete,
    )
    finding_counts = Counter(str(item["severity"]) for item in findings)
    state_counts = Counter(str(node["state"]) for node in nodes)
    relation_counts = Counter(str(edge["kind"]) for edge in edges)

    if finding_counts.get("blocking", 0):
        graph_status = "blocked"
    elif finding_counts.get("partial", 0):
        graph_status = "partial"
    else:
        graph_status = "current"

    unmapped_count = sum(str(edge.get("target") or "").startswith("unmapped:") for edge in edges)
    provenance = _input_provenance(
        root=root,
        paths=paths,
        nodes=nodes,
        complete=complete,
        current_head_sha=live_head,
        generated_at=generated_at,
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "report_status": "review_required" if findings else "passed",
        "graph_status": graph_status,
        "mode": "complete" if complete else "discovery",
        "node_count": len(nodes),
        "report_node_count": sum(node["type"] == "report_artifact" for node in nodes),
        "edge_count": len(edges),
        "cycle_count": len(cycles),
        "unmapped_dependency_count": unmapped_count,
        "state_counts": dict(sorted(state_counts.items())),
        "relation_counts": dict(sorted(relation_counts.items())),
        "nodes": nodes,
        "edges": edges,
        "cycles": cycles,
        "findings": findings,
        "finding_counts": {
            "blocking": finding_counts.get("blocking", 0),
            "partial": finding_counts.get("partial", 0),
            "advisory": finding_counts.get("advisory", 0),
        },
        "source_consistency": {
            "schema_version": consistency.get("schema_version", ""),
            "consistency_status": consistency.get("consistency_status", ""),
            "finding_counts": consistency.get("finding_counts", {}),
            "mode": consistency.get("mode", ""),
        },
        "rules": {
            "canonical_registry": "cross_report_consistency.REPORT_SPECS",
            "secondary_registry": "product_maturity_radar.REPORT_DEPENDENCY_SPECS",
            "source_reports_authoritative": True,
            "graph_is_projection_only": True,
            "cycles_block": True,
            "unmapped_dependencies_block_in_complete_mode": True,
            "missing_reports_block_in_complete_mode": True,
            "review_first": True,
        },
        **AUTHORITY_BOUNDARY,
        "authority_boundary": dict(AUTHORITY_BOUNDARY),
    }
    return attach_provenance(payload, provenance)


def report_dependency_graph_input_provenance(
    *,
    repo_root: str | Path = ".",
    report_json: Sequence[str] = (),
    complete: bool = False,
    current_head_sha: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    live_head = resolve_current_head(root, override=current_head_sha)
    paths = _resolve_report_paths(root, report_json)
    consistency = cross_report_consistency.build_cross_report_consistency(
        root,
        report_json=report_json,
        complete=complete,
        current_head_sha=live_head,
        generated_at=generated_at,
    )
    records = {
        str(record.get("report_id") or ""): record
        for record in consistency.get("report_records", [])
        if isinstance(record, Mapping)
    }
    nodes = [_controller_node(live_head)]
    nodes.extend(
        _node_from_record(spec, records.get(spec.report_id, {}))
        for spec in cross_report_consistency.REPORT_SPECS
    )
    return _input_provenance(
        root=root,
        paths=paths,
        nodes=nodes,
        complete=complete,
        current_head_sha=live_head,
        generated_at=generated_at,
    )


def check_report_dependency_graph_freshness(
    *,
    repo_root: str | Path = ".",
    report_path: str | Path = DEFAULT_OUT,
    report_json: Sequence[str] = (),
    complete: bool = False,
    current_head_sha: str | None = None,
) -> dict[str, Any]:
    current = report_dependency_graph_input_provenance(
        repo_root=repo_root,
        report_json=report_json,
        complete=complete,
        current_head_sha=current_head_sha,
    )
    result = check_report_path(
        report_path,
        current,
        expected_schema_version=SCHEMA_VERSION,
    )
    result["mode"] = "complete" if complete else "discovery"
    return result


def render_report_dependency_graph_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# SDETKit report dependency graph",
        "",
        f"- graph_status: `{payload.get('graph_status', 'unknown')}`",
        f"- mode: `{payload.get('mode', 'discovery')}`",
        f"- generated_at: `{payload.get('generated_at', '')}`",
        f"- current_head_sha: `{payload.get('current_head_sha', '')}`",
        f"- node_count: `{payload.get('node_count', 0)}`",
        f"- edge_count: `{payload.get('edge_count', 0)}`",
        f"- cycle_count: `{payload.get('cycle_count', 0)}`",
        f"- unmapped_dependency_count: `{payload.get('unmapped_dependency_count', 0)}`",
        "",
        "## Nodes",
        "",
        "| Node | Type | State | Artifact schema | Producer schema | Head |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for node in payload.get("nodes", []):
        if not isinstance(node, Mapping):
            continue
        lines.append(
            "| {id} | `{type}` | `{state}` | `{artifact}` | `{producer}` | `{head}` |".format(
                id=node.get("id", ""),
                type=node.get("type", ""),
                state=node.get("state", ""),
                artifact=node.get("expected_artifact_schema_version", ""),
                producer=node.get("producer_schema_version", ""),
                head=node.get("current_head_sha", ""),
            )
        )

    lines.extend(
        [
            "",
            "## Edges",
            "",
            "| Source | Target | Kind | Schema role | Status |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for edge in payload.get("edges", []):
        if not isinstance(edge, Mapping):
            continue
        lines.append(
            "| {source} | {target} | `{kind}` | `{role}` | `{status}` |".format(
                source=edge.get("source", ""),
                target=edge.get("target", ""),
                kind=edge.get("kind", ""),
                role=edge.get("schema_role", ""),
                status=edge.get("observed_status", "") or "declared",
            )
        )

    lines.extend(["", "## Cycles", ""])
    cycles = payload.get("cycles", [])
    if not cycles:
        lines.append("- none")
    else:
        for cycle in cycles:
            if isinstance(cycle, Mapping):
                lines.append(
                    "- `{members}`".format(
                        members=" -> ".join(str(member) for member in cycle.get("members", []))
                    )
                )

    lines.extend(["", "## Findings", ""])
    findings = payload.get("findings", [])
    if not findings:
        lines.append("- none")
    else:
        for finding in findings:
            if not isinstance(finding, Mapping):
                continue
            lines.append(
                "- **{severity}** `{finding_id}` — {summary} ({evidence})".format(
                    severity=finding.get("severity", "unknown"),
                    finding_id=finding.get("finding_id", "unknown"),
                    summary=finding.get("summary", ""),
                    evidence=finding.get("evidence", ""),
                )
            )

    lines.extend(
        [
            "",
            "## Authority boundary",
            "",
            "- reporting_only: true",
            "- repo_mutation: false",
            "- issue_mutation_allowed: false",
            "- automation_allowed: false",
            "- patch_application_allowed: false",
            "- security_dismissal_allowed: false",
            "- merge_authorized: false",
            "- semantic_equivalence_proven: false",
            "",
        ]
    )
    return "\n".join(lines)


def write_report_dependency_graph(
    *,
    repo_root: str | Path,
    out: str | Path,
    markdown_out: str | Path | None = None,
    report_json: Sequence[str] = (),
    complete: bool = False,
    current_head_sha: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    out_path = Path(out)
    markdown_path = Path(markdown_out) if markdown_out is not None else out_path.with_suffix(".md")
    payload = build_report_dependency_graph(
        repo_root,
        report_json=report_json,
        complete=complete,
        current_head_sha=current_head_sha,
        generated_at=generated_at,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(
        render_report_dependency_graph_markdown(payload) + "\n",
        encoding="utf-8",
    )
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit report-dependency-graph",
        description="Project report dependencies, schema roles, and freshness state.",
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--markdown-out", default="")
    parser.add_argument(
        "--report-json",
        action="append",
        default=[],
        metavar="REPORT-ID=PATH",
        help="Override a known report artifact path; repeatable.",
    )
    parser.add_argument("--complete", action="store_true")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    parser.add_argument("--check-freshness", action="store_true")
    ns = parser.parse_args(list(argv) if argv is not None else None)

    if ns.check_freshness:
        freshness = check_report_dependency_graph_freshness(
            repo_root=ns.root,
            report_path=ns.out,
            report_json=ns.report_json,
            complete=ns.complete,
        )
        if ns.format == "json":
            sys.stdout.write(json.dumps(freshness, indent=2, sort_keys=True) + "\n")
        else:
            sys.stdout.write(render_freshness_text(freshness) + "\n")
            sys.stdout.write(f"mode={freshness['mode']}\n")
        return 0 if freshness["fresh"] else 1

    payload = write_report_dependency_graph(
        repo_root=ns.root,
        out=ns.out,
        markdown_out=ns.markdown_out or None,
        report_json=ns.report_json,
        complete=ns.complete,
    )
    if ns.format == "json":
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    else:
        sys.stdout.write(
            "\n".join(
                [
                    f"graph_status={payload['graph_status']}",
                    f"mode={payload['mode']}",
                    f"node_count={payload['node_count']}",
                    f"edge_count={payload['edge_count']}",
                    f"cycle_count={payload['cycle_count']}",
                    f"unmapped_dependency_count={payload['unmapped_dependency_count']}",
                    f"blocking_findings={payload['finding_counts']['blocking']}",
                    f"partial_findings={payload['finding_counts']['partial']}",
                    "reporting_only=true",
                    "repo_mutation=false",
                    "automation_allowed=false",
                    "patch_application_allowed=false",
                    "security_dismissal_allowed=false",
                    "merge_authorized=false",
                    "semantic_equivalence_proven=false",
                ]
            )
            + "\n"
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
