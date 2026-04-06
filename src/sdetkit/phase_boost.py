from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path


def build_phase_boost_payload(repository: str, start_date: str) -> dict:
    return {
        "repository": repository,
        "start_date": start_date,
        "duration_window": 90,
        "goal": "S-class production readiness",
        "phases": [
            {"phase": "Phase 1 - Baseline hardening", "days": 30},
            {"phase": "Phase 2 - Scale and automation", "days": 30},
            {"phase": "Phase 3 - Release excellence", "days": 30},
        ],
    }


def _render_markdown(payload: dict) -> str:
    lines = [f"# Phase boost plan for {payload['repository']}", "", payload["goal"], ""]
    for p in payload["phases"]:
        lines.append(f"- {p['phase']} ({p['days']} days)")
    return "\n".join(lines) + "\n"


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sdetkit phase-boost")
    p.add_argument("--repo-name", default="repo")
    p.add_argument("--start-date", default=date.today().isoformat())
    p.add_argument("--output", default=None)
    p.add_argument("--json-output", default=None)
    return p


def main(argv: list[str] | None = None) -> int:
    ns = _parser().parse_args(argv)
    payload = build_phase_boost_payload(ns.repo_name, ns.start_date)
    md = _render_markdown(payload)
    print(md, end="")
    if ns.output:
        Path(ns.output).write_text(md, encoding="utf-8")
    if ns.json_output:
        Path(ns.json_output).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return 0
