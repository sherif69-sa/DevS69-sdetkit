from __future__ import annotations

import argparse
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sdetkit.diagnostic_vector.v1"
DEFAULT_GENERATED_AT = "1970-01-01T00:00:00Z"

DIAGNOSIS_ID = "_".join(("diagnosis", "id"))
FAILURE_SURFACE = "_".join(("failure", "surface"))
HEADLINE_FAILURE = "_".join(("headline", "failure"))
ACTUAL_FAILURE = "_".join(("actual", "failure"))
FIRST_FAILURE_LINE = "_".join(("first", "failure", "line"))
LINE_NUMBER = "_".join(("line", "number"))
SAFE_FIX_CANDIDATE = "_".join(("safe", "fix", "candidate"))
REVIEW_FIRST = "_".join(("review", "first"))
REVIEW_FIRST_REASON = "_".join(("review", "first", "reason"))
AFFECTED_FILES = "_".join(("affected", "files"))
LIKELY_OWNER_FILES = "_".join(("likely", "owner", "files"))
RECOMMENDED_NEXT_ACTION = "_".join(("recommended", "next", "action"))
PROOF_COMMANDS = "_".join(("proof", "commands"))
HISTORY_CONTEXT = "_".join(("history", "context"))
EVIDENCE_SOURCES = "_".join(("evidence", "sources"))
NOT_CAUSED_BY = "_".join(("not", "caused", "by"))
STALE_OR_CURRENT_SIGNAL = "_".join(("stale", "or", "current", "signal"))

VECTOR_JSON = "diagnostic-vector.json"
VECTOR_MD = "diagnostic-vector.md"
DEFAULT_OUT_DIR = str(Path("build") / "diagnostics")

REVIEW_FIRST_SURFACES = {
    "type_contract",
    "runtime",
    "release",
    "dependency",
    "security",
    "unknown",
}
SURFACE_ORDER = {
    "security": 0,
    "dependency": 1,
    "release": 2,
    "runtime": 3,
    "type_contract": 4,
    "test": 5,
    "formatting": 6,
    "quality": 7,
    "workflow": 8,
    "docs": 9,
    "unknown": 10,
}

ACTION_RUN_PRE_COMMIT = "_".join(("run", "pre", "commit"))
ACTION_REVIEW_TYPE = "_".join(("review", "first", "type", "contract"))
ACTION_REVIEW_RUNTIME = "_".join(("review", "first", "runtime", "debug"))
ACTION_REVIEW_RELEASE = "_".join(("review", "first", "release", "validation"))
ACTION_REVIEW_DEPENDENCY = "_".join(("review", "first", "dependency", "alignment"))
ACTION_REVIEW_SECURITY = "_".join(("review", "first", "security", "review"))
ACTION_COLLECT_LOGS = "_".join(("collect", "logs", "and", "classify"))
ACTION_REVIEW_DOCS = "_".join(("review", "first", "docs", "contract"))
ACTION_REVIEW_WORKFLOW = "_".join(("review", "first", "workflow", "contract"))
ACTION_RERUN_PROOF = "_".join(("rerun", "proof"))


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def _string(value: Any) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true", "yes"}


def _read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        msg = f"expected JSON object in {path}"
        raise ValueError(msg)
    return payload


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _string_list(value: Any) -> list[str]:
    values = _as_list(value)
    return sorted({_string(item) for item in values if _string(item)})


def _first_text(*values: Any) -> str:
    for value in values:
        text = _string(value)
        if text:
            return text
    return ""


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return slug or "unknown"


