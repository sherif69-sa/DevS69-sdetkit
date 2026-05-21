from __future__ import annotations

import argparse
import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.trajectory_history_report.v1"

JsonObject = dict[str, Any]


def _as_dict(value: Any) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true", "yes"}


def _count_by(values: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = value or "unknown"
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _read_jsonl(path: Path) -> list[JsonObject]:
    records: list[JsonObject] = []
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        line = raw_line.strip()
        if not line:
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            msg = f"expected JSON object on line {line_number} in {path}"
            raise ValueError(msg)
        records.append(payload)
    return records


def load_trajectory_records(paths: Iterable[Path]) -> list[JsonObject]:
    records: list[JsonObject] = []
    for path in paths:
        if not path.exists():
            msg = f"trajectory JSONL not found: {path}"
            raise FileNotFoundError(msg)
        records.extend(_read_jsonl(path))
    return records


def _risk_surface(record: Mapping[str, Any]) -> str:
    diagnosis = _as_dict(record.get("diagnosis"))
    return _string(diagnosis.get("risk_surface") or record.get("risk_surface") or "unknown")


def _failure_class(record: Mapping[str, Any]) -> str:
    diagnosis = _as_dict(record.get("diagnosis"))
    return _string(diagnosis.get("failure_class") or record.get("failure_class") or "unknown")


def _decision(record: Mapping[str, Any]) -> JsonObject:
    return _as_dict(record.get("decision"))


def _recent_decision(record: Mapping[str, Any]) -> JsonObject:
    decision = _decision(record)
    return {
        "trajectory_id": _string(record.get("trajectory_id") or "unknown"),
        "diagnostic_id": _string(record.get("diagnostic_id") or "unknown"),
        "action": _string(record.get("action") or "unknown"),
        "failure_class": _failure_class(record),
        "risk_surface": _risk_surface(record),
        "review_first": _bool(decision.get("review_first")),
        "auto_fix_allowed": _bool(decision.get("auto_fix_allowed")),
        "final_result": _string(record.get("final_result") or "unknown"),
        "commit_sha": _string(record.get("commit_sha") or "unknown"),
        "pr_number": record.get("pr_number", 0),
    }


def build_history_summary(
    records: list[Mapping[str, Any]],
    *,
    recent_limit: int = 5,
) -> JsonObject:
    rows = [_as_dict(record) for record in records if _as_dict(record)]
    decisions = [_decision(record) for record in rows]
    recent_rows = list(reversed(rows[-max(recent_limit, 0) :])) if recent_limit else []

    return {
        "schema_version": SCHEMA_VERSION,
        "record_count": len(rows),
        "review_first_count": sum(
            1 for decision in decisions if _bool(decision.get("review_first"))
        ),
        "auto_fix_allowed_count": sum(
            1 for decision in decisions if _bool(decision.get("auto_fix_allowed"))
        ),
        "by_final_result": _count_by(_string(row.get("final_result")) for row in rows),
        "by_risk_surface": _count_by(_risk_surface(row) for row in rows),
        "by_failure_class": _count_by(_failure_class(row) for row in rows),
        "by_action": _count_by(_string(row.get("action") or "unknown") for row in rows),
        "recent_decisions": [_recent_decision(row) for row in recent_rows],
    }


def render_history_markdown(summary: Mapping[str, Any]) -> str:
    lines = [
        "# Trajectory history summary",
        "",
        f"- Schema: `{_string(summary.get('schema_version'))}`",
        f"- Records: `{int(summary.get('record_count', 0) or 0)}`",
        f"- Review-first decisions: `{int(summary.get('review_first_count', 0) or 0)}`",
        f"- Auto-fix allowed decisions: `{int(summary.get('auto_fix_allowed_count', 0) or 0)}`",
        "",
    ]

    for title, key in (
        ("Final results", "by_final_result"),
        ("Risk surfaces", "by_risk_surface"),
        ("Failure classes", "by_failure_class"),
        ("Actions", "by_action"),
    ):
        lines.extend([f"## {title}", ""])
        counts = _as_dict(summary.get(key))
        if counts:
            lines.extend(f"- `{name}`: `{count}`" for name, count in counts.items())
        else:
            lines.append("- none")
        lines.append("")

    lines.extend(["## Recent decisions", ""])
    recent = [_as_dict(item) for item in _as_list(summary.get("recent_decisions"))]
    if recent:
        for item in recent:
            lines.append(
                "- "
                f"`{_string(item.get('diagnostic_id') or 'unknown')}`: "
                f"action=`{_string(item.get('action') or 'unknown')}`, "
                f"surface=`{_string(item.get('risk_surface') or 'unknown')}`, "
                f"class=`{_string(item.get('failure_class') or 'unknown')}`, "
                f"review_first=`{str(_bool(item.get('review_first'))).lower()}`, "
                f"auto_fix_allowed=`{str(_bool(item.get('auto_fix_allowed'))).lower()}`, "
                f"result=`{_string(item.get('final_result') or 'unknown')}`"
            )
    else:
        lines.append("- none")

    lines.append("")
    return "\n".join(lines)


def write_history_report(
    *,
    records: list[Mapping[str, Any]],
    json_out: Path | None = None,
    markdown_out: Path | None = None,
    recent_limit: int = 5,
) -> JsonObject:
    summary = build_history_summary(records, recent_limit=recent_limit)

    if json_out is not None:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if markdown_out is not None:
        markdown_out.parent.mkdir(parents=True, exist_ok=True)
        markdown_out.write_text(render_history_markdown(summary), encoding="utf-8")

    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.trajectory_history_report")
    parser.add_argument(
        "--trajectory-jsonl",
        type=Path,
        action="append",
        required=True,
        help="TrajectoryStore JSONL file. May be provided more than once.",
    )
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--markdown-out", type=Path)
    parser.add_argument("--recent-limit", type=int, default=5)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        records = load_trajectory_records(args.trajectory_jsonl)
        summary = write_history_report(
            records=records,
            json_out=args.json_out,
            markdown_out=args.markdown_out,
            recent_limit=args.recent_limit,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}")
        return 2

    if args.format == "json":
        print(json.dumps({"summary": summary}, indent=2, sort_keys=True))
    else:
        print(render_history_markdown(summary))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
