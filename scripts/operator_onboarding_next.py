from __future__ import annotations

import argparse
import json
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Generate a practical onboarding follow-up plan.")
    p.add_argument("--summary", default="build/first-proof/first-proof-summary.json")
    p.add_argument("--out-json", default="build/onboarding-next.json")
    p.add_argument("--out-md", default="build/onboarding-next.md")
    p.add_argument("--format", choices=("text", "json"), default="text")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    summary_path = Path(args.summary)
    tasks: list[str]

    if not summary_path.exists():
        tasks = [
            "make first-proof-local",
            "make first-proof-verify-local",
            "make upgrade-next",
        ]
        decision = "BOOTSTRAP"
    else:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if summary.get("ok"):
            tasks = [
                "make ops-now-lite",
                "make ops-next",
                "make plan-status",
            ]
            decision = "ADVANCE"
        else:
            tasks = [
                "make doctor-remediate",
                "make first-proof-local",
                "make first-proof-freshness",
            ]
            decision = "REMEDIATE"

    payload = {"decision": decision, "tasks": tasks, "source_summary": str(summary_path)}
    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(f"{json.dumps(payload, indent=2, sort_keys=True)}\n", encoding="utf-8")

    md = ["# Onboarding Next", "", f"- decision: **{decision}**", "", "## Next tasks"]
    md.extend([f"- `{task}`" for task in tasks])
    Path(args.out_md).write_text("\n".join(md) + "\n", encoding="utf-8")

    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"onboarding-next: decision={decision} tasks={len(tasks)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
