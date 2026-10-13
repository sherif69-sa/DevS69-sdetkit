from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from sdetkit.report_provenance import attach_provenance, build_input_provenance  # noqa: E402

SCHEMA_VERSION = "sdetkit.gate_decision_summary.v1"
GENERATOR_SOURCE = "scripts/render_gate_decision_summary.py"
FAST_NEXT_COMMAND = (
    "python -m sdetkit gate fast --format json --stable-json --out build/gate-fast.json"
)
RELEASE_NEXT_COMMAND = (
    "python -m sdetkit gate release --format json --out build/release-preflight.json"
)
SHIP_NEXT_COMMAND = "make gate-decision-summary-contract"
NEXT_ACTION_KEYS = (
    "decision",
    "classification",
    "first_failure",
    "affected_file",
    "next_command",
    "authority",
)


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


def _ship_allowed(
    *,
    release_ok: bool,
    release_failed_steps: list[str],
    fast_present: bool,
    fast_ok: bool | None,
    fast_failed_steps: list[str],
) -> bool:
    return (
        release_ok
        and not release_failed_steps
        and fast_present
        and fast_ok is True
        and not fast_failed_steps
    )


def _evidence_status(
    *,
    present: bool,
    payload: dict[str, Any] | None,
    ok_errors: list[str],
) -> str:
    if not present or payload is None:
        return "unavailable"
    if ok_errors:
        return "malformed"
    return "current_valid"


def _canonical_bytes(payload: dict[str, Any] | None) -> bytes:
    if payload is None:
        return b""
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _next_action_card(
    *,
    decision: str,
    fast_present: bool,
    fast_ok: bool | None,
    fast_failed_steps: list[str],
    release_ok: bool,
    release_failed_steps: list[str],
    validation_errors: list[str],
) -> dict[str, str]:
    if decision == "SHIP":
        return {
            "decision": "SHIP",
            "classification": "",
            "first_failure": "",
            "affected_file": "",
            "next_command": SHIP_NEXT_COMMAND,
            "authority": "review-first",
        }

    if not fast_present:
        first_failure = "fast artifact unavailable"
        next_command = FAST_NEXT_COMMAND
        classification = "unavailable"
    elif validation_errors:
        first_failure = validation_errors[0]
        next_command = (
            FAST_NEXT_COMMAND if not fast_present or fast_ok is not True else RELEASE_NEXT_COMMAND
        )
        classification = "malformed"
    elif fast_ok is not True or fast_failed_steps:
        first_failure = fast_failed_steps[0] if fast_failed_steps else "fast gate failed"
        next_command = FAST_NEXT_COMMAND
        classification = first_failure if fast_failed_steps else "unknown"
    else:
        first_failure = release_failed_steps[0] if release_failed_steps else "release gate failed"
        next_command = RELEASE_NEXT_COMMAND
        classification = first_failure if release_failed_steps else "unknown"

    return {
        "decision": "NO-SHIP",
        "classification": classification,
        "first_failure": first_failure,
        "affected_file": "",
        "next_command": next_command,
        "authority": "review-first",
    }


