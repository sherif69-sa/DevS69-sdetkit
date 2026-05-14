from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.pr-quality.evidence-narrative.v1"
JsonObject = dict[str, Any]

_SURFACE_PRIORITY = {
    "security": 100,
    "dependency": 90,
    "release": 85,
    "package": 80,
    "workflow": 75,
    "pr_quality": 74,
    "diagnostic_engine": 70,
    "cli": 65,
    "quality": 60,
    "tests": 55,
    "docs": 45,
    "maintenance": 40,
    "unknown": 0,
}

_SEVERITY_PRIORITY = {
    "critical": 50,
    "high": 40,
    "warning": 30,
    "medium": 25,
    "low": 10,
    "info": 0,
    "unknown": 0,
}

_SURFACE_REASON = {
    "security": "Security evidence affects trust boundaries, credentials, permissions, or supply-chain exposure.",
    "dependency": "Dependency evidence affects whether the repo can install, resolve, and test reproducibly.",
    "release": "Release evidence affects whether the package can be safely cut or published.",
    "package": "Package evidence affects installability, metadata, build outputs, or distribution safety.",
    "workflow": "Workflow evidence affects whether CI is proving the right thing before merge.",
    "pr_quality": "PR Quality evidence affects the comment maintainers use to decide what to trust during review.",
    "diagnostic_engine": "Diagnostic-intelligence evidence affects how SDETKit reads failures and routes operators.",
    "cli": "CLI evidence affects public commands and operator entry points.",
    "quality": "Quality-tooling evidence affects lint, type, format, coverage, or local proof gates.",
    "tests": "Test evidence affects behavior proof and regression detection.",
    "docs": "Documentation evidence affects operator navigation and public guidance.",
    "maintenance": "Maintenance evidence affects recurring automation and repo hygiene loops.",
    "unknown": "The evidence did not expose enough owner-file or artifact context to classify confidently.",
}


