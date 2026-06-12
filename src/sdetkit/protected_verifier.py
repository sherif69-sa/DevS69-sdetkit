from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.protected_verifier.decision.v1"
DEFAULT_OUT_DIR = Path("build") / "protected-verifier"
PROTECTED_VERIFIER_JSON = "protected-verifier-decision.json"
PROTECTED_VERIFIER_MD = "protected-verifier-decision.md"

JsonObject = dict[str, Any]

AUTHORITY_KEYS = (
    "automation_allowed",
    "patch_application_allowed",
    "merge_authorized",
    "semantic_equivalence_proven",
    "automatic_security_fix_allowed",
    "automatic_dismissal_allowed",
    "security_dismissal",
)


def _as_dict(value: Any) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true", "yes"}


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _string_list(value: Any) -> list[str]:
    seen: set[str] = set()
    rendered: list[str] = []
    for item in _as_list(value):
        text = _string(item)
        if text and text not in seen:
            seen.add(text)
            rendered.append(text)
    return rendered


def _read_json(path: Path | None) -> JsonObject:
    if path is None or not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        msg = f"expected JSON object in {path}"
        raise ValueError(msg)
    return payload


def _boundary_payloads(
    *,
    patch_score: Mapping[str, Any],
    failure_bundle: Mapping[str, Any],
    runtime_proof: Mapping[str, Any],
) -> list[tuple[str, JsonObject]]:
    patch_safety_gate = _as_dict(patch_score.get("safety_gate_evidence"))
    failure_safety_gate = _as_dict(failure_bundle.get("safety_gate"))
    runtime_safety_gate = _as_dict(runtime_proof.get("safety_gate"))

    return [
        ("patch_score", _as_dict(patch_score)),
        ("patch_score.decision", _as_dict(patch_score.get("decision"))),
        ("patch_score.decision_boundary", _as_dict(patch_score.get("decision_boundary"))),
        ("patch_score.authority_boundary", _as_dict(patch_score.get("authority_boundary"))),
        (
            "patch_score.safety_gate_evidence.decision_boundary",
            _as_dict(patch_safety_gate.get("decision_boundary")),
        ),
        ("failure_bundle.decision_boundary", _as_dict(failure_bundle.get("decision_boundary"))),
        ("failure_bundle.authority_boundary", _as_dict(failure_bundle.get("authority_boundary"))),
        ("failure_bundle.safety_gate", failure_safety_gate),
        (
            "failure_bundle.safety_gate.decision_boundary",
            _as_dict(failure_safety_gate.get("decision_boundary")),
        ),
        ("runtime_proof.decision_boundary", _as_dict(runtime_proof.get("decision_boundary"))),
        ("runtime_proof.authority_boundary", _as_dict(runtime_proof.get("authority_boundary"))),
        ("runtime_proof.safety_gate", runtime_safety_gate),
        (
            "runtime_proof.safety_gate.decision_boundary",
            _as_dict(runtime_safety_gate.get("decision_boundary")),
        ),
    ]


def _authority_expansion_flags(
    *,
    patch_score: Mapping[str, Any],
    failure_bundle: Mapping[str, Any],
    runtime_proof: Mapping[str, Any],
) -> list[JsonObject]:
    flags: list[JsonObject] = []
    for source, payload in _boundary_payloads(
        patch_score=patch_score,
        failure_bundle=failure_bundle,
        runtime_proof=runtime_proof,
    ):
        expanded = [key for key in AUTHORITY_KEYS if _bool(payload.get(key))]
        if not expanded:
            continue
        flags.append(
            {
                "code": "AUTHORITY_EXPANSION_ATTEMPT",
                "message": f"{source} attempted to expand ProtectedVerifier authority.",
                "blocking": True,
                "source": source,
                "fields": expanded,
            }
        )
    return flags


def _risk_flag(code: str, message: str, *, blocking: bool) -> JsonObject:
    return {
        "code": code,
        "message": message,
        "blocking": blocking,
    }


