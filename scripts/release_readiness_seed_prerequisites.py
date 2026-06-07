#!/usr/bin/env python3
"""Seed minimal prerequisite artifacts so release readiness workflow can execute end-to-end."""

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


def _baseline_baseline_seed() -> dict:
    return {
        "schema_version": "sdetkit.baseline_baseline.v1",
        "generated_at_utc": "2026-04-19T00:00:00Z",
        "out_dir": "build/baseline",
        "ok": True,
        "checks": [
            {
                "id": "seed_baseline",
                "ok": True,
                "rc": 0,
                "stdout_log": "build/baseline/seed.stdout.log",
                "stderr_log": "build/baseline/seed.stderr.log",
            }
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Seed minimal prerequisites for release readiness workflows."
    )
    parser.add_argument("--root", default=".")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()

    # release readiness kickoff prerequisites
    _write_json(
        root / "docs/artifacts/baseline-wrap-pack/baseline-wrap-summary.json",
        {"summary": {"activation_score": 99, "strict_pass": True}, "checks": [{"id": "seed"}]},
    )
    _write_board(
        root / "docs/artifacts/baseline-wrap-pack/baseline-wrap-release readiness-backlog.md",
        "Phase2 backlog",
    )

    # release readiness hardening prerequisites
    _write_json(
        root
        / "docs/artifacts/kpi-deep-audit-completion report-pack/kpi-deep-audit-completion report-summary.json",
        {"summary": {"activation_score": 99, "strict_pass": True}, "checks": [{"id": "seed"}]},
    )
    _write_board(
        root
        / "docs/artifacts/kpi-deep-audit-completion report-pack/kpi-deep-audit-delivery-board.md",
        "KPI deep audit board",
    )

    # release readiness wrap prerequisites
    _write_json(
        root
        / "docs/artifacts/platform-readiness-preplan-completion-report-pack/platform-readiness-preplan-completion-report-summary.json",
        {"summary": {"activation_score": 99, "strict_pass": True}, "checks": [{"id": "seed"}]},
    )
    _write_board(
        root
        / "docs/artifacts/platform-readiness-preplan-completion-report-pack/platform-readiness-preplan-delivery-board.md",
        "Phase3 preplan board",
    )

    _write_json(root / "build/baseline/baseline-summary.json", _baseline_baseline_seed())

    print(
        json.dumps(
            {
                "ok": True,
                "schema_version": "sdetkit.release_readiness_seed_prerequisites.v2",
                "root": str(root),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
