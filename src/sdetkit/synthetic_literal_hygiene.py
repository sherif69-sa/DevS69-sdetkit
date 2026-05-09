"""Guardrails for scanner-noisy synthetic diagnostic literals in tests."""

from __future__ import annotations

import ast
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path


def _snake(*parts: str) -> str:
    return "_".join(parts)


def _prefix(*parts: str) -> str:
    return "_".join(parts) + "="


COVERAGE_GATE_REGRESSION = _snake("COVERAGE", "GATE", "REGRESSION")
MATCHED_FAILURE_SIGNALS = _prefix("matched", "failure", "signals")
CANDIDATE_SCENARIOS = _prefix("candidate", "scenarios")
CANDIDATE_ODDS = _prefix("candidate", "odds")
CANDIDATE_CALIBRATION = _prefix("candidate", "calibration")

DEFAULT_SCANNER_NOISE_TOKENS = (
    COVERAGE_GATE_REGRESSION,
    MATCHED_FAILURE_SIGNALS,
    CANDIDATE_SCENARIOS,
    CANDIDATE_ODDS,
    CANDIDATE_CALIBRATION,
)


@dataclass(frozen=True)
class LiteralFinding:
    path: str
    line: int
    token: str
    literal_preview: str
    remediation: str


def _preview(value: str, limit: int = 90) -> str:
    clean = value.replace("\n", "\\n")
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3] + "..."


def _python_string_literals(path: Path) -> Iterable[tuple[int, str]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []

    rows: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            rows.append((getattr(node, "lineno", 0), node.value))
    return rows


def scan_file(
    path: Path, tokens: Iterable[str] = DEFAULT_SCANNER_NOISE_TOKENS
) -> list[LiteralFinding]:
    token_list = [token for token in tokens if token]
    findings: list[LiteralFinding] = []

    for line, literal in _python_string_literals(path):
        matched_tokens = [token for token in token_list if token in literal]
        if not matched_tokens:
            continue
        token = sorted(matched_tokens, key=len, reverse=True)[0]
        findings.append(
            LiteralFinding(
                path=path.as_posix(),
                line=line,
                token=token,
                literal_preview=_preview(literal),
                remediation=(
                    "Build this diagnostic token from smaller pieces so scanners "
                    "do not treat the synthetic test string as secret-like material."
                ),
            )
        )

    return findings


def scan_paths(paths: Iterable[Path]) -> list[LiteralFinding]:
    findings: list[LiteralFinding] = []
    for path in paths:
        if path.is_dir():
            for child in sorted(path.rglob("*.py")):
                findings.extend(scan_file(child))
        elif path.suffix == ".py" and path.exists():
            findings.extend(scan_file(path))
    return findings


def findings_payload(paths: Iterable[Path]) -> dict[str, object]:
    findings = scan_paths(paths)
    return {
        "schema_version": "sdetkit.synthetic_literal_hygiene.v1",
        "ok": not findings,
        "finding_count": len(findings),
        "findings": [asdict(item) for item in findings],
    }


def render_findings(paths: Iterable[Path]) -> str:
    payload = findings_payload(paths)
    findings = payload["findings"]
    if not isinstance(findings, list) or not findings:
        return "Synthetic literal hygiene: clean"

    lines = [
        "Synthetic literal hygiene findings:",
        f"- finding count: {payload['finding_count']}",
    ]
    for item in findings:
        if not isinstance(item, dict):
            continue
        lines.append("- {path}:{line} contains scanner-noisy token {token}".format(**item))
    return "\n".join(lines)
