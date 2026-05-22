from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from sdetkit.patch_scorer import PROTECTED_EXACT_PATHS, PROTECTED_PREFIXES

SCHEMA_VERSION = "sdetkit.protected_verifier.v1"
DEFAULT_OUT_DIR = Path("build") / "protected-verifier"
RESULT_JSON = "protected-verifier-result.json"
RESULT_MD = "protected-verifier-result.md"

JsonObject = dict[str, Any]

PATCH_SCORE_NOT_CANDIDATE = "_".join(("PATCH", "SCORE", "NOT", "CANDIDATE"))
AUTOMATION_BOUNDARY_VIOLATION = "_".join(("AUTOMATION", "BOUNDARY", "VIOLATION"))
VERIFICATION_FILE_INVENTORY_MISSING = "_".join(("VERIFICATION", "FILE", "INVENTORY", "MISSING"))
CHANGED_FILE_INVENTORY_MISMATCH = "_".join(("CHANGED", "FILE", "INVENTORY", "MISMATCH"))
OUTSIDE_SCORED_SCOPE = "_".join(("OUTSIDE", "SCORED", "SCOPE"))
PROTECTED_PATH_CHANGED = "_".join(("PROTECTED", "PATH", "CHANGED"))
PROOF_REQUIREMENTS_MISSING = "_".join(("PROOF", "REQUIREMENTS", "MISSING"))
REQUIRED_PROOF_NOT_CAPTURED = "_".join(("REQUIRED", "PROOF", "NOT", "CAPTURED"))
REQUIRED_PROOF_FAILED = "_".join(("REQUIRED", "PROOF", "FAILED"))
SEMANTIC_EQUIVALENCE_NOT_PROVEN = "_".join(("SEMANTIC", "EQUIVALENCE", "NOT", "PROVEN"))


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


def _int(value: Any, *, default: int = -1) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _string_list(value: Any) -> list[str]:
    return sorted({_string(item) for item in _as_list(value) if _string(item)})


def _read_json(path: Path) -> JsonObject:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        msg = f"expected JSON object in {path}"
        raise ValueError(msg)
    return payload


def _protected_path(path: str) -> bool:
    return path in PROTECTED_EXACT_PATHS or path.startswith(PROTECTED_PREFIXES)


def _finding(
    code: str,
    message: str,
    *,
    blocking: bool,
    files: list[str] | None = None,
    commands: list[str] | None = None,
) -> JsonObject:
    return {
        "code": code,
        "message": message,
        "blocking": blocking,
        "files": files or [],
        "commands": commands or [],
    }


def _proof_results_by_command(evidence: Mapping[str, Any]) -> dict[str, JsonObject]:
    results: dict[str, JsonObject] = {}
    for item in _as_list(evidence.get("proof_results")):
        result = _as_dict(item)
        command = _string(result.get("command"))
        if command:
            results[command] = result
    return results


def _proof_passed(result: Mapping[str, Any]) -> bool:
    status = _string(result.get("status")).lower()
    return (
        status in {"ok", "pass", "passed", "success", "succeeded"}
        and _int(result.get("exit_code")) == 0
    )


