from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sdetkit.investigation_safe_fix_policy import route_investigation_safe_fix_policy

SCHEMA_VERSION = "sdetkit.investigation.evidence.v1"
DEFAULT_PROOF_COMMANDS = {
    "MISSING_PUBLIC_API_PARITY": [
        "python -m sdetkit investigate surface --root . --surface {surface} --format json",
        "python -m pytest -q tests/test_{surface}.py",
    ],
    "PRODUCT_LOGIC_FAILURE": [
        "python -m sdetkit investigate surface --root . --surface {surface} --format json",
        "python -m pytest -q",
    ],
    "PRE_COMMIT_FORMAT_DRIFT": [
        "python -m pre_commit run -a",
        "./scripts/pr_preflight.sh",
    ],
    "RUFF_FIXABLE_LINT": [
        "python -m ruff check .",
        "python -m pre_commit run -a",
    ],
}


def _clean_token(value: str, name: str) -> str:
    clean = value.strip()
    if not clean:
        raise OSError(f"{name} is required")
    return clean


def _proof_commands(classification: str, surface: str) -> list[str]:
    template = DEFAULT_PROOF_COMMANDS.get(
        classification,
        [
            "python -m sdetkit investigate failure --log <log> --format markdown",
            "./scripts/pr_preflight.sh",
        ],
    )
    return [command.format(surface=surface) for command in template]


def _candidate_status(policy: dict[str, Any]) -> str:
    if bool(policy.get("candidate_later")):
        return "candidate_later_after_policy"
    return "review_required"


def _candidate_freeze_markdown(payload: dict[str, Any]) -> str:
    policy = payload["safe_fix_policy"]
    lines = [
        "# Investigation candidate freeze",
        "",
        f"- classification: **{payload['classification']}**",
        f"- surface: **{payload['surface']}**",
        f"- diagnostic only: **{payload['diagnostic_only']}**",
        f"- automation allowed: **{payload['automation_allowed']}**",
        f"- safe to auto-fix: **{payload['safe_to_auto_fix']}**",
        f"- requires human review: **{payload['requires_human_review']}**",
        f"- policy route: **{policy['route']}**",
        "",
        "## Freeze decision",
        "",
        policy["blocking_reason"],
    ]
    return "\n".join(lines).rstrip() + "\n"


def _audit_result_markdown(payload: dict[str, Any]) -> str:
    policy = payload["safe_fix_policy"]
    lines = [
        "# Investigation audit result",
        "",
        f"- classification: **{payload['classification']}**",
        f"- surface: **{payload['surface']}**",
        f"- proof status: **{payload['proof_status']}**",
        f"- candidate status: **{payload['candidate_status']}**",
        f"- policy route: **{policy['route']}**",
        "",
        "## Audit summary",
        "",
        payload["summary"],
        "",
        "## Safe-fix policy",
        "",
        policy["reason"],
    ]
    return "\n".join(lines).rstrip() + "\n"


def _proof_commands_markdown(payload: dict[str, Any]) -> str:
    lines = ["# Investigation proof commands", "", "```bash"]
    lines.extend(str(command) for command in payload["proof_commands"])
    lines.extend(["```", ""])
    return "\n".join(lines).rstrip() + "\n"


def build_investigation_evidence(
    classification: str,
    surface: str,
    out_dir: str | Path,
    root: str | Path = ".",
) -> dict[str, Any]:
    clean_classification = _clean_token(classification, "classification")
    clean_surface = _clean_token(surface, "surface")
    output_dir = Path(out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    commands = _proof_commands(clean_classification, clean_surface)
    policy = route_investigation_safe_fix_policy(clean_classification)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "diagnostic_only": True,
        "automation_allowed": False,
        "safe_to_auto_fix": False,
        "requires_human_review": True,
        "command": "investigate evidence",
        "classification": clean_classification,
        "surface": clean_surface,
        "root": Path(root).as_posix(),
        "out_dir": output_dir.as_posix(),
        "proof_status": "missing",
        "candidate_status": _candidate_status(policy),
        "summary": "Investigation evidence bundle created for human review.",
        "safe_fix_policy": policy,
        "proof_commands": commands,
        "files": {
            "candidate_freeze": (output_dir / "CANDIDATE_FREEZE.md").as_posix(),
            "audit_result": (output_dir / "AUDIT_RESULT.md").as_posix(),
            "proof_commands": (output_dir / "proof-commands.md").as_posix(),
            "investigation_json": (output_dir / "investigation.json").as_posix(),
        },
    }
    (output_dir / "CANDIDATE_FREEZE.md").write_text(
        _candidate_freeze_markdown(payload), encoding="utf-8"
    )
    (output_dir / "AUDIT_RESULT.md").write_text(_audit_result_markdown(payload), encoding="utf-8")
    (output_dir / "proof-commands.md").write_text(
        _proof_commands_markdown(payload), encoding="utf-8"
    )
    (output_dir / "investigation.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return payload