def _read_text(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _read_json(path: Path | None) -> JsonObject:
    if path is None or not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _as_dict(value: Any) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string_list(value: Any) -> list[str]:
    return [str(item) for item in _as_list(value) if str(item).strip()]


def _coverage_percent(log_text: str) -> str:
    matches = re.findall(r"Total coverage:\s*([0-9]+(?:\.[0-9]+)?)%", log_text, re.IGNORECASE)
    if matches:
        return matches[-1]
    matches = re.findall(r"coverage:\s*([0-9]+(?:\.[0-9]+)?)%", log_text, re.IGNORECASE)
    return matches[-1] if matches else "unknown"


def _quality_passed(outcome: str, log_text: str) -> bool:
    normalized = outcome.lower().strip()
    if normalized == "success":
        return True
    if normalized in {"failure", "cancelled", "timed_out"}:
        return False
    lowered = log_text.lower()
    return "quality.sh cov passed" in lowered or "coverage gate are green" in lowered


def _surface_for_path(path: str) -> str:
    lowered = path.lower()
    if lowered == ".github/workflows/pr-quality-comment.yml" or "pr-quality" in lowered:
        return "pr_quality"
    if lowered.startswith(".github/workflows/") or "workflow" in lowered:
        return "workflow"
    if "security" in lowered or "secret" in lowered:
        return "security"
    if "requirements" in lowered or "constraints" in lowered:
        return "dependency"
    if "release" in lowered or "version" in lowered:
        return "release"
    if "pyproject.toml" in lowered or "package" in lowered:
        return "package"
    if lowered.startswith("tests/"):
        return "tests"
    if lowered.startswith("docs/") or "mkdocs" in lowered:
        return "docs"
    if "cli" in lowered:
        return "cli"
    if any(
        token in lowered for token in ("diagnos", "sentinel", "evidence_graph", "evidence-graph")
    ):
        return "diagnostic_engine"
    if any(token in lowered for token in ("quality", "ruff", "mypy", "pre_commit", "pre-commit")):
        return "quality"
    return "unknown"


def _load_changed_files(path: Path | None) -> list[str]:
    return [line.strip() for line in _read_text(path).splitlines() if line.strip()]


def _changed_file_surfaces(files: list[str]) -> list[str]:
    surfaces = {_surface_for_path(path) for path in files}
    surfaces.discard("unknown")
    return sorted(surfaces, key=lambda item: (-_SURFACE_PRIORITY.get(item, 0), item))


def _graph_nodes(payload: JsonObject) -> list[JsonObject]:
    return [_as_dict(item) for item in _as_list(payload.get("nodes")) if isinstance(item, dict)]


def _node_score(node: JsonObject) -> tuple[int, int, int]:
    surface = str(node.get("risk_surface", "unknown"))
    severity = str(node.get("severity", "unknown"))
    review_first = 1 if bool(node.get("review_first", False)) else 0
    return (
        review_first,
        _SEVERITY_PRIORITY.get(severity, 0),
        _SURFACE_PRIORITY.get(surface, 0),
    )


def _primary_node(nodes: list[JsonObject]) -> JsonObject:
    return max(nodes, key=_node_score) if nodes else {}


def _fallback_failure_bundle(path: Path | None) -> JsonObject:
    if path is None:
        return {}
    payload = _read_json(path)
    if payload:
        return payload
    for name in ("failure-bundle.json", "adaptive-diagnosis.json"):
        payload = _read_json(path.parent / name)
        if payload:
            return payload
    return {}


def _primary_failure(payload: JsonObject) -> JsonObject:
    if not payload:
        return {}
    diagnoses = _as_list(payload.get("diagnoses"))
    if diagnoses and isinstance(diagnoses[0], dict):
        return _as_dict(diagnoses[0])
    diagnosis = _as_dict(payload.get("diagnosis"))
    nested = _as_list(diagnosis.get("diagnoses"))
    if nested and isinstance(nested[0], dict):
        return _as_dict(nested[0])
    code = str(payload.get("primary_diagnosis_code", "")).strip()
    if code:
        return {
            "code": code,
            "title": str(payload.get("primary_diagnosis_title", code.replace("_", " ").title())),
            "diagnosis": str(payload.get("summary", "")),
            "recommended_fix": _string_list(payload.get("recommended_fix")),
            "proof_commands": _string_list(payload.get("proof_commands")),
        }
    return {}


def _surface_for_failure(failure: JsonObject) -> str:
    text = " ".join(
        [
            str(failure.get("code", "")),
            str(failure.get("title", "")),
            str(failure.get("diagnosis", "")),
            " ".join(_string_list(failure.get("evidence"))),
        ]
    ).lower()
    if any(
        token in text for token in ("dependency", "resolver", "pip", "package install", "lockfile")
    ):
        return "dependency"
    if any(token in text for token in ("security", "secret", "vulnerability")):
        return "security"
    if any(token in text for token in ("release", "publish", "twine", "build")):
        return "release"
    if any(token in text for token in ("workflow", "github actions", "yaml")):
        return "workflow"
    if any(token in text for token in ("coverage", "quality", "ruff", "mypy", "pre-commit")):
        return "quality"
    if any(token in text for token in ("pytest", "assertion", "test")):
        return "tests"
    return "unknown"


def _commands_from_failure(failure: JsonObject) -> list[str]:
    commands = _string_list(failure.get("proof_commands"))
    if commands:
        return commands
    return _string_list(failure.get("recommended_fix"))[:3]


def _commands_from_nodes(nodes: list[JsonObject]) -> list[str]:
    commands: list[str] = []
    for node in sorted(nodes, key=_node_score, reverse=True):
        for key in ("proof_commands", "recommended_commands"):
            for command in _string_list(node.get(key)):
                if command not in commands:
                    commands.append(command)
                if len(commands) >= 5:
                    return commands
    return commands


def _artifact_paths(
    *,
    quality_log: Path | None,
    sentinel_control_room: Path | None,
    evidence_graph: Path | None,
    failure_bundle: Path | None,
) -> list[str]:
    candidates = [
        quality_log,
        sentinel_control_room,
        evidence_graph,
        evidence_graph.parent / "evidence-graph.md" if evidence_graph else None,
        failure_bundle,
    ]
    paths: list[str] = []
    for path in candidates:
        if path is not None and path.exists():
            rendered = path.as_posix()
            if rendered not in paths:
                paths.append(rendered)
    return paths


def build_narrative(
    *,
    quality_log: Path | None,
    quality_outcome: str,
    sentinel_control_room: Path | None,
    evidence_graph: Path | None,
    failure_bundle: Path | None,
    changed_files: Path | None,
) -> JsonObject:
    log_text = _read_text(quality_log)
    coverage = _coverage_percent(log_text)
    quality_ok = _quality_passed(quality_outcome, log_text)
    nodes = _graph_nodes(_read_json(evidence_graph))
    primary_node = _primary_node(nodes)
    changed = _load_changed_files(changed_files)
    changed_surfaces = _changed_file_surfaces(changed)
    failure_payload = _fallback_failure_bundle(failure_bundle)
    failure = _primary_failure(failure_payload) if not quality_ok else {}

    surfaces = {
        str(node.get("risk_surface", "unknown") or "unknown")
        for node in nodes
        if isinstance(node, dict)
    }
    surfaces.discard("unknown")
    surfaces.update(changed_surfaces)

    if failure:
        primary_kind = "actual_failure"
        primary_surface = _surface_for_failure(failure)
        primary_title = str(failure.get("title") or failure.get("code") or "Quality failure")
    elif primary_node:
        primary_kind = "review_signal"
        primary_surface = str(primary_node.get("risk_surface", "unknown") or "unknown")
        primary_title = str(primary_node.get("title", "Evidence graph finding"))
    else:
        primary_kind = "green"
        primary_surface = changed_surfaces[0] if changed_surfaces else "quality"
        primary_title = "Quality gate passed"

    commands = _commands_from_failure(failure) if failure else _commands_from_nodes(nodes)
    if not commands:
        commands = ["python -m pre_commit run -a", "bash quality.sh cov"]

    what_happened = _what_happened(
        quality_ok=quality_ok,
        coverage=coverage,
        nodes=nodes,
        changed_files=changed,
        changed_surfaces=changed_surfaces,
        failure=failure,
    )
    why_it_matters = _why_it_matters(
        quality_ok=quality_ok,
        primary_surface=primary_surface,
        failure=failure,
        nodes=nodes,
    )
    operator_action = _operator_action(
        quality_ok=quality_ok,
        primary_surface=primary_surface,
        failure=failure,
        nodes=nodes,
    )
    artifact_paths = _artifact_paths(
        quality_log=quality_log,
        sentinel_control_room=sentinel_control_room,
        evidence_graph=evidence_graph,
        failure_bundle=failure_bundle,
    )

    payload: JsonObject = {
        "schema_version": SCHEMA_VERSION,
        "quality": {"outcome": quality_outcome, "ok": quality_ok, "coverage_percent": coverage},
        "changed_files": changed,
        "changed_surfaces": changed_surfaces,
        "graph": {
            "node_count": len(nodes),
            "surfaces": sorted(surfaces, key=lambda item: (-_SURFACE_PRIORITY.get(item, 0), item)),
            "review_first_count": sum(1 for node in nodes if bool(node.get("review_first", False))),
            "critical_count": sum(
                1 for node in nodes if str(node.get("severity", "")) == "critical"
            ),
        },
        "primary_signal": {
            "kind": primary_kind,
            "surface": primary_surface,
            "title": primary_title,
        },
        "what_happened": what_happened,
        "why_it_matters": why_it_matters,
        "operator_action": operator_action,
        "next_proof": commands,
        "evidence": artifact_paths,
    }
    payload["markdown"] = render_markdown(
        quality_ok=quality_ok,
        coverage=coverage,
        primary_kind=primary_kind,
        primary_surface=primary_surface,
        primary_title=primary_title,
        what_happened=what_happened,
        why_it_matters=why_it_matters,
        operator_action=operator_action,
        next_proof=commands,
        evidence=artifact_paths,
    )
    return payload


def _what_happened(
    *,
    quality_ok: bool,
    coverage: str,
    nodes: list[JsonObject],
    changed_files: list[str],
    changed_surfaces: list[str],
    failure: JsonObject,
) -> list[str]:
    lines: list[str] = []
    if quality_ok:
        lines.append(f"quality.sh cov passed with coverage {coverage}%.")
    else:
        lines.append(f"quality.sh cov did not pass; last reported coverage is {coverage}%.")
    if failure:
        lines.append(
            "The adaptive failure bundle selected "
            f"{failure.get('code', 'an actual failure')} as the primary blocker."
        )
    if changed_files:
        preview = ", ".join(changed_files[:5])
        suffix = "" if len(changed_files) <= 5 else f", plus {len(changed_files) - 5} more"
        lines.append(f"The PR diff includes {preview}{suffix}.")
    if changed_surfaces:
        lines.append(f"Diff-owned risk surfaces: {', '.join(changed_surfaces)}.")
    if nodes:
        titles = [
            f"{node.get('title', 'finding')} [{node.get('risk_surface', 'unknown')}]"
            for node in nodes[:3]
        ]
        lines.append(
            f"Evidence graph normalized {len(nodes)} active finding(s): " + "; ".join(titles) + "."
        )
    else:
        lines.append("Evidence graph emitted no active findings.")
    return lines


def _why_it_matters(
    *,
    quality_ok: bool,
    primary_surface: str,
    failure: JsonObject,
    nodes: list[JsonObject],
) -> list[str]:
    if failure:
        return [
            "This is the actual failed signal; advisory graph findings are secondary until the blocker is fixed.",
            _SURFACE_REASON.get(primary_surface, _SURFACE_REASON["unknown"]),
        ]
    if quality_ok and nodes:
        return [
            "Quality is green, so the review focus is not coverage.",
            _SURFACE_REASON.get(primary_surface, _SURFACE_REASON["unknown"]),
            "The comment must guide maintainers toward the changed risk surface, not toward generic fixes.",
        ]
    return [
        "No blocker was detected in the required quality path.",
        "Keep the PR review proportional to the files that changed.",
    ]


def _operator_action(
    *,
    quality_ok: bool,
    primary_surface: str,
    failure: JsonObject,
    nodes: list[JsonObject],
) -> list[str]:
    if failure:
        return [
            "Fix the primary failed command or contract before treating advisory findings as blockers.",
            "Use the proof commands below to verify the smallest safe fix.",
        ]
    if quality_ok and nodes:
        return [
            f"Review the {primary_surface} evidence against the PR diff.",
            "Confirm the graph findings match the changed files and artifacts.",
            "Keep automation disabled unless a separate safe-fix policy explicitly allows it.",
        ]
    return ["Proceed with normal review.", "No adaptive remediation is recommended."]


def render_markdown(
    *,
    quality_ok: bool,
    coverage: str,
    primary_kind: str,
    primary_surface: str,
    primary_title: str,
    what_happened: list[str],
    why_it_matters: list[str],
    operator_action: list[str],
    next_proof: list[str],
    evidence: list[str],
) -> str:
    status = "✅ quality.sh cov passed" if quality_ok else "❌ quality.sh cov failed"
    lines = [
        "## SDET Quality Gate",
        "",
        status,
        "",
        f"coverage: {coverage}%",
        "",
        "## Adaptive release confidence",
        "",
        f"Primary signal: **{primary_title}**",
        f"Signal type: `{primary_kind}`",
        f"Risk surface: `{primary_surface}`",
        "",
        "### What happened",
        "",
        *_bullets(what_happened),
        "",
        "### Why it matters",
        "",
        *_bullets(why_it_matters),
        "",
        "### Operator action",
        "",
        *_bullets(operator_action),
        "",
        "### Next proof",
        "",
        *_code_bullets(next_proof),
        "",
        "### Evidence",
        "",
        *_code_bullets(evidence or ["No evidence artifacts were available."]),
        "",
    ]
    return "\n".join(lines).rstrip() + "\n"


def _bullets(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items]


def _code_bullets(items: list[str]) -> list[str]:
    return [f"- `{item}`" for item in items]


def write_narrative(payload: JsonObject, *, out: Path, json_out: Path | None = None) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(str(payload["markdown"]), encoding="utf-8")
    if json_out is not None:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.pr_quality_evidence_narrative")
    parser.add_argument("--quality-log", type=Path, default=Path("quality.log"))
    parser.add_argument("--quality-outcome", default="unknown")
    parser.add_argument("--sentinel-control-room", type=Path, default=None)
    parser.add_argument("--evidence-graph", type=Path, default=None)
    parser.add_argument("--failure-bundle", type=Path, default=None)
    parser.add_argument("--changed-files", type=Path, default=None)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--json-out", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = build_narrative(
        quality_log=args.quality_log,
        quality_outcome=str(args.quality_outcome),
        sentinel_control_room=args.sentinel_control_room,
        evidence_graph=args.evidence_graph,
        failure_bundle=args.failure_bundle,
        changed_files=args.changed_files,
    )
    write_narrative(payload, out=args.out, json_out=args.json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
