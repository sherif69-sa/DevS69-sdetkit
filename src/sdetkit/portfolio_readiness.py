from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _risk_from_repo_signals(
    ship_summary: dict[str, Any] | None, enterprise_summary: dict[str, Any] | None
) -> dict[str, Any]:
    ship = (ship_summary or {}).get("summary", {})
    enterprise_contract = (enterprise_summary or {}).get("upgrade_contract", {})
    enterprise_summary_block = (enterprise_summary or {}).get("summary", {})

    blockers = ship.get("blockers", []) if isinstance(ship, dict) else []
    blocker_count = len(blockers) if isinstance(blockers, list) else 0
    decision = ship.get("decision", "unknown") if isinstance(ship, dict) else "unknown"
    enterprise_risk_band = (
        enterprise_contract.get("risk_band", "unknown")
        if isinstance(enterprise_contract, dict)
        else "unknown"
    )

    decision_penalty = 0 if decision == "go" else 40
    blocker_penalty = min(40, blocker_count * 10)
    risk_band_penalty = {"low": 0, "medium": 15, "high": 30}.get(str(enterprise_risk_band), 10)
    enterprise_score_penalty = max(0, 100 - int(enterprise_summary_block.get("score", 0))) // 4
    risk_score = min(100, decision_penalty + blocker_penalty + risk_band_penalty + enterprise_score_penalty)

    if risk_score >= 70:
        priority = "critical"
    elif risk_score >= 40:
        priority = "high"
    elif risk_score >= 20:
        priority = "medium"
    else:
        priority = "low"

    return {
        "risk_score": risk_score,
        "priority": priority,
        "decision": decision,
        "blocker_count": blocker_count,
        "enterprise_risk_band": enterprise_risk_band,
    }


def build_portfolio_readiness(rows: list[dict[str, Any]]) -> dict[str, Any]:
    repo_rows: list[dict[str, Any]] = []
    for row in rows:
        repo = str(row.get("repo", "unknown"))
        ship_summary = row.get("ship_summary")
        enterprise_summary = row.get("enterprise_summary")
        risk = _risk_from_repo_signals(ship_summary, enterprise_summary)
        repo_rows.append(
            {
                "repo": repo,
                **risk,
            }
        )

    repo_rows.sort(key=lambda r: r["risk_score"], reverse=True)
    avg_risk = round(
        sum(int(r["risk_score"]) for r in repo_rows) / len(repo_rows), 2
    ) if repo_rows else 0.0
    critical = [r for r in repo_rows if r["priority"] == "critical"]
    high = [r for r in repo_rows if r["priority"] == "high"]
    go_count = sum(1 for r in repo_rows if r["decision"] == "go")

    return {
        "summary": {
            "repo_count": len(repo_rows),
            "average_risk_score": avg_risk,
            "critical_count": len(critical),
            "high_count": len(high),
            "go_count": go_count,
            "no_go_count": len(repo_rows) - go_count,
        },
        "repos": repo_rows,
        "top_risks": repo_rows[:5],
    }


def _load_manifest(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("manifest must be a JSON array")

    rows: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        ship_path = item.get("ship_summary")
        enterprise_path = item.get("enterprise_summary")
        row: dict[str, Any] = {"repo": item.get("repo", "unknown")}
        row["ship_summary"] = _load_json(Path(ship_path)) if ship_path else None
        row["enterprise_summary"] = _load_json(Path(enterprise_path)) if enterprise_path else None
        rows.append(row)
    return rows


def _render_text(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "portfolio-readiness",
        f"repos: {summary['repo_count']}",
        f"average_risk_score: {summary['average_risk_score']}",
        f"critical: {summary['critical_count']}",
        f"high: {summary['high_count']}",
        "",
        "top_risks:",
    ]
    for row in payload.get("top_risks", []):
        lines.append(
            f"- {row['repo']}: risk={row['risk_score']} priority={row['priority']} decision={row['decision']}"
        )
    return "\n".join(lines) + "\n"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m sdetkit portfolio-readiness",
        description="Aggregate ship/enterprise readiness contracts across repositories.",
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--strict", action="store_true", help="Exit non-zero if any critical repo exists.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    rows = _load_manifest(args.manifest)
    payload = build_portfolio_readiness(rows)

    if args.out:
        args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    if args.format == "json":
        print(json.dumps(payload, indent=2))
    else:
        print(_render_text(payload), end="")

    if args.strict and payload["summary"]["critical_count"] > 0:
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
