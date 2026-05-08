from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.adaptive.portfolio_rollup.v1"
SEVERITY_SCORE = {"high": 30, "medium": 18, "low": 8, "info": 3}
STATUS_RANK = {"needs_fix": 4, "needs_attention": 3, "monitor": 2, "clear": 1}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value.strip())
    return 0


def _safe(value: Any, limit: int = 240) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _repo_name(payload: dict[str, Any], path: Path | None = None) -> str:
    for key in ("repo", "repository", "repo_name"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    metadata = _as_dict(payload.get("metadata"))
    for key in ("repo", "repository", "repo_name"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    if path is not None:
        return path.parent.name or path.stem
    return "unknown"


def _diagnosis_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [_as_dict(item) for item in _as_list(payload.get("diagnoses"))]
    return [row for row in rows if row]


def _candidate_codes(row: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for item in _as_list(row.get("evidence")):
        text = str(item)
        if not text.startswith("candidate_scenarios="):
            continue
        for code in text.split("=", 1)[1].split(","):
            code = code.strip()
            if code and code not in out:
                out.append(code)
    return out


def _append_scenario(
    scenarios: dict[str, dict[str, Any]],
    *,
    code: str,
    title: str,
    repo: str,
    severity: str,
    confidence: str,
    repeat_count: int,
    risk_points: int,
    source: str,
) -> None:
    row = scenarios.setdefault(
        code,
        {
            "code": code,
            "title": _safe(title, 160),
            "repo_count": 0,
            "repos": [],
            "occurrences": 0,
            "candidate_mentions": 0,
            "severity_counts": {},
            "confidence_counts": {},
            "repeat_count": 0,
            "risk_points": 0,
            "source_counts": {},
        },
    )
    if repo not in row["repos"]:
        row["repos"].append(repo)
        row["repo_count"] = len(row["repos"])
    row["occurrences"] += 1
    if source == "candidate":
        row["candidate_mentions"] += 1
    row["repeat_count"] += max(0, repeat_count)
    row["risk_points"] += max(0, risk_points)
    row["severity_counts"][severity] = _as_int(row["severity_counts"].get(severity)) + 1
    row["confidence_counts"][confidence] = _as_int(row["confidence_counts"].get(confidence)) + 1
    row["source_counts"][source] = _as_int(row["source_counts"].get(source)) + 1


def _risk_points(payload: dict[str, Any], row: dict[str, Any]) -> int:
    severity = str(row.get("severity", "info"))
    repeat_count = _as_int(row.get("repeat_count"))
    return (
        SEVERITY_SCORE.get(severity, 3)
        + min(repeat_count, 5) * 2
        + min(
            _as_int(payload.get("risk_score")),
            100,
        )
        // 10
    )


def build_portfolio_rollup(
    payloads: Sequence[dict[str, Any]], paths: Sequence[Path] | None = None
) -> dict[str, Any]:
    path_list = list(paths or [])
    scenarios: dict[str, dict[str, Any]] = {}
    repo_status: dict[str, dict[str, Any]] = {}
    repo_risk: dict[str, int] = defaultdict(int)
    status_counts: Counter[str] = Counter()
    confidence_counts: Counter[str] = Counter()

    for index, payload in enumerate(payloads):
        path = path_list[index] if index < len(path_list) else None
        repo = _repo_name(payload, path)
        status = str(payload.get("status", "unknown"))
        status_counts[status] += 1
        confidence_counts[str(payload.get("confidence", "unknown"))] += 1
        repo_risk[repo] += _as_int(payload.get("risk_score"))
        repo_status.setdefault(
            repo,
            {
                "repo": repo,
                "artifact_count": 0,
                "max_status": "clear",
                "risk_score": 0,
                "diagnosis_count": 0,
            },
        )
        repo_status[repo]["artifact_count"] += 1
        repo_status[repo]["risk_score"] += _as_int(payload.get("risk_score"))
        repo_status[repo]["diagnosis_count"] += _as_int(payload.get("diagnosis_count"))
        if STATUS_RANK.get(status, 0) > STATUS_RANK.get(str(repo_status[repo]["max_status"]), 0):
            repo_status[repo]["max_status"] = status

        for row in _diagnosis_rows(payload):
            code = _safe(row.get("code") or "UNKNOWN", 80)
            risk_points = _risk_points(payload, row)
            _append_scenario(
                scenarios,
                code=code,
                title=str(row.get("title") or code),
                repo=repo,
                severity=str(row.get("severity", "info")),
                confidence=str(row.get("confidence", "unknown")),
                repeat_count=_as_int(row.get("repeat_count")),
                risk_points=risk_points,
                source="primary" if code else "unknown",
            )
            for candidate in _candidate_codes(row):
                _append_scenario(
                    scenarios,
                    code=candidate,
                    title=f"Candidate scenario {candidate}",
                    repo=repo,
                    severity="info",
                    confidence="candidate",
                    repeat_count=0,
                    risk_points=max(1, risk_points // 3),
                    source="candidate",
                )

    top_risk = sorted(
        scenarios.values(),
        key=lambda row: (
            -_as_int(row.get("risk_points")),
            -_as_int(row.get("repo_count")),
            str(row.get("code")),
        ),
    )
    repo_rows = sorted(
        repo_status.values(),
        key=lambda row: (-_as_int(row.get("risk_score")), str(row.get("repo"))),
    )
    needs_fix_repos = [row["repo"] for row in repo_rows if row.get("max_status") == "needs_fix"]
    portfolio_risk_score = min(100, sum(repo_risk.values()))
    recommendation = "NO_SHIP" if needs_fix_repos else "SHIP_WITH_CONTROLS" if top_risk else "SHIP"

    return {
        "schema_version": SCHEMA_VERSION,
        "ok": not needs_fix_repos,
        "recommendation": recommendation,
        "artifact_count": len(payloads),
        "repo_count": len(repo_rows),
        "portfolio_risk_score": portfolio_risk_score,
        "status_counts": dict(sorted(status_counts.items())),
        "confidence_counts": dict(sorted(confidence_counts.items())),
        "needs_fix_repos": needs_fix_repos,
        "top_risk_scenarios": top_risk[:10],
        "recurrence_by_repo": repo_rows,
        "next_owner_action": _next_owner_action(recommendation, top_risk, needs_fix_repos),
    }


def _next_owner_action(
    recommendation: str, top_risk: Sequence[dict[str, Any]], needs_fix_repos: Sequence[str]
) -> str:
    if recommendation == "SHIP":
        return "No adaptive diagnosis risks were present; keep collecting portfolio evidence."
    if needs_fix_repos:
        repo_list = ", ".join(needs_fix_repos[:5])
        scenario = top_risk[0].get("code") if top_risk else "UNKNOWN"
        return f"Block release signoff for {repo_list}; start with top scenario {scenario}."
    scenario = top_risk[0].get("code") if top_risk else "UNKNOWN"
    return (
        f"Ship only with controls and review recurring scenario {scenario} before the next batch."
    )


def render_text(payload: dict[str, Any]) -> str:
    lines = [
        f"schema_version={payload['schema_version']}",
        f"ok={str(payload['ok']).lower()}",
        f"recommendation={payload['recommendation']}",
        f"repo_count={payload['repo_count']}",
        f"artifact_count={payload['artifact_count']}",
        f"portfolio_risk_score={payload['portfolio_risk_score']}",
    ]
    for row in _as_list(payload.get("top_risk_scenarios"))[:5]:
        item = _as_dict(row)
        lines.append(
            "scenario="
            f"{item.get('code')}|risk={item.get('risk_points')}|repos={item.get('repo_count')}"
        )
    lines.append(f"next_owner_action={payload['next_owner_action']}")
    return "\n".join(lines) + "\n"


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Adaptive Portfolio Rollup",
        "",
        f"- Recommendation: `{payload['recommendation']}`",
        f"- OK: `{str(payload['ok']).lower()}`",
        f"- Portfolio risk score: `{payload['portfolio_risk_score']}`",
        f"- Repositories: `{payload['repo_count']}`",
        f"- Artifacts: `{payload['artifact_count']}`",
        "",
        "## Top-risk scenarios",
        "",
        "| Scenario | Risk points | Repos | Occurrences | Candidate mentions |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in _as_list(payload.get("top_risk_scenarios"))[:10]:
        item = _as_dict(row)
        lines.append(
            f"| `{item.get('code')}` | {item.get('risk_points')} | {item.get('repo_count')} | "
            f"{item.get('occurrences')} | {item.get('candidate_mentions')} |"
        )
    if not _as_list(payload.get("top_risk_scenarios")):
        lines.append("| none | 0 | 0 | 0 | 0 |")
    lines += [
        "",
        "## Recurrence by repo",
        "",
        "| Repo | Max status | Risk score | Diagnosis count | Artifacts |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for row in _as_list(payload.get("recurrence_by_repo")):
        item = _as_dict(row)
        lines.append(
            f"| `{item.get('repo')}` | `{item.get('max_status')}` | {item.get('risk_score')} | "
            f"{item.get('diagnosis_count')} | {item.get('artifact_count')} |"
        )
    lines += ["", "## Next owner action", "", str(payload.get("next_owner_action", "")), ""]
    return "\n".join(lines)


def _load_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.adaptive_portfolio_rollup")
    parser.add_argument("diagnosis_json", nargs="+", help="Adaptive diagnosis JSON artifact(s)")
    parser.add_argument("--format", choices=["text", "json", "md"], default="text")
    parser.add_argument("--out", default="")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv if argv is not None else sys.argv[1:]))
    paths = [Path(item) for item in args.diagnosis_json]
    try:
        payload = build_portfolio_rollup([_load_payload(path) for path in paths], paths)
        if args.format == "json":
            rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        elif args.format == "md":
            rendered = render_markdown(payload) + "\n"
        else:
            rendered = render_text(payload)
        if args.out:
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
