#!/usr/bin/env python3
"""Persist Phase 1 baseline summary snapshots for Phase 3 trend comparisons."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _fingerprint(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _generated_tag(payload: dict[str, Any]) -> str:
    raw = str(payload.get("generated_at_utc", "")).strip() or datetime.now(UTC).isoformat()
    safe = raw.replace(":", "-").replace("+", "-").replace("Z", "")
    return safe


def _history_files(history_dir: Path) -> list[Path]:
    return sorted(
        path for path in history_dir.glob("phase1-baseline-summary-*.json") if path.is_file()
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", default="build/phase1-baseline/phase1-baseline-summary.json")
    parser.add_argument("--history-dir", default="build/phase1-baseline/history")
    parser.add_argument("--max-history", type=int, default=30)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)

    summary_path = Path(args.summary)
    payload = _load_json(summary_path)
    if not payload:
        out = {
            "ok": False,
            "schema_version": "sdetkit.phase3_baseline_history.v1",
            "reason": f"missing summary: {summary_path}",
            "history_dir": str(args.history_dir),
        }
        if args.format == "json":
            print(json.dumps(out, indent=2, sort_keys=True))
        else:
            print(f"phase3-baseline-history: FAIL ({out['reason']})")
        return 1

    history_dir = Path(args.history_dir)
    history_dir.mkdir(parents=True, exist_ok=True)

    current_fingerprint = _fingerprint(payload)
    existing = _history_files(history_dir)
    for item in existing:
        prior = _load_json(item)
        if prior and _fingerprint(prior) == current_fingerprint:
            out = {
                "ok": True,
                "schema_version": "sdetkit.phase3_baseline_history.v1",
                "summary": str(summary_path),
                "saved": False,
                "deduped": True,
                "history_dir": str(history_dir),
                "history_count": len(existing),
                "saved_path": str(item),
            }
            if args.format == "json":
                print(json.dumps(out, indent=2, sort_keys=True))
            else:
                print("phase3-baseline-history: OK (deduped)")
                print(f"- existing: {item}")
            return 0

    target = history_dir / f"phase1-baseline-summary-{_generated_tag(payload)}.json"
    suffix = 1
    while target.exists():
        target = history_dir / f"phase1-baseline-summary-{_generated_tag(payload)}-{suffix}.json"
        suffix += 1
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    history = _history_files(history_dir)
    while len(history) > max(1, args.max_history):
        old = history.pop(0)
        old.unlink(missing_ok=True)

    out = {
        "ok": True,
        "schema_version": "sdetkit.phase3_baseline_history.v1",
        "summary": str(summary_path),
        "saved": True,
        "deduped": False,
        "history_dir": str(history_dir),
        "history_count": len(_history_files(history_dir)),
        "saved_path": str(target),
    }
    if args.format == "json":
        print(json.dumps(out, indent=2, sort_keys=True))
    else:
        print("phase3-baseline-history: OK")
        print(f"- saved: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
