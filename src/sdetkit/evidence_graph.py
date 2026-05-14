from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Literal, TypedDict, cast

SCHEMA_VERSION = "sdetkit.evidence-graph.v1"
DEFAULT_OUTPUT_DIR = Path("build/sdetkit/evidence-graph")

SourceName = Literal[
    "sentinel",
    "doctor",
    "doctor_cortex",
    "mission_control",
    "investigate",
    "ci_failure_triage",
    "security",
    "release",
    "dependency",
    "maintenance",
    "pr_quality",
]

JsonScalar = str | int | float | bool | None
JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject = dict[str, JsonValue]


class EvidenceNode(TypedDict):
    source: str
    finding_id: str
    title: str
    summary: str
    risk_surface: str
    severity: str
    review_first: bool
    safe_to_auto_fix: bool
    owner_files: list[str]
    source_artifacts: list[str]
    recommended_commands: list[str]
    proof_commands: list[str]
    recurrence_state: str
    operator_action: str
    automation_allowed_now: bool


class SourceSummary(TypedDict):
    source: str
    path: str
    found: bool
    status: str
    findings_seen: int
    findings_emitted: int


class EvidenceGraph(TypedDict):
    schema_version: str
    nodes: list[EvidenceNode]
    source_summary: list[SourceSummary]


class EvidenceGraphManifest(TypedDict):
    schema_version: str
    graph_path: str
    markdown_path: str
    sources: list[SourceSummary]
    node_count: int
    automation_allowed_now: bool


_REVIEW_FIRST_SURFACES = {
    "workflow",
    "dependency",
    "security",
    "release",
    "cli",
    "package",
    "diagnostic_engine",
    "pr_quality",
    "quality",
    "unknown",
}

_VALID_SURFACES = {
    "workflow",
    "dependency",
    "security",
    "release",
    "tests",
    "cli",
    "docs",
    "package",
    "diagnostic_engine",
    "maintenance",
    "pr_quality",
    "quality",
    "unknown",
}

_VALID_SEVERITIES = {"healthy", "warning", "critical"}
_VALID_RECURRENCE = {"first_seen", "recurring", "escalated", "unknown"}


def load_json_object(path: Path) -> JsonObject:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return cast(JsonObject, data)


def build_evidence_graph(
    *,
    sentinel_control_room: Path | None = None,
    mission_control: Path | None = None,
) -> EvidenceGraph:
    nodes: list[EvidenceNode] = []
    source_summary: list[SourceSummary] = []

    sentinel_nodes, sentinel_summary = _normalize_source(
        source="sentinel",
        path=sentinel_control_room,
        finding_keys=("active_threats", "findings", "threats"),
    )
    nodes.extend(sentinel_nodes)
    source_summary.append(sentinel_summary)

    mission_nodes, mission_summary = _normalize_source(
        source="mission_control",
        path=mission_control,
        finding_keys=("findings", "active_findings", "risks", "blocks"),
    )
    nodes.extend(mission_nodes)
    source_summary.append(mission_summary)

    nodes.sort(key=lambda node: (node["source"], node["finding_id"]))

    return {
        "schema_version": SCHEMA_VERSION,
        "nodes": nodes,
        "source_summary": source_summary,
    }


