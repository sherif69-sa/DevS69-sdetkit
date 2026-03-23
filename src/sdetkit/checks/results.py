from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from .base import CheckProfileName, CheckStatus

ConfidenceLevel = Literal[
    "low (smoke-only)",
    "medium (standard validation)",
    "high (merge/release truth)",
    "planned (adaptive selection)",
]
Recommendation = Literal[
    "continue-local-iteration",
    "run-standard-validation",
    "run-full-verification-before-merge",
    "ready-for-merge-review",
    "do-not-merge",
]

_PROFILE_CONFIDENCE: dict[CheckProfileName, ConfidenceLevel] = {
    "quick": "low (smoke-only)",
    "standard": "medium (standard validation)",
    "strict": "high (merge/release truth)",
    "adaptive": "planned (adaptive selection)",
}


@dataclass(frozen=True)
class CheckRecord:
    id: str
    title: str
    status: CheckStatus
    blocking: bool = True
    reason: str = ""
    command: str = ""
    advisory: tuple[str, ...] = ()
    log_path: str = ""

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["advisory"] = list(self.advisory)
        return payload


@dataclass(frozen=True)
class FinalVerdict:
    profile: CheckProfileName
    verdict_contract: str
    checks_run: tuple[CheckRecord, ...]
    checks_skipped: tuple[CheckRecord, ...]
    blocking_failures: tuple[str, ...]
    advisory_findings: tuple[str, ...]
    confidence_level: ConfidenceLevel
    recommendation: Recommendation
    summary: str
    ok: bool
    merge_truth: bool
    profile_notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "verdict_contract": self.verdict_contract,
            "ok": self.ok,
            "merge_truth": self.merge_truth,
            "summary": self.summary,
            "profile_notes": self.profile_notes,
            "checks_run": [record.as_dict() for record in self.checks_run],
            "checks_skipped": [record.as_dict() for record in self.checks_skipped],
            "blocking_failures": list(self.blocking_failures),
            "advisory_findings": list(self.advisory_findings),
            "confidence_level": self.confidence_level,
            "recommendation": self.recommendation,
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), sort_keys=True, indent=2) + "\n"

    def to_markdown(self) -> str:
        lines = [
            "## Final Verdict",
            f"- profile used: `{self.profile}`",
            f"- summary: {self.summary}",
            f"- confidence level: {self.confidence_level}",
            f"- merge/release recommendation: `{self.recommendation}`",
            f"- merge truth: {'yes' if self.merge_truth else 'no'}",
        ]
        if self.profile_notes:
            lines.append(f"- profile notes: {self.profile_notes}")
        lines.extend(["", "### Checks run"])
        for record in self.checks_run:
            lines.append(
                f"- `{record.id}` - {record.title}: **{record.status.upper()}**"
                + (f" (`{record.reason}`)" if record.reason else "")
            )
        lines.extend(["", "### Checks skipped"])
        if self.checks_skipped:
            for record in self.checks_skipped:
                lines.append(f"- `{record.id}` - {record.reason or 'skipped by profile'}")
        else:
            lines.append("- none")
        lines.extend(["", "### Blocking failures"])
        if self.blocking_failures:
            for item in self.blocking_failures:
                lines.append(f"- {item}")
        else:
            lines.append("- none")
        lines.extend(["", "### Advisory findings"])
        if self.advisory_findings:
            for item in self.advisory_findings:
                lines.append(f"- {item}")
        else:
            lines.append("- none")
        return "\n".join(lines) + "\n"


def build_final_verdict(
    *,
    profile: CheckProfileName,
    checks: list[CheckRecord],
    profile_notes: str = "",
    metadata: dict[str, Any] | None = None,
) -> FinalVerdict:
    checks_run = tuple(record for record in checks if record.status != "skipped")
    checks_skipped = tuple(record for record in checks if record.status == "skipped")
    blocking_failures = tuple(
        f"{record.id}: {record.title}"
        for record in checks_run
        if record.status == "failed" and record.blocking
    )
    advisory_findings = tuple(
        item
        for record in checks
        for item in (
            list(record.advisory)
            + ([record.reason] if record.status == "skipped" and record.reason else [])
        )
        if item
    )
    ok = not blocking_failures
    merge_truth = profile == "strict"
    recommendation: Recommendation
    if ok and profile == "quick":
        recommendation = "run-full-verification-before-merge"
    elif ok and profile == "standard":
        recommendation = "ready-for-merge-review"
    elif ok and profile == "strict":
        recommendation = "ready-for-merge-review"
    elif ok:
        recommendation = "run-standard-validation"
    else:
        recommendation = "do-not-merge"

    summary = (
        "All blocking checks passed."
        if ok
        else f"Blocking failures present: {', '.join(blocking_failures)}"
    )
    return FinalVerdict(
        profile=profile,
        verdict_contract="sdetkit.final-verdict.v1",
        checks_run=checks_run,
        checks_skipped=checks_skipped,
        blocking_failures=blocking_failures,
        advisory_findings=advisory_findings,
        confidence_level=_PROFILE_CONFIDENCE[profile],
        recommendation=recommendation,
        summary=summary,
        ok=ok,
        merge_truth=merge_truth,
        profile_notes=profile_notes,
        metadata=metadata or {},
    )
