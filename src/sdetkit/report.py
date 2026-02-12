from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

from .atomicio import atomic_write_text
from .security import SecurityError, safe_path

_UTC = getattr(dt, "UTC", dt.timezone.utc)  # noqa: UP017
RUN_SCHEMA = "sdetkit.audit.run.v1"


def _severity_rank(level: str) -> int:
    return {"info": 0, "warn": 1, "error": 2}.get(level, 2)


def _tool_version() -> str:
    try:
        from importlib import metadata

        return metadata.version("sdetkit")
    except Exception:
        return "0.2.8"


def _captured_at() -> str | None:
    raw = os.environ.get("SOURCE_DATE_EPOCH")
    if not raw:
        return None
    try:
        epoch = int(raw)
    except ValueError:
        return None
    return dt.datetime.fromtimestamp(epoch, tz=_UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_path(path: str) -> str:
    clean = path.replace("\\", "/")
    while clean.startswith("/"):
        clean = clean[1:]
    return clean or "."


def _canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def build_run_record(
    payload: dict[str, Any],
    *,
    profile: str,
    packs: tuple[str, ...],
    fail_on: str,
    repo_root: str | None,
    config_used: str | None,
) -> dict[str, Any]:
    suppressed_map: dict[str, str] = {}
    for item in payload.get("suppressed", []):
        if isinstance(item, dict):
            fp = str(item.get("fingerprint", ""))
            if fp:
                suppressed_map[fp] = str(item.get("reason", ""))

    findings: list[dict[str, Any]] = []
    for item in payload.get("findings", []):
        if not isinstance(item, dict):
            continue
        fp = str(item.get("fingerprint", ""))
        sev = str(item.get("severity", "error"))
        findings.append(
            {
                "fingerprint": fp,
                "rule_id": str(item.get("rule_id") or item.get("code") or "unknown"),
                "severity": sev,
                "message": str(item.get("message", "")),
                "path": _normalize_path(str(item.get("path", "."))),
                "line": int(item.get("line", 1)) if item.get("line") is not None else None,
                "tags": sorted(set(str(x) for x in (item.get("tags") or []))),
                "pack": str(item.get("pack", "core")),
                "fixable": bool(item.get("fixable", False)),
                "suppressed": fp in suppressed_map,
                "suppression_reason": suppressed_map.get(fp),
            }
        )

    findings.sort(
        key=lambda x: (
            _severity_rank(str(x.get("severity", "error"))),
            str(x.get("rule_id", "")),
            str(x.get("path", "")),
            str(x.get("fingerprint", "")),
        )
    )

    counts = {"info": 0, "warn": 0, "error": 0}
    fixable = 0
    suppressed = 0
    for finding in findings:
        sev = str(finding.get("severity", "error"))
        counts[sev] = counts.get(sev, 0) + 1
        if finding.get("fixable"):
            fixable += 1
        if finding.get("suppressed"):
            suppressed += 1

    source: dict[str, Any] = {}
    sha = os.environ.get("GITHUB_SHA")
    if sha:
        source["commit_sha"] = sha
    captured = _captured_at()
    if captured:
        source["captured_at"] = captured

    run = {
        "schema_version": RUN_SCHEMA,
        "tool_version": _tool_version(),
        "profile": profile,
        "packs": list(packs),
        "fail_on": fail_on,
        "findings": findings,
        "aggregates": {
            "counts_by_severity": {k: counts[k] for k in sorted(counts)},
            "counts_suppressed": suppressed,
            "counts_fixable": fixable,
        },
    }
    if repo_root:
        run["repo_root"] = _normalize_path(repo_root)
    if config_used:
        run["config_used"] = Path(config_used).name
    if source:
        run["source"] = source
    return run


def _coerce_run_record(doc: dict[str, Any]) -> dict[str, Any]:
    if doc.get("schema_version") == RUN_SCHEMA:
        return doc
    if "findings" in doc and "summary" in doc:
        summary = doc.get("summary", {})
        return build_run_record(
            doc,
            profile=str(summary.get("profile", "default")),
            packs=tuple(summary.get("packs", ["core"])),
            fail_on="none",
            repo_root=str(doc.get("root", "")),
            config_used=None,
        )
    raise ValueError("unsupported run record schema")


def load_run_record(path: Path) -> dict[str, Any]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError("run record must be an object")
    run = _coerce_run_record(doc)
    if run.get("schema_version") != RUN_SCHEMA:
        raise ValueError("expected schema_version sdetkit.audit.run.v1")
    return run


def _findings_map(run: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for finding in run.get("findings", []):
        if not isinstance(finding, dict):
            continue
        fp = str(finding.get("fingerprint", ""))
        if fp:
            out[fp] = finding
    return out


def diff_runs(from_run: dict[str, Any], to_run: dict[str, Any]) -> dict[str, Any]:
    old_map = _findings_map(from_run)
    new_map = _findings_map(to_run)
    old_fps = set(old_map)
    new_fps = set(new_map)
    new_only = sorted(new_fps - old_fps)
    resolved = sorted(old_fps - new_fps)
    unchanged = sorted(new_fps & old_fps)

    counts = {"info": 0, "warn": 0, "error": 0}
    for fp in new_only:
        sev = str(new_map[fp].get("severity", "error"))
        counts[sev] = counts.get(sev, 0) + 1

    top_new = [new_map[fp] for fp in new_only]
    top_new.sort(
        key=lambda x: (
            -_severity_rank(str(x.get("severity", "error"))),
            str(x.get("rule_id", "")),
            str(x.get("path", "")),
            str(x.get("fingerprint", "")),
        )
    )

    return {
        "from": from_run.get("source", {}),
        "to": to_run.get("source", {}),
        "counts": {
            "new": len(new_only),
            "resolved": len(resolved),
            "unchanged": len(unchanged),
            "new_by_severity": {k: counts[k] for k in sorted(counts)},
        },
        "new": top_new,
        "resolved": [old_map[fp] for fp in resolved],
    }


def _render_diff_text(payload: dict[str, Any], limit: int = 10) -> str:
    lines = [
        (
            "NEW: "
            f"{payload['counts']['new']} RESOLVED: {payload['counts']['resolved']} "
            f"UNCHANGED: {payload['counts']['unchanged']}"
        ),
        (
            "NEW by severity: "
            f"error={payload['counts']['new_by_severity']['error']} "
            f"warn={payload['counts']['new_by_severity']['warn']} "
            f"info={payload['counts']['new_by_severity']['info']}"
        ),
    ]
    for item in payload.get("new", [])[:limit]:
        lines.append(
            f"- [{item.get('severity')}] {item.get('rule_id')} {item.get('path')}#{item.get('fingerprint')}"
        )
    return "\n".join(lines) + "\n"


def _threshold_rank(level: str) -> int:
    if level == "none":
        return 9
    return _severity_rank(level)


def _new_count_at_or_above(payload: dict[str, Any], threshold: str) -> int:
    rank = _threshold_rank(threshold)
    return sum(
        1
        for item in payload.get("new", [])
        if _severity_rank(str(item.get("severity", "error"))) >= rank
    )


def _summary_markdown(run: dict[str, Any], diff_payload: dict[str, Any] | None = None) -> str:
    findings = [x for x in run.get("findings", []) if isinstance(x, dict)]
    suppressed = sum(1 for x in findings if x.get("suppressed"))
    actionable = len(findings) - suppressed
    lines = [
        "## sdetkit repo audit summary",
        "",
        f"- total findings: {len(findings)}",
        f"- suppressed: {suppressed}",
        f"- actionable: {actionable}",
    ]
    if diff_payload is not None:
        lines.extend(
            [
                f"- NEW: {diff_payload['counts']['new']}",
                f"- RESOLVED: {diff_payload['counts']['resolved']}",
            ]
        )
    lines.extend(["", "### Top actionable findings", ""])
    actionable_items = [x for x in findings if not x.get("suppressed")]
    actionable_items.sort(
        key=lambda x: (
            -_severity_rank(str(x.get("severity", "error"))),
            str(x.get("rule_id", "")),
            str(x.get("path", "")),
        )
    )
    for item in actionable_items[:10]:
        lines.append(
            f"- [{item.get('severity')}] `{item.get('rule_id')}` `{item.get('path')}`: {item.get('message')}"
        )
    lines.extend(["", "Run: sdetkit repo fix-audit --dry-run", ""])
    return "\n".join(lines)


def _history_runs(history_dir: Path) -> list[dict[str, Any]]:
    index_path = history_dir / "index.json"
    if not index_path.exists():
        return []
    data = json.loads(index_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return []
    items = data.get("runs", [])
    if not isinstance(items, list):
        return []
    return [x for x in items if isinstance(x, dict)]


def _write_history_index(history_dir: Path, items: list[dict[str, Any]]) -> None:
    payload = {"schema_version": "sdetkit.audit.history.v1", "runs": items}
    atomic_write_text(
        history_dir / "index.json",
        json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n",
    )


def _sparkline(values: list[int]) -> str:
    if not values:
        return ""
    max_v = max(values) or 1
    width = 220
    height = 40
    step = width / max(1, len(values) - 1)
    points = []
    for i, value in enumerate(values):
        x = i * step
        y = height - ((value / max_v) * (height - 4)) - 2
        points.append(f"{x:.1f},{y:.1f}")
    return (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        'xmlns="http://www.w3.org/2000/svg"><polyline fill="none" '
        f'stroke="#0b5fff" stroke-width="2" points="{" ".join(points)}" /></svg>'
    )


def build_dashboard(history_dir: Path, output: Path, fmt: str, since: int | None) -> None:
    runs = _history_runs(history_dir)
    if since is not None:
        runs = runs[-since:]
    if not runs:
        content = "# sdetkit audit trends\n\nNo audit history found.\n"
        atomic_write_text(output, content)
        return

    totals = [
        int(item.get("aggregates", {}).get("counts_by_severity", {}).get("error", 0))
        for item in runs
    ]
    totals = [
        int(item.get("aggregates", {}).get("counts_by_severity", {}).get("error", 0))
        + int(item.get("aggregates", {}).get("counts_by_severity", {}).get("warn", 0))
        for item in runs
    ]
    last = runs[-1]
    previous = runs[-2] if len(runs) > 1 else None
    delta = diff_runs(previous, last) if previous else None

    recurring_rules: dict[str, int] = {}
    recurring_paths: dict[str, int] = {}
    for run in runs:
        for finding in run.get("findings", []):
            if not isinstance(finding, dict):
                continue
            recurring_rules[str(finding.get("rule_id", "unknown"))] = (
                recurring_rules.get(str(finding.get("rule_id", "unknown")), 0) + 1
            )
            recurring_paths[str(finding.get("path", "."))] = (
                recurring_paths.get(str(finding.get("path", ".")), 0) + 1
            )

    top_rules = sorted(recurring_rules.items(), key=lambda x: (-x[1], x[0]))[:10]
    top_paths = sorted(recurring_paths.items(), key=lambda x: (-x[1], x[0]))[:10]

    if fmt == "md":
        lines = [
            "# sdetkit audit trends",
            "",
            f"- runs: {len(runs)}",
            f"- latest actionable findings: {len(last.get('findings', []))}",
        ]
        if delta is not None:
            lines.append(
                f"- delta vs previous: NEW={delta['counts']['new']} RESOLVED={delta['counts']['resolved']}"
            )
        lines.extend(["", "## Top recurring rules", ""])
        for rule, count in top_rules:
            lines.append(f"- `{rule}`: {count}")
        lines.extend(["", "## Top paths", ""])
        for path, count in top_paths:
            lines.append(f"- `{path}`: {count}")
        atomic_write_text(output, "\n".join(lines) + "\n")
        return

    lines = [
        "<html><head><meta charset='utf-8'><title>sdetkit audit trends</title></head><body>",
        "<h1>sdetkit audit trends</h1>",
        f"<p>Runs: {len(runs)}</p>",
        f"<p>Latest actionable findings: {len(last.get('findings', []))}</p>",
        f"<div>{_sparkline(totals)}</div>",
    ]
    if delta is not None:
        lines.append(
            f"<p>Delta vs previous: NEW={delta['counts']['new']} RESOLVED={delta['counts']['resolved']}</p>"
        )
    lines.append("<h2>Top recurring rules</h2><table><tr><th>Rule</th><th>Count</th></tr>")
    for rule, count in top_rules:
        lines.append(f"<tr><td>{rule}</td><td>{count}</td></tr>")
    lines.append("</table><h2>Top paths</h2><table><tr><th>Path</th><th>Count</th></tr>")
    for path, count in top_paths:
        lines.append(f"<tr><td>{path}</td><td>{count}</td></tr>")
    lines.append("</table></body></html>\n")
    atomic_write_text(output, "".join(lines))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sdetkit report")
    sub = parser.add_subparsers(dest="report_cmd", required=True)

    ip = sub.add_parser("ingest")
    ip.add_argument("run_json")
    ip.add_argument("--history-dir", default=".sdetkit/audit-history")
    ip.add_argument("--label", default=None)

    dp = sub.add_parser("diff")
    dp.add_argument("--from", dest="from_run", required=True)
    dp.add_argument("--to", dest="to_run", required=True)
    dp.add_argument("--format", choices=["text", "json"], default="text")
    dp.add_argument("--fail-on", choices=["none", "warn", "error"], default="none")

    bp = sub.add_parser("build")
    bp.add_argument("--history-dir", default=".sdetkit/audit-history")
    bp.add_argument("--output", default="report.html")
    bp.add_argument("--format", choices=["html", "md"], default="html")
    bp.add_argument("--since", type=int, default=None)

    ns = parser.parse_args(argv)

    try:
        if ns.report_cmd == "ingest":
            src = safe_path(Path.cwd(), ns.run_json, allow_absolute=True)
            history_dir = safe_path(Path.cwd(), ns.history_dir, allow_absolute=True)
            history_dir.mkdir(parents=True, exist_ok=True)
            run = load_run_record(src)
            digest = hashlib.sha256(_canonical_json_bytes(run)).hexdigest()
            target = history_dir / f"{digest}.json"
            if not target.exists():
                atomic_write_text(
                    target, json.dumps(run, ensure_ascii=True, sort_keys=True, indent=2) + "\n"
                )

            index_items = _history_runs(history_dir)
            rows = {(str(x.get("sha256")), str(x.get("file"))): x for x in index_items}
            row = {
                "sha256": digest,
                "file": target.name,
                "label": ns.label,
                "captured_at": run.get("source", {}).get("captured_at"),
            }
            rows[(digest, target.name)] = row
            ordered = sorted(
                rows.values(),
                key=lambda x: (str(x.get("captured_at", "")), str(x.get("sha256", ""))),
            )
            _write_history_index(history_dir, ordered)
            return 0

        if ns.report_cmd == "diff":
            from_run = load_run_record(safe_path(Path.cwd(), ns.from_run, allow_absolute=True))
            to_run = load_run_record(safe_path(Path.cwd(), ns.to_run, allow_absolute=True))
            payload = diff_runs(from_run, to_run)
            if ns.format == "json":
                sys.stdout.write(
                    json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n"
                )
            else:
                sys.stdout.write(_render_diff_text(payload))
            return 1 if _new_count_at_or_above(payload, ns.fail_on) > 0 else 0

        history_dir = safe_path(Path.cwd(), ns.history_dir, allow_absolute=True)
        output = safe_path(Path.cwd(), ns.output, allow_absolute=True)
        build_dashboard(history_dir, output, ns.format, ns.since)
        return 0
    except (ValueError, OSError, SecurityError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
