from __future__ import annotations

import re
import subprocess
from pathlib import Path


def test_quality_script_unknown_mode_suggests_closest_match() -> None:
    result = subprocess.run(
        ["bash", "quality.sh", "cit"],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert "Did you mean: bash quality.sh ci" in result.stderr


def test_quality_script_help_documents_fast_and_full_lanes() -> None:
    text = Path("quality.sh").read_text(encoding="utf-8")
    assert (
        "Usage: bash quality.sh {all|ci|verify|fmt|lint|type|doctor|test|full-test|cov|mut|muthtml|boost|registry}"
        in text
    )
    assert "quick     Fast local confidence / smoke profile." in text
    assert "standard  Default repository validation profile." in text
    assert "strict    Merge/release truth profile." in text
    assert (
        "adaptive  Planner-selected profile with explainable targeting and adaptive resolution."
        in text
    )
    assert "Fast/smoke lane for local confidence; not merge truth." in text
    assert (
        "Full verification lane before merge (doctor, format, lint, typing, full tests, security scan)."
        in text
    )
    assert "registry   Validate and smoke-test feature-registry docs/contracts surface." in text


def test_quality_script_verify_delegates_to_planner_runner() -> None:
    text = Path("quality.sh").read_text(encoding="utf-8")
    match = re.search(r"  verify\)\n(?P<body>.*?    ;;)", text, re.DOTALL)
    assert match is not None
    body = match.group("body")
    assert 'profile_used="strict"' in body
    assert "python -m sdetkit.checks run" in body
    assert "--profile strict" in body
    assert '--json-output "$QUALITY_VERDICT_JSON"' in body
    assert '--markdown-output "$QUALITY_SUMMARY_MD"' in body


def test_quality_script_ci_delegates_to_planner_runner() -> None:
    text = Path("quality.sh").read_text(encoding="utf-8")
    match = re.search(r"  ci\)\n(?P<body>.*?    ;;)", text, re.DOTALL)
    assert match is not None
    body = match.group("body")
    assert 'profile_used="quick"' in body
    assert "python -m sdetkit.checks run" in body
    assert "--profile quick" in body


def test_quality_script_writes_final_verdict_contract() -> None:
    text = Path("quality.sh").read_text(encoding="utf-8")
    assert "quality-verdict.json" in text
    assert "quality-summary.md" in text
    assert "final verdict contract:" in text
    assert "verdict.verdict_contract" in text
    assert "profile used" in text
    assert "checks skipped" in text
    assert "merge/release recommendation" in text


def test_quality_script_registry_mode_runs_contract_chain() -> None:
    text = Path("quality.sh").read_text(encoding="utf-8")
    match = re.search(r"  registry\)\n(?P<body>.*?    ;;)", text, re.DOTALL)
    assert match is not None
    body = match.group("body")
    assert "run_required \"feature_registry_contract\"" in body
    assert "run_registry_contract" in body
    assert "--expect-command kits" in text
    assert "--expect-total 8" in text
    assert "--expect-tier-count A=8" in text
    assert "--expect-status-count stable=8" in text
    assert "--fail-on-empty" in text