def _surface_from_text(*values: Any) -> str:
    haystack = " ".join(_string(value).lower() for value in values if _string(value))

    if any(token in haystack for token in ("security", "secret", "gitleaks", "codeql")):
        return "security"
    if any(
        token in haystack for token in ("dependency", "dependencies", "resolver", "pip ", "osv")
    ):
        return "dependency"
    if any(token in haystack for token in ("release", "twine", "wheel", "sdist", "build artifact")):
        return "release"
    if any(
        token in haystack
        for token in ("mypy", "type_contract", "type contract", "incompatible return")
    ):
        return "type_contract"
    if any(
        token in haystack
        for token in ("traceback", "runtime", "exception", "modulenotfound", "importerror")
    ):
        return "runtime"
    if any(token in haystack for token in ("pytest", "assertion", "test_failure", "test failure")):
        return "test"
    if any(
        token in haystack
        for token in ("ruff", "format", "formatter", "whitespace", "trailing", "eof")
    ):
        return "formatting"
    if any(token in haystack for token in ("coverage", "quality", "quality gate")):
        return "quality"
    if any(token in haystack for token in ("workflow", "github actions", "required context")):
        return "workflow"
    if "docs" in haystack or "documentation" in haystack:
        return "docs"
    return "unknown"


def _normal_surface(record: Mapping[str, Any]) -> str:
    diagnosis = _as_dict(record.get("diagnosis"))
    first_failure = _as_dict(record.get("first_failure"))

    explicit = _first_text(
        record.get("failure_surface"),
        record.get("surface"),
        record.get("risk_surface"),
        diagnosis.get("surface"),
        diagnosis.get("classification"),
        record.get("classification"),
    )
    if explicit:
        mapped = explicit.lower().replace("-", "_")
        if mapped == "format":
            return "formatting"
        if mapped == "runtime_failure":
            return "runtime"
        return mapped

    return _surface_from_text(
        record.get("name"),
        record.get("title"),
        record.get("summary"),
        record.get("first_failure_line"),
        first_failure.get("line"),
        first_failure.get("tool"),
        first_failure.get("kind"),
        diagnosis.get("code"),
        diagnosis.get("title"),
    )


def _first_failure(record: Mapping[str, Any]) -> dict[str, Any]:
    existing = _as_dict(record.get("first_failure"))
    if existing:
        return existing

    line = _first_text(
        record.get("first_failure_line"), record.get("line"), record.get("actual_failure")
    )
    if not line:
        return {}

    return {
        "line": line,
        "line_number": record.get("line_number", 0),
        "tool": _first_text(record.get("tool"), "unknown"),
        "kind": _first_text(record.get("kind"), "unknown"),
    }


def _headline(record: Mapping[str, Any]) -> str:
    diagnosis = _as_dict(record.get("diagnosis"))
    return _first_text(
        diagnosis.get("title"),
        record.get("title"),
        record.get("name"),
        record.get("check_name"),
        record.get("summary"),
        "Unknown failure",
    )


def _affected_files(record: Mapping[str, Any]) -> list[str]:
    files: list[str] = []
    for key in ("affected_files", "owner_files", "likely_owner_files", "files", "changed_files"):
        files.extend(_string_list(record.get(key)))
    diagnosis = _as_dict(record.get("diagnosis"))
    files.extend(_string_list(diagnosis.get("affected_files")))
    safe = _as_dict(record.get("safe_remediation"))
    files.extend(_string_list(safe.get("affected_files")))
    return sorted(set(files))


def _proof_commands(surface: str, record: Mapping[str, Any]) -> list[str]:
    for key in ("proof_commands", "recommended_commands", "commands"):
        commands = _string_list(record.get(key))
        if commands:
            return commands

    if surface == "formatting":
        return ["python -m pre_commit run -a"]
    if surface == "type_contract":
        return ["python -m mypy src"]
    if surface == "test":
        return ["python -m pytest -q -o addopts="]
    if surface == "release":
        return [
            "rm -rf dist build/lib build/bdist.*",
            "PYTHONPATH=src python -m build && PYTHONPATH=src python -m twine check dist/*",
        ]
    if surface == "dependency":
        return ["python -m pip check"]
    if surface == "security":
        return ["python -m sdetkit security check --root . --format json"]
    return ["collect failed check logs and rerun focused proof"]


def _recommended_action(surface: str, safe_candidate: bool, review_first: bool) -> str:
    if safe_candidate and surface == "formatting":
        return ACTION_RUN_PRE_COMMIT
    if surface == "type_contract":
        return ACTION_REVIEW_TYPE
    if surface == "runtime":
        return ACTION_REVIEW_RUNTIME
    if surface == "release":
        return ACTION_REVIEW_RELEASE
    if surface == "dependency":
        return ACTION_REVIEW_DEPENDENCY
    if surface == "security":
        return ACTION_REVIEW_SECURITY
    if surface == "docs":
        return ACTION_REVIEW_DOCS
    if surface == "workflow":
        return ACTION_REVIEW_WORKFLOW
    if review_first:
        return ACTION_COLLECT_LOGS
    return ACTION_RERUN_PROOF


