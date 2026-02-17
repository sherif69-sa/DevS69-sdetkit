from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import os
import sys
from pathlib import Path
from typing import Any, TypedDict

from .atomicio import atomic_write_text, canonical_json_bytes, canonical_json_dumps
from .security import SecurityError, safe_path

_UTC = getattr(dt, "UTC", dt.timezone.utc)  # noqa: UP017
RUN_SCHEMA = "sdetkit.audit.run.v1"


def _history_run_sort_key(r: dict[str, Any]) -> tuple[str, str]:
    src = r.get("source")
    cap = src.get("captured_at") if isinstance(src, dict) else ""
    return (str(cap), str(r.get("_sha256") or ""))


def _severity_rank(level: str) -> int:
    return {"info": 0, "warn": 1, "error": 2}.get(level, 2)


def _tool_version() -> str:
    try:
        from importlib import metadata

        return metadata.version("sdetkit")
    except Exception:
        return "1.0.0"


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


def build_run_record(
    payload: dict[str, Any],
    *,
    profile: str,
    packs: tuple[str, ...],
    fail_on: str,
    repo_root: str | None,
    config_used: str | None,
    incremental_used: bool = False,
    changed_file_count: int = 0,
    cache_summary: dict[str, Any] | None = None,
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
    execution: dict[str, Any] = {
        "incremental_used": bool(incremental_used),
        "changed_file_count": int(changed_file_count),
    }
    if isinstance(cache_summary, dict):
        execution["cache"] = cache_summary
    run["execution"] = execution
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


_DIFF_MUTATION_FIELDS = (
    "severity",
    "rule_id",
    "message",
    "path",
    "line",
    "pack",
    "fixable",
    "suppressed",
    "suppression_reason",
)


def _is_finding_changed(old: dict[str, Any], new: dict[str, Any]) -> tuple[bool, list[str]]:
    changed_fields = [field for field in _DIFF_MUTATION_FIELDS if old.get(field) != new.get(field)]
    old_tags = sorted(str(x) for x in (old.get("tags") or []))
    new_tags = sorted(str(x) for x in (new.get("tags") or []))
    if old_tags != new_tags:
        changed_fields.append("tags")
    return bool(changed_fields), changed_fields


def diff_runs(
    from_run: dict[str, Any], to_run: dict[str, Any], *, new_limit: int | None = None
) -> dict[str, Any]:
    old_map = _findings_map(from_run)
    new_map = _findings_map(to_run)
    old_fps = set(old_map)
    new_fps = set(new_map)
    new_only = sorted(new_fps - old_fps)
    resolved = sorted(old_fps - new_fps)
    unchanged = sorted(new_fps & old_fps)
    changed: list[dict[str, Any]] = []

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

    if new_limit is not None:
        top_new = top_new[: max(new_limit, 0)]

    for fp in unchanged:
        old = old_map[fp]
        new = new_map[fp]
        is_changed, changed_fields = _is_finding_changed(old, new)
        if not is_changed:
            continue
        changed.append(
            {
                "fingerprint": fp,
                "changed_fields": changed_fields,
                "from": {
                    "severity": str(old.get("severity", "error")),
                    "rule_id": str(old.get("rule_id", "unknown")),
                    "path": str(old.get("path", ".")),
                },
                "to": {
                    "severity": str(new.get("severity", "error")),
                    "rule_id": str(new.get("rule_id", "unknown")),
                    "path": str(new.get("path", ".")),
                },
            }
        )

    changed.sort(
        key=lambda item: (
            -_severity_rank(str(item.get("to", {}).get("severity", "error"))),
            str(item.get("to", {}).get("rule_id", "")),
            str(item.get("to", {}).get("path", "")),
            str(item.get("fingerprint", "")),
        )
    )

    return {
        "from": from_run.get("source", {}),
        "to": to_run.get("source", {}),
        "counts": {
            "new": len(new_only),
            "resolved": len(resolved),
            "unchanged": len(unchanged) - len(changed),
            "changed": len(changed),
            "new_by_severity": {k: counts[k] for k in sorted(counts)},
        },
        "new": top_new,
        "changed": changed,
        "resolved": [old_map[fp] for fp in resolved],
    }


def _render_diff_text(payload: dict[str, Any], limit: int | None = 10) -> str:
    lines = [
        (
            "NEW: "
            f"{payload['counts']['new']} RESOLVED: {payload['counts']['resolved']} "
            f"UNCHANGED: {payload['counts']['unchanged']} CHANGED: {payload['counts']['changed']}"
        ),
        (
            "NEW by severity: "
            f"error={payload['counts']['new_by_severity']['error']} "
            f"warn={payload['counts']['new_by_severity']['warn']} "
            f"info={payload['counts']['new_by_severity']['info']}"
        ),
    ]
    items = payload.get("new", []) if limit is None else payload.get("new", [])[:limit]
    for item in items:
        lines.append(
            f"- [{item.get('severity')}] {item.get('rule_id')} {item.get('path')}#{item.get('fingerprint')}"
        )
    changed_items = (
        payload.get("changed", []) if limit is None else payload.get("changed", [])[:limit]
    )
    for item in changed_items:
        from_meta = item.get("from", {})
        to_meta = item.get("to", {})
        lines.append(
            "~ "
            f"[{from_meta.get('severity')}->{to_meta.get('severity')}] "
            f"{to_meta.get('rule_id')} {to_meta.get('path')}#{item.get('fingerprint')} "
            f"fields={','.join(str(x) for x in item.get('changed_fields', []))}"
        )
    return "\n".join(lines) + "\n"


def _render_diff_markdown(payload: dict[str, Any], limit: int | None = 10) -> str:
    lines = [
        "# sdetkit audit diff",
        "",
        (
            f"- NEW: {payload['counts']['new']}"
            f" | RESOLVED: {payload['counts']['resolved']}"
            f" | UNCHANGED: {payload['counts']['unchanged']}"
            f" | CHANGED: {payload['counts']['changed']}"
        ),
        (
            "- NEW by severity: "
            f"error={payload['counts']['new_by_severity']['error']} "
            f"warn={payload['counts']['new_by_severity']['warn']} "
            f"info={payload['counts']['new_by_severity']['info']}"
        ),
    ]

    new_items = payload.get("new", []) if limit is None else payload.get("new", [])[:limit]
    lines.extend(["", "## New findings"])
    if not new_items:
        lines.append("- none")
    else:
        for item in new_items:
            lines.append(
                "- "
                f"**[{item.get('severity')}] {item.get('rule_id')}** "
                f"`{item.get('path')}#{item.get('fingerprint')}`"
            )

    changed_items = (
        payload.get("changed", []) if limit is None else payload.get("changed", [])[:limit]
    )
    lines.extend(["", "## Changed findings"])
    if not changed_items:
        lines.append("- none")
    else:
        for item in changed_items:
            from_meta = item.get("from", {})
            to_meta = item.get("to", {})
            changed_fields = ",".join(str(x) for x in item.get("changed_fields", []))
            lines.append(
                "- "
                f"`{item.get('fingerprint')}` "
                f"**{to_meta.get('rule_id')}** "
                f"{from_meta.get('severity')}\u2192{to_meta.get('severity')} "
                f"({changed_fields})"
            )
    lines.append("")
    return "\n".join(lines)


def _threshold_rank(level: str) -> int:
    if level == "none":
        return 9
    return _severity_rank(level)


def _new_count_at_or_above(payload: dict[str, Any], threshold: str) -> int:
    rank = _threshold_rank(threshold)
    counts = payload.get("counts", {}).get("new_by_severity", {})
    if not isinstance(counts, dict):
        return 0

    total = 0
    for sev, count in counts.items():
        if _severity_rank(str(sev)) >= rank:
            total += int(count)
    return total


def _changed_count_crossing_threshold(payload: dict[str, Any], threshold: str) -> int:
    rank = _threshold_rank(threshold)
    if rank > _severity_rank("error"):
        return 0

    return sum(
        1
        for item in payload.get("changed", [])
        if _severity_rank(str(item.get("from", {}).get("severity", "error"))) < rank
        and _severity_rank(str(item.get("to", {}).get("severity", "error"))) >= rank
    )


def _fail_count_at_or_above(payload: dict[str, Any], threshold: str) -> int:
    return _new_count_at_or_above(payload, threshold) + _changed_count_crossing_threshold(
        payload, threshold
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
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(
            f"warning: ignoring unreadable history index {index_path.name}: {exc}",
            file=sys.stderr,
        )
        return []
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


BUSINESS_SCENARIOS: dict[str, dict[str, Any]] = {
    "engineering": {
        "keywords": ("test", "lint", "repo", "import", "security"),
        "dashboard": "quality_overview",
        "helpers": (
            "Enable incremental scans to reduce CI time while preserving coverage.",
            "Prioritize recurring rule IDs in sprint hygiene goals.",
        ),
    },
    "api-operations": {
        "keywords": ("api", "http", "request", "response", "network", "timeout"),
        "dashboard": "reliability_scorecard",
        "helpers": (
            "Track error/warn split per endpoint to catch reliability regressions.",
            "Use diff-based fail gates for high-severity API findings.",
        ),
    },
    "compliance": {
        "keywords": ("secret", "auth", "token", "policy", "license", "privacy"),
        "dashboard": "compliance_posture",
        "helpers": (
            "Review suppressed findings weekly and enforce expiration windows.",
            "Map recurring policy failures to control IDs in governance reports.",
        ),
    },
}


def _tokenize_workflow_text(text: str) -> list[str]:
    lowered = text.lower()
    out: list[str] = []
    token = []
    for ch in lowered:
        if ch.isalnum() or ch in {"-", "_"}:
            token.append(ch)
        elif token:
            out.append("".join(token))
            token = []
    if token:
        out.append("".join(token))
    return out


def _findings(run: dict[str, Any]) -> list[dict[str, Any]]:
    raw = run.get("findings")
    if not isinstance(raw, list):
        return []
    return [x for x in raw if isinstance(x, dict)]


def _load_history_run_records(history_dir: Path) -> list[dict[str, Any]]:
    items = _history_runs(history_dir)
    runs: list[dict[str, Any]] = []

    for item in items:
        if not isinstance(item, dict):
            continue
        file_name = item.get("file")
        if not isinstance(file_name, str) or not file_name:
            continue
        run_path = history_dir / file_name
        if not run_path.exists():
            continue

        try:
            loaded = load_run_record(run_path)
        except (OSError, ValueError) as exc:
            print(
                f"warning: skipping unreadable history run {file_name}: {exc}",
                file=sys.stderr,
            )
            continue
        run: dict[str, Any] | None = None
        if isinstance(loaded, dict) and isinstance(loaded.get("run_record"), dict):
            rr = loaded["run_record"]
            run = rr if isinstance(rr, dict) else None
        elif isinstance(loaded, dict):
            run = loaded

        if run is None:
            continue

        sha = item.get("sha256")
        if isinstance(sha, str) and sha:
            run["_sha256"] = sha
        run["_file"] = file_name

        src = run.get("source")
        cap = src.get("captured_at") if isinstance(src, dict) else None
        if not cap:
            cap2 = item.get("captured_at")
            if isinstance(cap2, str) and cap2:
                if isinstance(src, dict):
                    src["captured_at"] = cap2
                else:
                    run["source"] = {"captured_at": cap2}

        runs.append(run)

    runs.sort(
        key=lambda r: (
            str((r.get("source") or {}).get("captured_at", ""))
            if isinstance(r.get("source"), dict)
            else "",
            str(r.get("_sha256") or ""),
        ),
    )
    return runs


def _detect_business_scenario(runs: list[dict[str, Any]]) -> str:
    scenario_scores = {name: 0 for name in BUSINESS_SCENARIOS}
    corpus: list[str] = []
    for run in runs:
        for finding in run.get("findings", []):
            if not isinstance(finding, dict):
                continue
            corpus.extend(
                [
                    str(finding.get("rule_id", "")),
                    str(finding.get("message", "")),
                    str(finding.get("path", "")),
                    " ".join(str(x) for x in (finding.get("tags") or [])),
                ]
            )

    tokens = _tokenize_workflow_text(" ".join(corpus))
    for scenario, config in BUSINESS_SCENARIOS.items():
        keywords = set(str(x) for x in config.get("keywords", ()))
        scenario_scores[scenario] = sum(1 for token in tokens if token in keywords)

    best = max(scenario_scores.items(), key=lambda x: (x[1], x[0]))
    return str(best[0]) if best[1] > 0 else "engineering"


def _top_recurring(
    findings: list[dict[str, Any]], key: str, limit: int = 5
) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for finding in findings:
        value = str(finding.get(key, "unknown"))
        counts[value] = counts.get(value, 0) + 1
    return sorted(counts.items(), key=lambda x: (-x[1], x[0]))[:limit]


def _severity_weight(level: str) -> int:
    return {"info": 1, "warn": 3, "error": 5}.get(level, 5)


class RiskHotspotRow(TypedDict):
    name: str
    count: int
    risk_score: int


def _top_risk_hotspots(
    findings: list[dict[str, Any]], key: str, *, limit: int = 5, min_occurrences: int = 1
) -> list[RiskHotspotRow]:
    stats: dict[str, dict[str, int]] = {}
    for finding in findings:
        entity = str(finding.get(key, "unknown"))
        severity = str(finding.get("severity", "error"))
        slot = stats.setdefault(entity, {"count": 0, "risk_score": 0})
        slot["count"] += 1
        slot["risk_score"] += _severity_weight(severity)

    rows: list[RiskHotspotRow] = [
        {"name": entity, "count": values["count"], "risk_score": values["risk_score"]}
        for entity, values in stats.items()
        if values["count"] >= max(min_occurrences, 1)
    ]
    rows.sort(key=lambda item: (-item["risk_score"], -item["count"], item["name"]))
    return rows[:limit]


def _trend_direction(series: list[int]) -> str:
    if len(series) < 2:
        return "stable"
    if series[-1] > series[0]:
        return "regressing"
    if series[-1] < series[0]:
        return "improving"
    return "stable"


def suggest_optimizations(
    history_dir: Path,
    requested_scenario: str,
    *,
    limit: int = 5,
    since: int | None = None,
    min_occurrences: int = 1,
) -> dict[str, Any]:
    runs = _load_history_run_records(history_dir)
    if since is not None:
        runs = runs[-max(since, 0) :]

    detected = _detect_business_scenario(runs)
    scenario = detected if requested_scenario == "auto" else requested_scenario
    config = BUSINESS_SCENARIOS.get(scenario, BUSINESS_SCENARIOS["engineering"])

    all_findings: list[dict[str, Any]] = []
    for run in runs:
        all_findings.extend(_findings(run))

    top_rules = _top_recurring(all_findings, "rule_id", limit=limit)
    top_paths = _top_recurring(all_findings, "path", limit=limit)
    severity_series = []
    for run in runs:
        counts = (run.get("aggregates") or {}).get("counts_by_severity") or {}
        error_count = int(counts.get("error", 0)) if isinstance(counts, dict) else 0
        warn_count = int(counts.get("warn", 0)) if isinstance(counts, dict) else 0
        severity_series.append(error_count + warn_count)

    risky_rules = _top_risk_hotspots(
        all_findings,
        "rule_id",
        limit=limit,
        min_occurrences=min_occurrences,
    )
    risky_paths = _top_risk_hotspots(
        all_findings,
        "path",
        limit=limit,
        min_occurrences=min_occurrences,
    )

    return {
        "detected_scenario": detected,
        "active_scenario": scenario,
        "dashboard_template": config["dashboard"],
        "recommendations": list(config["helpers"]),
        "top_rules": [{"rule_id": rule, "count": count} for rule, count in top_rules],
        "top_paths": [{"path": path, "count": count} for path, count in top_paths],
        "risk_hotspots": {
            "rules": [
                {
                    "rule_id": row["name"],
                    "count": row["count"],
                    "risk_score": row["risk_score"],
                }
                for row in risky_rules
            ],
            "paths": [
                {
                    "path": row["name"],
                    "count": row["count"],
                    "risk_score": row["risk_score"],
                }
                for row in risky_paths
            ],
        },
        "run_window": {"requested_since": since, "effective_runs": len(runs)},
        "trend": {
            "actionable_series": severity_series,
            "direction": _trend_direction(severity_series),
        },
        "runs_analyzed": len(runs),
    }


def _render_recommend_text(payload: dict[str, Any]) -> str:
    lines = [
        "# sdetkit workflow recommendations",
        "",
        f"- runs analyzed: {payload['runs_analyzed']}",
        f"- detected scenario: {payload['detected_scenario']}",
        f"- active scenario: {payload['active_scenario']}",
        f"- dashboard template: {payload['dashboard_template']}",
        f"- trend direction: {payload.get('trend', {}).get('direction', 'stable')}",
        "",
        "## Recommended helpers",
    ]
    for item in payload.get("recommendations", []):
        lines.append(f"- {item}")
    lines.extend(["", "## Top recurring rules"])
    for item in payload.get("top_rules", []):
        lines.append(f"- {item['rule_id']}: {item['count']}")
    lines.extend(["", "## Top recurring paths"])
    for item in payload.get("top_paths", []):
        lines.append(f"- {item['path']}: {item['count']}")
    lines.extend(["", "## Risk hotspots (weighted)"])
    for item in payload.get("risk_hotspots", {}).get("rules", []):
        lines.append(f"- rule {item['rule_id']}: score={item['risk_score']} count={item['count']}")
    lines.append("")
    return "\n".join(lines)


def _render_recommend_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# sdetkit workflow recommendations",
        "",
        f"- runs analyzed: {payload['runs_analyzed']}",
        f"- detected scenario: {payload['detected_scenario']}",
        f"- active scenario: {payload['active_scenario']}",
        f"- dashboard template: {payload['dashboard_template']}",
        f"- trend direction: {payload.get('trend', {}).get('direction', 'stable')}",
        "",
        "## Recommended helpers",
    ]
    recommendations = payload.get("recommendations", [])
    if not recommendations:
        lines.append("- none")
    else:
        for item in recommendations:
            lines.append(f"- {item}")

    lines.extend(["", "## Top recurring rules"])
    top_rules = payload.get("top_rules", [])
    if not top_rules:
        lines.append("- none")
    else:
        for item in top_rules:
            lines.append(f"- {item['rule_id']}: {item['count']}")

    lines.extend(["", "## Top recurring paths"])
    top_paths = payload.get("top_paths", [])
    if not top_paths:
        lines.append("- none")
    else:
        for item in top_paths:
            lines.append(f"- {item['path']}: {item['count']}")

    lines.extend(["", "## Risk hotspots (weighted rules)"])
    risky_rules = payload.get("risk_hotspots", {}).get("rules", [])
    if not risky_rules:
        lines.append("- none")
    else:
        for item in risky_rules:
            lines.append(f"- {item['rule_id']}: score={item['risk_score']} count={item['count']}")

    lines.extend(["", "## Risk hotspots (weighted paths)"])
    risky_paths = payload.get("risk_hotspots", {}).get("paths", [])
    if not risky_paths:
        lines.append("- none")
    else:
        for item in risky_paths:
            lines.append(f"- {item['path']}: score={item['risk_score']} count={item['count']}")
    lines.append("")
    return "\n".join(lines)


def build_dashboard(history_dir: Path, output: Path, fmt: str, since: int | None) -> None:
    runs = _load_history_run_records(history_dir)
    if since is not None:
        runs = runs[-since:]

    if not runs:
        content = "# sdetkit audit trends\n\nNo audit history found.\n"
        atomic_write_text(output, content)
        return

    totals: list[int] = []
    for r in runs:
        agg = r.get("aggregates")
        sev = agg.get("counts_by_severity") if isinstance(agg, dict) else None
        err = int(sev.get("error", 0)) if isinstance(sev, dict) else 0
        warn = int(sev.get("warn", 0)) if isinstance(sev, dict) else 0
        totals.append(err + warn)

    last = runs[-1]
    previous = runs[-2] if len(runs) > 1 else None
    delta = diff_runs(previous, last) if previous else None

    recurring_rules: dict[str, int] = {}
    recurring_paths: dict[str, int] = {}
    for run in runs:
        for finding in _findings(run):
            recurring_rules[str(finding.get("rule_id", "unknown"))] = (
                recurring_rules.get(str(finding.get("rule_id", "unknown")), 0) + 1
            )
            recurring_paths[str(finding.get("path", "."))] = (
                recurring_paths.get(str(finding.get("path", ".")), 0) + 1
            )

    top_rules = sorted(recurring_rules.items(), key=lambda x: (-x[1], x[0]))[:10]
    top_paths = sorted(recurring_paths.items(), key=lambda x: (-x[1], x[0]))[:10]

    latest_count = len(_findings(last))

    if fmt == "md":
        lines = [
            "# sdetkit audit trends",
            "",
            f"- runs: {len(runs)}",
            f"- latest actionable findings: {latest_count}",
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
        f"<p>Latest actionable findings: {latest_count}</p>",
        f"<div>{_sparkline(totals)}</div>",
    ]
    if delta is not None:
        lines.append(
            f"<p>Delta vs previous: NEW={delta['counts']['new']} RESOLVED={delta['counts']['resolved']}</p>"
        )

    lines.append("<h2>Top recurring rules</h2><table><tr><th>Rule</th><th>Count</th></tr>")
    for rule, count in top_rules:
        lines.append(f"<tr><td>{html.escape(str(rule))}</td><td>{count}</td></tr>")
    lines.append("</table><h2>Top paths</h2><table><tr><th>Path</th><th>Count</th></tr>")
    for path, count in top_paths:
        lines.append(f"<tr><td>{html.escape(str(path))}</td><td>{count}</td></tr>")
    lines.append("</table></body></html>\n")
    atomic_write_text(output, "".join(lines))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit report",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="Ingest, diff, and build deterministic report artifacts.",
    )
    sub = parser.add_subparsers(dest="report_cmd", required=True)

    ip = sub.add_parser("ingest", help="Ingest a run record into deterministic history index.")
    ip.add_argument("run_json")
    ip.add_argument("--history-dir", default=".sdetkit/audit-history")
    ip.add_argument("--label", default=None)

    dp = sub.add_parser(
        "diff", help="Diff two run records and optionally fail by severity threshold."
    )
    dp.add_argument("--from", dest="from_run", required=True)
    dp.add_argument("--to", dest="to_run", required=True)
    dp.add_argument("--format", choices=["text", "json", "md"], default="text")
    dp.add_argument("--fail-on", choices=["none", "warn", "error"], default="none")
    dp.add_argument("--limit-new", type=int, default=None)

    bp = sub.add_parser("build", help="Build HTML/Markdown trends dashboard from history.")
    bp.add_argument("--history-dir", default=".sdetkit/audit-history")
    bp.add_argument("--output", default="report.html")
    bp.add_argument("--format", choices=["html", "md"], default="html")
    bp.add_argument("--since", type=int, default=None)

    rp = sub.add_parser("recommend", help="Generate workflow recommendations from report history.")
    rp.add_argument("--history-dir", default=".sdetkit/audit-history")
    rp.add_argument("--scenario", choices=["auto", *sorted(BUSINESS_SCENARIOS)], default="auto")
    rp.add_argument("--format", choices=["text", "json", "md"], default="text")
    rp.add_argument("--limit", type=int, default=5)
    rp.add_argument("--since", type=int, default=None)
    rp.add_argument("--min-occurrences", type=int, default=1)

    ns = parser.parse_args(argv)

    try:
        if ns.report_cmd == "ingest":
            src = safe_path(Path.cwd(), ns.run_json, allow_absolute=True)
            history_dir = safe_path(Path.cwd(), ns.history_dir, allow_absolute=True)
            history_dir.mkdir(parents=True, exist_ok=True)
            run = load_run_record(src)
            digest = hashlib.sha256(canonical_json_bytes(run)).hexdigest()
            target = history_dir / f"{digest}.json"
            if not target.exists():
                atomic_write_text(target, canonical_json_dumps(run))

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
            payload = diff_runs(from_run, to_run, new_limit=ns.limit_new)
            if ns.format == "json":
                sys.stdout.write(canonical_json_dumps(payload))
            elif ns.format == "md":
                markdown_limit = ns.limit_new if ns.limit_new is not None else 10
                sys.stdout.write(_render_diff_markdown(payload, limit=markdown_limit))
            else:
                text_limit = ns.limit_new if ns.limit_new is not None else 10
                sys.stdout.write(_render_diff_text(payload, limit=text_limit))
            return 1 if _fail_count_at_or_above(payload, ns.fail_on) > 0 else 0

        if ns.report_cmd == "recommend":
            history_dir = safe_path(Path.cwd(), ns.history_dir, allow_absolute=True)
            payload = suggest_optimizations(
                history_dir,
                ns.scenario,
                limit=max(ns.limit, 1),
                since=ns.since,
                min_occurrences=max(ns.min_occurrences, 1),
            )
            if ns.format == "json":
                sys.stdout.write(canonical_json_dumps(payload))
            elif ns.format == "md":
                sys.stdout.write(_render_recommend_markdown(payload))
            else:
                sys.stdout.write(_render_recommend_text(payload))
            return 0

        history_dir = safe_path(Path.cwd(), ns.history_dir, allow_absolute=True)
        output = safe_path(Path.cwd(), ns.output, allow_absolute=True)
        build_dashboard(history_dir, output, ns.format, ns.since)
        return 0
    except (ValueError, OSError, SecurityError) as exc:
        message = str(exc).replace("\n", " ")
        print(f"report error: {message}", file=sys.stderr)
        return 2
