from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def _posture_level(followup: dict[str, Any], rollup: dict[str, Any]) -> str:
    if bool(rollup.get("escalation_recommended")):
        return "escalate"
    if str(followup.get("decision")) == "NO-SHIP":
        return "attention"
    return "stable"


def build_posture(followup: dict[str, Any], rollup: dict[str, Any]) -> dict[str, Any]:
    level = _posture_level(followup, rollup)
    headline = {
        "stable": "Adoption posture is stable.",
        "attention": "Adoption posture needs attention before broadening rollout.",
        "escalate": "Adoption posture requires escalation.",
    }[level]
    return {
        "schema_version": "sdetkit.adoption_posture.v1",
        "posture_level": level,
        "headline": headline,
        "fit": followup.get("fit", "unknown"),
        "decision": followup.get("decision", "NO-DATA"),
        "next_command": followup.get("next_command", ""),
        "total_runs": rollup.get("total_runs", 0),
        "escalation_recommended": bool(rollup.get("escalation_recommended", False)),
        "escalation_reason": rollup.get("escalation_reason", "none"),
    }


def _to_markdown(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Adoption posture",
            "",
            f"- Posture level: `{payload['posture_level']}`",
            f"- Headline: {payload['headline']}",
            f"- Fit: `{payload['fit']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Total runs: `{payload['total_runs']}`",
            f"- Escalation: `{payload['escalation_recommended']}` (`{payload['escalation_reason']}`)",
            f"- Next command: `{payload['next_command']}`",
            "",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render adoption posture from follow-up + rollup.")
    parser.add_argument("--followup", type=Path, default=Path("build/adoption-followup.json"))
    parser.add_argument("--rollup", type=Path, default=Path("build/adoption-followup-history-rollup.json"))
    parser.add_argument("--format", choices=("json", "md"), default="md")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    try:
        followup = _load(args.followup)
        rollup = _load(args.rollup)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        payload = {"ok": False, "error": str(exc), "followup": str(args.followup), "rollup": str(args.rollup)}
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 1

    posture = build_posture(followup, rollup)
    rendered = json.dumps(posture, indent=2, sort_keys=True) if args.format == "json" else _to_markdown(posture)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + ("\n" if not rendered.endswith("\n") else ""), encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
