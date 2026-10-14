from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .repo_model import RepoModel, build_repo_model

_LEVEL = {"low": 1, "medium": 2, "high": 3}
_SIZE = {"small": 1, "medium": 2, "large": 3}


def _risk_drivers(
    *,
    repo_size: str,
    team_size: str,
    release_frequency: str,
    change_failure_impact: str,
    compliance_pressure: str,
) -> list[str]:
    drivers: list[tuple[int, str]] = [
        (_LEVEL[change_failure_impact] * 2, f"change-failure impact is {change_failure_impact}"),
        (_LEVEL[compliance_pressure] * 2, f"compliance pressure is {compliance_pressure}"),
        (_SIZE[repo_size], f"repository size is {repo_size}"),
        (_SIZE[team_size], f"team size is {team_size}"),
        (_LEVEL[release_frequency], f"release frequency is {release_frequency}"),
    ]
    drivers.sort(key=lambda row: (-row[0], row[1]))
    return [text for _, text in drivers[:3]]


def _confidence(score: int) -> str:
    if score >= 14:
        return "high"
    if score >= 10:
        return "medium"
    return "low"


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
            "recommendation": "Adopt the canonical gate path and merge-readiness evidence in CI now.",
            "next_steps": [
                "python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json",
                "python -m sdetkit gate release --reuse-fast build/gate-fast.json --format json --out build/release-preflight.json",
                "python -m sdetkit verify merge --checks-json <checks.json> --evidence build/release-preflight.json",
            ],
        }
    if score >= 10:
        return {
            "fit": "medium",
            "segment": "growing delivery risk",
            "recommendation": "Adopt the canonical gate path now; add merge-readiness evidence before release windows.",
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


def _repo_facts(model: RepoModel) -> tuple[dict[str, Any], list[str]]:
    """What the repository shows, and the steps that close its gaps."""

    facts = {
        "languages": list(model.languages),
        "ci_systems": list(model.ci_systems),
        "test_suites": [suite.step_id for suite in model.test_suites],
        "file_count": model.file_count,
        "inferred_repo_size": model.size(),
    }
    gaps: list[str] = []
    if not model.test_suites:
        gaps.append(
            "No test command was proven for this repository; add one the gate can run "
            "(see: python -m sdetkit adoption-surface --format report)."
        )
    if not model.ci_systems:
        gaps.append("No CI system was detected; run `python -m sdetkit gate fast` in CI.")
    elif not model.ci_security_tools():
        gaps.append(
            "CI runs no security scanner; add one, then check: python -m sdetkit doctor --ci"
        )
    return facts, gaps


def _render_text(payload: dict[str, Any]) -> str:
    lines = [
        f"SDETKIT_FIT={payload['fit'].upper()}",
        f"segment: {payload['segment']}",
        f"score: {payload['score']}",
        f"confidence: {payload['confidence']}",
        f"recommendation: {payload['recommendation']}",
        "next_steps:",
    ]
    lines.extend(f"- {step}" for step in payload["next_steps"])
    if payload.get("repo"):
        repo = payload["repo"]
        lines.append(
            "repo: languages="
            + (",".join(repo["languages"]) or "none")
            + " ci="
            + (",".join(repo["ci_systems"]) or "none")
            + f" size={repo['inferred_repo_size']}"
        )
    if payload.get("risk_drivers"):
        lines.append("risk_drivers:")
        lines.extend(f"- {row}" for row in payload["risk_drivers"])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sdetkit fit",
        description="Recommend SDETKit adoption depth based on delivery risk profile.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Read the repository at this path: infer its size and add steps for its gaps.",
    )
    parser.add_argument("--repo-size", choices=["small", "medium", "large"], default=None)
    parser.add_argument("--team-size", choices=["small", "medium", "large"], default="small")
    parser.add_argument("--release-frequency", choices=["low", "medium", "high"], default="low")
    parser.add_argument(
        "--change-failure-impact", choices=["low", "medium", "high"], default="medium"
    )
    parser.add_argument("--compliance-pressure", choices=["low", "medium", "high"], default="low")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    model = build_repo_model(args.root) if args.root is not None else None
    if args.repo_size is None:
        args.repo_size = model.size() if model is not None else "small"

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
        "confidence": _confidence(score),
        "inputs": {
            "repo_size": args.repo_size,
            "team_size": args.team_size,
            "release_frequency": args.release_frequency,
            "change_failure_impact": args.change_failure_impact,
            "compliance_pressure": args.compliance_pressure,
        },
        "risk_drivers": _risk_drivers(
            repo_size=args.repo_size,
            team_size=args.team_size,
            release_frequency=args.release_frequency,
            change_failure_impact=args.change_failure_impact,
            compliance_pressure=args.compliance_pressure,
        ),
        **recommend_profile(score),
    }
    if model is not None:
        facts, gaps = _repo_facts(model)
        payload["repo"] = facts
        payload["next_steps"] = [*gaps, *payload["next_steps"]]
    rendered = (
        json.dumps(payload, indent=2, sort_keys=True)
        if args.format == "json"
        else _render_text(payload)
    )
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            rendered + ("\n" if not rendered.endswith("\n") else ""), encoding="utf-8"
        )
    print(rendered)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
