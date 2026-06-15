from __future__ import annotations

import argparse
import html
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from sdetkit.atomicio import atomic_write_text
from sdetkit.job_queue import CLAIMED, COMPLETED, FAILED, PENDING, load_queue

SCHEMA_VERSION = "sdetkit.local_diagnostic_queue_dashboard.v1"
DEFAULT_OUT = Path("build") / "local-diagnostic-queue" / "dashboard.html"

JsonObject = dict[str, Any]


def _as_dict(value: Any) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


def _relative_link(path: Path, out_path: Path) -> str:
    try:
        return path.resolve().relative_to(out_path.resolve().parent).as_posix()
    except ValueError:
        try:
            return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
        except ValueError:
            return path.as_posix()


def _artifact_rows(record: Mapping[str, Any], *, out_path: Path) -> list[JsonObject]:
    artifacts = _as_dict(record.get("result_artifacts"))
    rows: list[JsonObject] = []
    for name, raw_path in sorted(artifacts.items()):
        path_text = _string(raw_path)
        if not path_text:
            continue
        path = Path(path_text)
        rows.append(
            {
                "name": _string(name),
                "path": path_text,
                "link": _relative_link(path, out_path),
                "present": path.is_file(),
            }
        )
    return rows


def _state_counts(records: list[JsonObject]) -> dict[str, int]:
    return {
        PENDING: sum(_string(record.get("state")) == PENDING for record in records),
        CLAIMED: sum(_string(record.get("state")) == CLAIMED for record in records),
        COMPLETED: sum(_string(record.get("state")) == COMPLETED for record in records),
        FAILED: sum(_string(record.get("state")) == FAILED for record in records),
    }


def _job_row(record: Mapping[str, Any], *, out_path: Path) -> JsonObject:
    job = _as_dict(record.get("job"))
    event = _as_dict(job.get("event"))
    artifacts = _artifact_rows(record, out_path=out_path)
    return {
        "job_id": _string(record.get("job_id")),
        "state": _string(record.get("state")),
        "repo": _string(event.get("repo")),
        "pr_number": int(event.get("pr_number", 0) or 0),
        "head_sha": _string(event.get("head_sha")),
        "created_at": _string(job.get("created_at")),
        "enqueued_at": _string(record.get("enqueued_at")),
        "claimed_at": _string(record.get("claimed_at")),
        "completed_at": _string(record.get("completed_at")),
        "failed_at": _string(record.get("failed_at")),
        "failure_reason": _string(record.get("failure_reason")),
        "artifact_count": len(artifacts),
        "present_artifact_count": sum(
            1 for artifact in artifacts if artifact.get("present") is True
        ),
        "artifacts": artifacts,
    }


def _decision_boundary() -> JsonObject:
    return {
        "current_pr_decision_input": False,
        "automation_allowed": False,
        "automatic_retry": False,
        "proof_commands_executed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
    }


def build_dashboard(queue_path: Path, *, out_path: Path) -> JsonObject:
    queue_exists = queue_path.is_file()
    queue = load_queue(queue_path)
    records = [_as_dict(record) for record in _as_list(queue.get("jobs")) if _as_dict(record)]
    jobs = [_job_row(record, out_path=out_path) for record in records]
    artifact_count = sum(int(job.get("artifact_count", 0) or 0) for job in jobs)
    present_artifact_count = sum(int(job.get("present_artifact_count", 0) or 0) for job in jobs)
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "ready" if jobs else "empty",
        "queue_path": queue_path.as_posix(),
        "queue_exists": queue_exists,
        "source_queue_schema_version": _string(queue.get("schema_version")),
        "execution_mode": _string(queue.get("execution_mode")),
        "local_only": True,
        "read_only": True,
        "job_count": len(jobs),
        "state_counts": _state_counts(records),
        "artifact_count": artifact_count,
        "present_artifact_count": present_artifact_count,
        "missing_artifact_count": artifact_count - present_artifact_count,
        "jobs": jobs,
        "decision_boundary": _decision_boundary(),
    }


def _escape(value: Any) -> str:
    return html.escape(_string(value))


def _artifact_list(job: Mapping[str, Any]) -> str:
    artifacts = [_as_dict(item) for item in _as_list(job.get("artifacts")) if _as_dict(item)]
    if not artifacts:
        return "<p class='muted'>No result artifacts.</p>"
    items: list[str] = []
    for artifact in artifacts:
        name = _escape(artifact.get("name"))
        link = html.escape(_string(artifact.get("link")) or "#", quote=True)
        presence = "present" if artifact.get("present") is True else "missing"
        items.append(
            f"<li><a href='{link}'>{name}</a> <span class='{presence}'>{presence}</span></li>"
        )
    return f"<ul>{''.join(items)}</ul>"