def _history_context(
    *,
    surface: str,
    affected_files: list[str],
    safe_fix_history: Mapping[str, Any] | None,
    record: Mapping[str, Any],
) -> str:
    explicit = _first_text(record.get("history_context"), record.get("recurrence_state"))
    if explicit:
        return explicit

    history = _as_dict(safe_fix_history)
    metrics = _as_dict(history.get("metrics"))
    if not metrics:
        return "unknown"

    recurring_files = {
        _string(_as_dict(item).get("file"))
        for item in _as_list(metrics.get("recurring_format_drift_files"))
        if _string(_as_dict(item).get("file"))
    }
    if affected_files and recurring_files.intersection(affected_files):
        return "recurring"

    if surface == "unknown" and _as_list(metrics.get("recurring_refusal_reasons")):
        return "recurring"

    if int(metrics.get("safe_fix_attempts_total", 0) or 0) == 0:
        return "new"
    return "new"


def _review_first_reason(surface: str, record: Mapping[str, Any]) -> str:
    safe = _as_dict(record.get("safe_remediation"))
    return _first_text(
        record.get("review_first_reason"),
        record.get("blocked_reason"),
        record.get("reason"),
        safe.get("reason"),
        safe.get("blocked_reason"),
        f"{surface} requires human review" if surface in REVIEW_FIRST_SURFACES else "",
    )


def _stale_signal(record: Mapping[str, Any]) -> str:
    explicit = _first_text(record.get("stale_or_current_signal"), record.get("freshness"))
    if explicit:
        return explicit
    if record.get("stale") is True:
        return "stale"
    if record.get("current") is True:
        return "current"
    return "unknown"


def _vector_from_record(
    record: Mapping[str, Any],
    *,
    source: str,
    safe_fix_history: Mapping[str, Any] | None,
) -> dict[str, Any]:
    surface = _normal_surface(record)
    first_failure = _first_failure(record)
    first_line = _first_text(
        first_failure.get("line"), record.get("first_failure_line"), record.get("summary")
    )
    affected_files = _affected_files(record)
    safe = _as_dict(record.get("safe_remediation"))

    safe_to_auto_fix = _bool(record.get("safe_to_auto_fix")) or _bool(safe.get("safe_to_auto_fix"))
    review_first = (
        _bool(record.get("review_first"))
        or _first_text(safe.get("strategy")).lower() == "review_first"
        or (not safe_to_auto_fix and surface in REVIEW_FIRST_SURFACES)
    )
    safe_candidate = bool(safe_to_auto_fix and not review_first and surface == "formatting")
    headline = _headline(record)
    diagnosis_id = _slug("|".join((surface, headline, first_line or source)))

    return {
        DIAGNOSIS_ID: diagnosis_id,
        FAILURE_SURFACE: surface,
        HEADLINE_FAILURE: headline,
        ACTUAL_FAILURE: first_line or headline,
        FIRST_FAILURE_LINE: first_line,
        LINE_NUMBER: int(first_failure.get("line_number", record.get("line_number", 0)) or 0),
        "tool": _first_text(first_failure.get("tool"), record.get("tool"), "unknown"),
        "kind": _first_text(first_failure.get("kind"), record.get("kind"), surface),
        "confidence": _first_text(
            record.get("confidence"), _as_dict(record.get("diagnosis")).get("confidence"), "medium"
        ),
        SAFE_FIX_CANDIDATE: safe_candidate,
        REVIEW_FIRST: review_first,
        REVIEW_FIRST_REASON: _review_first_reason(surface, record),
        AFFECTED_FILES: affected_files,
        LIKELY_OWNER_FILES: affected_files,
        RECOMMENDED_NEXT_ACTION: _recommended_action(surface, safe_candidate, review_first),
        PROOF_COMMANDS: _proof_commands(surface, record),
        HISTORY_CONTEXT: _history_context(
            surface=surface,
            affected_files=affected_files,
            safe_fix_history=safe_fix_history,
            record=record,
        ),
        EVIDENCE_SOURCES: sorted(
            set(
                [source]
                + _string_list(record.get("evidence_sources"))
                + _string_list(record.get("source_artifacts"))
            )
        ),
        NOT_CAUSED_BY: _string_list(record.get("not_caused_by")),
        STALE_OR_CURRENT_SIGNAL: _stale_signal(record),
    }