def build_summary(
    release_payload: dict[str, Any],
    fast_payload: dict[str, Any] | None,
    *,
    root: Path | None = None,
    current_head_sha: str | None = None,
) -> dict[str, Any]:
    release_ok, release_errors = _parse_ok(release_payload, artifact_name="release artifact")
    release_failed_steps = _step_list(release_payload)

    fast_ok: bool | None = None
    fast_failed_steps: list[str] = []
    validation_errors: list[str] = list(release_errors)
    if fast_payload is not None:
        fast_ok, fast_errors = _parse_ok(fast_payload, artifact_name="fast artifact")
        fast_failed_steps = _step_list(fast_payload)
        validation_errors.extend(fast_errors)

    ship_ok = _ship_allowed(
        release_ok=release_ok,
        release_failed_steps=release_failed_steps,
        fast_present=fast_payload is not None,
        fast_ok=fast_ok,
        fast_failed_steps=fast_failed_steps,
    )
    decision = "SHIP" if ship_ok else "NO-SHIP"
    headline = (
        "Fast gate and release preflight passed: candidate is ready to ship."
        if decision == "SHIP"
        else "Gate evidence is incomplete or failed: do not ship until blockers are resolved."
    )

    reviewers = [
        "Open release and fast artifacts; confirm ok/failed_steps/profile on both.",
        "If either artifact failed, fix the first failing step and rerun that gate.",
        "Record one remediation action and expected rerun command in PR/release notes.",
    ]
    if decision == "SHIP":
        reviewers = [
            "Confirm both artifacts ok=true and failed_steps empty.",
            "Link artifacts in PR/release thread for audit trail.",
            "Proceed with merge/tag using your standard release lane.",
        ]

    next_action = _next_action_card(
        decision=decision,
        fast_present=fast_payload is not None,
        fast_ok=fast_ok,
        fast_failed_steps=fast_failed_steps,
        release_ok=release_ok,
        release_failed_steps=release_failed_steps,
        validation_errors=validation_errors,
    )
    data_inputs: dict[str, bytes] = {
        "release": _canonical_bytes(release_payload),
        "fast": _canonical_bytes(fast_payload),
    }
    provenance = build_input_provenance(
        schema_version=SCHEMA_VERSION,
        generator_source=GENERATOR_SOURCE,
        generator_bytes=Path(__file__).read_bytes(),
        data_inputs=data_inputs,
        root=root or _REPO_ROOT,
        source_issue_numbers=(),
        input_artifact_schemas={
            "release": str(release_payload.get("schema_version", "sdetkit.gate.release")),
            "fast": (
                str(fast_payload.get("schema_version", "sdetkit.gate.fast"))
                if fast_payload is not None
                else ""
            ),
        },
        current_head_sha=current_head_sha,
    )
    if fast_payload is None:
        provenance["input_digests"]["fast"] = ""

    summary = {
        "schema_version": SCHEMA_VERSION,
        "decision": decision,
        "headline": headline,
        "review_required": not ship_ok,
        "validation_errors": validation_errors,
        "artifacts": {
            "release": {
                "ok": release_ok,
                "failed_steps": release_failed_steps,
                "profile": str(release_payload.get("profile", "release")),
                "evidence_status": _evidence_status(
                    present=True,
                    payload=release_payload,
                    ok_errors=release_errors,
                ),
            },
            "fast": {
                "present": fast_payload is not None,
                "ok": fast_ok,
                "failed_steps": fast_failed_steps,
                "profile": None
                if fast_payload is None
                else str(fast_payload.get("profile", "fast")),
                "evidence_status": _evidence_status(
                    present=fast_payload is not None,
                    payload=fast_payload,
                    ok_errors=[]
                    if fast_payload is None
                    else [row for row in validation_errors if row.startswith("fast artifact:")],
                ),
            },
        },
        "reviewer_checklist": reviewers,
        "next_action": next_action,
    }
    return attach_provenance(summary, provenance)


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
        f"- `evidence_status`: `{release.get('evidence_status', '')}`",
        "",
        "## Fast gate artifact",
    ]
    if fast["present"]:
        lines.extend(
            [
                f"- `ok`: `{str(fast['ok']).lower()}`",
                f"- `failed_steps`: `{fast['failed_steps']}`",
                f"- `profile`: `{fast['profile']}`",
                f"- `evidence_status`: `{fast.get('evidence_status', '')}`",
            ]
        )
    else:
        lines.append("- not provided")
        lines.append(f"- `evidence_status`: `{fast.get('evidence_status', 'unavailable')}`")
    lines.extend(["", "## next_action"])
    card = payload.get("next_action")
    if isinstance(card, dict):
        lines.append("next_action:")
        for key in NEXT_ACTION_KEYS:
            lines.append(f"{key}: {card.get(key, '')}")
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
