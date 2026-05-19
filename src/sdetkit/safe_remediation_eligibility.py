from __future__ import annotations

import re
from typing import Any

SCHEMA_VERSION = "sdetkit.safe_remediation_eligibility.v1"

JsonObject = dict[str, Any]

FORMAT_SAFE_STRATEGY = "run_pre_commit"
REVIEW_FIRST_STRATEGY = "review_first"


def _as_dict(value: Any) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _string(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _lower(value: Any) -> str:
    return _string(value).lower()


FILE_PATH_RE = re.compile(
    r"(?P<path>(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+\."
    r"(?:py|pyi|toml|yaml|yml|md|rst|txt|json|cfg|ini))"
)


def _extract_affected_files(text: str) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for match in FILE_PATH_RE.finditer(text):
        value = match.group("path").strip().strip(":")
        if not value or value in seen:
            continue
        if value.startswith(("http://", "https://")):
            continue
        seen.add(value)
        values.append(value)
    return values


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(needle in lowered for needle in needles)


SAFE_FORMAT_MARKERS = (
    "end-of-file-fixer",
    "fix end of files",
    "trim trailing whitespace",
    "trailing whitespace",
    "ruff format",
    "ruff-format",
    "files were modified by this hook",
    "would reformat",
    "import block is un-sorted or un-formatted",
    "organize imports",
    "found 1 error (1 fixed, 0 remaining)",
    "1 file reformatted",
    "files reformatted",
)

UNSAFE_REVIEW_MARKERS = (
    "assertionerror",
    "traceback",
    "runtimeerror",
    "modulenotfounderror",
    "importerror",
    "invaliddistribution",
    "twine",
    "metadata is invalid",
    "resolutionimpossible",
    "cannot install",
    "mypy",
    "incompatible return value",
    "high entropy",
    "secret",
    "token",
    "github advanced security",
    "ghas",
    "permission",
    "oidc",
    "publish",
    "release artifact",
)


def classify_check_failure(
    *,
    name: str = "",
    diagnosis: JsonObject | None = None,
    first_failure: JsonObject | None = None,
    log_text: str = "",
) -> JsonObject:
    diagnosis = _as_dict(diagnosis)
    first_failure = _as_dict(first_failure)

    first_line = _string(first_failure.get("line"))
    tool = _lower(first_failure.get("tool"))
    kind = _lower(first_failure.get("kind"))
    code = _lower(diagnosis.get("code"))
    title = _lower(diagnosis.get("title"))
    combined = "\n".join(
        value
        for value in (
            name,
            first_line,
            tool,
            kind,
            code,
            title,
            log_text,
        )
        if value
    )

    raw_context = first_failure.get("context", [])
    if not isinstance(raw_context, list):
        raw_context = []
    context_text = "\n".join(
        _string(_as_dict(item).get("text")) for item in raw_context if isinstance(item, dict)
    )
    affected_files = _extract_affected_files(
        "\n".join(value for value in (first_line, context_text, log_text) if value)
    )

    if _contains_any(combined, UNSAFE_REVIEW_MARKERS) and not _contains_any(
        combined,
        SAFE_FORMAT_MARKERS,
    ):
        return {
            "schema_version": SCHEMA_VERSION,
            "safe_to_auto_fix": False,
            "strategy": REVIEW_FIRST_STRATEGY,
            "category": "review_first",
            "reason": "Failure matches review-first markers and is not formatting-only.",
            "proof_commands": [],
        }

    if kind == "format_drift" or _contains_any(combined, SAFE_FORMAT_MARKERS):
        return {
            "schema_version": SCHEMA_VERSION,
            "safe_to_auto_fix": True,
            "strategy": FORMAT_SAFE_STRATEGY,
            "category": "formatting_only",
            "affected_files": affected_files,
            "reason": "Failure is limited to deterministic formatting or whitespace hooks.",
            "proof_commands": [
                "python -m pre_commit run -a",
                "python -m ruff check src tests",
                "python -m mypy src",
            ],
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "safe_to_auto_fix": False,
        "strategy": REVIEW_FIRST_STRATEGY,
        "category": "unknown",
        "reason": "Failure is not in the approved safe-remediation allowlist.",
        "proof_commands": [],
    }
