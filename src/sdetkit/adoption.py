from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_optional(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def build_followup(
    *,
    fit_payload: dict[str, Any] | None,
    summary_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    actions: list[dict[str, str]] = []
    fit = "unknown"
    if fit_payload is None:
        actions.append(
            {
                "priority": "P0",
                "title": "Generate fit recommendation",
                "action": "make fit-check",
            }
        )
    else:
        fit = str(fit_payload.get("fit", "unknown"))
        if fit in {"high", "medium"}:
            actions.append(
                {
                    "priority": "P0",
                    "title": "Adopt canonical gate lane in CI",
                    "action": "python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json && python -m sdetkit gate release --format json --out build/release-preflight.json",
                }
            )
        else:
            actions.append(
                {
                    "priority": "P1",
                    "title": "Run lightweight lane only",
                    "action": "python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json",
                }
            )

    if summary_payload is None:
        actions.append(
            {
                "priority": "P0",
                "title": "Generate reviewer decision artifacts",
                "action": "make gate-decision-summary && make gate-decision-summary-contract",
            }
        )
        decision = "NO-DATA"
    else:
        decision = str(summary_payload.get("decision", "NO-DATA"))
        if decision == "NO-SHIP":
            actions.append(
                {
                    "priority": "P0",
                    "title": "Remediate first failing release step",
                    "action": "Inspect build/release-preflight.json failed_steps and fix first blocker before rerun.",
                }
            )
        else:
            actions.append(
                {
                    "priority": "P2",
                    "title": "Attach decision summary to PR/release thread",
                    "action": "Link build/gate-decision-summary.md in reviewer handoff notes.",
                }
            )
        if summary_payload.get("validation_errors"):
            actions.append(
                {
                    "priority": "P0",
                    "title": "Clear summary validation errors",
                    "action": "Run make gate-decision-summary-contract and resolve listed mismatches.",
                }
            )

    actions.sort(key=lambda item: {"P0": 0, "P1": 1, "P2": 2}.get(item["priority"], 9))
    top = actions[0] if actions else {"priority": "P2", "title": "No action", "action": "none"}
    return {
        "schema_version": "sdetkit.adoption_followup.v1",
        "fit": fit,
        "decision": decision,
        "next_command": top["action"],
        "recommendations": actions,
    }


def _to_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Adoption follow-up",
        "",
        f"- Fit: `{payload['fit']}`",
        f"- Decision: `{payload['decision']}`",
        f"- Next command: `{payload['next_command']}`",
        "",
        "## Recommendations",
    ]
    for idx, rec in enumerate(payload["recommendations"], start=1):
        lines.append(f"{idx}. **[{rec['priority']}] {rec['title']}** — `{rec['action']}`")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit adoption",
        description="Build prioritized adoption follow-up actions from fit and gate decision artifacts.",
    )
    parser.add_argument("--fit", type=Path, default=Path("build/sdetkit-fit-recommendation.json"))
    parser.add_argument("--summary", type=Path, default=Path("build/gate-decision-summary.json"))
    parser.add_argument("--format", choices=["json", "md"], default="json")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    payload = build_followup(
        fit_payload=_load_optional(args.fit),
        summary_payload=_load_optional(args.summary),
    )
    rendered = json.dumps(payload, indent=2, sort_keys=True) if args.format == "json" else _to_markdown(payload)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + ("\n" if not rendered.endswith("\n") else ""), encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
