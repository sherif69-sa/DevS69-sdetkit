#!/usr/bin/env python3
"""Seed minimal prerequisite artifacts so Phase 2 workflow can execute end-to-end."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_board(path: Path, title: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# {title}",
        "- [ ] item-1",
        "- [ ] item-2",
        "- [ ] item-3",
        "- [ ] item-4",
        "- [ ] item-5",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")




def _phase1_baseline_seed() -> dict:
    return {
        "schema_version": "sdetkit.phase1_baseline.v1",
        "generated_at_utc": "2026-04-19T00:00:00Z",
        "out_dir": "build/phase1-baseline",
        "ok": True,
        "checks": [
            {
                "id": "seed_baseline",
                "ok": True,
                "rc": 0,
                "stdout_log": "build/phase1-baseline/seed.stdout.log",
                "stderr_log": "build/phase1-baseline/seed.stderr.log",
            }
        ],
    }

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed minimal prerequisites for phase2 workflows.")
    parser.add_argument("--root", default=".")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()

    # phase2 kickoff prerequisites
    _write_json(
        root / "docs/artifacts/phase1-wrap-pack/phase1-wrap-summary.json",
        {"summary": {"activation_score": 99, "strict_pass": True}, "checks": [{"id": "seed"}]},
    )
    _write_board(root / "docs/artifacts/phase1-wrap-pack/phase1-wrap-phase2-backlog.md", "Phase2 backlog")

    # phase2 hardening prerequisites
    _write_json(
        root / "docs/artifacts/kpi-deep-audit-closeout-pack/kpi-deep-audit-closeout-summary.json",
        {"summary": {"activation_score": 99, "strict_pass": True}, "checks": [{"id": "seed"}]},
    )
    _write_board(
        root / "docs/artifacts/kpi-deep-audit-closeout-pack/kpi-deep-audit-delivery-board.md",
        "KPI deep audit board",
    )

    # phase2 wrap prerequisites
    _write_json(
        root / "docs/artifacts/phase3-preplan-closeout-pack/phase3-preplan-closeout-summary.json",
        {"summary": {"activation_score": 99, "strict_pass": True}, "checks": [{"id": "seed"}]},
    )
    _write_board(
        root / "docs/artifacts/phase3-preplan-closeout-pack/phase3-preplan-delivery-board.md",
        "Phase3 preplan board",
    )

    _write_json(root / "build/phase1-baseline/phase1-baseline-summary.json", _phase1_baseline_seed())

    print(
        json.dumps(
            {
                "ok": True,
                "schema_version": "sdetkit.phase2_seed_prerequisites.v2",
                "root": str(root),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
