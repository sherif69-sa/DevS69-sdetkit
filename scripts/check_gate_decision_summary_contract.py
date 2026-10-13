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


def check_contract(
    summary_payload: dict[str, Any], *, release_payload: dict[str, Any] | None = None
) -> list[str]:
    errors: list[str] = []
    required = (
        "schema_version",
        "decision",
        "headline",
        "review_required",
        "validation_errors",
        "artifacts",
        "reviewer_checklist",
        "next_action",
        "input_provenance",
    )
    for key in required:
        if key not in summary_payload:
            errors.append(f"missing top-level key: {key}")

    decision = summary_payload.get("decision")
    if decision not in {"SHIP", "NO-SHIP"}:
        errors.append("decision must be SHIP or NO-SHIP")

    review_required = summary_payload.get("review_required")
    if not isinstance(review_required, bool):
        errors.append("review_required must be a boolean")

    validation_errors = summary_payload.get("validation_errors")
    if not isinstance(validation_errors, list) or not all(
        isinstance(item, str) for item in validation_errors
    ):
        errors.append("validation_errors must be list[str]")

    checklist = summary_payload.get("reviewer_checklist")
    if (
        not isinstance(checklist, list)
        or not checklist
        or not all(isinstance(item, str) and item.strip() for item in checklist)
    ):
        errors.append("reviewer_checklist must be a non-empty list[str]")

    artifacts = summary_payload.get("artifacts")
    if not isinstance(artifacts, dict):
        errors.append("artifacts must be an object")
        return errors
    release = artifacts.get("release")
    if not isinstance(release, dict):
        errors.append("artifacts.release must be an object")
        return errors
    if not isinstance(release.get("ok"), bool):
        errors.append("artifacts.release.ok must be boolean")
    if not isinstance(release.get("failed_steps"), list):
        errors.append("artifacts.release.failed_steps must be list")
    if not isinstance(release.get("profile"), str) or not release.get("profile"):
        errors.append("artifacts.release.profile must be non-empty string")
    valid_statuses = {"current_valid", "stale", "malformed", "unavailable"}
    if release.get("evidence_status") not in valid_statuses:
        errors.append("artifacts.release.evidence_status must be a known evidence status")

    fast = artifacts.get("fast")
    if not isinstance(fast, dict):
        errors.append("artifacts.fast must be an object")
        fast = {}
    if fast and fast.get("evidence_status") not in valid_statuses:
        errors.append("artifacts.fast.evidence_status must be a known evidence status")

    next_action = summary_payload.get("next_action")
    if not isinstance(next_action, dict):
        errors.append("next_action must be an object")
    else:
        for key in (
            "decision",
            "classification",
            "first_failure",
            "affected_file",
            "next_command",
            "authority",
        ):
            if key not in next_action:
                errors.append(f"missing next_action key: {key}")
        if next_action.get("authority") != "review-first":
            errors.append("next_action.authority must be review-first")
        if next_action.get("decision") not in {"SHIP", "NO-SHIP", "CONTINUE"}:
            errors.append("next_action.decision must be SHIP, NO-SHIP, or CONTINUE")

    provenance = summary_payload.get("input_provenance")
    if not isinstance(provenance, dict):
        errors.append("input_provenance must be an object")
    else:
        digest = provenance.get("input_digest")
        head = provenance.get("generated_from_head_sha")
        if provenance.get("digest_algorithm") != "sha256":
            errors.append("input_provenance.digest_algorithm must be sha256")
        if not isinstance(digest, str) or len(digest) != 64:
            errors.append("input_provenance.input_digest must be a sha256 hex digest")
        if not isinstance(head, str) or len(head) != 40:
            errors.append("input_provenance.generated_from_head_sha must be a full SHA-1")
        digests = provenance.get("input_digests")
        if not isinstance(digests, dict) or "release" not in digests:
            errors.append("input_provenance.input_digests must include release")

    release_ok = release.get("ok")
    release_failed = release.get("failed_steps")
    fast_present = fast.get("present")
    fast_ok = fast.get("ok")
    fast_failed = fast.get("failed_steps")
    release_steps_ok = isinstance(release_failed, list) and not release_failed
    fast_steps_ok = isinstance(fast_failed, list) and not fast_failed
    ship_ok = (
        release_ok is True
        and release_steps_ok
        and fast_present is True
        and fast_ok is True
        and fast_steps_ok
        and release.get("evidence_status") == "current_valid"
        and fast.get("evidence_status") == "current_valid"
    )
    expected_decision = "SHIP" if ship_ok else "NO-SHIP"
    if decision in {"SHIP", "NO-SHIP"} and decision != expected_decision:
        errors.append("decision must match two-artifact SHIP contract")
    if isinstance(review_required, bool) and review_required != (not ship_ok):
        errors.append("review_required must be the inverse of the two-artifact SHIP contract")

    if release_payload is not None:
        src_ok = release_payload.get("ok")
        src_failed = release_payload.get("failed_steps")
        if isinstance(src_ok, bool) and isinstance(release_ok, bool) and src_ok != release_ok:
            errors.append("summary artifacts.release.ok must match release artifact ok")
        if isinstance(src_failed, list) and isinstance(release.get("failed_steps"), list):
            if [str(item) for item in src_failed] != [
                str(item) for item in release["failed_steps"]
            ]:
                errors.append(
                    "summary artifacts.release.failed_steps must match release artifact failed_steps"
                )

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate gate decision summary contract.")
    parser.add_argument("--summary", type=Path, default=Path("build/gate-decision-summary.json"))
    parser.add_argument("--release", type=Path, default=Path("build/release-preflight.json"))
    parser.add_argument("--allow-missing-release", action="store_true")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    try:
        summary = _load(args.summary)
        release_payload: dict[str, Any] | None = None
        if args.release.exists():
            release_payload = _load(args.release)
        elif not args.allow_missing_release:
            raise FileNotFoundError(
                f"release artifact missing: {args.release}. pass --allow-missing-release to continue"
            )
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        result = {"ok": False, "errors": [str(exc)], "summary": str(args.summary)}
        if args.format == "json":
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print("gate decision summary contract: fail")
            print(f"- {exc}")
        return 1

    errors = check_contract(summary, release_payload=release_payload)
    result = {
        "ok": not errors,
        "errors": errors,
        "summary": str(args.summary),
        "release": str(args.release),
    }
    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    elif result["ok"]:
        print("gate decision summary contract: ok")
    else:
        print("gate decision summary contract: fail")
        for row in errors:
            print(f"- {row}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
