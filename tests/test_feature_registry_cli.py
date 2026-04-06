from __future__ import annotations

import json
import subprocess
import sys

import pytest

from sdetkit import feature_registry_cli


def test_feature_registry_cli_json_filter_tier_a(capsys) -> None:
    rc = feature_registry_cli.main(["--tier", "A", "--format", "json"])
    assert rc == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload
    assert all(item["tier"] == "A" for item in payload)


def test_feature_registry_cli_table_contains_header(capsys) -> None:
    rc = feature_registry_cli.main(["--format", "table"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "| Command | Tier | Status |" in out


def test_feature_registry_cli_only_core_sets_tier_a(capsys) -> None:
    rc = feature_registry_cli.main(["--only-core", "--format", "json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload
    assert all(item["tier"] == "A" for item in payload)


def test_feature_registry_cli_markdown_format_has_markers(capsys) -> None:
    rc = feature_registry_cli.main(["--format", "markdown"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "<!-- feature-registry:table:start -->" in out
    assert "<!-- feature-registry:table:end -->" in out


def test_feature_registry_cli_summary_json_has_expected_shape(capsys) -> None:
    rc = feature_registry_cli.main(["--format", "summary-json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["total"] >= 1
    assert "A" in payload["by_tier"]
    assert "stable" in payload["by_status"]
    assert isinstance(payload["commands"], list)
    assert "kits" in payload["commands"]


def test_feature_registry_cli_rejects_conflicting_only_core_and_tier() -> None:
    with pytest.raises(SystemExit):
        feature_registry_cli.main(["--only-core", "--tier", "B"])


def test_feature_registry_cli_expect_command_passes_when_present(capsys) -> None:
    rc = feature_registry_cli.main(["--expect-command", "kits", "--format", "summary-json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert "kits" in payload["commands"]


def test_feature_registry_cli_expect_command_fails_when_missing(capsys) -> None:
    rc = feature_registry_cli.main(
        ["--expect-command", "nope-nope-nope", "--format", "summary-json"]
    )
    assert rc == 2
    err = capsys.readouterr().err
    assert "missing expected command" in err


def test_feature_registry_cli_fail_on_empty_returns_nonzero(capsys) -> None:
    rc = feature_registry_cli.main(
        ["--tier", "A", "--status", "experimental", "--fail-on-empty", "--format", "summary-json"]
    )
    assert rc == 1
    err = capsys.readouterr().err
    assert "filtered result set is empty" in err


def test_feature_registry_cli_expect_tier_and_status_count_pass(capsys) -> None:
    rc = feature_registry_cli.main(
        [
            "--expect-total",
            "8",
            "--expect-tier-count",
            "A=8",
            "--expect-status-count",
            "stable=8",
            "--format",
            "summary-json",
        ]
    )
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["by_tier"]["A"] == 8
    assert payload["by_status"]["stable"] == 8


def test_feature_registry_cli_expect_total_mismatch_fails(capsys) -> None:
    rc = feature_registry_cli.main(["--expect-total", "999", "--format", "summary-json"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "total count mismatch" in err


def test_feature_registry_cli_expect_total_negative_fails(capsys) -> None:
    rc = feature_registry_cli.main(["--expect-total", "-1", "--format", "summary-json"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "--expect-total must be >= 0" in err


def test_feature_registry_cli_expect_tier_count_mismatch_fails(capsys) -> None:
    rc = feature_registry_cli.main(["--expect-tier-count", "A=999", "--format", "summary-json"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "tier count mismatch" in err


def test_feature_registry_cli_invalid_expectation_format_fails(capsys) -> None:
    rc = feature_registry_cli.main(
        ["--expect-tier-count", "bad-format", "--format", "summary-json"]
    )
    assert rc == 2
    err = capsys.readouterr().err
    assert "invalid tier-count expectation" in err


def test_python_m_sdetkit_feature_registry_json() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "sdetkit", "feature-registry", "--format", "json"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert isinstance(payload, list)
    assert payload
