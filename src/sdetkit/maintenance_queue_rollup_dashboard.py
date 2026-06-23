from __future__ import annotations

import argparse
import html
import json
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from sdetkit import maintenance_queue_rollup
from sdetkit.atomicio import atomic_write_text

SCHEMA_VERSION = "sdetkit.maintenance_queue_rollup_dashboard.v1"
LEGACY_SOURCE_SCHEMA_VERSION = "sdetkit.maintenance.queue.rollup.v1"
SUPPORTED_SOURCE_SCHEMA_VERSIONS = {
    LEGACY_SOURCE_SCHEMA_VERSION,
    maintenance_queue_rollup.SCHEMA_VERSION,
}
DEFAULT_OUT = Path("build") / "sdetkit" / "maintenance-queue-rollup-dashboard.html"

JsonObject = dict[str, Any]

_SOURCE_AUTHORITY_FIELDS = (
    "automation_allowed",
    "merge_authorized",
    "semantic_equivalence_proven",
)


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


def _validate_denied_authority(
    value: Mapping[str, Any],
    *,
    context: str,
) -> None:
    expanded = [field for field in _SOURCE_AUTHORITY_FIELDS if value.get(field) is not False]
    if expanded:
        fields = ", ".join(expanded)
        raise ValueError(f"{context} authority boundary must remain denied: {fields}")


def _load_rollup(path: Path) -> JsonObject:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("expected maintenance queue rollup JSON object")

    schema_version = _string(payload.get("schema_version"))
    if schema_version not in SUPPORTED_SOURCE_SCHEMA_VERSIONS:
        raise ValueError(
            f"unsupported maintenance queue rollup schema: {schema_version or 'missing'}"
        )

    _validate_denied_authority(
        payload,
        context="maintenance queue rollup",
    )
    return payload


