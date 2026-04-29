from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Render consolidated first-proof dashboard artifacts.")
    p.add_argument("--artifact-dir", default="build/first-proof")
    p.add_argument("--onboarding", default="build/onboarding-next.json")
    p.add_argument("--out-json", default="build/first-proof/dashboard.json")
    p.add_argument("--out-md", default="build/first-proof/dashboard.md")
    p.add_argument("--format", choices=("text", "json"), default="text")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    root = Path(args.artifact_dir)
    summary = _load(root / "first-proof-summary.json")
    health = _load(root / "health-score.json")
    trend = _load(root / "ops-bundle-contract-trend.json")
    exec_contract = _load(root / "execution-contract.json")
    followup = _load(root / "followup-ready.json")
    onboarding = _load(Path(args.onboarding))

    payload = {
        "schema_version": "1.0.0",
        "decision": summary.get("decision", "NO-DATA"),
        "health_score": health.get("score"),
        "health_decision": health.get("decision"),
        "trend_pass_rate": trend.get("recent_pass_rate"),
        "branch_pass_rate": trend.get("branch_recent_pass_rate"),
        "execution_contract_ok": exec_contract.get("ok"),
        "followup_ready": followup.get("ok"),
        "onboarding_decision": onboarding.get("decision"),
        "next_tasks": onboarding.get("tasks", []),
    }

    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(f"{json.dumps(payload, indent=2, sort_keys=True)}\n", encoding="utf-8")

    lines = [
        "# First-Proof Dashboard",
        "",
        f"- decision: **{payload['decision']}**",
        f"- health: **{payload['health_score']}** ({payload['health_decision']})",
        f"- trend pass rate: **{payload['trend_pass_rate']}**",
        f"- branch pass rate: **{payload['branch_pass_rate']}**",
        f"- execution contract ok: **{payload['execution_contract_ok']}**",
        f"- follow-up ready: **{payload['followup_ready']}**",
        f"- onboarding decision: **{payload['onboarding_decision']}**",
        "",
        "## Next Tasks",
    ]
    lines.extend([f"- `{task}`" for task in payload["next_tasks"]])
    Path(args.out_md).write_text("\n".join(lines) + "\n", encoding="utf-8")

    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"first-proof-dashboard: decision={payload['decision']} health={payload['health_score']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
