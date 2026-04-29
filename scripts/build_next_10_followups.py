from __future__ import annotations

import argparse
import json
from pathlib import Path


FOLLOWUPS = [
    "Automate first-proof artifact retention cleanup with explicit TTL policy.",
    "Add CI job to publish execution-report.md and upgrade-status-line.txt as artifacts.",
    "Add failure taxonomy tags to doctor-remediate outputs for better routing.",
    "Track median time-to-remediate from followup-ready history.",
    "Add weekly trend markdown report for ops-bundle contract pass rate.",
    "Introduce per-branch trend splits (main vs feature branches).",
    "Add schema versioning + schema contract tests for all new first-proof artifacts.",
    "Expose `make first-proof-dashboard` to render consolidated summary bundle.",
    "Add changelog automation for follow-up workflow improvements.",
    "Create a release-readiness score threshold gate configurable by profile.",
]


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Build a concrete next-10 follow-up plan.")
    p.add_argument("--out-json", default="build/first-proof/next-10-followups.json")
    p.add_argument("--out-md", default="docs/next-10-followups.md")
    p.add_argument("--format", choices=("text", "json"), default="text")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    items = [
        {"id": i + 1, "title": title, "status": "pending"} for i, title in enumerate(FOLLOWUPS)
    ]
    payload = {"count": len(items), "items": items}

    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(f"{json.dumps(payload, indent=2, sort_keys=True)}\n", encoding="utf-8")

    md_lines = [
        "# Next 10 Follow-ups",
        "",
        "Planned follow-ups to continue polishing the upgrade lane.",
        "",
    ]
    for item in items:
        md_lines.append(f"{item['id']}. [ ] {item['title']}")
    Path(args.out_md).write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"next-10-followups: count={len(items)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
