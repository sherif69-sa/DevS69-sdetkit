from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def _step_list(payload: dict[str, Any]) -> list[str]:
    failed_steps = payload.get("failed_steps", [])
    if not isinstance(failed_steps, list):
        return []
    return [str(step) for step in failed_steps]


def _parse_ok(payload: dict[str, Any], *, artifact_name: str) -> tuple[bool, list[str]]:
    value = payload.get("ok")
    if isinstance(value, bool):
        return value, []
    return False, [f"{artifact_name}: expected boolean `ok`, got {type(value).__name__}"]


def build_summary(
    release_payload: dict[str, Any],
    fast_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    release_ok, release_errors = _parse_ok(release_payload, artifact_name="release artifact")
    release_failed_steps = _step_list(release_payload)

    fast_ok: bool | None = None
    fast_failed_steps: list[str] = []
    validation_errors: list[str] = release_errors
    if fast_payload is not None:
        fast_ok, fast_errors = _parse_ok(fast_payload, artifact_name="fast artifact")
        fast_failed_steps = _step_list(fast_payload)
        validation_errors.extend(fast_errors)

    decision = "SHIP" if release_ok else "NO-SHIP"
    headline = (
        "Release preflight passed: candidate is ready to ship."
        if decision == "SHIP"
        else "Release preflight failed: do not ship until blockers are resolved."
    )

    reviewers = [
        "Open release artifact first; confirm ok/failed_steps/profile.",
        "If release failed on gate_fast, open fast-gate artifact and fix first failing step.",
        "Record one remediation action and expected rerun command in PR/release notes.",
    ]
    if decision == "SHIP":
        reviewers = [
            "Confirm release artifact ok=true and failed_steps is empty.",
            "Link artifact in PR/release thread for audit trail.",
            "Proceed with merge/tag using your standard release lane.",
        ]

    return {
        "schema_version": "sdetkit.gate_decision_summary.v1",
        "decision": decision,
        "headline": headline,
        "review_required": not release_ok,
        "validation_errors": validation_errors,
        "artifacts": {
            "release": {
                "ok": release_ok,
                "failed_steps": release_failed_steps,
                "profile": str(release_payload.get("profile", "release")),
            },
            "fast": {
                "present": fast_payload is not None,
                "ok": fast_ok,
                "failed_steps": fast_failed_steps,
                "profile": None
                if fast_payload is None
                else str(fast_payload.get("profile", "fast")),
            },
        },
        "reviewer_checklist": reviewers,
    }


def _to_markdown(payload: dict[str, Any]) -> str:
    decision = payload["decision"]
    release = payload["artifacts"]["release"]
    fast = payload["artifacts"]["fast"]
    icon = "✅" if decision == "SHIP" else "❌"
    lines = [
        "# Gate decision summary",
        "",
        f"- **Decision:** {icon} {decision}",
        f"- **Headline:** {payload['headline']}",
        f"- **Review required:** {'yes' if payload['review_required'] else 'no'}",
        "",
        "## Release artifact",
        f"- `ok`: `{str(release['ok']).lower()}`",
        f"- `failed_steps`: `{release['failed_steps']}`",
        f"- `profile`: `{release['profile']}`",
        "",
        "## Fast gate artifact",
    ]
    if fast["present"]:
        lines.extend(
            [
                f"- `ok`: `{str(fast['ok']).lower()}`",
                f"- `failed_steps`: `{fast['failed_steps']}`",
                f"- `profile`: `{fast['profile']}`",
            ]
        )
    else:
        lines.append("- not provided")
    lines.extend(["", "## Reviewer checklist"])
    for idx, item in enumerate(payload["reviewer_checklist"], start=1):
        lines.append(f"{idx}. {item}")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render concise SHIP/NO-SHIP summary from gate artifacts."
    )
    parser.add_argument("--release", type=Path, default=Path("build/release-preflight.json"))
    parser.add_argument("--fast", type=Path, default=Path("build/gate-fast.json"))
    parser.add_argument("--allow-missing-fast", action="store_true")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument(
        "--out", type=Path, default=None, help="Optional output file (.json or .md)."
    )
    args = parser.parse_args(argv)

    try:
        release_payload = _load_json(args.release)
        fast_payload: dict[str, Any] | None = None
        if args.fast.exists():
            fast_payload = _load_json(args.fast)
        elif not args.allow_missing_fast:
            raise FileNotFoundError(
                f"fast artifact missing: {args.fast}. pass --allow-missing-fast to continue without it"
            )

        summary = build_summary(release_payload, fast_payload)
        if args.format == "json":
            rendered = json.dumps(summary, indent=2, sort_keys=True)
        else:
            rendered = _to_markdown(summary)

        if args.out is not None:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(
                rendered + ("\n" if not rendered.endswith("\n") else ""), encoding="utf-8"
            )
        print(rendered)
        return 0
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
        error_payload = {
            "ok": False,
            "error": str(exc),
            "release": str(args.release),
            "fast": str(args.fast),
        }
        if args.format == "json":
            print(json.dumps(error_payload, indent=2, sort_keys=True))
        else:
            print("gate decision summary: fail")
            print(f"- {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
