from __future__ import annotations

import argparse
import json
from pathlib import Path

HINTS = {
    "gate-fast": {
        "why": "Fast gate failed; repo may violate baseline quality or policy checks.",
        "likely_causes": ["lint/test contract failures", "environment drift"],
        "first_fix_step": "make test-bootstrap",
        "next_commands": ["make test-bootstrap", "make first-proof-local"],
        "tags": ["quality", "baseline", "gating"],
    },
    "gate-release": {
        "why": "Release gate failed; release readiness policy is not satisfied.",
        "likely_causes": ["missing evidence artifacts", "release policy violation"],
        "first_fix_step": "python -m sdetkit gate release --format json",
        "next_commands": ["make release-room-fast", "make first-proof-local"],
        "tags": ["release", "policy", "readiness"],
    },
    "doctor": {
        "why": "Doctor checks failed; deterministic health checks found actionable issues.",
        "likely_causes": ["repo hygiene/policy drift", "missing expected files or metadata"],
        "first_fix_step": "python -m sdetkit doctor --format json --out build/doctor.json",
        "next_commands": ["python -m sdetkit doctor", "make merge-ready"],
        "tags": ["doctor", "hygiene", "contracts"],
    },
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate top remediation actions from first-proof results.")
    parser.add_argument("--summary", default="build/first-proof/first-proof-summary.json")
    parser.add_argument("--out-json", default="build/first-proof/doctor-remediate.json")
    parser.add_argument("--out-md", default="build/first-proof/doctor-remediate.md")
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    summary = json.loads(Path(args.summary).read_text(encoding="utf-8"))
    failed_steps = list(summary.get("failed_steps") or [])

    actions = []
    for step in failed_steps[: args.limit]:
        hint = HINTS.get(step)
        if hint is None:
            hint = {
                "why": "Unknown failing step.",
                "likely_causes": ["inspect step stderr log"],
                "first_fix_step": f"inspect {step}.stderr.log",
                "next_commands": ["make first-proof-local"],
                "tags": ["unknown", "manual-triage"],
            }
        actions.append({"step": step, **hint})

    payload = {
        "ok": len(actions) == 0,
        "decision": "NO-ACTION" if len(actions) == 0 else "REMEDIATE",
        "actions": actions,
        "source_summary": args.summary,
    }

    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(f"{json.dumps(payload, indent=2, sort_keys=True)}\n", encoding="utf-8")

    lines = ["# Doctor Remediation", ""]
    if not actions:
        lines += ["No failed steps detected."]
    else:
        lines += ["Top remediation actions:"]
        for action in actions:
            lines += [
                f"- step: `{action['step']}`",
                f"  - why: {action['why']}",
                f"  - likely causes: {', '.join(action['likely_causes'])}",
                f"  - first fix step: `{action['first_fix_step']}`",
                f"  - tags: {', '.join(action['tags'])}",
            ]
    Path(args.out_md).write_text("\n".join(lines) + "\n", encoding="utf-8")

    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"doctor-remediate: decision={payload['decision']} actions={len(actions)}")
        for action in actions:
            print(f"- {action['step']}: {action['first_fix_step']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
