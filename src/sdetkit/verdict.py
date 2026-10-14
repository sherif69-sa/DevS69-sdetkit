"""One release verdict shared by every decision surface.

Gate, mission control, release room, merge readiness and the remediation loop
each keep their own detailed vocabulary, and each also emits this verdict so
that consumers (merge readiness, evidence packs, reports) read one contract.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.verdict.v1"

SHIP = "SHIP"
NO_SHIP = "NO_SHIP"
REVIEW = "REVIEW"
NOT_RUN = "NOT_RUN"
DECISIONS = (SHIP, REVIEW, NOT_RUN, NO_SHIP)

# Worst first: a combined verdict takes the most severe decision present.
_SEVERITY = {NO_SHIP: 3, NOT_RUN: 2, REVIEW: 1, SHIP: 0}

# Every vocabulary the decision surfaces used before this contract.
_ALIASES = {
    "ship": SHIP,
    "continue": SHIP,
    "pass": SHIP,
    "green": SHIP,
    "ok": SHIP,
    "ready_for_merge_review": SHIP,
    "no_ship": NO_SHIP,
    "no-ship": NO_SHIP,
    "fail": NO_SHIP,
    "failed": NO_SHIP,
    "blocked": NO_SHIP,
    "do-not-merge": NO_SHIP,
    "blocked_review_first": NO_SHIP,
    "review": REVIEW,
    "watch": REVIEW,
    "ship_with_findings": REVIEW,
    "review_required": REVIEW,
    "review_first": REVIEW,
    "verified_candidate": REVIEW,
    "proof_not_run": NOT_RUN,
    "no_change": REVIEW,
    "not_run": NOT_RUN,
    "pending": NOT_RUN,
    "unknown": NOT_RUN,
}

DECISION_BOUNDARY: dict[str, bool] = {
    "automation_allowed": False,
    "patch_application_allowed": False,
    "merge_authorized": False,
    "semantic_equivalence_proven": False,
}


def normalize_decision(raw: object) -> str:
    """Map any legacy decision word onto the shared vocabulary (unknown means NOT_RUN)."""

    text = str(raw or "").strip()
    if text.upper() in DECISIONS:
        return text.upper()
    return _ALIASES.get(text.lower().replace(" ", "_"), NOT_RUN)


def build_verdict(
    *,
    source: str,
    decision: object,
    reasons: Iterable[str] = (),
    next_action: str = "",
    evidence: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "source": source,
        "decision": normalize_decision(decision),
        "source_decision": str(decision or ""),
        "reasons": [str(reason) for reason in reasons if str(reason).strip()],
        "next_action": next_action,
        "evidence": dict(evidence or {}),
        **DECISION_BOUNDARY,
    }


def combine_verdicts(source: str, verdicts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Fold several verdicts into one; the most severe decision wins."""

    if not verdicts:
        return build_verdict(source=source, decision=NOT_RUN, reasons=["no verdicts supplied"])
    worst = max(verdicts, key=lambda item: _SEVERITY[normalize_decision(item.get("decision"))])
    reasons = [
        f"{item.get('source', 'unknown')}: {normalize_decision(item.get('decision'))}"
        for item in verdicts
    ]
    return build_verdict(
        source=source,
        decision=normalize_decision(worst.get("decision")),
        reasons=reasons,
        next_action=str(worst.get("next_action") or ""),
    )


def verdict_from_artifact(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    """Return the shared verdict an artifact carries, if it carries one."""

    candidate = payload.get("verdict")
    if isinstance(candidate, Mapping) and candidate.get("schema_version") == SCHEMA_VERSION:
        return dict(candidate)
    if payload.get("schema_version") == SCHEMA_VERSION:
        return dict(payload)
    return None


def load_verdict(path: Path) -> dict[str, Any] | None:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    return verdict_from_artifact(loaded) if isinstance(loaded, dict) else None


def git_provenance(root: Path) -> dict[str, Any]:
    """Identify the exact tree a result describes, so later steps can trust or reject it."""

    def _git(*args: str) -> str | None:
        try:
            completed = subprocess.run(
                ["git", *args],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        return completed.stdout if completed.returncode == 0 else None

    head = _git("rev-parse", "HEAD")
    status = _git("status", "--porcelain")
    return {
        "head_sha": (head or "").strip(),
        "tree_clean": status is not None and not status.strip(),
    }
