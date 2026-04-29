from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Render compact first-proof execution report.")
    p.add_argument("--artifact-dir", default="build/first-proof")
    p.add_argument("--onboarding", default="build/onboarding-next.json")
    p.add_argument("--out-json", default="build/first-proof/execution-report.json")
    p.add_argument("--out-md", default="build/first-proof/execution-report.md")
    p.add_argument("--format", choices=("text", "json"), default="text")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    root = Path(args.artifact_dir)
    summary = _load(root / "first-proof-summary.json")
    health = _load(root / "health-score.json")
    trend = _load(root / "ops-bundle-contract-trend.json")
    onboarding = _load(Path(args.onboarding))

    payload = {
        "schema_version": "1.0.0",
        "decision": summary.get("decision", "NO-DATA"),
        "health_score": health.get("score"),
        "health_decision": health.get("decision"),
        "ops_contract_pass_rate": trend.get("recent_pass_rate"),
        "onboarding_decision": onboarding.get("decision"),
        "next_tasks": onboarding.get("tasks", []),
    }

    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(f"{json.dumps(payload, indent=2, sort_keys=True)}\n", encoding="utf-8")

    md = [
        "# First-Proof Execution Report",
        "",
        f"- decision: **{payload['decision']}**",
        f"- health score: **{payload['health_score']}** ({payload['health_decision']})",
        f"- ops contract pass-rate: **{payload['ops_contract_pass_rate']}**",
        f"- onboarding decision: **{payload['onboarding_decision']}**",
        "",
        "## Next Tasks",
    ]
    md.extend([f"- `{task}`" for task in payload["next_tasks"]])
    Path(args.out_md).write_text("\n".join(md) + "\n", encoding="utf-8")

    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"execution-report: decision={payload['decision']} health={payload['health_score']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
