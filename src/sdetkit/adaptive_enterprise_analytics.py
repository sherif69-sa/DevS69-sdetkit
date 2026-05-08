from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.adaptive.enterprise_analytics.v1"
TERMINAL_PROOF_OUTCOMES = {"proof_passed", "proof_failed"}
CLOSED_OUTCOMES = TERMINAL_PROOF_OUTCOMES | {"reverted", "rejected"}
PENDING_OUTCOMES = {"planned", "applied"}


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


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL at line {line_number}: {exc}") from exc
        if isinstance(payload, dict):
            records.append(payload)
    return records


def _record_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("source_path", "")),
        str(row.get("plan_kind", "unknown")),
        str(row.get("source_code", "UNKNOWN")),
        str(row.get("action_type", "unknown")),
    )


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _seconds_between(start: datetime, end: datetime) -> float | None:
    if start.tzinfo is None and end.tzinfo is not None:
        end = end.replace(tzinfo=None)
    elif start.tzinfo is not None and end.tzinfo is None:
        start = start.replace(tzinfo=None)
    delta = (end - start).total_seconds()
    if delta < 0:
        return None
    return delta


def _portfolio_source_codes(portfolio: dict[str, Any]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for row in _as_list(portfolio.get("top_risk_scenarios")):
        item = _as_dict(row)
        code = str(item.get("code", "UNKNOWN") or "UNKNOWN")
        counter[code] += max(1, _as_int(item.get("occurrences")))
    return counter


def _top_risky_repos(portfolio: dict[str, Any]) -> list[dict[str, Any]]:
    repos: list[dict[str, Any]] = []
    for row in _as_list(portfolio.get("recurrence_by_repo")):
        item = _as_dict(row)
        repo = str(item.get("repo", "unknown") or "unknown")
        repos.append(
            {
                "repo": repo,
                "risk_score": _as_int(item.get("risk_score")),
                "max_status": str(item.get("max_status", "unknown")),
                "diagnosis_count": _as_int(item.get("diagnosis_count")),
                "artifact_count": _as_int(item.get("artifact_count")),
            }
        )
    return sorted(repos, key=lambda row: (-_as_int(row.get("risk_score")), str(row.get("repo"))))[:10]


def _proof_metrics(records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    outcomes = Counter(str(row.get("outcome", "unknown")) for row in records)
    source_codes = Counter(str(row.get("source_code", "UNKNOWN") or "UNKNOWN") for row in records)
    terminal_by_key: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    pending_records: list[dict[str, Any]] = []
    proof_durations: list[float] = []

    for row in records:
        outcome = str(row.get("outcome", "unknown"))
        key = _record_key(row)
        if outcome in CLOSED_OUTCOMES:
            terminal_by_key.setdefault(key, []).append(row)
        if outcome in PENDING_OUTCOMES:
            pending_records.append(row)

    for row in pending_records:
        key = _record_key(row)
        start = _parse_datetime(row.get("recorded_at"))
        terminals = terminal_by_key.get(key, [])
        if start is not None:
            candidate_seconds = []
            for terminal in terminals:
                if str(terminal.get("outcome")) not in TERMINAL_PROOF_OUTCOMES:
                    continue
                end = _parse_datetime(terminal.get("recorded_at"))
                if end is None:
                    continue
                seconds = _seconds_between(start, end)
                if seconds is not None:
                    candidate_seconds.append(seconds)
            if candidate_seconds:
                proof_durations.append(min(candidate_seconds))

    missing_proof = [
        row
        for row in pending_records
        if not any(str(item.get("outcome")) in CLOSED_OUTCOMES for item in terminal_by_key.get(_record_key(row), []))
    ]
    remediation_decision_count = len(pending_records)
    proof_passed_count = outcomes.get("proof_passed", 0)
    proof_failed_count = outcomes.get("proof_failed", 0)
    successful_closed_count = sum(
        1
        for key, terminals in terminal_by_key.items()
        if any(str(row.get("outcome")) == "proof_passed" for row in terminals)
        and any(_record_key(pending) == key for pending in pending_records)
    )
    return {
        "record_count": len(records),
        "outcomes": dict(sorted(outcomes.items())),
        "remediation_decision_count": remediation_decision_count,
        "proof_passed_count": proof_passed_count,
        "proof_failed_count": proof_failed_count,
        "missing_proof_count": len(missing_proof),
        "remediation_success_rate": _rate(successful_closed_count, remediation_decision_count),
        "missing_proof_rate": _rate(len(missing_proof), remediation_decision_count),
        "failed_proof_rate": _rate(proof_failed_count, max(1, proof_passed_count + proof_failed_count)),
        "mean_time_to_proof_seconds": round(sum(proof_durations) / len(proof_durations), 2)
        if proof_durations
        else None,
        "proof_duration_sample_count": len(proof_durations),
        "source_codes": source_codes,
    }


def build_enterprise_analytics(
    portfolio: dict[str, Any], fix_audit_records: Sequence[dict[str, Any]]
) -> dict[str, Any]:
    proof = _proof_metrics(fix_audit_records)
    portfolio_counter = _portfolio_source_codes(portfolio)
    source_codes = Counter(proof.pop("source_codes"))
    source_codes.update(portfolio_counter)
    top_recurring_source_codes = [
        {"code": code, "count": count} for code, count in source_codes.most_common(10)
    ]
    top_risky_repos = _top_risky_repos(portfolio)
    portfolio_recommendation = str(portfolio.get("recommendation", "UNKNOWN"))
    if proof["proof_failed_count"] > 0 or portfolio_recommendation == "NO_SHIP":
        recommendation = "NO_SHIP"
        next_owner_action = "Block release signoff; resolve failed proof or top portfolio risk first."
    elif proof["missing_proof_count"] > 0 or portfolio_recommendation == "SHIP_WITH_CONTROLS":
        recommendation = "SHIP_WITH_CONTROLS"
        next_owner_action = "Ship only with explicit controls; collect missing proof and review top recurring sources."
    else:
        recommendation = "SHIP"
        next_owner_action = "Proof and portfolio signals are complete; continue collecting analytics evidence."
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": recommendation != "NO_SHIP",
        "recommendation": recommendation,
        "next_owner_action": next_owner_action,
        "portfolio": {
            "schema_version": str(portfolio.get("schema_version", "unknown")),
            "recommendation": portfolio_recommendation,
            "repo_count": _as_int(portfolio.get("repo_count")),
            "artifact_count": _as_int(portfolio.get("artifact_count")),
            "portfolio_risk_score": _as_int(portfolio.get("portfolio_risk_score")),
        },
        "metrics": proof,
        "top_recurring_source_codes": top_recurring_source_codes,
        "top_risky_repos": top_risky_repos,
    }


def render_text(payload: dict[str, Any]) -> str:
    metrics = _as_dict(payload.get("metrics"))
    portfolio = _as_dict(payload.get("portfolio"))
    lines = [
        f"schema_version={payload['schema_version']}",
        f"ok={str(payload['ok']).lower()}",
        f"recommendation={payload['recommendation']}",
        f"repo_count={portfolio.get('repo_count', 0)}",
        f"portfolio_risk_score={portfolio.get('portfolio_risk_score', 0)}",
        f"remediation_success_rate={metrics.get('remediation_success_rate', 0.0)}",
        f"missing_proof_rate={metrics.get('missing_proof_rate', 0.0)}",
        f"failed_proof_rate={metrics.get('failed_proof_rate', 0.0)}",
        f"mean_time_to_proof_seconds={metrics.get('mean_time_to_proof_seconds')}",
    ]
    for row in _as_list(payload.get("top_recurring_source_codes"))[:5]:
        item = _as_dict(row)
        lines.append(f"source_code={item.get('code')}|count={item.get('count')}")
    for row in _as_list(payload.get("top_risky_repos"))[:5]:
        item = _as_dict(row)
        lines.append(f"repo={item.get('repo')}|risk={item.get('risk_score')}|status={item.get('max_status')}")
    lines.append(f"next_owner_action={payload['next_owner_action']}")
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.adaptive_enterprise_analytics")
    parser.add_argument("--portfolio", required=True, help="Adaptive portfolio rollup JSON artifact")
    parser.add_argument("--fix-audit", required=True, help="Adaptive fix-audit JSONL records")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--out", default="")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv if argv is not None else sys.argv[1:]))
    try:
        payload = build_enterprise_analytics(
            _load_json(Path(args.portfolio)), read_jsonl(Path(args.fix_audit))
        )
        rendered = (
            json.dumps(payload, indent=2, sort_keys=True) + "\n"
            if args.format == "json"
            else render_text(payload)
        )
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
