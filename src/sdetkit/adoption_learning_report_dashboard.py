from __future__ import annotations

import argparse
import html
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from sdetkit import adoption_learning_report
from sdetkit.atomicio import atomic_write_text

SCHEMA_VERSION = "sdetkit.adoption_learning_report_dashboard.v1"
DEFAULT_OUT = Path("build") / "sdetkit" / "adoption-learning-report-dashboard.html"

JsonObject = dict[str, Any]


def _as_dict(value: Any) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


def _strings(value: Any) -> list[str]:
    return [_string(item) for item in _as_list(value) if _string(item)]


def _integer(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _candidate_row(value: Any) -> JsonObject:
    candidate = _as_dict(value)
    return {
        "rank": _integer(candidate.get("rank")),
        "classification": _string(candidate.get("classification")) or "unknown",
        "priority": _string(candidate.get("priority")) or "unknown",
        "ranking_score": _integer(candidate.get("ranking_score")),
        "next_pr_title": _string(candidate.get("next_pr_title")),
        "observed_in_repos": _strings(candidate.get("observed_in_repos")),
        "frequency_across_matrix": _integer(candidate.get("frequency_across_matrix")),
        "owner_files": _strings(candidate.get("owner_files")),
        "reason_from_real_repo": _string(candidate.get("reason_from_real_repo")),
        "proof_needed": _strings(candidate.get("proof_needed")),
        "review_first": candidate.get("review_first") is True,
        "safe_to_patch": candidate.get("safe_to_patch") is True,
        "recommended_next_action": _string(candidate.get("recommended_next_action")),
    }


def _repo_memory_summary(value: Any) -> JsonObject:
    memory = _as_dict(value)
    authority = _as_dict(memory.get("authority_boundary"))
    return {
        "connected": memory.get("connected") is True,
        "path": _string(memory.get("path")),
        "schema_version": _string(memory.get("schema_version")),
        "profile_status": _string(memory.get("profile_status")) or "not_provided",
        "memory_mode": _string(memory.get("memory_mode")),
        "review_first": memory.get("review_first") is True,
        "authoritative_for_adoption_report": (
            memory.get("authoritative_for_adoption_report") is True
        ),
        "authority_boundary": {
            "automation_allowed": authority.get("automation_allowed") is True,
            "patch_application_allowed": authority.get("patch_application_allowed") is True,
            "merge_authorized": authority.get("merge_authorized") is True,
            "semantic_equivalence_proven": (authority.get("semantic_equivalence_proven") is True),
        },
    }


def _decision_boundary() -> JsonObject:
    return {
        "current_pr_decision_input": False,
        "automation_allowed": False,
        "proof_commands_executed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }


def _load_report(path: Path) -> JsonObject:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("expected adoption learning report JSON object")
    schema_version = _string(payload.get("schema_version"))
    if schema_version != adoption_learning_report.SCHEMA_VERSION:
        raise ValueError(
            f"unsupported adoption learning report schema: {schema_version or 'missing'}"
        )
    return payload


def build_dashboard(report_path: Path, *, out_path: Path) -> JsonObject:
    report = _load_report(report_path)
    candidates = [
        _candidate_row(candidate)
        for candidate in _as_list(report.get("prioritized_upgrade_candidates"))
        if isinstance(candidate, dict)
    ]
    top_candidate_raw = report.get("top_candidate")
    top_candidate = (
        _candidate_row(top_candidate_raw) if isinstance(top_candidate_raw, dict) else None
    )
    source_count = _integer(report.get("candidate_count"))
    if source_count != len(candidates):
        raise ValueError("candidate_count does not match prioritized_upgrade_candidates")
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "ready" if candidates else "empty",
        "report_path": report_path.as_posix(),
        "report_exists": report_path.is_file(),
        "source_report_schema_version": _string(report.get("schema_version")),
        "source_matrix": _string(report.get("source_matrix")),
        "source_matrix_schema_version": _string(report.get("source_matrix_schema_version")),
        "source_matrix_status": _string(report.get("source_matrix_status")),
        "source_repo_count": _integer(report.get("source_repo_count")),
        "candidate_count": len(candidates),
        "top_candidate": top_candidate,
        "prioritized_upgrade_candidates": candidates,
        "repo_memory_profile": _repo_memory_summary(report.get("repo_memory_profile")),
        "operator_summary": _as_dict(report.get("operator_summary")),
        "local_only": True,
        "read_only": True,
        "decision_boundary": _decision_boundary(),
    }


def _escape(value: Any) -> str:
    return html.escape(_string(value))


def _string_list(values: Any, *, empty: str = "none") -> str:
    items = _strings(values)
    if not items:
        return f"<span class='muted'>{html.escape(empty)}</span>"
    return "<ul>" + "".join(f"<li>{html.escape(item)}</li>" for item in items) + "</ul>"


def _candidate_card(candidate: Mapping[str, Any]) -> str:
    safe_to_patch = candidate.get("safe_to_patch") is True
    review_first = candidate.get("review_first") is True
    state_class = "unsafe" if safe_to_patch else "review"
    title = _escape(candidate.get("next_pr_title")) or "Untitled candidate"
    return (
        f"<article class='card {state_class}'>"
        f"<h2>#{_integer(candidate.get('rank'))} {title}</h2>"
        "<dl>"
        f"<dt>Classification</dt><dd>{_escape(candidate.get('classification'))}</dd>"
        f"<dt>Priority</dt><dd>{_escape(candidate.get('priority'))}</dd>"
        f"<dt>Ranking score</dt><dd>{_integer(candidate.get('ranking_score'))}</dd>"
        f"<dt>Frequency</dt><dd>{_integer(candidate.get('frequency_across_matrix'))}</dd>"
        f"<dt>Review first</dt><dd>{str(review_first).lower()}</dd>"
        f"<dt>Safe to patch</dt><dd>{str(safe_to_patch).lower()}</dd>"
        "</dl>"
        f"<p><strong>Reason:</strong> {_escape(candidate.get('reason_from_real_repo')) or '—'}</p>"
        "<h3>Observed in repositories</h3>"
        f"{_string_list(candidate.get('observed_in_repos'))}"
        "<h3>Owner files</h3>"
        f"{_string_list(candidate.get('owner_files'))}"
        "<h3>Proof needed</h3>"
        f"{_string_list(candidate.get('proof_needed'))}"
        f"<p><strong>Recommended next action:</strong> "
        f"{_escape(candidate.get('recommended_next_action')) or '—'}</p>"
        "</article>"
    )


def render_html(payload: Mapping[str, Any]) -> str:
    candidates = [
        _as_dict(candidate)
        for candidate in _as_list(payload.get("prioritized_upgrade_candidates"))
        if isinstance(candidate, dict)
    ]
    cards = "".join(_candidate_card(candidate) for candidate in candidates)
    if not cards:
        cards = (
            "<article class='card empty'>"
            "<h2>No upgrade candidates</h2>"
            "<p>The source report is valid and contains no prioritized candidates.</p>"
            "</article>"
        )

    top = _as_dict(payload.get("top_candidate"))
    top_title = _escape(top.get("next_pr_title")) if top else "none"
    memory = _as_dict(payload.get("repo_memory_profile"))
    boundary = _as_dict(payload.get("decision_boundary"))

    boundary_items = "".join(
        f"<li><strong>{html.escape(key)}</strong>: {str(value).lower()}</li>"
        for key, value in sorted(boundary.items())
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Adoption learning report dashboard</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #172033; background: #f6f7fb; }}
    header {{ margin-bottom: 1.5rem; }}
    .summary {{ display: flex; flex-wrap: wrap; gap: .6rem; margin: 1rem 0; }}
    .pill {{ background: white; border: 1px solid #d7dce8; border-radius: 999px; padding: .45rem .8rem; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1rem; }}
    .card {{ background: white; border: 1px solid #d7dce8; border-radius: 14px; padding: 1rem; box-shadow: 0 1px 2px rgb(20 30 50 / 8%); }}
    .review {{ border-top: 5px solid #175cd3; }}
    .unsafe {{ border-top: 5px solid #b42318; }}
    .empty {{ border-top: 5px solid #667085; }}
    .muted {{ color: #667085; }}
    dl {{ display: grid; grid-template-columns: max-content 1fr; gap: .35rem .75rem; }}
    dt {{ font-weight: 700; }}
    dd {{ margin: 0; overflow-wrap: anywhere; }}
    code {{ overflow-wrap: anywhere; }}
  </style>
</head>
<body>
  <header>
    <h1>Adoption learning report dashboard</h1>
    <p>Static, local-only, read-only view of the accepted Python adoption learning report artifact.</p>
    <div class="summary">
      <span class="pill">status: {_escape(payload.get("status"))}</span>
      <span class="pill">matrix status: {_escape(payload.get("source_matrix_status"))}</span>
      <span class="pill">repositories: {_integer(payload.get("source_repo_count"))}</span>
      <span class="pill">candidates: {_integer(payload.get("candidate_count"))}</span>
      <span class="pill">local only: {str(payload.get("local_only")).lower()}</span>
      <span class="pill">read only: {str(payload.get("read_only")).lower()}</span>
    </div>
    <p><strong>Report:</strong> <code>{_escape(payload.get("report_path"))}</code></p>
    <p><strong>Top candidate:</strong> {top_title}</p>
    <p><strong>RepoMemory connected:</strong> {str(memory.get("connected") is True).lower()}</p>
  </header>
  <main class="grid">
    {cards}
    <article class="card">
      <h2>Authority boundary</h2>
      <ul>{boundary_items}</ul>
      <p>This dashboard is not proof execution, patch approval, a current-PR decision, or merge authorization.</p>
    </article>
  </main>
</body>
</html>
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m sdetkit.adoption_learning_report_dashboard",
        description=(
            "Render a deterministic local-only dashboard from an existing "
            "adoption learning report JSON artifact."
        ),
    )
    parser.add_argument("--report-path", type=Path, required=True)
    parser.add_argument("--format", choices=("html", "json"), default="html")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    try:
        payload = build_dashboard(args.report_path, out_path=args.out)
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


if __name__ == "__main__":
    raise SystemExit(main())