def verify_patch(
    *,
    patch_score: Mapping[str, Any],
    failure_bundle: Mapping[str, Any] | None = None,
    runtime_proof: Mapping[str, Any] | None = None,
) -> JsonObject:
    bundle = _as_dict(failure_bundle)
    runtime = _as_dict(runtime_proof)
    patch_decision = _as_dict(patch_score.get("decision"))

    patch_id = _string(patch_score.get("patch_id")) or "unknown"
    diagnosis_id = _string(patch_score.get("diagnosis_id")) or "unknown"
    patch_score_status = _string(patch_decision.get("status")) or "unknown"
    candidate = _bool(patch_decision.get("candidate_for_protected_verification"))
    score = _int(patch_score.get("score"))
    minimum_score = _int(patch_score.get("minimum_score"))
    proof_requirements = _string_list(patch_score.get("proof_requirements"))
    changed_files = _string_list(patch_score.get("changed_files"))
    allowed_files = _string_list(patch_score.get("allowed_files"))

    flags = _authority_expansion_flags(
        patch_score=patch_score,
        failure_bundle=bundle,
        runtime_proof=runtime,
    )

    if patch_score_status != "candidate_for_protected_verification" or not candidate:
        flags.append(
            _risk_flag(
                "PATCH_SCORE_NOT_CANDIDATE",
                "PatchScorer did not mark this patch as a protected-verification candidate.",
                blocking=True,
            )
        )

    if score < minimum_score:
        flags.append(
            _risk_flag(
                "PATCH_SCORE_BELOW_MINIMUM",
                "Patch score is below the configured minimum verification threshold.",
                blocking=True,
            )
        )

    if not proof_requirements:
        flags.append(
            _risk_flag(
                "PROOF_REQUIREMENTS_MISSING",
                "Protected verification requires explicit proof commands from PatchScorer.",
                blocking=True,
            )
        )

    blocked = any(_bool(flag.get("blocking")) for flag in flags)
    status = "blocked_review_first" if blocked else "review_required"
    next_action = (
        "resolve_blocking_verification_flags"
        if blocked
        else "human_review_required_before_patch_application"
    )
    reason = (
        "Blocking verification flags prevent protected review."
        if blocked
        else "Candidate is reviewable, but ProtectedVerifier grants no patch, merge, or semantic authority."
    )

    decision_boundary = {
        "automation_allowed": False,
        "patch_application_allowed": False,
        "merge_authorized": False,
        "semantic_equivalence_proven": False,
        "automatic_security_fix_allowed": False,
        "automatic_dismissal_allowed": False,
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "sdetkit.protected_verifier",
        "collection_status": "collected",
        "patch_id": patch_id,
        "diagnosis_id": diagnosis_id,
        "inputs": {
            "patch_score_schema": _string(patch_score.get("schema_version")) or "unknown",
            "patch_score_status": patch_score_status,
            "failure_bundle_status": _string(bundle.get("status")) or "not_collected",
            "runtime_proof_status": _string(runtime.get("status")) or "not_collected",
        },
        "verification_evidence": {
            "score": score,
            "minimum_score": minimum_score,
            "changed_files": changed_files,
            "allowed_files": allowed_files,
            "proof_requirements": proof_requirements,
            "patch_score_risk_flags": [
                _string(_as_dict(item).get("code"))
                for item in _as_list(patch_score.get("risk_flags"))
                if _string(_as_dict(item).get("code"))
            ],
        },
        "risk_flags": flags,
        "decision": {
            "status": status,
            "review_first": True,
            "candidate_for_protected_verification": candidate and not blocked,
            "protected_verification_passed": False,
            "automation_allowed": False,
            "patch_application_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
            "reason": reason,
            "next_action": next_action,
        },
        "decision_boundary": decision_boundary,
    }


