from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class Snapshot:
    captured_at: str
    decision: str
    ok: bool
    selected_python: str
    failed_steps: list[str]
    step_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "captured_at": self.captured_at,
            "decision": self.decision,
            "ok": self.ok,
            "selected_python": self.selected_python,
            "failed_steps": self.failed_steps,
            "step_count": self.step_count,
        }


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("first-proof summary must be a JSON object")
    return payload


def _load_db(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _append_db(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")


def _build_rollup(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    ship = sum(1 for row in rows if row.get("decision") == "SHIP")
    no_ship = sum(1 for row in rows if row.get("decision") == "NO-SHIP")
    ship_rate = (ship / total) if total else 0.0

    failed_counts: dict[str, int] = {}
    for row in rows:
        failed = row.get("failed_steps")
        if not isinstance(failed, list):
            continue
        for step in failed:
            if isinstance(step, str):
                failed_counts[step] = failed_counts.get(step, 0) + 1

    top_failed = sorted(failed_counts.items(), key=lambda kv: kv[1], reverse=True)[:5]
    adaptive_actions: list[str] = []
    if failed_counts.get("gate-fast", 0) > 0:
        adaptive_actions.append(
            "Prioritize adaptive reviewer probes on fast-gate blockers and map contradictions to failing signals."
        )
    if failed_counts.get("gate-release", 0) > 0:
        adaptive_actions.append(
            "Strengthen release-readiness adaptive checks and enforce pre-merge review recommendations."
        )
    if ship_rate < 0.5:
        adaptive_actions.append(
            "Increase adaptive reviewer cadence (daily) until SHIP rate stabilizes above 50%."
        )
    if not adaptive_actions:
        adaptive_actions.append("Maintain weekly adaptive reviewer refresh and drift monitoring.")

    return {
        "schema_version": "sdetkit.first-proof-learning-rollup.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "summary": {
            "total_runs": total,
            "ship_runs": ship,
            "no_ship_runs": no_ship,
            "ship_rate": ship_rate,
            "top_failed_steps": [{"step": k, "count": v} for k, v in top_failed],
        },
        "adaptive_reviewer": {
            "mode": "parallel-learning",
            "actions": adaptive_actions,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Append first-proof summary into learning DB and emit adaptive rollup."
    )
    parser.add_argument(
        "--summary", type=Path, default=Path("build/first-proof/first-proof-summary.json")
    )
    parser.add_argument(
        "--db", type=Path, default=Path("build/first-proof/first-proof-learning-db.jsonl")
    )
    parser.add_argument(
        "--rollup-out",
        type=Path,
        default=Path("build/first-proof/first-proof-learning-rollup.json"),
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    summary = _read_json(args.summary)
    snapshot = Snapshot(
        captured_at=datetime.now(UTC).isoformat(),
        decision=str(summary.get("decision", "NO-SHIP")),
        ok=bool(summary.get("ok", False)),
        selected_python=str(summary.get("selected_python", "unknown")),
        failed_steps=[s for s in summary.get("failed_steps", []) if isinstance(s, str)],
        step_count=len(summary.get("steps", [])) if isinstance(summary.get("steps"), list) else 0,
    )

    row = snapshot.to_dict()
    _append_db(args.db, row)
    rows = _load_db(args.db)
    rollup = _build_rollup(rows)

    args.rollup_out.parent.mkdir(parents=True, exist_ok=True)
    args.rollup_out.write_text(
        json.dumps(rollup, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    result = {
        "ok": True,
        "db": str(args.db),
        "rollup": str(args.rollup_out),
        "total_runs": rollup["summary"]["total_runs"],
        "ship_rate": rollup["summary"]["ship_rate"],
    }

    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"first-proof learning db updated: {args.db}")
        print(f"first-proof rollup: {args.rollup_out}")
        print(f"total runs={result['total_runs']} ship_rate={result['ship_rate']:.2f}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