def verify_candidate(
    *,
    patch_score: Mapping[str, Any],
    verification_evidence: Mapping[str, Any],
) -> JsonObject:
    decision = _as_dict(patch_score.get("decision"))
    patch_id = _string(patch_score.get("patch_id")) or "unknown"
    diagnosis_id = _string(patch_score.get("diagnosis_id")) or "unknown"
    scored_files = _string_list(patch_score.get("changed_files"))
    allowed_files = _string_list(patch_score.get("allowed_files"))
    evidence_files = _string_list(verification_evidence.get("changed_files"))
    proof_requirements = _string_list(patch_score.get("proof_requirements"))
    proof_results = _proof_results_by_command(verification_evidence)
    findings: list[JsonObject] = []

    if _string(decision.get("status")) != "candidate_for_protected_verification" or not _bool(
        decision.get("candidate_for_protected_verification")
    ):
        findings.append(
            _finding(
                PATCH_SCORE_NOT_CANDIDATE,
                "PatchScorer did not nominate this patch for protected verification.",
                blocking=True,
            )
        )

    if _bool(decision.get("automation_allowed")):
        findings.append(
            _finding(
                AUTOMATION_BOUNDARY_VIOLATION,
                "PatchScorer output unexpectedly attempts to authorize automation.",
                blocking=True,
            )
        )

    if not evidence_files:
        findings.append(
            _finding(
                VERIFICATION_FILE_INVENTORY_MISSING,
                "Verification evidence must include the observed changed-file inventory.",
                blocking=True,
            )
        )
    elif evidence_files != scored_files:
        findings.append(
            _finding(
                CHANGED_FILE_INVENTORY_MISMATCH,
                "Observed changed files do not exactly match the PatchScorer inventory.",
                blocking=True,
                files=sorted(set(evidence_files).symmetric_difference(scored_files)),
            )
        )

    outside_scope = sorted(set(evidence_files) - set(allowed_files))
    if outside_scope:
        findings.append(
            _finding(
                OUTSIDE_SCORED_SCOPE,
                "Observed changed files exceed PatchScorer approved scope.",
                blocking=True,
                files=outside_scope,
            )
        )

    protected_files = [path for path in evidence_files if _protected_path(path)]
    if protected_files:
        findings.append(
            _finding(
                PROTECTED_PATH_CHANGED,
                "Protected test, workflow, gate, or policy paths remain review-first.",
                blocking=True,
                files=protected_files,
            )
        )

    if not proof_requirements:
        findings.append(
            _finding(
                PROOF_REQUIREMENTS_MISSING,
                "PatchScorer supplied no required proof commands.",
                blocking=True,
            )
        )
    else:
        missing_commands = [
            command for command in proof_requirements if command not in proof_results
        ]
        if missing_commands:
            findings.append(
                _finding(
                    REQUIRED_PROOF_NOT_CAPTURED,
                    "Required proof command results were not captured.",
                    blocking=True,
                    commands=missing_commands,
                )
            )

        failed_commands = [
            command
            for command in proof_requirements
            if command in proof_results and not _proof_passed(proof_results[command])
        ]
        if failed_commands:
            findings.append(
                _finding(
                    REQUIRED_PROOF_FAILED,
                    "One or more required proof commands did not pass.",
                    blocking=True,
                    commands=failed_commands,
                )
            )

    findings.append(
        _finding(
            SEMANTIC_EQUIVALENCE_NOT_PROVEN,
            (
                "This prototype verifies structural scope and captured proof results only; "
                "it does not prove semantic equivalence."
            ),
            blocking=False,
        )
    )

    blocked = any(_bool(finding.get("blocking")) for finding in findings)
    status = "blocked_review_first" if blocked else "structurally_verified_candidate"

    return {
        "schema_version": SCHEMA_VERSION,
        "patch_id": patch_id,
        "diagnosis_id": diagnosis_id,
        "patch_score": int(patch_score.get("score", 0) or 0),
        "scored_files": scored_files,
        "observed_changed_files": evidence_files,
        "allowed_files": allowed_files,
        "proof_requirements": proof_requirements,
        "findings": findings,
        "decision": {
            "status": status,
            "structural_verification_passed": not blocked,
            "semantic_equivalence_proven": False,
            "automation_allowed": False,
            "merge_authorized": False,
            "reason": (
                "Structural scope and captured proof requirements passed; "
                "semantic proof and automation wiring remain unavailable."
                if not blocked
                else "Protected verification found blocking evidence; keep this patch review-first."
            ),
        },
    }


def render_markdown(payload: Mapping[str, Any]) -> str:
    decision = _as_dict(payload.get("decision"))
    findings = [_as_dict(item) for item in _as_list(payload.get("findings"))]

    lines = [
        "# Protected verifier result",
        "",
        f"- Patch: `{_string(payload.get('patch_id'))}`",
        f"- Diagnosis: `{_string(payload.get('diagnosis_id'))}`",
        f"- Patch score: `{int(payload.get('patch_score', 0) or 0)}`",
        f"- Decision: `{_string(decision.get('status'))}`",
        (
            "- Structural verification passed: "
            f"`{str(_bool(decision.get('structural_verification_passed'))).lower()}`"
        ),
        "- Semantic equivalence proven: `false`",
        "- Automation allowed: `false`",
        "- Merge authorized: `false`",
        "",
        "## Findings",
        "",
    ]

    for finding in findings:
        files = ", ".join(_string(item) for item in _as_list(finding.get("files")))
        commands = ", ".join(_string(item) for item in _as_list(finding.get("commands")))
        suffix = ""
        if files:
            suffix += f" files=`{files}`"
        if commands:
            suffix += f" commands=`{commands}`"
        lines.append(
            f"- `{_string(finding.get('code'))}`: "
            f"blocking=`{str(_bool(finding.get('blocking'))).lower()}` "
            f"{_string(finding.get('message'))}{suffix}"
        )

    lines.extend(["", "## Required proof evaluated", ""])
    proof_requirements = _string_list(payload.get("proof_requirements"))
    if proof_requirements:
        lines.extend(f"- `{command}`" for command in proof_requirements)
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- This verifier is read-only.",
            "- Passing means structural proof evidence is consistent with PatchScorer scope.",
            "- Passing does not prove semantic equivalence or authorize automated remediation.",
            "- A later replayable benchmark harness must supply stronger execution evidence.",
            "",
        ]
    )
    return "\n".join(lines)


def write_result(payload: Mapping[str, Any], *, out_dir: Path) -> dict[str, str]:
    json_path = out_dir / RESULT_JSON
    markdown_path = out_dir / RESULT_MD
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
    parser.add_argument("--verification-evidence", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        payload = verify_candidate(
            patch_score=_read_json(args.patch_score),
            verification_evidence=_read_json(args.verification_evidence),
        )
        artifacts = write_result(payload, out_dir=args.out_dir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}")
        return 2

    if args.format == "json":
        print(
            json.dumps(
                {
                    "artifacts": artifacts,
                    "decision": payload["decision"],
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
