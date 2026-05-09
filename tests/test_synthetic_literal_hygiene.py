from __future__ import annotations

from pathlib import Path

from sdetkit import synthetic_literal_hygiene


def _snake(*parts: str) -> str:
    return "_".join(parts)


def _prefix(*parts: str) -> str:
    return "_".join(parts) + "="


COVERAGE_GATE_REGRESSION = _snake("COVERAGE", "GATE", "REGRESSION")
MATCHED_FAILURE_SIGNALS = _prefix("matched", "failure", "signals")
CANDIDATE_SCENARIOS = _prefix("candidate", "scenarios")


def test_scan_file_reports_scanner_noisy_literal(tmp_path: Path) -> None:
    target = tmp_path / "test_bad.py"
    literal = MATCHED_FAILURE_SIGNALS + "coverage-failure"
    target.write_text(f'VALUE = "{literal}"\n', encoding="utf-8")

    findings = synthetic_literal_hygiene.scan_file(target)

    assert len(findings) == 1
    assert findings[0].token == MATCHED_FAILURE_SIGNALS
    assert findings[0].line == 1
    assert "smaller pieces" in findings[0].remediation


def test_scan_file_allows_split_synthetic_literal(tmp_path: Path) -> None:
    target = tmp_path / "test_good.py"
    target.write_text(
        'VALUE = "matched_" + "failure_" + "signals=" + "coverage-failure"\n',
        encoding="utf-8",
    )

    assert synthetic_literal_hygiene.scan_file(target) == []


def test_scan_paths_accepts_directories(tmp_path: Path) -> None:
    package = tmp_path / "tests"
    package.mkdir()
    literal = CANDIDATE_SCENARIOS + COVERAGE_GATE_REGRESSION
    (package / "test_bad.py").write_text(f'VALUE = "{literal}"\n', encoding="utf-8")
    (package / "test_good.py").write_text(
        'VALUE = "candidate_" + "scenarios="\n',
        encoding="utf-8",
    )

    findings = synthetic_literal_hygiene.scan_paths([package])

    assert len(findings) == 1
    assert findings[0].token in {CANDIDATE_SCENARIOS, COVERAGE_GATE_REGRESSION}


def test_findings_payload_reports_clean_status(tmp_path: Path) -> None:
    target = tmp_path / "test_clean.py"
    target.write_text('VALUE = "ordinary fixture"\n', encoding="utf-8")

    payload = synthetic_literal_hygiene.findings_payload([target])

    assert payload["ok"] is True
    assert payload["finding_count"] == 0
    assert payload["findings"] == []


def test_findings_payload_reports_noisy_status(tmp_path: Path) -> None:
    target = tmp_path / "test_bad.py"
    literal = COVERAGE_GATE_REGRESSION
    target.write_text(f'VALUE = "{literal}"\n', encoding="utf-8")

    payload = synthetic_literal_hygiene.findings_payload([target])

    assert payload["ok"] is False
    assert payload["finding_count"] == 1


def test_render_findings_is_operator_readable(tmp_path: Path) -> None:
    target = tmp_path / "test_bad.py"
    literal = MATCHED_FAILURE_SIGNALS + "ci-exit-code"
    target.write_text(f'VALUE = "{literal}"\n', encoding="utf-8")

    rendered = synthetic_literal_hygiene.render_findings([target])

    assert "Synthetic literal hygiene findings:" in rendered
    assert "scanner-noisy token" in rendered


def test_render_findings_reports_clean_when_no_findings(tmp_path: Path) -> None:
    target = tmp_path / "test_clean.py"
    target.write_text('VALUE = "ordinary fixture"\n', encoding="utf-8")

    assert synthetic_literal_hygiene.render_findings([target]) == (
        "Synthetic literal hygiene: clean"
    )


def test_new_synthetic_literal_hygiene_test_file_stays_scanner_clean() -> None:
    target = Path("tests/test_synthetic_literal_hygiene.py")

    assert synthetic_literal_hygiene.scan_file(target) == []


def test_default_tokens_are_built_from_diagnostic_parts() -> None:
    assert COVERAGE_GATE_REGRESSION in synthetic_literal_hygiene.DEFAULT_SCANNER_NOISE_TOKENS
    assert MATCHED_FAILURE_SIGNALS in synthetic_literal_hygiene.DEFAULT_SCANNER_NOISE_TOKENS
    assert CANDIDATE_SCENARIOS in synthetic_literal_hygiene.DEFAULT_SCANNER_NOISE_TOKENS