def _queue_item(value: Any) -> JsonObject:
    item = _as_dict(value)
    _validate_denied_authority(
        item,
        context="maintenance queue item",
    )
    return {
        "issue_number": _integer(item.get("issue_number")),
        "title": _string(item.get("title")),
        "lane": _string(item.get("lane")) or "triage",
        "classification": (_string(item.get("classification")) or "needs_human_review"),
        "rank_score": _integer(item.get("rank_score")),
        "review_required": item.get("review_required") is True,
        "close_candidate": item.get("close_candidate") is True,
        "security_disposition": _string(item.get("security_disposition")),
        "automation_health_state": _string(item.get("automation_health_state")),
        "recommended_action": _string(item.get("recommended_action")),
        "automation_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }


def _input_artifacts(value: Any) -> JsonObject:
    artifacts = _as_dict(value)
    return {
        "issue_queue_schema_version": _string(artifacts.get("issue_queue_schema_version")),
        "automation_health_schema_version": _string(
            artifacts.get("automation_health_schema_version")
        ),
        "security_schema": _string(artifacts.get("security_schema")),
    }


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


def _validate_source_counts(
    rollup: Mapping[str, Any],
    items: list[JsonObject],
) -> None:
    source_count = _integer(rollup.get("queue_item_count"))
    if source_count != len(items):
        raise ValueError("queue_item_count does not match queue_items")

    review_required_count = sum(item["review_required"] is True for item in items)
    if _integer(rollup.get("review_required_count")) != review_required_count:
        raise ValueError("review_required_count does not match queue_items")

    close_candidate_count = sum(item["close_candidate"] is True for item in items)
    if _integer(rollup.get("close_candidate_count")) != close_candidate_count:
        raise ValueError("close_candidate_count does not match queue_items")

    raw_primary = rollup.get("primary_issue")
    primary_issue = _integer(raw_primary) if raw_primary is not None else None
    expected_primary = _integer(items[0].get("issue_number")) if items else None
    if primary_issue != expected_primary:
        raise ValueError("primary_issue does not match queue ordering")


def build_dashboard(
    rollup_path: Path,
    *,
    out_path: Path,
) -> JsonObject:
    del out_path

    rollup = _load_rollup(rollup_path)
    items = [
        _queue_item(item) for item in _as_list(rollup.get("queue_items")) if isinstance(item, dict)
    ]
    _validate_source_counts(rollup, items)

    lane_counts = dict(
        sorted(Counter(_string(item.get("lane")) or "triage" for item in items).items())
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "ready" if items else "empty",
        "rollup_path": rollup_path.as_posix(),
        "rollup_exists": rollup_path.is_file(),
        "source_rollup_schema_version": _string(rollup.get("schema_version")),
        "source_rollup_status": _string(rollup.get("status")),
        "source_issue_count": _integer(rollup.get("source_issue_count")),
        "queue_item_count": len(items),
        "review_required_count": sum(item["review_required"] is True for item in items),
        "close_candidate_count": sum(item["close_candidate"] is True for item in items),
        "primary_issue": (_integer(items[0].get("issue_number")) if items else None),
        "recommended_next_action": _string(rollup.get("recommended_next_action")),
        "lane_counts": lane_counts,
        "input_artifacts": _input_artifacts(rollup.get("input_artifacts")),
        "queue_items": items,
        "local_only": True,
        "read_only": True,
        "decision_boundary": _decision_boundary(),
    }


def _escape(value: Any) -> str:
    return html.escape(_string(value))


def _queue_card(item: Mapping[str, Any]) -> str:
    review_required = item.get("review_required") is True
    close_candidate = item.get("close_candidate") is True

    if review_required:
        state_class = "review"
        state_label = "review required"
    elif close_candidate:
        state_class = "close"
        state_label = "close candidate"
    else:
        state_class = "ready"
        state_label = "ready with proof"

    return (
        f"<article class='card {state_class}'>"
        f"<h2>Issue #{_integer(item.get('issue_number'))}</h2>"
        f"<p class='state'>{html.escape(state_label)}</p>"
        "<dl>"
        f"<dt>Title</dt><dd>{_escape(item.get('title')) or '—'}</dd>"
        f"<dt>Lane</dt><dd>{_escape(item.get('lane'))}</dd>"
        f"<dt>Classification</dt><dd>{_escape(item.get('classification'))}</dd>"
        f"<dt>Rank score</dt><dd>{_integer(item.get('rank_score'))}</dd>"
        f"<dt>Security disposition</dt><dd>{_escape(item.get('security_disposition')) or '—'}</dd>"
        f"<dt>Automation health</dt><dd>{_escape(item.get('automation_health_state')) or '—'}</dd>"
        "</dl>"
        f"<p><strong>Recommended action:</strong> "
        f"{_escape(item.get('recommended_action')) or '—'}</p>"
        "<p class='muted'>This item is review context only. "
        "It does not authorize issue mutation, security dismissal, "
        "patch application, or merge.</p>"
        "</article>"
    )


def render_html(payload: Mapping[str, Any]) -> str:
    items = [
        _as_dict(item) for item in _as_list(payload.get("queue_items")) if isinstance(item, dict)
    ]
    cards = "".join(_queue_card(item) for item in items)
    if not cards:
        cards = (
            "<article class='card empty'>"
            "<h2>No maintenance queue items</h2>"
            "<p>The source rollup is valid and currently empty.</p>"
            "</article>"
        )

    lane_counts = _as_dict(payload.get("lane_counts"))
    lane_items = "".join(
        f"<li><strong>{html.escape(key)}</strong>: {_integer(value)}</li>"
        for key, value in sorted(lane_counts.items())
    )
    if not lane_items:
        lane_items = "<li class='muted'>none</li>"

    boundary = _as_dict(payload.get("decision_boundary"))
    boundary_items = "".join(
        f"<li><strong>{html.escape(key)}</strong>: {str(value).lower()}</li>"
        for key, value in sorted(boundary.items())
    )

    primary_issue = payload.get("primary_issue")
    primary_text = str(_integer(primary_issue)) if primary_issue is not None else "none"

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Maintenance queue rollup dashboard</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #172033; background: #f6f7fb; }}
    header {{ margin-bottom: 1.5rem; }}
    .summary {{ display: flex; flex-wrap: wrap; gap: .6rem; margin: 1rem 0; }}
    .pill {{ background: white; border: 1px solid #d7dce8; border-radius: 999px; padding: .45rem .8rem; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1rem; }}
    .card {{ background: white; border: 1px solid #d7dce8; border-radius: 14px; padding: 1rem; box-shadow: 0 1px 2px rgb(20 30 50 / 8%); }}
    .review {{ border-top: 5px solid #b42318; }}
    .close {{ border-top: 5px solid #b54708; }}
    .ready {{ border-top: 5px solid #247a3f; }}
    .empty {{ border-top: 5px solid #667085; }}
    .state {{ font-weight: 700; text-transform: uppercase; }}
    .muted {{ color: #667085; }}
    dl {{ display: grid; grid-template-columns: max-content 1fr; gap: .35rem .75rem; }}
    dt {{ font-weight: 700; }}
    dd {{ margin: 0; overflow-wrap: anywhere; }}
    code {{ overflow-wrap: anywhere; }}
  </style>
</head>
<body>
  <header>
    <h1>Maintenance queue rollup dashboard</h1>
    <p>Static, local-only, read-only view of the accepted Python maintenance queue rollup artifact.</p>
    <div class="summary">
      <span class="pill">status: {_escape(payload.get("status"))}</span>
      <span class="pill">source status: {_escape(payload.get("source_rollup_status"))}</span>
      <span class="pill">queue items: {_integer(payload.get("queue_item_count"))}</span>
      <span class="pill">review required: {_integer(payload.get("review_required_count"))}</span>
      <span class="pill">close candidates: {_integer(payload.get("close_candidate_count"))}</span>
      <span class="pill">primary issue: {html.escape(primary_text)}</span>
      <span class="pill">local only: {str(payload.get("local_only")).lower()}</span>
      <span class="pill">read only: {str(payload.get("read_only")).lower()}</span>
    </div>
    <p><strong>Rollup:</strong> <code>{_escape(payload.get("rollup_path"))}</code></p>
    <p><strong>Recommended next action:</strong> {_escape(payload.get("recommended_next_action")) or "—"}</p>
  </header>
  <main class="grid">
    {cards}
    <article class="card">
      <h2>Lane counts</h2>
      <ul>{lane_items}</ul>
    </article>
    <article class="card">
      <h2>Authority boundary</h2>
      <ul>{boundary_items}</ul>
      <p>This dashboard is not proof execution, issue mutation, security dismissal, patch approval, a current-PR decision, or merge authorization.</p>
    </article>
  </main>
</body>
</html>
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=("python -m sdetkit.maintenance_queue_rollup_dashboard"),
        description=(
            "Render a deterministic local-only dashboard from an "
            "existing maintenance queue rollup JSON artifact."
        ),
    )
    parser.add_argument(
        "--rollup-path",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--format",
        choices=("html", "json"),
        default="html",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    try:
        payload = build_dashboard(
            args.rollup_path,
            out_path=args.out,
        )
        rendered = (
            json.dumps(
                payload,
                indent=2,
                sort_keys=True,
            )
            + "\n"
            if args.format == "json"
            else render_html(payload)
        )
        atomic_write_text(args.out, rendered)
    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        print(
            f"error={_string(exc) or type(exc).__name__}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
