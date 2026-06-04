from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class CommentFailureFamily:
    family: str
    title: str
    evidence: str
    recommended_action: str


_PATTERNS: tuple[tuple[str, str, re.Pattern[str], str], ...] = (
    (
        "cli_invalid_command_or_arguments",
        "CLI command/argument contract failed",
        re.compile(
            r"(invalid choice:|unrecognized arguments:|usage:\s+sdetkit\b)",
            re.IGNORECASE,
        ),
        "Check the registered argparse subcommand and dispatch path. If this is a canonical rename, add the canonical command while preserving legacy aliases.",
    ),
    (
        "artifact_set_mismatch",
        "Workflow artifact set mismatch",
        re.compile(
            r"artifact-set mismatch missing=\[.*?\]\s+extra=\[.*?\]",
            re.IGNORECASE | re.DOTALL,
        ),
        "Compare the workflow output directory, produced artifact filenames, and test expectations. Rename stale expectations only after confirming the workflow producer is canonical.",
    ),
    (
        "schema_version_mismatch",
        "Contract schema_version mismatch",
        re.compile(
            r"(invalid value/type for key:\s*schema_version|schema_version[\"']?:\s*[\"'][^\"']+)",
            re.IGNORECASE,
        ),
        "Inspect the producer and checker schema constants. Normalize accidental duplicated canonical names such as baseline_baseline before changing contract expectations.",
    ),
    (
        "pytest_stale_rename_expectation",
        "Pytest expectation is stale after canonical rename",
        re.compile(
            r"FAILED\s+tests/.*?AssertionError:.*?(phase[-_ ]?\d|demo|closeout).*?(baseline|release readiness|platform readiness|operational readiness|example|completion report)",
            re.IGNORECASE | re.DOTALL,
        ),
        "Prefer updating stale tests when implementation output has already moved to the canonical wording. Do not restore legacy wording just to satisfy old assertions.",
    ),
    (
        "make_target_contract_failed",
        "Make target contract failed",
        re.compile(
            r"make(?:\[\d+\])?: \*\*\* \[Makefile:\d+:[^\]]+\] Error \d+",
            re.IGNORECASE,
        ),
        "Scroll above the make footer to the first failing command output and classify that underlying failure before changing Makefile targets.",
    ),
)


def extract_comment_failure_families(log_text: str) -> list[CommentFailureFamily]:
    families: list[CommentFailureFamily] = []

    for family, title, pattern, action in _PATTERNS:
        match = pattern.search(log_text)
        if not match:
            continue

        evidence = " ".join(match.group(0).split())
        if len(evidence) > 260:
            evidence = evidence[:257] + "..."

        families.append(
            CommentFailureFamily(
                family=family,
                title=title,
                evidence=evidence,
                recommended_action=action,
            )
        )

    return families


def render_comment_failure_families(log_text: str) -> str:
    families = extract_comment_failure_families(log_text)

    if not families:
        return "Additional failure families: none detected"

    lines = ["Additional failure families detected:"]
    for item in families:
        lines.extend(
            [
                f"- `{item.family}` — {item.title}",
                f"  - evidence: {item.evidence}",
                f"  - next action: {item.recommended_action}",
            ]
        )

    return "\n".join(lines)
