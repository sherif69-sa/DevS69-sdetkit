"""Classify GitHub workflow warnings into reviewable SDETKit signals."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class WorkflowWarning:
    code: str
    severity: str
    confidence: str
    title: str
    summary: str
    why_it_matters: str
    recommended_action: str
    proof_command: str
    evidence: tuple[str, ...]


def _lowered(text: str) -> str:
    return text.lower()


def _contains_all(text: str, tokens: Iterable[str]) -> bool:
    lowered = _lowered(text)
    return all(token.lower() in lowered for token in tokens)


def _contains_any(text: str, tokens: Iterable[str]) -> bool:
    lowered = _lowered(text)
    return any(token.lower() in lowered for token in tokens)


def _warning(
    *,
    code: str,
    title: str,
    summary: str,
    why_it_matters: str,
    recommended_action: str,
    proof_command: str,
    evidence: tuple[str, ...],
    severity: str = "low",
    confidence: str = "high",
) -> WorkflowWarning:
    return WorkflowWarning(
        code=code,
        severity=severity,
        confidence=confidence,
        title=title,
        summary=summary,
        why_it_matters=why_it_matters,
        recommended_action=recommended_action,
        proof_command=proof_command,
        evidence=evidence,
    )


def classify_warning_text(text: str) -> list[WorkflowWarning]:
    warnings: list[WorkflowWarning] = []
    if not text.strip():
        return warnings

    if _looks_like_setup_python_path_fallback(text):
        warnings.append(_setup_python_path_fallback_warning())

    if _looks_like_projects_classic_deprecation(text):
        warnings.append(_projects_classic_deprecation_warning())

    if _looks_like_high_entropy_test_literal_warning(text):
        warnings.append(_high_entropy_test_literal_warning())

    if _looks_like_unpinned_setup_python_warning(text):
        warnings.append(_unpinned_setup_python_warning())

    return warnings


def classify_warning_payload(text: str) -> dict[str, object]:
    warnings = classify_warning_text(text)
    return {
        "schema_version": "sdetkit.workflow_warning_classifier.v1",
        "ok": True,
        "warning_count": len(warnings),
        "warnings": [asdict(item) for item in warnings],
        "status": warning_status(warnings),
    }


def warning_status(warnings: Iterable[WorkflowWarning]) -> str:
    rows = list(warnings)
    if not rows:
        return "clear"
    if any(row.severity == "high" for row in rows):
        return "needs_fix"
    if any(row.severity == "medium" for row in rows):
        return "needs_attention"
    return "monitor"


def render_warning_summary(text: str) -> str:
    payload = classify_warning_payload(text)
    warnings = payload["warnings"]
    if not isinstance(warnings, list) or not warnings:
        return "Workflow warnings: none"

    lines = [
        "Workflow warnings:",
        f"- status: {payload['status']}",
        f"- warning count: {payload['warning_count']}",
    ]
    for item in warnings:
        if not isinstance(item, dict):
            continue
        lines.append(f"- {item.get('code')}: {item.get('title')}")
        lines.append(f"  next: {item.get('recommended_action')}")
    return "\n".join(lines)


def _looks_like_setup_python_path_fallback(text: str) -> bool:
    return _contains_all(
        text,
        (
            "actions/setup-python",
            "neither 'python-version' nor 'python-version-file'",
            "version of python currently in `path` will be used",
        ),
    )


def _looks_like_projects_classic_deprecation(text: str) -> bool:
    return _contains_all(
        text,
        (
            "projects (classic) is being deprecated",
            "repository.pullrequest.projectcards",
        ),
    )


def _looks_like_high_entropy_test_literal_warning(text: str) -> bool:
    return (
        _contains_any(text, ("high-entropy string literal", "high entropy string literal"))
        and _contains_any(text, ("tests/", "test_"))
    ) or _contains_all(text, ("high entropy string", "synthetic"))


def _looks_like_unpinned_setup_python_warning(text: str) -> bool:
    if _looks_like_setup_python_path_fallback(text):
        return False
    return _contains_all(text, ("actions/setup-python",)) and _contains_any(
        text,
        ("not pinned", "unpinned", "floating action ref"),
    )


def _setup_python_path_fallback_warning() -> WorkflowWarning:
    return _warning(
        code="SETUP_PYTHON_PATH_FALLBACK",
        title="setup-python is falling back to runner PATH",
        summary=(
            "GitHub could not resolve a Python version from the setup-python step, "
            "so the runner PATH version was used instead."
        ),
        why_it_matters=(
            "Runner PATH fallback can hide environment drift and make future CI "
            "runs depend on the image default instead of the repository contract."
        ),
        recommended_action=(
            "Check the workflow or composite action input that feeds setup-python "
            "and make sure it has a non-empty python-version or python-version-file."
        ),
        proof_command=("python -m pytest -q tests/test_github_setup_python_pinning.py -o addopts="),
        evidence=(
            "actions/setup-python warning",
            "missing python-version or python-version-file",
            "runner PATH fallback",
        ),
    )


def _projects_classic_deprecation_warning() -> WorkflowWarning:
    return _warning(
        code="GH_PROJECTS_CLASSIC_DEPRECATION",
        title="GitHub Projects Classic field is deprecated",
        summary=("A GitHub API call touched the deprecated Projects Classic GraphQL field."),
        why_it_matters=(
            "The command may fail even when the repository state is healthy, which "
            "can confuse PR maintenance and release work."
        ),
        recommended_action=(
            "Use REST or a GraphQL query that avoids projectCards when editing PR metadata."
        ),
        proof_command="gh api repos/OWNER/REPO/pulls/NUMBER --jq '.number'",
        evidence=("projects classic deprecation", "pullRequest.projectCards"),
    )


def _high_entropy_test_literal_warning() -> WorkflowWarning:
    return _warning(
        code="SYNTHETIC_LITERAL_SCANNER_NOISE",
        title="Synthetic test literal triggered scanner noise",
        summary=(
            "A test fixture or assertion contains a diagnostic-looking literal that "
            "a scanner may treat as secret-like material."
        ),
        why_it_matters=(
            "Synthetic diagnostic strings are not secrets, but repeated scanner "
            "comments slow review and can hide real alerts."
        ),
        recommended_action=(
            "Build synthetic diagnostic tokens from smaller pieces in tests and keep "
            "the behavior assertion readable."
        ),
        proof_command=("python -m pytest -q tests/test_synthetic_literal_hygiene.py -o addopts="),
        evidence=("security scanner warning", "test fixture literal"),
    )


def _unpinned_setup_python_warning() -> WorkflowWarning:
    return _warning(
        code="SETUP_PYTHON_ACTION_UNPINNED",
        title="setup-python action is not pinned",
        summary="A setup-python step appears to use an unpinned or floating action ref.",
        why_it_matters=("Floating action refs can change behavior without a repository change."),
        recommended_action=(
            "Pin setup-python to the repository's accepted action ref or update the "
            "workflow guardrail if the policy changes."
        ),
        proof_command=("python -m pytest -q tests/test_github_setup_python_pinning.py -o addopts="),
        evidence=("setup-python action", "pinning warning"),
        severity="medium",
    )
