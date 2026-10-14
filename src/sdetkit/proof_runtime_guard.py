from __future__ import annotations

from collections.abc import Mapping
from typing import Any

SCHEMA_VERSION = "sdetkit.proof_runtime_guard.v1"

CLEAN = "clean"
CLAIMED_WRITE = "_".join(("claimed", "write"))
UNCLAIMED_WRITE = "_".join(("unclaimed", "write"))
EVIDENCE_SHADOW = "_".join(("evidence", "shadow"))
RUNTIME_GUARD_VIOLATION = "_".join(("runtime", "guard", "violation"))

_RESERVED_DIR = "/".join(("build", "-".join(("isolated", "proof", "runner"))))
_RESERVED_STEM = "-".join(("verification", "evidence"))
RESERVED_EVIDENCE_PATHS = (
    f"{_RESERVED_DIR}/{_RESERVED_STEM}.json",
    f"{_RESERVED_DIR}/{_RESERVED_STEM}.md",
)

JsonObject = dict[str, Any]


def _clean_paths(values: list[str]) -> list[str]:
    return sorted({str(item).strip() for item in values if str(item).strip()})


def assess_runtime_guard(
    *,
    expected_changed_files: list[str],
    mutated_files: list[str],
    reserved_evidence_changed_files: list[str],
) -> JsonObject:
    expected = _clean_paths(expected_changed_files)
    mutated = _clean_paths(mutated_files)
    reserved = _clean_paths(reserved_evidence_changed_files)

    expected_set = set(expected)
    claimed_mutations = sorted(set(mutated) & expected_set)
    unclaimed_mutations = sorted(set(mutated) - expected_set)

    violations: list[str] = []
    if reserved:
        violations.append(EVIDENCE_SHADOW)
    if unclaimed_mutations:
        violations.append(UNCLAIMED_WRITE)
    if claimed_mutations:
        violations.append(CLAIMED_WRITE)

    if reserved:
        status = EVIDENCE_SHADOW
    elif unclaimed_mutations:
        status = UNCLAIMED_WRITE
    elif claimed_mutations:
        status = CLAIMED_WRITE
    else:
        status = CLEAN

    violation = bool(violations)
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        RUNTIME_GUARD_VIOLATION: violation,
        "expected_changed_files": expected,
        "mutated_files": mutated,
        "claimed_mutated_files": claimed_mutations,
        "unclaimed_mutated_files": unclaimed_mutations,
        "reserved_evidence_shadowed_files": reserved,
        "violation_classes": violations,
        "proof_result_allowed": not violation,
        "boundary": {
            "copied_workspace_observed": True,
            "external_filesystem_containment_enforced": False,
            "process_escape_prevention_enforced": False,
            "network_isolation_enforced": False,
            "automation_allowed": False,
            "merge_authorized": False,
            "semantic_equivalence_proven": False,
        },
    }


def render_markdown(result: Mapping[str, Any]) -> str:
    boundary = result.get("boundary", {})
    if not isinstance(boundary, dict):
        boundary = {}

    lines = [
        "# Proof runtime guard result",
        "",
        f"- Status: `{result.get('status', '')}`",
        (f"- Runtime guard violation: `{str(bool(result.get(RUNTIME_GUARD_VIOLATION))).lower()}`"),
        "",
        "## Observed writes",
        "",
    ]

    for key in (
        "claimed_mutated_files",
        "unclaimed_mutated_files",
        "reserved_evidence_shadowed_files",
    ):
        values = result.get(key, [])
        rendered = values if isinstance(values, list) else []
        lines.append(f"- {key}: `{len(rendered)}`")
        lines.extend(f"  - `{value}`" for value in rendered)

    lines.extend(
        [
            "",
            "## Boundary",
            "",
            (
                "- External filesystem containment enforced: "
                f"`{str(bool(boundary.get('external_filesystem_containment_enforced'))).lower()}`"
            ),
            (
                "- Process escape prevention enforced: "
                f"`{str(bool(boundary.get('process_escape_prevention_enforced'))).lower()}`"
            ),
            "- Automation allowed: `false`",
            "- Merge authorized: `false`",
            "- Semantic equivalence proven: `false`",
            "",
        ]
    )
    return "\n".join(lines)