def _job_card(job: Mapping[str, Any]) -> str:
    state = _escape(job.get("state") or "unknown")
    failure_reason = _string(job.get("failure_reason"))
    failure_html = ""
    if failure_reason:
        failure_html = f"<p><strong>Failure:</strong> {html.escape(failure_reason)}</p>"
    return (
        f"<article class='card state-{state}'>"
        f"<h2>{_escape(job.get('job_id'))}</h2>"
        f"<p class='state'>{state}</p>"
        "<dl>"
        f"<dt>Repository</dt><dd>{_escape(job.get('repo'))}</dd>"
        f"<dt>PR</dt><dd>{int(job.get('pr_number', 0) or 0)}</dd>"
        f"<dt>Head SHA</dt><dd>{_escape(job.get('head_sha'))}</dd>"
        f"<dt>Created</dt><dd>{_escape(job.get('created_at'))}</dd>"
        f"<dt>Enqueued</dt><dd>{_escape(job.get('enqueued_at'))}</dd>"
        f"<dt>Claimed</dt><dd>{_escape(job.get('claimed_at')) or '—'}</dd>"
        f"<dt>Completed</dt><dd>{_escape(job.get('completed_at')) or '—'}</dd>"
        f"<dt>Failed</dt><dd>{_escape(job.get('failed_at')) or '—'}</dd>"
        "</dl>"
        f"{failure_html}"
        "<h3>Result artifacts</h3>"
        f"{_artifact_list(job)}"
        "</article>"
    )


def render_html(payload: Mapping[str, Any]) -> str:
    counts = _as_dict(payload.get("state_counts"))
    jobs = [_as_dict(item) for item in _as_list(payload.get("jobs")) if _as_dict(item)]
    cards = "".join(_job_card(job) for job in jobs)
    if not cards:
        cards = (
            "<article class='card empty'>"
            "<h2>No queued jobs</h2>"
            "<p>The queue is valid and currently empty.</p>"
            "</article>"
        )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Local diagnostic queue dashboard</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #172033; background: #f6f7fb; }}
    header {{ margin-bottom: 1.5rem; }}
    .summary {{ display: flex; flex-wrap: wrap; gap: .6rem; margin: 1rem 0; }}
    .pill {{ background: white; border: 1px solid #d7dce8; border-radius: 999px; padding: .45rem .8rem; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1rem; }}
    .card {{ background: white; border: 1px solid #d7dce8; border-radius: 14px; padding: 1rem; box-shadow: 0 1px 2px rgb(20 30 50 / 8%); }}
    .state-pending {{ border-top: 5px solid #667085; }}
    .state-claimed {{ border-top: 5px solid #175cd3; }}
    .state-completed {{ border-top: 5px solid #247a3f; }}
    .state-failed {{ border-top: 5px solid #b42318; }}
    .state {{ font-weight: 700; text-transform: uppercase; }}
    .muted {{ color: #667085; }}
    .present {{ color: #247a3f; }}
    .missing {{ color: #b42318; }}
    dl {{ display: grid; grid-template-columns: max-content 1fr; gap: .35rem .75rem; }}
    dt {{ font-weight: 700; }}
    dd {{ margin: 0; overflow-wrap: anywhere; }}
    a {{ color: #175cd3; }}
  </style>
</head>
<body>
  <header>
    <h1>Local diagnostic queue dashboard</h1>
    <p>Static, local-only, read-only view of the validated Python queue artifact.</p>
    <div class="summary">
      <span class="pill">status: {_escape(payload.get("status"))}</span>
      <span class="pill">jobs: {int(payload.get("job_count", 0) or 0)}</span>
      <span class="pill">pending: {int(counts.get(PENDING, 0) or 0)}</span>
      <span class="pill">claimed: {int(counts.get(CLAIMED, 0) or 0)}</span>
      <span class="pill">completed: {int(counts.get(COMPLETED, 0) or 0)}</span>
      <span class="pill">failed: {int(counts.get(FAILED, 0) or 0)}</span>
      <span class="pill">missing artifacts: {int(payload.get("missing_artifact_count", 0) or 0)}</span>
      <span class="pill">local only: {str(payload.get("local_only")).lower()}</span>
      <span class="pill">read only: {str(payload.get("read_only")).lower()}</span>
    </div>
    <p><strong>Queue:</strong> {_escape(payload.get("queue_path"))}</p>
  </header>
  <main class="grid">
    {cards}
  </main>
</body>
</html>
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m sdetkit.local_diagnostic_queue_dashboard",
        description=(
            "Render a deterministic local-only dashboard from an existing "
            "diagnostic job queue artifact."
        ),
    )
    parser.add_argument("--queue-path", type=Path, required=True)
    parser.add_argument("--format", choices=("html", "json"), default="html")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    try:
        payload = build_dashboard(args.queue_path, out_path=args.out)
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