def render_markdown(payload: Mapping[str, Any]) -> str:
    decision = _as_dict(payload.get("decision"))
    evidence = _as_dict(payload.get("verification_evidence"))
    boundary = _as_dict(payload.get("decision_boundary"))
    flags = [_as_dict(item) for item in _as_list(payload.get("risk_flags"))]

    lines = [
        "# ProtectedVerifier decision",
        "",
        f"- Patch: `{_string(payload.get('patch_id'))}`",
        f"- Diagnosis: `{_string(payload.get('diagnosis_id'))}`",
        f"- Status: `{_string(decision.get('status'))}`",
        f"- Review first: `{str(_bool(decision.get('review_first'))).lower()}`",
        (
            "- Candidate for protected verification: "
            f"`{str(_bool(decision.get('candidate_for_protected_verification'))).lower()}`"
        ),
        (
            "- Protected verification passed: "
            f"`{str(_bool(decision.get('protected_verification_passed'))).lower()}`"
        ),
        f"- Next action: `{_string(decision.get('next_action'))}`",
        "",
        "## Verification evidence",
        "",
        f"- Score: `{_int(evidence.get('score'))}`",
        f"- Minimum score: `{_int(evidence.get('minimum_score'))}`",
        "- Changed files:",
    ]

    changed_files = _string_list(evidence.get("changed_files"))
    lines.extend(f"  - `{path}`" for path in changed_files) if changed_files else lines.append(
        "  - none"
    )

    proof_requirements = _string_list(evidence.get("proof_requirements"))
    lines.extend(["", "## Proof requirements", ""])
    lines.extend(
        f"- `{command}`" for command in proof_requirements
    ) if proof_requirements else lines.append("- none")

    lines.extend(["", "## Risk flags", ""])
    if flags:
        for flag in flags:
            fields = ", ".join(
                _string(item) for item in _as_list(flag.get("fields")) if _string(item)
            )
            suffix = f" fields=`{fields}`" if fields else ""
            lines.append(
                f"- `{_string(flag.get('code'))}`: "
                f"blocking=`{str(_bool(flag.get('blocking'))).lower()}` "
                f"{_string(flag.get('message'))}{suffix}"
            )
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Boundary",
            "",
            f"- Automation allowed: `{str(_bool(boundary.get('automation_allowed'))).lower()}`",
            (
                "- Patch application allowed: "
                f"`{str(_bool(boundary.get('patch_application_allowed'))).lower()}`"
            ),
            f"- Merge authorized: `{str(_bool(boundary.get('merge_authorized'))).lower()}`",
            (
                "- Semantic equivalence proven: "
                f"`{str(_bool(boundary.get('semantic_equivalence_proven'))).lower()}`"
            ),
            (
                "- Automatic security fix allowed: "
                f"`{str(_bool(boundary.get('automatic_security_fix_allowed'))).lower()}`"
            ),
            (
                "- Automatic dismissal allowed: "
                f"`{str(_bool(boundary.get('automatic_dismissal_allowed'))).lower()}`"
            ),
            "",
            "This verifier is reporting-only. It does not apply patches, authorize merge, "
            "or claim semantic equivalence.",
            "",
        ]
    )
    return "\n".join(lines)


def write_protected_verifier_decision(
    payload: Mapping[str, Any],
    *,
    out_dir: Path,
) -> dict[str, str]:
    json_path = out_dir / PROTECTED_VERIFIER_JSON
    markdown_path = out_dir / PROTECTED_VERIFIER_MD
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(payload), encoding="utf-8")
    return {
        "protected_verifier_json": json_path.as_posix(),
        "protected_verifier_markdown": markdown_path.as_posix(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.protected_verifier")
    parser.add_argument("--patch-score", type=Path, required=True)
    parser.add_argument("--failure-bundle", type=Path)
    parser.add_argument("--runtime-proof", type=Path)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        payload = verify_patch(
            patch_score=_read_json(args.patch_score),
            failure_bundle=_read_json(args.failure_bundle),
            runtime_proof=_read_json(args.runtime_proof),
        )
        artifacts = write_protected_verifier_decision(payload, out_dir=args.out_dir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}")
        return 2

    if args.format == "json":
        print(
            json.dumps(
                {
                    "artifacts": artifacts,
                    "decision": payload["decision"],
                    "risk_flags": payload["risk_flags"],
                    "schema_version": payload["schema_version"],
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        for key, value in artifacts.items():
            print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