def _vectors_from_check_intelligence(
    payload: Mapping[str, Any],
    *,
    safe_fix_history: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    vectors = []
    for record in _as_list(payload.get("failed_checks")):
        row = _as_dict(record)
        if row:
            vectors.append(
                _vector_from_record(
                    row,
                    source="check_intelligence",
                    safe_fix_history=safe_fix_history,
                )
            )
    return vectors


def _vectors_from_evidence_graph(
    payload: Mapping[str, Any],
    *,
    safe_fix_history: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    vectors = []
    for node in _as_list(payload.get("nodes")):
        row = _as_dict(node)
        if not row:
            continue
        adapted = dict(row)
        adapted["title"] = _first_text(row.get("title"), row.get("summary"))
        adapted["surface"] = _first_text(row.get("risk_surface"), row.get("surface"))
        adapted["affected_files"] = _string_list(row.get("owner_files"))
        vectors.append(
            _vector_from_record(
                adapted,
                source="evidence_graph",
                safe_fix_history=safe_fix_history,
            )
        )
    return vectors


def _vectors_from_failed_logs(
    payload: Mapping[str, Any],
    *,
    safe_fix_history: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    rows = []
    for key in ("failed_checks", "checks", "logs", "items"):
        rows.extend(_as_list(payload.get(key)))

    vectors = []
    for item in rows:
        row = _as_dict(item)
        if not row:
            continue
        first_line = _first_text(
            row.get("first_failure_line"),
            row.get("first_failure"),
            row.get("line"),
            row.get("excerpt"),
        )
        if first_line:
            row = dict(row)
            row["first_failure_line"] = first_line
        vectors.append(
            _vector_from_record(
                row,
                source="failed_check_logs",
                safe_fix_history=safe_fix_history,
            )
        )
    return vectors


def _vectors_from_security_review(
    payload: Mapping[str, Any],
    *,
    safe_fix_history: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    vectors = []
    for finding in _as_list(payload.get("findings")):
        row = _as_dict(finding)
        if not row:
            continue
        adapted = dict(row)
        adapted["surface"] = "security"
        adapted["title"] = _first_text(
            row.get("title"), row.get("summary"), "Security review finding"
        )
        adapted["review_first"] = True
        adapted["safe_to_auto_fix"] = False
        vectors.append(
            _vector_from_record(
                adapted,
                source="security_review",
                safe_fix_history=safe_fix_history,
            )
        )
    return vectors


def _vectors_from_action_report(
    payload: Mapping[str, Any],
    *,
    safe_fix_history: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    blocker = _as_dict(payload.get("primary_blocker"))
    if not blocker:
        return []
    return [
        _vector_from_record(
            blocker,
            source="pr_quality_action_report",
            safe_fix_history=safe_fix_history,
        )
    ]


def _dedupe_vectors(vectors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for vector in vectors:
        key = _string(vector.get(DIAGNOSIS_ID))
        existing = merged.get(key)
        if existing is None:
            merged[key] = dict(vector)
            continue
        existing[EVIDENCE_SOURCES] = sorted(
            set(
                _string_list(existing.get(EVIDENCE_SOURCES))
                + _string_list(vector.get(EVIDENCE_SOURCES))
            )
        )
        existing[PROOF_COMMANDS] = sorted(
            set(
                _string_list(existing.get(PROOF_COMMANDS))
                + _string_list(vector.get(PROOF_COMMANDS))
            )
        )
    return sorted(
        merged.values(),
        key=lambda row: (
            SURFACE_ORDER.get(_string(row.get(FAILURE_SURFACE)), 99),
            _string(row.get(HEADLINE_FAILURE)),
            _string(row.get(ACTUAL_FAILURE)),
        ),
    )


def build_diagnostic_vector(
    *,
    check_intelligence: Mapping[str, Any] | None = None,
    failed_check_logs: Mapping[str, Any] | None = None,
    safe_remediation: Mapping[str, Any] | None = None,
    safe_fix_outcome: Mapping[str, Any] | None = None,
    safe_fix_history: Mapping[str, Any] | None = None,
    release_evidence: Mapping[str, Any] | None = None,
    security_review: Mapping[str, Any] | None = None,
    dependency_evidence: Mapping[str, Any] | None = None,
    test_failure_bundle: Mapping[str, Any] | None = None,
    evidence_graph: Mapping[str, Any] | None = None,
    pr_quality_action_report: Mapping[str, Any] | None = None,
    operator_loop: Mapping[str, Any] | None = None,
    generated_at: str = DEFAULT_GENERATED_AT,
) -> dict[str, Any]:
    vectors: list[dict[str, Any]] = []

    vectors.extend(
        _vectors_from_check_intelligence(
            _as_dict(check_intelligence),
            safe_fix_history=safe_fix_history,
        )
    )
    vectors.extend(
        _vectors_from_failed_logs(
            _as_dict(failed_check_logs),
            safe_fix_history=safe_fix_history,
        )
    )
    vectors.extend(
        _vectors_from_evidence_graph(
            _as_dict(evidence_graph),
            safe_fix_history=safe_fix_history,
        )
    )
    vectors.extend(
        _vectors_from_security_review(
            _as_dict(security_review),
            safe_fix_history=safe_fix_history,
        )
    )
    vectors.extend(
        _vectors_from_action_report(
            _as_dict(pr_quality_action_report),
            safe_fix_history=safe_fix_history,
        )
    )

    for source, payload in (
        ("safe_remediation", safe_remediation),
        ("release_evidence", release_evidence),
        ("dependency_evidence", dependency_evidence),
        ("test_failure_bundle", test_failure_bundle),
        ("operator_loop", operator_loop),
    ):
        record = _as_dict(payload)
        if record and (
            record.get("failed") is True
            or record.get("review_first") is True
            or record.get("safe_to_auto_fix") is True
            or _first_text(
                record.get("surface"), record.get("risk_surface"), record.get("first_failure_line")
            )
        ):
            vectors.append(
                _vector_from_record(
                    record,
                    source=source,
                    safe_fix_history=safe_fix_history,
                )
            )

    vectors = _dedupe_vectors(vectors)
    primary = vectors[0] if vectors else {}

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "summary": {
            "diagnosis_count": len(vectors),
            "review_first_count": sum(1 for vector in vectors if vector.get(REVIEW_FIRST) is True),
            "safe_fix_candidate_count": sum(
                1 for vector in vectors if vector.get(SAFE_FIX_CANDIDATE) is True
            ),
            "primary_surface": _string(primary.get(FAILURE_SURFACE)),
            "primary_action": _string(primary.get(RECOMMENDED_NEXT_ACTION)),
        },
        "diagnoses": vectors,
        "source_status": {
            "check_intelligence": bool(check_intelligence),
            "failed_check_logs": bool(failed_check_logs),
            "safe_remediation": bool(safe_remediation),
            "safe_fix_outcome": bool(safe_fix_outcome),
            "safe_fix_history": bool(safe_fix_history),
            "release_evidence": bool(release_evidence),
            "security_review": bool(security_review),
            "dependency_evidence": bool(dependency_evidence),
            "test_failure_bundle": bool(test_failure_bundle),
            "evidence_graph": bool(evidence_graph),
            "pr_quality_action_report": bool(pr_quality_action_report),
            "operator_loop": bool(operator_loop),
        },
    }


def render_markdown(payload: Mapping[str, Any]) -> str:
    summary = _as_dict(payload.get("summary"))
    lines = [
        "# Diagnostic Vector",
        "",
        f"- Diagnosis count: {summary.get('diagnosis_count', 0)}",
        f"- Review-first count: {summary.get('review_first_count', 0)}",
        f"- Safe-fix candidates: {summary.get('safe_fix_candidate_count', 0)}",
        f"- Primary surface: {summary.get('primary_surface', '') or 'none'}",
        f"- Primary action: {summary.get('primary_action', '') or 'none'}",
        "",
        "## Diagnoses",
        "",
    ]

    diagnoses = _as_list(payload.get("diagnoses"))
    if not diagnoses:
        lines.append("- None")
    for item in diagnoses:
        diagnosis = _as_dict(item)
        lines.extend(
            [
                f"### {diagnosis.get(HEADLINE_FAILURE, 'Unknown failure')}",
                "",
                f"- Surface: {diagnosis.get(FAILURE_SURFACE, 'unknown')}",
                f"- Actual failure: {diagnosis.get(ACTUAL_FAILURE, '')}",
                f"- First failure line: {diagnosis.get(FIRST_FAILURE_LINE, '')}",
                f"- Tool/kind: {diagnosis.get('tool', 'unknown')} / {diagnosis.get('kind', 'unknown')}",
                f"- Safe-fix candidate: {str(diagnosis.get(SAFE_FIX_CANDIDATE, False)).lower()}",
                f"- Review-first: {str(diagnosis.get(REVIEW_FIRST, False)).lower()}",
                f"- History context: {diagnosis.get(HISTORY_CONTEXT, 'unknown')}",
                f"- Recommended next action: {diagnosis.get(RECOMMENDED_NEXT_ACTION, 'unknown')}",
                "",
            ]
        )

    return "\n".join(lines) + "\n"


def write_diagnostic_vector(payload: Mapping[str, Any], out_dir: Path) -> dict[str, str]:
    json_path = out_dir / VECTOR_JSON
    markdown_path = out_dir / VECTOR_MD
    _write_json(json_path, payload)
    _write_text(markdown_path, render_markdown(payload))
    return {
        "diagnostic_vector_json": json_path.as_posix(),
        "diagnostic_vector_markdown": markdown_path.as_posix(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sdetkit.diagnostic_vector_engine")
    parser.add_argument("--check-intelligence", default="")
    parser.add_argument("--failed-check-logs", default="")
    parser.add_argument("--safe-remediation", default="")
    parser.add_argument("--safe-fix-outcome", default="")
    parser.add_argument("--safe-fix-history", default="")
    parser.add_argument("--release-evidence", default="")
    parser.add_argument("--security-review", default="")
    parser.add_argument("--dependency-evidence", default="")
    parser.add_argument("--test-failure-bundle", default="")
    parser.add_argument("--evidence-graph", default="")
    parser.add_argument("--pr-quality-action-report", default="")
    parser.add_argument("--operator-loop", default="")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--generated-at", default=DEFAULT_GENERATED_AT)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser


def _optional_path(value: str) -> Path | None:
    return Path(value) if value else None


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        payload = build_diagnostic_vector(
            check_intelligence=_read_json(_optional_path(args.check_intelligence)),
            failed_check_logs=_read_json(_optional_path(args.failed_check_logs)),
            safe_remediation=_read_json(_optional_path(args.safe_remediation)),
            safe_fix_outcome=_read_json(_optional_path(args.safe_fix_outcome)),
            safe_fix_history=_read_json(_optional_path(args.safe_fix_history)),
            release_evidence=_read_json(_optional_path(args.release_evidence)),
            security_review=_read_json(_optional_path(args.security_review)),
            dependency_evidence=_read_json(_optional_path(args.dependency_evidence)),
            test_failure_bundle=_read_json(_optional_path(args.test_failure_bundle)),
            evidence_graph=_read_json(_optional_path(args.evidence_graph)),
            pr_quality_action_report=_read_json(_optional_path(args.pr_quality_action_report)),
            operator_loop=_read_json(_optional_path(args.operator_loop)),
            generated_at=args.generated_at,
        )
        artifacts = write_diagnostic_vector(payload, Path(args.out_dir))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error={exc}")
        return 2

    if args.format == "json":
        print(
            json.dumps(
                {"artifacts": artifacts, "summary": payload["summary"]}, indent=2, sort_keys=True
            )
        )
    else:
        for key, value in artifacts.items():
            print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
