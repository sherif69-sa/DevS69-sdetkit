from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

_LEVEL = {"low": 1, "medium": 2, "high": 3}
_SIZE = {"small": 1, "medium": 2, "large": 3}


def _score(
    *,
    repo_size: str,
    team_size: str,
    release_frequency: str,
    change_failure_impact: str,
    compliance_pressure: str,
) -> int:
    return (
        _SIZE[repo_size]
        + _SIZE[team_size]
        + _LEVEL[release_frequency]
        + (_LEVEL[change_failure_impact] * 2)
        + (_LEVEL[compliance_pressure] * 2)
    )


def recommend_profile(score: int) -> dict[str, Any]:
    if score >= 14:
        return {
            "fit": "high",
            "segment": "medium-to-high-stakes delivery",
            "recommendation": "Adopt canonical gate path + decision-summary contract in CI now.",
            "next_steps": [
                "python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json",
                "python -m sdetkit gate release --format json --out build/release-preflight.json",
                "make gate-decision-summary",
                "make gate-decision-summary-contract",
            ],
        }
    if score >= 10:
        return {
            "fit": "medium",
            "segment": "growing delivery risk",
            "recommendation": "Adopt canonical path now; add summary contract before release windows.",
            "next_steps": [
                "python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json",
                "python -m sdetkit gate release --format json --out build/release-preflight.json",
                "python -m sdetkit doctor --format json --out build/doctor.json",
            ],
        }
    return {
        "fit": "low",
        "segment": "low-stakes / very small repos",
        "recommendation": "Start with lightweight path only; defer broader rollout until risk increases.",
        "next_steps": [
            "python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json",
            "python -m sdetkit gate release --format json --out build/release-preflight.json",
        ],
    }


def _render_text(payload: dict[str, Any]) -> str:
    lines = [
        f"SDETKIT_FIT={payload['fit'].upper()}",
        f"segment: {payload['segment']}",
        f"score: {payload['score']}",
        f"recommendation: {payload['recommendation']}",
        "next_steps:",
    ]
    lines.extend(f"- {step}" for step in payload["next_steps"])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python scripts/recommend_sdetkit_fit.py",
        description="Recommend SDETKit adoption depth based on delivery risk profile.",
    )
    parser.add_argument("--repo-size", choices=["small", "medium", "large"], default="small")
    parser.add_argument("--team-size", choices=["small", "medium", "large"], default="small")
    parser.add_argument(
        "--release-frequency",
        choices=["low", "medium", "high"],
        default="low",
        help="How often production changes ship.",
    )
    parser.add_argument(
        "--change-failure-impact",
        choices=["low", "medium", "high"],
        default="medium",
        help="Business impact when a release fails.",
    )
    parser.add_argument(
        "--compliance-pressure",
        choices=["low", "medium", "high"],
        default="low",
        help="Auditability/compliance pressure on release decisions.",
    )
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    score = _score(
        repo_size=args.repo_size,
        team_size=args.team_size,
        release_frequency=args.release_frequency,
        change_failure_impact=args.change_failure_impact,
        compliance_pressure=args.compliance_pressure,
    )
    payload = {
        "schema_version": "sdetkit.fit_recommendation.v1",
        "score": score,
        "inputs": {
            "repo_size": args.repo_size,
            "team_size": args.team_size,
            "release_frequency": args.release_frequency,
            "change_failure_impact": args.change_failure_impact,
            "compliance_pressure": args.compliance_pressure,
        },
        **recommend_profile(score),
    }
    rendered = (
        json.dumps(payload, indent=2, sort_keys=True) if args.format == "json" else _render_text(payload)
    )
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + ("\n" if not rendered.endswith("\n") else ""), encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