def write_evidence_graph(
    graph: EvidenceGraph,
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> EvidenceGraphManifest:
    output_dir.mkdir(parents=True, exist_ok=True)

    graph_path = output_dir / "evidence-graph.json"
    markdown_path = output_dir / "evidence-graph.md"
    manifest_path = output_dir / "evidence-graph-manifest.json"

    graph_path.write_text(
        json.dumps(graph, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown(graph), encoding="utf-8")

    manifest: EvidenceGraphManifest = {
        "schema_version": SCHEMA_VERSION,
        "graph_path": graph_path.as_posix(),
        "markdown_path": markdown_path.as_posix(),
        "sources": graph["source_summary"],
        "node_count": len(graph["nodes"]),
        "automation_allowed_now": False,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return manifest


def render_markdown(graph: EvidenceGraph) -> str:
    lines = [
        "# SDETKit Evidence Graph",
        "",
        f"Schema: `{graph['schema_version']}`",
        "",
        "Automation allowed now: `false`",
        "",
        "## Source summary",
        "",
    ]

    for source in graph["source_summary"]:
        lines.append(
            "- "
            f"`{source['source']}`: "
            f"found={str(source['found']).lower()}, "
            f"status=`{source['status']}`, "
            f"findings_seen={source['findings_seen']}, "
            f"findings_emitted={source['findings_emitted']}"
        )

    lines.extend(["", "## Active findings", ""])

    if not graph["nodes"]:
        lines.append("No active review findings were normalized.")
        lines.append("")
        return "\n".join(lines)

    for node in graph["nodes"]:
        lines.extend(
            [
                f"### {node['title']}",
                "",
                f"- Source: `{node['source']}`",
                f"- Finding ID: `{node['finding_id']}`",
                f"- Risk surface: `{node['risk_surface']}`",
                f"- Severity: `{node['severity']}`",
                f"- Review first: `{str(node['review_first']).lower()}`",
                f"- Safe to auto-fix: `{str(node['safe_to_auto_fix']).lower()}`",
                "- Automation allowed now: `false`",
                f"- Recurrence: `{node['recurrence_state']}`",
                f"- Operator action: `{node['operator_action']}`",
                "",
                node["summary"],
                "",
            ]
        )

        if node["owner_files"]:
            lines.append("Owner files:")
            lines.extend(f"- `{path}`" for path in node["owner_files"])
            lines.append("")

        if node["source_artifacts"]:
            lines.append("Source artifacts:")
            lines.extend(f"- `{path}`" for path in node["source_artifacts"])
            lines.append("")

        if node["recommended_commands"]:
            lines.append("Recommended commands:")
            lines.extend(f"- `{command}`" for command in node["recommended_commands"])
            lines.append("")

        if node["proof_commands"]:
            lines.append("Proof commands:")
            lines.extend(f"- `{command}`" for command in node["proof_commands"])
            lines.append("")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m sdetkit.evidence_graph",
        description=(
            "Build a read-only SDETKit evidence graph from existing diagnostic artifacts."
        ),
    )
    parser.add_argument(
        "--sentinel-control-room",
        type=Path,
        default=None,
        help="Path to a Sentinel control-room JSON artifact.",
    )
    parser.add_argument(
        "--mission-control",
        type=Path,
        default=None,
        help="Path to a Mission Control JSON artifact.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for evidence-graph artifacts.",
    )

    args = parser.parse_args(argv)
    graph = build_evidence_graph(
        sentinel_control_room=args.sentinel_control_room,
        mission_control=args.mission_control,
    )
    manifest = write_evidence_graph(graph, output_dir=args.out_dir)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


def _normalize_source(
    *,
    source: SourceName,
    path: Path | None,
    finding_keys: tuple[str, ...],
) -> tuple[list[EvidenceNode], SourceSummary]:
    if path is None or not path.exists():
        return [], {
            "source": source,
            "path": "" if path is None else path.as_posix(),
            "found": False,
            "status": "missing",
            "findings_seen": 0,
            "findings_emitted": 0,
        }

    payload = load_json_object(path)
    findings = _extract_findings(payload, finding_keys)
    nodes = [
        node
        for finding in findings
        if (node := _normalize_finding(source, finding, path)) is not None
    ]

    return nodes, {
        "source": source,
        "path": path.as_posix(),
        "found": True,
        "status": _source_status(payload),
        "findings_seen": len(findings),
        "findings_emitted": len(nodes),
    }


def _extract_findings(
    payload: JsonObject,
    finding_keys: tuple[str, ...],
) -> list[JsonObject]:
    for key in finding_keys:
        value = payload.get(key)
        if isinstance(value, list):
            return [cast(JsonObject, item) for item in value if isinstance(item, dict)]

    nested = payload.get("evidence")
    if isinstance(nested, dict):
        return _extract_findings(cast(JsonObject, nested), finding_keys)

    return []


def _normalize_finding(
    source: SourceName,
    finding: JsonObject,
    source_path: Path,
) -> EvidenceNode | None:
    severity = _severity(finding)
    status = _text(finding, "status", default="").lower()

    if severity == "healthy" or status in {"clear", "clean", "healthy", "ok", "pass"}:
        return None

    title = _text(finding, "title", "name", "headline", default="Untitled finding")
    summary = _text(
        finding,
        "summary",
        "details",
        "description",
        "message",
        default=title,
    )
    owner_files = _string_list(finding.get("owner_files"))
    source_artifacts = _string_list(finding.get("source_artifacts"))
    recommended_commands = _string_list(
        finding.get("recommended_commands")
        or finding.get("next_commands")
        or finding.get("commands")
    )
    proof_commands = _string_list(
        finding.get("proof_commands") or finding.get("verification_commands")
    )
    risk_surface = _risk_surface(
        source,
        finding,
        owner_files,
        source_artifacts,
        recommended_commands,
        proof_commands,
        title,
        summary,
    )
    review_first = _bool(
        finding.get("review_first"),
        default=risk_surface in _REVIEW_FIRST_SURFACES or severity == "critical",
    )
    safe_to_auto_fix = _bool(finding.get("safe_to_auto_fix"), default=False)
    if review_first:
        safe_to_auto_fix = False

    if not source_artifacts:
        source_artifacts = [source_path.as_posix()]

    return {
        "source": source,
        "finding_id": _finding_id(source, finding, title, summary),
        "title": title,
        "summary": summary,
        "risk_surface": risk_surface,
        "severity": severity,
        "review_first": review_first,
        "safe_to_auto_fix": safe_to_auto_fix,
        "owner_files": owner_files,
        "source_artifacts": source_artifacts,
        "recommended_commands": recommended_commands,
        "proof_commands": proof_commands,
        "recurrence_state": _recurrence_state(finding),
        "operator_action": _operator_action(review_first, severity),
        "automation_allowed_now": False,
    }


def _text(payload: JsonObject, *keys: str, default: str) -> str:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, (int, float, bool)):
            return str(value)
    return default


def _bool(value: JsonValue | None, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return default


def _string_list(value: JsonValue | None) -> list[str]:
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            if isinstance(item, str) and item:
                result.append(item)
            elif isinstance(item, (int, float, bool)):
                result.append(str(item))
        return result
    return []


def _severity(finding: JsonObject) -> str:
    raw = _text(finding, "severity", "level", default="warning").lower()
    if raw in _VALID_SEVERITIES:
        return raw
    if raw in {"fail", "failed", "error", "blocker", "high"}:
        return "critical"
    if raw in {"ok", "pass", "passed", "clean", "clear"}:
        return "healthy"
    return "warning"


def _risk_surface(
    source: SourceName,
    finding: JsonObject,
    owner_files: list[str],
    source_artifacts: list[str],
    recommended_commands: list[str],
    proof_commands: list[str],
    title: str,
    summary: str,
) -> str:
    explicit = _text(finding, "risk_surface", "surface", "category", default="").lower()
    if explicit in _VALID_SURFACES:
        return explicit

    haystack = " ".join(
        [
            source,
            title,
            summary,
            *owner_files,
            *source_artifacts,
            *recommended_commands,
            *proof_commands,
        ]
    ).lower()

    if "pr-quality-comment.yml" in haystack or "pr quality" in haystack or "pr-quality" in haystack:
        return "pr_quality"
    if (
        "quality.sh" in haystack
        or "coverage" in haystack
        or "quality verdict" in haystack
        or "cov passed" in haystack
        or "cov failed" in haystack
        or "pre_commit" in haystack
        or "pre-commit" in haystack
        or "ruff" in haystack
        or "mypy" in haystack
    ):
        return "quality"
    if ".github/workflows" in haystack or "workflow" in haystack:
        return "workflow"
    if "requirements" in haystack or "constraints" in haystack:
        return "dependency"
    if "security" in haystack or "secret" in haystack:
        return "security"
    if "release" in haystack or "publish" in haystack:
        return "release"
    if "/tests/" in haystack or haystack.startswith("tests/") or "pytest" in haystack:
        return "tests"
    if "cli" in haystack or "__main__" in haystack:
        return "cli"
    if "docs/" in haystack or "mkdocs" in haystack:
        return "docs"
    if "pyproject.toml" in haystack or "package" in haystack:
        return "package"
    if (
        "doctor" in haystack
        or "diagnos" in haystack
        or "sentinel" in haystack
        or "control-room" in haystack
        or "evidence graph" in haystack
        or "evidence-graph" in haystack
        or "evidence_graph" in haystack
    ):
        return "diagnostic_engine"
    if "maintenance" in haystack:
        return "maintenance"

    return "unknown"


def _recurrence_state(finding: JsonObject) -> str:
    raw = _text(
        finding,
        "recurrence_state",
        "trend_state",
        "state",
        default="unknown",
    ).lower()
    if raw in _VALID_RECURRENCE:
        return raw
    if raw in {"repeat", "repeated"}:
        return "recurring"
    if raw in {"escalate", "quality_regression_loop"}:
        return "escalated"
    return "unknown"


def _operator_action(review_first: bool, severity: str) -> str:
    if review_first:
        return "review"
    if severity == "critical":
        return "investigate"
    return "rerun_proof"


def _finding_id(
    source: SourceName,
    finding: JsonObject,
    title: str,
    summary: str,
) -> str:
    explicit = _text(
        finding,
        "finding_id",
        "id",
        "fingerprint",
        default="",
    )
    if explicit:
        return explicit

    digest = hashlib.sha256(f"{source}:{title}:{summary}".encode()).hexdigest()
    return f"{source}-{digest[:12]}"


def _source_status(payload: JsonObject) -> str:
    status = _text(payload, "status", "state", "verdict", default="unknown").lower()
    if status in {"ok", "pass", "passed", "clean"}:
        return "healthy"
    return status


if __name__ == "__main__":
    raise SystemExit(main())
